#!/usr/bin/env python3
"""Fast iteration harness: parse a fixed random SAMPLE of oracle sentences.

Use this between full runs to get quick feedback (~2 min instead of ~35 min).
The full run (test_parse.py) remains the source of truth for coverage.
"""
import sys, os, time, argparse, random
from lark import Lark, LarkError
from preprocess import segment
from mtd import all_oracle_text, card_type_set, name_set
from transformer import OracleTransformer

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')


def build_parser():
    return Lark.open(GRAMMAR, parser='earley', start='start',
                     ambiguity='resolve', keep_all_tokens=False)


def collect_items():
    out = []
    for name, text in all_oracle_text():
        for it in segment(text):
            out.append((name, it))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=150, help='sample size')
    ap.add_argument('-s', '--seed', dest='seed', type=int, default=7, help='random seed (fixed sample)')
    ap.add_argument('--all', action='store_true', help='run the whole corpus')
    args = ap.parse_args()

    items = collect_items()
    if args.all:
        sample = items
    else:
        random.seed(args.seed)
        sample = random.sample(items, min(args.n, len(items)))

    parser = build_parser()
    tr = OracleTransformer(types=card_type_set(), names=name_set())

    ok = 0
    fails = []
    t0 = time.time()
    for i, (name, it) in enumerate(sample):
        s = it['text']
        try:
            parser.parse(s)
            ok += 1
        except LarkError as e:
            fails.append((s, str(e).split('\n')[0][:80]))
        if (i + 1) % 25 == 0:
            print(f"  ...{i+1}/{len(sample)}  {ok} ok  {time.time()-t0:.0f}s",
                  file=sys.stderr, flush=True)

    el = time.time() - t0
    print(f"\n==== SAMPLE {ok}/{len(sample)} = {100*ok/len(sample):.1f}%  ({el:.0f}s) ====")
    if fails:
        from collections import Counter
        print(f"--- {len(fails)} failures (most common) ---")
        for s, n in Counter(s for s, _ in fails).most_common(30):
            print(f"  [{n}] {s}")


if __name__ == '__main__':
    main()
