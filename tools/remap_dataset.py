#!/usr/bin/env python3
"""Rebuild dataset texts and spans from the source, using offset maps.

This is the deterministic replacement for surface-matching repair.  It knows the
two historical normalizers:

    legacy   normalize_names(strip_reminders(raw)) then " ".join(text.split())
    current  setdata.normalize_text(raw)  (line breaks preserved)

For each record it maps old normalized span -> original source span -> new
normalized span.  Text and spans are updated together; teacher label indices do
not change (candidate order is preserved).  If any span cannot be mapped to the
same surface, the record is left untouched and reported.

Usage:
    python remap_dataset.py coref_standard.json --source Standard.json --dry-run
    python remap_dataset.py coref_standard.json --source Standard.json --out coref_standard.json
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import argparse
import json
import os
import sys

BASE = _paths.ROOT
sys.path.insert(0, BASE)

from dataset_validation import validate_record
from preprocess import name_pattern
from setdata import (
    OffsetMap, _char_units, _collapse_line, _is_common_word,
    _replace_name_units, _strip_reminder_units, load, normalize_with_map,
)


def normalize_legacy_with_map(raw, names=None):
    """The pre-newline normalizer, with a map back to `raw`."""
    units = _strip_reminder_units(_char_units(raw))
    units = _replace_name_units(units, name_pattern(names))
    # Historical label_cases used " ".join(text.split()), collapsing newlines.
    units = _collapse_line(units)
    text = ''.join(u[0] for u in units)
    return text, OffsetMap(text, [(u[1], u[2]) for u in units], len(raw))


def _legacy_names(items):
    """The pre-type-filter name set (full + short names, curated stopwords only)."""
    names = set()
    for name, _raw, _code in items:
        names.add(name)
        names.add(name.split(',')[0].strip())
    return {n for n in names if n and not _is_common_word(n)}


def _source_texts(source_path):
    items, _types, names, _sets = load(source_path)
    by_name = {}
    for name, raw, _code in items:
        if raw:
            by_name.setdefault(name.lower(), []).append(raw)
    return by_name, names, _legacy_names(items)


def _choose_source(raws, stored, names, legacy_names):
    for raw in raws:
        new_text, new_map = normalize_with_map(raw, names)
        candidates = [
            (new_text, None),
            (normalize_legacy_with_map(raw, names)[0],
             normalize_legacy_with_map(raw, names)[1]),
            (normalize_with_map(raw, legacy_names)[0],
             normalize_with_map(raw, legacy_names)[1]),
            (normalize_legacy_with_map(raw, legacy_names)[0],
             normalize_legacy_with_map(raw, legacy_names)[1]),
        ]
        for text, old_map in candidates:
            if text == stored:
                return raw, new_text, new_map, old_map
    return None, None, None, None


def _remap_record(case, raw, new_text, new_map, old_map):
    """Return (new_case, error).  Never partially mutates on failure."""
    new_case = json.loads(json.dumps(case))
    if old_map is None:
        # Text already current; spans are already in the new coordinate system.
        if new_text != case.get("text"):
            return None, "text differs but no legacy map"
    else:
        for field in ("candidates", "anaphors"):
            for rec in new_case.get(field) or []:
                try:
                    ostart, oend = old_map.to_original(rec["start"], rec["end"])
                except Exception as exc:
                    return None, f"{field} span cannot map to source: {exc}"
                mapped = new_map.to_normalized(ostart, oend)
                if mapped is None:
                    return None, f"{field} span has no normalized overlap"
                nstart, nend = mapped
                rec["start"], rec["end"] = nstart, nend
                # Name normalization changed between dataset builds (e.g. a
                # short name that collided with a creature type).  The span is
                # still the same object, so follow the new text's surface.
                rec["surface"] = new_text[nstart:nend]
        new_case["text"] = new_text

    issues = validate_record(new_case)
    if issues:
        return None, f"revalidation failed: {issues[0]['code']}"
    return new_case, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-report", type=int, default=10)
    args = ap.parse_args()

    args.dataset = _paths.data(args.dataset)
    with open(args.dataset) as fh:
        raw_text = fh.read()
    pretty = raw_text.lstrip().startswith('[\n')
    data = json.loads(raw_text)
    by_name, names, legacy_names = _source_texts(args.source)

    changed = same = missing = failed = 0
    errors = []
    for i, case in enumerate(data):
        if not isinstance(case, dict):
            failed += 1
            continue
        card = case.get("card") or ""
        raws = by_name.get(card.lower())
        if not raws:
            missing += 1
            if len(errors) < args.max_report:
                errors.append((card, "card missing from source"))
            continue

        raw, new_text, new_map, old_map = _choose_source(
            raws, case.get("text"), names, legacy_names)
        if raw is None:
            failed += 1
            if len(errors) < args.max_report:
                errors.append((card, "stored text matches neither current nor legacy normalizer"))
            continue

        if new_text == case.get("text"):
            same += 1
            continue

        fixed, error = _remap_record(case, raw, new_text, new_map, old_map)
        if fixed is None:
            failed += 1
            if len(errors) < args.max_report:
                errors.append((card, error))
            continue
        data[i] = fixed
        changed += 1

    print(f"records={len(data)}  changed={changed}  already-current={same}  "
          f"missing-source={missing}  failed={failed}")
    for card, error in errors:
        print(f"  {card}: {error}")
    if args.dry_run:
        print("[dry-run] no file written")
        return 1 if failed else 0
    if not changed:
        print("no changes; file left untouched")
        return 1 if failed else 0
    out = args.out or args.dataset
    with open(out, "w") as fh:
        if pretty:
            json.dump(data, fh, indent=1, ensure_ascii=False)
        else:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(f"wrote {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
