#!/usr/bin/env python3
"""Repair invalid candidate spans in a coreference dataset without losing labels.

`dataset_validation.py` is the gate; this tool is the migration path for datasets
built before the current normalizer.  It does not touch `text` or gold label
semantics:

  * a candidate whose span no longer reproduces its surface is moved to the
    nearest occurrence of that surface in the stored text, if one exists;
  * if the surface does not occur in the text at all, the bogus candidate is
    dropped;
  * duplicate spans are collapsed;
  * gold antecedent indices are remapped; a label that pointed at a dropped
    candidate is preserved by surface when possible, otherwise set to -1.

The script is idempotent and writes nothing when the dataset is already valid.

Usage:
    python repair_dataset_spans.py coref_standard.json --dry-run
    python repair_dataset_spans.py coref_standard.json --out coref_standard.json
    python repair_dataset_spans.py coref_standard.json --out /tmp/fixed.json
"""

import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from dataset_validation import validate_record


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid(text, rec):
    if not isinstance(rec, dict):
        return False
    surf, start, end = rec.get("surface"), rec.get("start"), rec.get("end")
    return (isinstance(surf, str) and surf
            and _is_int(start) and _is_int(end)
            and 0 <= start < end <= len(text)
            and text[start:end] == surf)


def _hits(text, surface):
    """All (start, end) occurrences of `surface`, including overlaps."""
    if not surface:
        return []
    out, pos = [], 0
    while True:
        i = text.find(surface, pos)
        if i < 0:
            return out
        out.append((i, i + len(surface)))
        pos = i + 1


def _nearest(text, surface, old_start):
    hits = _hits(text, surface)
    if not hits:
        return None
    return min(hits, key=lambda span: (abs(span[0] - old_start), span[0]))


def repair_case(case, stats):
    """Repair one dataset record in place.  Return True if anything changed."""
    text = case.get("text")
    if not isinstance(text, str):
        return False
    candidates = case.get("candidates") or []
    anaphors = case.get("anaphors") or []
    changed = False

    # Propose a span for every old candidate.  Keeping the old index lets us
    # remap gold labels even when the candidate list is reordered/deduped.
    proposed = []
    for old_i, cand in enumerate(candidates):
        if _valid(text, cand):
            surf, start, end = cand["surface"], cand["start"], cand["end"]
        else:
            surf = cand.get("surface") if isinstance(cand, dict) else ""
            start = cand.get("start", 0) if isinstance(cand, dict) else 0
            hit = _nearest(text, surf, start if _is_int(start) else 0)
            if hit is None:
                stats["dropped_candidates"] += 1
                changed = True
                continue
            start, end = hit
            stats["fixed_candidates"] += 1
            changed = True
        proposed.append((old_i, surf, start, end))

    # Deduplicate by span, then sort by position (longest first at equal start).
    unique = {}
    old_to_span = {}
    for old_i, surf, start, end in proposed:
        span = (start, end)
        old_to_span[old_i] = span
        unique.setdefault(span, surf)
    ordered = sorted(unique.items(), key=lambda kv: (kv[0][0], -(kv[0][1] - kv[0][0])))
    span_to_new = {span: i for i, (span, _surf) in enumerate(ordered)}
    new_candidates = [
        {"surface": surf, "start": span[0], "end": span[1]}
        for span, surf in ordered
    ]
    if len(new_candidates) != len(candidates):
        changed = True
    old_to_new = {old_i: span_to_new[span] for old_i, span in old_to_span.items()}

    # Anaphor spans should already be valid; if one drifted, move it to the
    # nearest matching surface rather than silently keeping a bad coordinate.
    for ana in anaphors:
        if not isinstance(ana, dict) or _valid(text, ana):
            continue
        surf = ana.get("surface", "")
        start = ana.get("start", 0)
        hit = _nearest(text, surf, start if _is_int(start) else 0)
        if hit is not None:
            ana["start"], ana["end"] = hit
            stats["fixed_anaphors"] += 1
            changed = True

    # Remap gold labels.  `old_to_new` covers every surviving candidate,
    # including duplicates that collapsed onto a shared span.
    for ana in anaphors:
        if not isinstance(ana, dict):
            continue
        gold = ana.get("antecedent")
        if gold is None or gold == -1:
            continue
        if not _is_int(gold):
            ana["antecedent"] = -1
            stats["lost_gold"] += 1
            changed = True
            continue
        if gold in old_to_new:
            new_gold = old_to_new[gold]
            if new_gold != gold:
                stats["remapped_gold"] += 1
                changed = True
            ana["antecedent"] = new_gold
            continue

        # The old candidate was dropped.  Preserve the label by surface when a
        # surviving candidate has the same surface; otherwise abstain (-1).
        old_surf = (candidates[gold].get("surface")
                    if 0 <= gold < len(candidates) else None)
        old_start = (candidates[gold].get("start", 0)
                     if 0 <= gold < len(candidates) else 0)
        choices = []
        if old_surf:
            for i, cand in enumerate(new_candidates):
                if cand["surface"] == old_surf:
                    choices.append((abs(cand["start"] - old_start), cand["start"], i))
        if choices:
            ana["antecedent"] = min(choices)[2]
            stats["preserved_gold"] += 1
        else:
            ana["antecedent"] = -1
            stats["lost_gold"] += 1
        changed = True

    if changed:
        case["candidates"] = new_candidates
    return changed


def repair_dataset(data):
    stats = {
        "cards_changed": 0,
        "fixed_candidates": 0,
        "dropped_candidates": 0,
        "fixed_anaphors": 0,
        "remapped_gold": 0,
        "preserved_gold": 0,
        "lost_gold": 0,
    }
    for case in data:
        before = json.dumps(case, sort_keys=True, ensure_ascii=False)
        repair_case(case, stats)
        after = json.dumps(case, sort_keys=True, ensure_ascii=False)
        if before != after:
            stats["cards_changed"] += 1
    return stats


def _write(path, data):
    with open(path, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--out", default=None,
                    help="output path (default: in-place)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    with open(args.dataset) as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        print("dataset is not a JSON list", file=sys.stderr)
        return 2

    before_issues = sum(len(validate_record(c, i)) for i, c in enumerate(data))
    stats = repair_dataset(data)
    after_issues = sum(len(validate_record(c, i)) for i, c in enumerate(data))

    print(f"issues: {before_issues} -> {after_issues}")
    for key in ("cards_changed", "fixed_candidates", "dropped_candidates",
                "fixed_anaphors", "remapped_gold", "preserved_gold",
                "lost_gold"):
        print(f"  {key:<20} {stats[key]}")

    if after_issues:
        print("\nremaining issues (first 10):", file=sys.stderr)
        shown = 0
        for i, case in enumerate(data):
            for issue in validate_record(case, i):
                print(f"  {issue['card']}: [{issue['code']}] {issue['message']}",
                      file=sys.stderr)
                shown += 1
                if shown >= 10:
                    break
            if shown >= 10:
                break

    if args.dry_run:
        print("\n[dry-run] no file written")
        return 1 if after_issues else 0

    if not stats["cards_changed"] and not args.out:
        print("\nno changes; file left untouched")
        return 1 if after_issues else 0

    out = args.out or args.dataset
    _write(out, data)
    print(f"\nwrote {out}")
    return 1 if after_issues else 0


if __name__ == "__main__":
    sys.exit(main())
