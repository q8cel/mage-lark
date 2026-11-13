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

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys, os, json, time, hashlib, pickle, argparse
import multiprocessing as mp

BASE = _paths.ROOT
GRAMMAR = _paths.GRAMMAR
CACHE = _paths.CACHE

_P = None
_I = None
_TIMEOUT = 0


class _ParseTimeout(Exception):
    pass


def _alarm(sig, frm):
    raise _ParseTimeout()


def _init(grammar_path, types, names, timeout=0):
    global _P, _I, _TIMEOUT
    from interpret import Interpreter
    from larkparser import build_parser
    _P = build_parser("interp", grammar_path)
    _I = Interpreter(types=types, names=names)
    _TIMEOUT = timeout


def _parse_one(s):
    global _P
    if not _TIMEOUT:
        return _P.parse(s)
    import signal
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, _TIMEOUT)
    try:
        return _P.parse(s)
    except _ParseTimeout:
        # A timed-out Earley parse can leave internal state inconsistent.
        _P = None
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _work(texts):
    """texts: list[str] -> list[(text, 1/0, timed_out)]."""
    global _P
    out = []
    from larkparser import build_parser
    for s in texts:
        if _P is None:
            _P = build_parser("interp")
        try:
            _parse_one(s)
            out.append((s, 1, False))
        except _ParseTimeout:
            out.append((s, 0, True))
        except Exception:
            out.append((s, 0, False))
    return out

def _has_unparsed(node, top=False):
    if isinstance(node, list):
        return any(_has_unparsed(x) for x in node)
    if not isinstance(node, dict):
        return False
    if node.get('unparsed') or node.get('type') == 'unparsed' or 'text' in node:
        return True
    return any(_has_unparsed(v) for k, v in node.items() if k != 'meta')


