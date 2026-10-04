#!/usr/bin/env python3
"""Optimized coverage runner with on-disk caching.

Two caches make repeat checks fast (the point: a Standard re-check should NOT
re-run the whole corpus for hours):

  1. SEGMENT cache  (.cache/seg_<hash>.pkl)
     Keyed by the content hash of the data file. Stores the segmented
     (card_name, sentence) list so we never re-load/re-split a 70MB file.

  2. PARSE cache    (.cache/parse_<gramhash>.json)
     Keyed by the content hash of grammar.lark. Maps sentence text -> 1/0
     (parsed/failed). If you haven't changed the grammar, every sentence is a
     cache hit and the run is near-instant. Change the grammar -> new key ->
     everything re-parses (in parallel, deduped by unique text).

Only unique sentence *texts* are parsed (many repeat across cards), then results
are rolled back up to per-occurrence coverage.

Usage:
  python run.py --data FDN.json
  python run.py --data Standard.json --dump failures.txt
  python run.py --data Standard.json --sets OTJ,WOE     # subset of sets
  python run.py --data Standard.json --workers 24
"""
import sys, os, json, time, hashlib, pickle, argparse
import multiprocessing as mp

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')
CACHE = os.path.join(BASE, '.cache')

_P = None
_I = None

def _init(grammar_path, types, names):
    global _P, _I
    from lark import Lark
    from interpret import Interpreter
    _P = Lark.open(grammar_path, parser='earley', start='start',
                   ambiguity='resolve', keep_all_tokens=True)
    _I = Interpreter(types=types, names=names)

def _work(texts):
    """texts: list[str] -> list[(text, 1/0)]."""
    out = []
    for s in texts:
        try:
            _P.parse(s)
            out.append((s, 1))
        except Exception:
            out.append((s, 0))
    return out

def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def file_hash(path, chunk=1 << 20):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument('--chunk', type=int, default=8)
    ap.add_argument('--sets', default=None, help='comma list of set codes to include')
    ap.add_argument('--dump', default=None)
    ap.add_argument('--n', type=int, default=0)
    ap.add_argument('--no-cache', action='store_true')
    args = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)

    from setdata import load
    from preprocess import segment

    t0 = time.time()
    # ---- segment cache ----
    dh = file_hash(args.data)
    seg_cache = os.path.join(CACHE, f'seg_{dh}.pkl')
    items, types, names, sets = None, None, None, None
    if not args.no_cache and os.path.exists(seg_cache):
        t = time.time()
        items, types, names, sets = pickle.load(open(seg_cache, 'rb'))
        print(f"[seg-cache HIT] {time.time()-t:.1f}s")
    else:
        items, types, names, sets = load(args.data)
        pickle.dump((items, types, names, sets), open(seg_cache, 'wb'))
        print(f"[seg-cache MISS] loaded+stored in {time.time()-t0:.1f}s")

    if args.sets:
        keep = set(args.sets.split(','))
        items = [it for it in items if it[2] in keep]
        sets = [s for s in sets if s in keep]
        print(f"filtered to sets {sets}: {len(items)} cards")

    # segment (cached: keyed by data hash + preprocess.py hash, so a change to
    # the segmentation logic invalidates it automatically)
    import preprocess as _pp
    # sent-cache is only valid for the full (unfiltered) corpus; keyed by data
    # + segmentation logic (preprocess.py) + name source (setdata.py)
    seg_key = (dh + '_' + file_hash(os.path.join(BASE, 'preprocess.py'))
               + '_' + file_hash(os.path.join(BASE, 'setdata.py')))
    seg_cache2 = os.path.join(CACHE, f'sent_{seg_key}.pkl')
    t = time.time()
    use_sent_cache = not args.no_cache and not args.sets
    if use_sent_cache and os.path.exists(seg_cache2):
        work = pickle.load(open(seg_cache2, 'rb'))
        print(f"[sent-cache HIT] {time.time()-t:.1f}s")
    else:
        work = []
        for name, text, code in items:
            for d in segment(text, names):
                s = d['text']
                if s and not d['modal']:
                    work.append(s)
        if use_sent_cache:
            pickle.dump(work, open(seg_cache2, 'wb'))
        print(f"[sent-cache {'store' if use_sent_cache else 'skip'}] segmented in {time.time()-t:.1f}s")
    total_occ = len(work)
    if args.n:
        work = work[:args.n]
        total_occ = len(work)
    uniq = sorted(set(work))
    print(f"occurrences={total_occ}  unique_texts={len(uniq)}")

    # ---- parse cache ----
    gh = file_hash(GRAMMAR)
    parse_cache_path = os.path.join(CACHE, f'parse_{gh}.json')
    cache = {}
    if not args.no_cache and os.path.exists(parse_cache_path):
        cache = json.load(open(parse_cache_path))
        print(f"[parse-cache] {len(cache)} entries from grammar hash {gh}")

    todo = [s for s in uniq if s not in cache]
    print(f"cache hits={len(uniq)-len(todo)}  to-parse={len(todo)}  workers={args.workers}")

    if todo:
        t = time.time()
        batches = list(_chunked(todo, args.chunk))
        with mp.Pool(args.workers, initializer=_init,
                     initargs=(GRAMMAR, types, names)) as pool:
            for i, res in enumerate(pool.imap_unordered(_work, batches), 1):
                for s, ok in res:
                    cache[s] = ok
                if i % max(1, len(batches)//10) == 0:
                    print(f"  ...{i}/{len(batches)} batches, {time.time()-t:.0f}s",
                          file=sys.stderr, flush=True)
        if not args.no_cache:
            json.dump(cache, open(parse_cache_path, 'w'))
            print(f"[parse-cache] saved {len(cache)} entries in {time.time()-t:.0f}s")
        else:
            print(f"parsed in {time.time()-t:.0f}s (no cache write)")
    else:
        print("all unique texts cached -> nothing to parse")

    # ---- roll up to occurrences ----
    ok_occ = 0
    fails = []
    seen_fail = set()
    for s in work:
        if cache.get(s):
            ok_occ += 1
        else:
            fails.append(s)
    total = len(work)
    print(f"\n==== COVERAGE: {ok_occ}/{total} = {100*ok_occ/total:.1f}%  "
          f"(unique {sum(cache.get(s,0) for s in uniq)}/{len(uniq)}) ====")
    print(f"Failures (occurrences): {len(fails)}  (unique: {len(set(fails))})")

    if args.dump:
        with open(args.dump, 'w') as f:
            for s in fails:
                f.write(f"{s}\n")
        print(f"Dumped to {args.dump}")
    else:
        from collections import Counter
        c = Counter(fails)
        print("--- most common unique failures ---")
        for s, n in c.most_common(40):
            print(f"  [{n}x] {s}")

if __name__ == '__main__':
    main()
