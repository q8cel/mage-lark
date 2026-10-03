#!/usr/bin/env python3
"""Parallel coverage runner: parse every oracle sentence with a process pool.

Usage:
  python test_parallel.py --data FDN.json
  python test_parallel.py --data Standard.json --workers 24
  python test_parallel.py --data Standard.json --dump failures_std.txt
"""
import sys, os, json, argparse, time
import multiprocessing as mp

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')

# ---- per-worker globals (initialized once per process) ----
_P = None
_I = None

def _init(grammar_path, types, names):
    global _P, _I
    from lark import Lark
    from interpret import Interpreter
    _P = Lark.open(grammar_path, parser='earley', start='start',
                   ambiguity='resolve', keep_all_tokens=True)
    _I = Interpreter(types=types, names=names)

def _work(batch):
    """batch: list of (idx, name, text) -> list of (idx, name, text, err_or_None)."""
    out = []
    for idx, name, s in batch:
        try:
            _P.parse(s)
            out.append((idx, name, s, None))
        except Exception as e:
            out.append((idx, name, s, str(e).split('\n')[0][:120]))
    return out

def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='path to FDN.json or mtgjson set')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument('--chunk', type=int, default=16, help='items per pool task')
    ap.add_argument('--dump', default=None)
    ap.add_argument('--n', type=int, default=0, help='limit items (0 = all)')
    args = ap.parse_args()

    from setdata import load
    from preprocess import segment

    t0 = time.time()
    items, types, names, sets = load(args.data)
    # segment each card's text into sentences
    work = []
    for name, text in items:
        for d in segment(text):
            s = d['text']
            if s and not d['modal']:
                work.append((name, s))
    total_all = len(work)
    if args.n:
        work = work[:args.n]
    total = len(work)
    setstr = ','.join(sets) if len(sets) <= 6 else f"{len(sets)} sets"
    print(f"set: {os.path.basename(args.data)}  sets=[{setstr}]  cards={len(items)}  "
          f"sentences={total_all}  testing={total}  workers={args.workers}  "
          f"(loaded in {time.time()-t0:.1f}s)")

    # reindex
    work = [(i, name, s) for i, (name, s) in enumerate(work)]
    batches = list(_chunked(work, args.chunk))

    t1 = time.time()
    fails = []
    ok = 0
    done = 0
    with mp.Pool(args.workers, initializer=_init,
                 initargs=(GRAMMAR, types, names)) as pool:
        for res in pool.imap_unordered(_work, batches):
            for idx, name, s, err in res:
                if err is None:
                    ok += 1
                else:
                    fails.append((name, s, err))
            done += 1
            if done % max(1, len(batches)//20) == 0:
                el = time.time() - t1
                print(f"  ...{done}/{len(batches)} batches, {ok} ok, {el:.0f}s",
                      file=sys.stderr, flush=True)
    el = time.time() - t1
    rate = total/el if el > 0 else 0

    print(f"\n==== COVERAGE: {ok}/{total} = {100*ok/total:.1f}%  in {el:.0f}s ({rate:.1f} sent/s) ====")
    print(f"Failures: {len(fails)}")

    if args.dump:
        with open(args.dump, 'w') as f:
            for n, s, e in fails:
                f.write(f"{s}\n")
        print(f"Dumped failures to {args.dump}")
    else:
        from collections import Counter
        c = Counter(s for _, s, _ in fails)
        print("--- most common failures ---")
        for s, n in c.most_common(40):
            print(f"  [{n}] {s}")

if __name__ == '__main__':
    main()
