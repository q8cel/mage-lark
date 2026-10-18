#!/usr/bin/env python3
"""Re-derive dataset texts with line breaks preserved (ability boundaries).

`setdata.normalize_text` keeps the newline that separates abilities; the old
normalizer collapsed it, merging e.g. `Trample, haste` with the trigger line that
follows. The change is exactly length-preserving, so this is a *character swap*:
each affected position holds a space in the dataset and a newline in the derived
text, and every span in the record stays valid.

Identity check: the derived text, with newlines turned back into spaces, must equal
the stored text exactly. Anything else is skipped and reported.

    python upgrade_texts.py coref_standard.json --source /path/Standard.json --dry-run
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from setdata import load, normalize_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--source", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    items, _, names, _ = load(args.source)
    by_collapsed = {}
    for _n, raw, _c in items:
        if not raw:
            continue
        t = normalize_text(raw, names)
        by_collapsed.setdefault(t.replace("\n", " "), t)

    data = json.load(open(args.dataset))
    changed = skipped = missing = 0
    reasons = {}
    for rec in data:
        new = by_collapsed.get(rec["text"])
        if new is None:
            missing += 1
            continue
        if new == rec["text"]:
            continue
        if len(new) != len(rec["text"]):
            skipped += 1
            reasons["length"] = reasons.get("length", 0) + 1
            continue
        bad = sum(1 for a, b in zip(rec["text"], new)
                  if a != b and not (a == " " and b == "\n"))
        if bad:
            skipped += 1
            reasons["unexpected char"] = reasons.get("unexpected char", 0) + 1
            continue
        # spans must still reproduce their surfaces
        ok = all(new[m["start"]:m["end"]] == m["surface"] for m in rec["candidates"])
        ok = ok and all(new[a["start"]:a["end"]] == a["surface"] for a in rec["anaphors"])
        if not ok:
            skipped += 1
            reasons["span"] = reasons.get("span", 0) + 1
            continue
        if not args.dry_run:
            rec["text"] = new
        changed += 1

    n_lines = sum(1 for rec in data if "\n" in rec["text"]) if args.dry_run else changed
    print(f"records: {len(data)}  upgraded: {changed}  already clean: {len(data)-changed-skipped-missing}")
    print(f"  skipped: {skipped} {reasons}   no source match: {missing}")
    print(f"  records now containing line breaks: {n_lines}")
    if args.dry_run:
        for rec in data[:3]:
            new = by_collapsed.get(rec["text"])
            if new and new != rec["text"]:
                print(f"\n{rec['card']}\n  old: {rec['text'][:100]}\n  new: {new[:100]}")
        return
    out = args.json_out or args.dataset
    with open(out, "w") as fh:
        json.dump(data, fh)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
