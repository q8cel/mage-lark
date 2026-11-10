#!/usr/bin/env python3
"""Hyperparameter sweep for the mention-ranking head.

Encodes each text once (disk-cached) and reuses the pair features across many
head configurations, so only the tiny MLP is retrained per config.

Usage:
  python sweep_head.py --model sentence-transformers/all-MiniLM-L6-v2
  python sweep_head.py --model roberta-base --layer 6
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from train_head import (Encoder, build_examples, eval_gold, train_model)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="coref_dataset.json,coref_standard.json")
    ap.add_argument("--bench", default=os.path.join(BASE, "coref_benchmark.json"))
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    ap.add_argument("--layer", type=int, default=3)
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    data = []
    for p in args.data.split(","):
        data.extend(json.load(open(p)))
    seen = set()
    data = [d for d in data if not (d["card"] in seen or seen.add(d["card"]))]
    bench = json.load(open(args.bench))
    holdout = {b[0] for b in bench}

    enc = Encoder(args.model, args.layer)
    d = enc.encode(data[0]["text"])[0].shape[1]
    train_ex, skipped = build_examples(data, enc, holdout, args.layer)
    enc.save()
    print(f"train pools={len(train_ex)} dim={d} layer={args.layer} model={args.model}")

    grid = list(itertools.product([32, 128, 256], [0.1, 0.3, 0.5], [1e-4, 1e-2]))
    best = None
    print(f"{'hidden':>6} {'drop':>5} {'wd':>7}   mean  runs")
    for hidden, drop, wd in grid:
        scores = []
        for s in range(args.seeds):
            model = train_model(train_ex, d, 40, 1e-3, s, hidden, drop, wd)
            n, ok, base = eval_gold(model, enc, data, bench)
            scores.append(100 * ok / max(n, 1))
        m = sum(scores) / len(scores)
        runs = " ".join(f"{x:.0f}" for x in scores)
        mark = ""
        if best is None or m > best[0]:
            best = (m, hidden, drop, wd)
            mark = "  *"
        print(f"{hidden:>6} {drop:>5} {wd:>7.0e}  {m:5.1f}  {runs}{mark}")
    print(f"\nBEST: hidden={best[1]} dropout={best[2]} wd={best[3]:.0e}  mean={best[0]:.1f}%")


if __name__ == "__main__":
    main()
