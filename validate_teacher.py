#!/usr/bin/env python3
"""Validate the teacher-labelled dataset against the 72 human-gold cases.

Checks two things:
  1. candidate recall  -- is the gold antecedent even present in the candidate list?
  2. teacher agreement -- did the teacher pick the gold antecedent?

Usage: python validate_teacher.py [coref_dataset.json]
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from anaphora import find_anaphors


def match(ss, g):
    return g in ss or ss in g


def norm(s):
    return s.lower().replace("\u2019s", "").replace("'s", "")


def main():
    ds_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "coref_dataset.json")
    data = json.load(open(ds_path))
    by_card = {c["card"]: c for c in data}
    bench = json.load(open(os.path.join(BASE, "coref_benchmark.json")))

    n = ok = recall = 0
    rows = []
    for card, ana, occ, gold in bench:
        rec = by_card.get(card)
        if not rec:
            rows.append((card, ana, gold, "NO_DATASET_RECORD", None, None))
            continue
        anas = find_anaphors(rec["text"])
        idxs = [i for i, a in enumerate(anas) if norm(a["surface"]) == norm(ana)]
        if len(idxs) <= occ:
            rows.append((card, ana, gold, "OCCURRENCE_MISSING", None, None))
            continue
        a = anas[idxs[occ]]
        cands = rec["candidates"]
        g = gold.lower()
        has_recall = any(match(c["surface"].lower(), g) for c in cands)
        recall += int(has_recall)
        hit = [x for x in rec["anaphors"] if x["start"] == a["start"] and x["end"] == a["end"]]
        ant = hit[0]["antecedent"] if hit else None
        pred = cands[ant]["surface"] if isinstance(ant, int) and 0 <= ant < len(cands) else str(ant)
        good = isinstance(ant, int) and 0 <= ant < len(cands) and match(cands[ant]["surface"].lower(), g)
        ok += int(good)
        n += 1
        rows.append((card, ana, gold, pred, "OK" if good else ("RECALL_MISS" if not has_recall else "WRONG"), has_recall))

    print(f"n={n}  teacher_ok={ok} ({100 * ok / max(n, 1):.0f}%)  "
          f"candidate_recall={recall} ({100 * recall / max(n, 1):.0f}%)")
    print("\n-- disagreements / issues --")
    for card, ana, gold, pred, status, hr in rows:
        if status != "OK":
            print(f"  [{status}] {card}: {ana!r} gold={gold!r} -> {pred!r}")


if __name__ == "__main__":
    main()