def _check_outputs(texts):
    """texts: list[str] already known to parse -> [(text, bad)]. """
    global _P, _I
    out = []
    for s in texts:
        try:
            tree = _P.parse(s)
            res = _I.interp(tree)
            bad = _has_unparsed(res)
        except Exception:
            bad = True
        out.append((s, bad))
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
    ap.add_argument('--checkpoint', type=int, default=50,
                    help='save the parse cache every N batches (0 = only at end)')
    ap.add_argument('--lenient', action='store_true',
                    help='count parsed sentences as covered even if the output is unparsed')
    ap.add_argument('--timeout', type=float, default=0,
                    help='per-sentence parse cap in seconds (0 = no cap)')
    ap.add_argument('--seed', default=None,
                    help='path to an older parse_<hash>.json; for strictly-additive '
                         'grammar edits, trust its passing (1) sentences and re-parse only '
                         'the old failures (spot-checked for safety)')
    args = ap.parse_args()
    args.data = _paths.data(args.data)
    os.makedirs(CACHE, exist_ok=True)

    from setdata import load
    from preprocess import segment

    t0 = time.time()
    # ---- segment cache ----
    dh = file_hash(args.data)
    # the load() result (esp. the `names` normalization set) depends on
    # setdata.py's logic, so key the cache by setdata.py too -- otherwise a
    # change to the name-exclusion stoplist serves a stale `names` set.
    _sdh = file_hash(_paths.source('setdata.py'))
    seg_cache = os.path.join(CACHE, f'seg_{dh}_{_sdh}.pkl')
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
    seg_key = (dh + '_' + file_hash(_paths.source('preprocess.py'))
               + '_' + file_hash(_paths.source('setdata.py')))
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
    # Sentence text is surface text: a protected-list token here means an
    # upstream stage persisted the parser form (see lists.parse_ready).
    bad = next((t for t in uniq if '@@' in t), None)
    if bad is not None:
        raise SystemExit(
            f"sentence text contains a protected-list token: {bad[:120]!r}")
    print(f"occurrences={total_occ}  unique_texts={len(uniq)}")

    # ---- parse cache ----
    gh = file_hash(GRAMMAR)
    parse_cache_path = os.path.join(CACHE, f'parse_{gh}.json')
    cache = {}
    if not args.no_cache and os.path.exists(parse_cache_path):
        cache = json.load(open(parse_cache_path))
        # Sentence texts are decoded now; old entries were keyed by the
        # protected-list form and can only be stale.
        stale = [k for k in cache if '@@' in k]
        for k in stale:
            cache.pop(k)
        if stale:
            print(f"[parse-cache] dropped {len(stale)} protected-list keys")
        print(f"[parse-cache] {len(cache)} entries from grammar hash {gh}")

    # --seed: additive-grammar optimization. When this edit only ADDED parse
    # alternatives, the new grammar's parseable set is a superset of the seed's,
    # so every previously-passing sentence still parses. We trust the seed's 1s
    # and re-parse only the old failures, plus a small spot-check of the trusted
    # 1s to confirm the edit really was additive.
    seed_sample = []
    if args.seed and os.path.exists(args.seed) and not args.no_cache:
        seed = json.load(open(args.seed))
        uniq_set = set(uniq)
        new_passes = [t for t, v in seed.items() if v == 1 and t in uniq_set and t not in cache]
        if new_passes:
            import random
            seed_sample = random.Random(1234).sample(new_passes, min(40, len(new_passes)))
            for t in new_passes:
                cache[t] = 1
            print(f"[seed] trusting {len(new_passes)} old passes ({os.path.basename(args.seed)}); spot-check {len(seed_sample)}")

    todo = [s for s in uniq if s not in cache]
    if seed_sample:
        todo_set = set(todo)
        todo += [s for s in seed_sample if s not in todo_set]
    print(f"cache hits={len(uniq)-len(todo)}  to-parse={len(todo)}  workers={args.workers}")

    def _save_parse_cache():
        if args.no_cache:
            return
        tmp = parse_cache_path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(cache, fh)
        os.replace(tmp, parse_cache_path)

    def _parse_batch(texts):
        if not texts:
            return
        t = time.time()
        batches = list(_chunked(texts, args.chunk))
        with mp.Pool(args.workers, initializer=_init,
                     initargs=(GRAMMAR, types, names, args.timeout)) as pool:
            for i, res in enumerate(pool.imap_unordered(_work, batches), 1):
                for s, ok, _timed_out in res:
                    cache[s] = ok
                if i % max(1, len(batches)//10) == 0:
                    print(f"  ...{i}/{len(batches)} batches, {time.time()-t:.0f}s",
                          file=sys.stderr, flush=True)
                if args.checkpoint and i % args.checkpoint == 0:
                    _save_parse_cache()
                    print(f"  [checkpoint] {len(cache)} cached",
                          file=sys.stderr, flush=True)
        print(f"[parse] {len(texts)} texts in {time.time()-t:.0f}s")

    try:
        _parse_batch(todo)
    except KeyboardInterrupt:
        _save_parse_cache()
        print(f"\n[interrupted] saved {len(cache)} cache entries",
              file=sys.stderr, flush=True)
        raise

    # seed safety: if any spot-check sample regressed, the edit was NOT purely
    # additive -> discard trusted 1s and re-parse the whole dataset.
    if seed_sample:
        regressed = [s for s in seed_sample if not cache.get(s)]
        if regressed:
            print(f"[seed] WARNING: {len(regressed)}/{len(seed_sample)} spot-check REGRESSED -> not additive; full re-parse")
            cache = {}
            _parse_batch([s for s in uniq])

    if not args.no_cache:
        _save_parse_cache()
        print(f"[parse-cache] saved {len(cache)} entries")
    elif not cache:
        print("all unique texts cached -> nothing to parse")

    # ---- roll up to occurrences ----
    parse_ok = sum(1 for s in work if cache.get(s))
    total = len(work)
    unparsed = {}
    if not args.lenient:
        passing = [s for s in uniq if cache.get(s)]
        batches = list(_chunked(passing, max(1, args.chunk * 4)))
        with mp.Pool(args.workers, initializer=_init,
                     initargs=(GRAMMAR, types, names, args.timeout)) as pool:
            for res in pool.imap_unordered(_check_outputs, batches):
                for s, bad in res:
                    unparsed[s] = bad
    honest_ok = 0
    parse_fails = []
    interp_fails = []
    for s in work:
        if not cache.get(s):
            parse_fails.append(s)
        elif unparsed.get(s):
            interp_fails.append(s)
        else:
            honest_ok += 1
    print(f"\n==== PARSE COVERAGE: {parse_ok}/{total} = {100*parse_ok/total:.1f}%  "
          f"(unique {sum(cache.get(s,0) for s in uniq)}/{len(uniq)}) ====")
    if args.lenient:
        print("==== HONEST COVERAGE: lenient (unparsed outputs counted as covered) ====")
    else:
        print(f"==== HONEST COVERAGE: {honest_ok}/{total} = {100*honest_ok/total:.1f}% "
              f"(unique {sum(1 for s in uniq if cache.get(s) and not unparsed.get(s))}/{len(uniq)}) ====")
    print(f"Failures (occurrences): parse_fail {len(parse_fails)} "
          f"(unique {len(set(parse_fails))}), interpret_unparsed {len(interp_fails)} "
          f"(unique {len(set(interp_fails))})")
    fails = parse_fails + interp_fails

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
