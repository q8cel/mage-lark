#!/usr/bin/env python3
"""Validate the span invariants of a coreference dataset.

The datasets store character offsets into their own `text` field.  Every
consumer (training, resolver evaluation, error analysis) assumes:

    text[start:end] == surface

and that a gold antecedent is a valid candidate index.  A normalizer change can
silently invalidate those assumptions, so this is the gate to run before using a
dataset for measurement.

Usage:
    python dataset_validation.py coref_standard.json coref_dataset.json
    python dataset_validation.py coref_standard.json --max-examples 20
    python dataset_validation.py coref_standard.json --json
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

KINDS = {"pronoun", "phrase", "demonstrative"}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _span_error(text, rec):
    """Return a short error string if a span is malformed, else None."""
    if not isinstance(rec, dict):
        return "record is not an object"
    surface = rec.get("surface")
    start, end = rec.get("start"), rec.get("end")
    if not isinstance(surface, str) or not surface:
        return "empty/non-string surface"
    if not (_is_int(start) and _is_int(end)):
        return "start/end must be integers"
    if start < 0 or end <= start or end > len(text):
        return f"out-of-range span [{start}, {end}) for text length {len(text)}"
    actual = text[start:end]
    if actual != surface:
        return f"text[{start}:{end}]={actual!r} != surface={surface!r}"
    return None


def validate_record(case, case_index=None):
    """Return a list of issue dicts for one dataset card."""
    issues = []

    def add(code, message, kind=None, index=None):
        issues.append({
            "code": code,
            "card": case.get("card") if isinstance(case, dict) else None,
            "case_index": case_index,
            "kind": kind,
            "index": index,
            "message": message,
        })

    if not isinstance(case, dict):
        add("bad_record", "dataset entry is not an object")
        return issues
    text = case.get("text")
    if not isinstance(text, str) or not text:
        add("bad_text", "missing or empty text")
        return issues
    candidates = case.get("candidates")
    anaphors = case.get("anaphors")
    if not isinstance(candidates, list):
        add("bad_candidates", "candidates is not a list")
        candidates = []
    if not isinstance(anaphors, list):
        add("bad_anaphors", "anaphors is not a list")
        anaphors = []

    bad_candidates = set()
    seen_spans = set()
    for i, cand in enumerate(candidates):
        err = _span_error(text, cand)
        if err:
            add("candidate_span", err, "candidate", i)
            bad_candidates.add(i)
            continue
        key = (cand["start"], cand["end"])
        if key in seen_spans:
            add("duplicate_candidate", f"duplicate span {key}", "candidate", i)
        else:
            seen_spans.add(key)

    bad_anaphors = set()
    for i, ana in enumerate(anaphors):
        err = _span_error(text, ana)
        if err:
            add("anaphor_span", err, "anaphor", i)
            bad_anaphors.add(i)
        kind = ana.get("kind") if isinstance(ana, dict) else None
        if kind not in KINDS:
            add("anaphor_kind", f"unknown kind {kind!r}", "anaphor", i)
        gold = ana.get("antecedent") if isinstance(ana, dict) else None
        if gold is None or gold == -1:
            continue
        if not _is_int(gold):
            add("gold_type", f"antecedent is not an int/None/-1: {gold!r}",
                "anaphor", i)
            continue
        if gold < -1 or gold >= len(candidates):
            add("gold_range", f"antecedent {gold} outside 0..{len(candidates)-1}",
                "anaphor", i)
            continue
        if gold in bad_candidates:
            add("gold_invalid_candidate",
                f"antecedent {gold} points at an invalid candidate", "anaphor", i)
        cand = candidates[gold]
        if (isinstance(cand, dict)
                and (cand.get("start"), cand.get("end"))
                == (ana.get("start"), ana.get("end"))):
            add("gold_self", f"antecedent {gold} is the anaphor itself",
                "anaphor", i)

    return issues


def validate_dataset(data):
    issues = []
    for i, case in enumerate(data):
        issues.extend(validate_record(case, i))
    return issues



def validate_source(data, source_path):
    """Check that each stored text/span is reproducible from the source file.

    This uses `setdata.normalize_with_map`, so it is grounded in the original
    oracle text rather than surface heuristics.  Older datasets built with the
    collapsed-newline normalizer will report `source_text_mismatch`; rebuild or
    upgrade those before using this as a hard gate.
    """
    from setdata import load, normalize_text, normalize_with_map

    items, _types, names, _sets = load(source_path)
    by_name = {}
    for name, raw, _code in items:
        if raw:
            by_name.setdefault(name.lower(), []).append(raw)

    issues = []
    for case_i, case in enumerate(data):
        if not isinstance(case, dict):
            continue
        card = case.get("card") or ""
        raws = by_name.get(card.lower())
        if not raws:
            issues.append({"code": "source_card_missing", "card": card,
                           "case_index": case_i, "kind": None, "index": None,
                           "message": f"card not found in {source_path}"})
            continue
        text = case.get("text")
        chosen = None
        for raw in raws:
            normalized, omap = normalize_with_map(raw, names)
            if normalized == text:
                chosen = (raw, omap)
                break
        if chosen is None:
            issues.append({"code": "source_text_mismatch", "card": card,
                           "case_index": case_i, "kind": None, "index": None,
                           "message": "stored text != normalize_with_map(source)"})
            continue
        raw, omap = chosen

        span_records = ([(("candidate"), i, c)
                         for i, c in enumerate(case.get("candidates") or [])]
                        + [(("anaphor"), i, a)
                           for i, a in enumerate(case.get("anaphors") or [])])
        for kind, i, rec in span_records:
            if _span_error(text, rec):
                continue
            os_, oe = omap.to_original(rec["start"], rec["end"])
            original_slice = raw[os_:oe]
            got = normalize_text(original_slice, names)
            if got != rec["surface"]:
                issues.append({"code": "source_span_mismatch", "card": card,
                               "case_index": case_i, "kind": kind, "index": i,
                               "message": f"source slice {original_slice!r} "
                                          f"normalizes to {got!r}, "
                                          f"expected {rec['surface']!r}"})
    return issues

def summarize(path, issues, data):
    print(f"\n== {path}")
    print(f"  cards={len(data)}  candidates={sum(len(c.get('candidates', [])) for c in data)}"
          f"  anaphors={sum(len(c.get('anaphors', [])) for c in data)}")
    if not issues:
        print("  OK: all span and gold invariants hold")
        return
    counts = Counter(x["code"] for x in issues)
    print(f"  {len(issues)} issue(s) in {len({x['case_index'] for x in issues})} card(s)")
    for code, count in counts.most_common():
        print(f"    {count:5d}  {code}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datasets", nargs="+")
    ap.add_argument("--max-examples", type=int, default=8,
                    help="examples to print per dataset (0 = none)")
    ap.add_argument("--json", action="store_true",
                    help="print all issues as JSON instead of a summary")
    ap.add_argument("--source", default=None,
                    help="also verify texts/spans against this source json")
    args = ap.parse_args()

    failed = False
    all_issues = {}
    for path in args.datasets:
        with open(path) as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            print(f"{path}: top-level JSON is not a list", file=sys.stderr)
            failed = True
            continue
        issues = validate_dataset(data)
        if args.source:
            issues.extend(validate_source(data, args.source))
        all_issues[path] = issues
        if args.json:
            continue
        summarize(path, issues, data)
        if issues:
            failed = True
            for issue in issues[:args.max_examples]:
                card = issue["card"] or f"case#{issue['case_index']}"
                print(f"    [{issue['code']}] {card} "
                      f"{issue['kind'] or ''}{issue['index'] if issue['index'] is not None else ''}: "
                      f"{issue['message']}")

    if args.json:
        json.dump(all_issues, sys.stdout, indent=1, ensure_ascii=False)
        print()
        failed = any(all_issues.values())

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
