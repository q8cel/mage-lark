#!/usr/bin/env python3
"""Run the parser over every oracle sentence; report coverage and dump failures."""
import sys, os, json, argparse
from lark import Lark, Transformer, v_args, LarkError
from preprocess import segment
from mtd import all_oracle_text, card_type_set, name_set

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')

def build_parser():
    parser = Lark.open(GRAMMAR, parser='earley', start='start',
                       ambiguity='resolve', keep_all_tokens=True)
    return parser

def collect_items():
    out = []
    for name, text in all_oracle_text():
        for it in segment(text):
            out.append((name, it))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', type=int, default=0, help='show up to N parsed trees')
    ap.add_argument('--fail', action='store_true', help='only show failures')
    ap.add_argument('--dump', default=None, help='dump failures to file')
    args = ap.parse_args()

    parser = build_parser()
    types = card_type_set()
    names = name_set()

    from interpret import Interpreter
    interp = Interpreter(types=types, names=names)
    total = 0
    ok = 0
    fails = []
    shown = 0
    import time
    t0 = time.time()
    for name, it in collect_items():
        s = it['text']
        total += 1
        if total % 100 == 0:
            el = time.time() - t0
            print(f"  ...{total} items, {ok} ok, {el:.0f}s elapsed", file=sys.stderr, flush=True)
        try:
            tree = parser.parse(s)
            result = interp.interp(tree)
            ok += 1
            if args.show and shown < args.show and not args.fail:
                shown += 1
                print(f"=== {s}\n{json.dumps(result, indent=1, ensure_ascii=False)[:600]}\n")
        except LarkError as e:
            fails.append((name, s, str(e).split('\n')[0][:120]))
            if not args.fail or True:
                if len(fails) <= (0 if args.dump else 200):
                    pass

    print(f"\n==== COVERAGE: {ok}/{total} = {100*ok/total:.1f}% ====")
    print(f"Failures: {len(fails)}")

    if args.dump:
        with open(args.dump, 'w') as f:
            for n,s,e in fails:
                f.write(f"{s}\n")
        print(f"Dumped failures to {args.dump}")
    else:
        from collections import Counter
        c = Counter(s for _,s,_ in fails)
        print("--- most common failures ---")
        for s,n in c.most_common(40):
            print(f"  [{n}] {s}")

if __name__ == '__main__':
    main()
