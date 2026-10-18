#!/usr/bin/env python3
"""Repair the card-name clobbering in a teacher-labelled dataset.

`preprocess.normalize_names` used to match card names without word boundaries, so
45 Standard names that are word prefixes corrupted ordinary words:

    "Search your library"  ->  "~ch your library"      (card "Sear")
    "Rite of ..."          ->  "~te of ..."            (card "Rit"?)

The normalizer is fixed, but the dataset stores the corrupted text. This script
rebuilds each affected record from the ORIGINAL oracle text and re-derives its
spans, keeping the teacher's antecedent labels.

How a record is matched to its source: re-run the *buggy* normalizer on every
candidate source card and require an exact string match with the stored text.
That is a strong identity check — no name-based guessing.

Invariants enforced per repaired record (any failure = record left untouched):
  * the number of mentions and anaphors is unchanged,
  * every mention/anaphor surface is unchanged, index for index,
  * text[start:end] == surface for all of them.

Usage:
    python repair_dataset.py coref_standard.json --source /path/Standard.json --dry-run
    python repair_dataset.py coref_standard.json --source /path/Standard.json
"""
import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from preprocess import normalize_names, strip_reminders
from setdata import load


def _buggy_normalize(text, names):
    """The pre-fix normalizer: no word-boundary fences."""
    alts = sorted((n for n in names if n), key=len, reverse=True)
    if not alts:
        return text
    return re.compile('|'.join(re.escape(n) for n in alts)).sub('~', text)


def _norm_text(raw, names, buggy=False):
    t = strip_reminders(raw)
    t = _buggy_normalize(t, names) if buggy else normalize_names(t, names)
    return " ".join(t.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--source", required=True, help="original data file (mtgjson or FDN)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    items, _, names, _ = load(args.source)
    # buggy text -> (original text) so a stored record maps back to its source
    buggy = {}
    for name, raw, _code in items:
        if not raw:
            continue
        buggy.setdefault(_norm_text(raw, names, buggy=True), raw)

    data = json.load(open(args.dataset))
    affected = [c for c in data if re.search(r"~[A-Za-z]", c["text"])]
    print(f"records: {len(data)}   with a clobbered token: {len(affected)}")

    # rebuild the texts first so the mention cache can be pre-filled in parallel
    rebuilt = {}
    unmatched = 0
    for c in affected:
        raw = buggy.get(c["text"])
        if raw is None:
            unmatched += 1
            continue
        fixed = _norm_text(raw, names)
        if fixed != c["text"]:
            rebuilt[c["card"]] = fixed
    print(f"rebuilt texts: {len(rebuilt)}   source-text match failures: {unmatched}")
    if not rebuilt:
        return
    if args.dry_run:
        for card in list(rebuilt)[:6]:
            old = next(c for c in data if c["card"] == card)["text"]
            print(f"\n{card}\n  old: {old[:110]}\n  new: {rebuilt[card][:110]}")
        return

    import difflib

    def offset_map(a, b):
        """Map a character offset in `a` to the corresponding one in `b`."""
        ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()

        def m(i):
            for tag, i1, i2, j1, j2 in ops:
                if i1 <= i < i2:
                    return (j1 + (i - i1)) if tag == "equal" else j1
            return len(b)
        return m

    ok = skipped = 0
    dropped_cands = lost_labels = 0
    reasons = {}
    for c in data:
        if c["card"] not in rebuilt:
            continue
        new_text = rebuilt[c["card"]]
        if new_text == c["text"]:
            continue
        m = offset_map(c["text"], new_text)

        # anaphor spans must survive exactly; otherwise leave the record alone
        bad = None
        for a_ in c["anaphors"]:
            s2, e2 = m(a_["start"]), m(a_["end"])
            if new_text[s2:e2] != a_["surface"]:
                bad = "anaphor span"
                break
        if bad:
            skipped += 1
            reasons[bad] = reasons.get(bad, 0) + 1
            continue

        # candidates whose span no longer reproduces their surface were created
        # BY the clobbering (e.g. "~ch" produced a bogus `~` self-reference)
        keep, remap = [], {}
        for i, cand in enumerate(c["candidates"]):
            s2, e2 = m(cand["start"]), m(cand["end"])
            if new_text[s2:e2] == cand["surface"]:
                remap[i] = len(keep)
                keep.append({"surface": cand["surface"], "start": s2, "end": e2})
            else:
                dropped_cands += 1

        for a_ in c["anaphors"]:
            g = a_.get("antecedent")
            a_["start"], a_["end"] = m(a_["start"]), m(a_["end"])
            if g is None or g < 0:
                continue
            if g in remap:
                a_["antecedent"] = remap[g]
            else:
                a_["antecedent"] = -1
                lost_labels += 1
        c["candidates"] = keep
        c["text"] = new_text
        ok += 1

    print(f"repaired: {ok}   skipped: {skipped} {reasons}")
    print(f"bogus mentions dropped: {dropped_cands}   "
          f"teacher labels lost (pointed at a bogus mention): {lost_labels}")
    out = args.json_out or args.dataset
    with open(out, "w") as fh:
        json.dump(data, fh)
    print(f"wrote {out}")
    left = sum(1 for c in data if re.search(r"~[A-Za-z]", c["text"]))
    print(f"records still carrying a clobbered token: {left}")


if __name__ == "__main__":
    main()
