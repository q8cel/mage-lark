#!/usr/bin/env python3
"""Deterministic output snapshots for the parse+interpret pipeline.

A snapshot is the review baseline for the interpreter: every successfully
parsed unique sentence with a canonical output hash and a structural shape
hash, plus the full interpreted output.  Two builds from the same sources and
the same caches are byte-identical; ``diff`` classifies what changed.

Snapshot layout (compact, sorted JSON)::

    meta
      corpus, created_from_commit, grammar_sha1, interp_sha1,
      preprocess_sha1, setdata_sha1, count, digest, occurrences
    sentences
      {text: {out_sha1, shape_sha1, cluster}}
    outputs
      {text: <interpreted output>}
    unparsed            (only with --unparsed)
      [text, ...]

``cluster`` is the k2 parse signature: the preorder rule tree with terminals
collapsed to ``$TOKEN_TYPE`` and Lark's generated anonymous token names
normalised to ``$@``.  ``shape_sha1`` hashes the recursive sorted key-path
skeleton of the output (values ignored, ``note``/``head``/``shared_prefix``/
``shared_suffix`` ignored); ``out_sha1`` hashes the full canonical output.

Both subcommands bootstrap like every other tool: put the repo root on
``sys.path``, then ``import paths; paths.bootstrap()``.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import argparse
import hashlib
import gzip
import json
import multiprocessing as mp
import os
import pickle
import re
import signal
import subprocess
import sys
import time
from collections import Counter

from lark import Token, Tree

BASE = _paths.ROOT
GRAMMAR = _paths.GRAMMAR
CACHE = _paths.CACHE

ANON = re.compile(r"\$__ANON_\d+")
SHAPE_SKIP = frozenset({"note", "head", "shared_prefix", "shared_suffix"})
_P = None
_I = None
_TREES = None
_TIMEOUT = 0


class _Timeout(Exception):
    pass


def _alarm(sig, frm):
    raise _Timeout()


def _pool_context():
    try:
        return mp.get_context("fork")
    except ValueError:
        return mp.get_context()


def _init_worker(types, names, timeout):
    global _P, _I, _TIMEOUT
    from larkparser import build_parser
    from interpret import Interpreter
    _P = build_parser("interp")
    _I = Interpreter(types=set(types), names=set(names))
    _TIMEOUT = timeout


def _parse(text):
    global _P
    if not _TIMEOUT:
        return _P.parse(text)
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, _TIMEOUT)
    try:
        return _P.parse(text)
    except _Timeout:
        # A timed-out Earley parse can leave parser state inconsistent.
        from larkparser import build_parser
        _P = build_parser("interp")
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _init_worker_cached(types, names):
    """Tree mode: no parser, only the interpreter."""
    global _I
    from interpret import Interpreter
    _I = Interpreter(types=set(types), names=set(names))


def _work_parse(texts):
    """Parse only: return trees so they can go into the tree cache."""
    out = []
    for text in texts:
        try:
            tree = _parse(text)
        except Exception:
            out.append((text, 0, None))
            continue
        out.append((text, 1, tree))
    return out


def _work_cached(texts):
    """Interpret trees inherited from the parent via fork."""
    out = []
    for text in texts:
        tree = _TREES.get(text)
        if tree is None:
            out.append((text, 0, None, None))
            continue
        try:
            output = _I.interp(tree)
        except Exception:
            out.append((text, 0, None, None))
            continue
        out.append((text, 1, output, ANON.sub("$@", tree_sig(tree))))
    return out


def file_hash(path, chunk=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()[:16]


def source_hashes():
    return {
        "grammar_sha1": file_hash(GRAMMAR),
        "interp_sha1": file_hash(_paths.source("interpret.py")),
        "preprocess_sha1": file_hash(_paths.source("preprocess.py")),
        "setdata_sha1": file_hash(_paths.source("setdata.py")),
    }


def created_from_commit():
    try:
        head = subprocess.run(["git", "-C", BASE, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", BASE, "status", "--porcelain",
                                "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


# ----------------------------------------------------------------- signatures
def tree_sig(node):
    """Rule-name tree with terminals collapsed to their token type."""
    if isinstance(node, Token):
        return "$" + node.type
    if isinstance(node, Tree):
        return node.data + "(" + ",".join(tree_sig(c) for c in node.children) + ")"
    return ""


def skeleton(obj):
    """Recursive sorted key-path skeleton; values and annotation keys ignored."""
    if isinstance(obj, dict):
        return "{" + ",".join("%s:%s" % (k, skeleton(v))
                              for k, v in sorted(obj.items())
                              if k not in SHAPE_SKIP) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(skeleton(v) for v in obj) + "]"
    return "."


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def out_hashes(output):
    full = canonical(output)
    return (hashlib.sha1(full.encode()).hexdigest(),
            hashlib.sha1(skeleton(output).encode()).hexdigest())


# ------------------------------------------------------------------ corpus IO
def _seg_paths(data_path):
    dh = file_hash(data_path)
    sdh = file_hash(_paths.source("setdata.py"))
    pph = file_hash(_paths.source("preprocess.py"))
    seg = os.path.join(CACHE, "seg_%s_%s.pkl" % (dh, sdh))
    sent = os.path.join(CACHE, "sent_%s_%s_%s.pkl" % (dh, pph, sdh))
    return seg, sent


def corpus_texts(data):
    """Reuse tools/run.py's segmentation caches; write them when absent."""
    from setdata import load
    from preprocess import segment
    data_path = _paths.data(data)
    seg_cache, sent_cache = _seg_paths(data_path)
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(seg_cache):
        with open(seg_cache, "rb") as fh:
            items, types, names, _sets = pickle.load(fh)
    else:
        items, types, names, _sets = load(data_path)
        with open(seg_cache, "wb") as fh:
            pickle.dump((items, types, names, _sets), fh)
    if os.path.exists(sent_cache):
        with open(sent_cache, "rb") as fh:
            work = pickle.load(fh)
    else:
        work = []
        for _name, text, _code in items:
            for item in segment(text, names):
                if item["text"] and not item["modal"]:
                    work.append(item["text"])
        with open(sent_cache, "wb") as fh:
            pickle.dump(work, fh)
    bad = next((t for t in work if '@@' in t), None)
    if bad is not None:
        raise SystemExit(
            "sentence text contains a protected-list token: %r" % bad[:120])
    return sorted(set(work)), Counter(work), sorted(types), sorted(names)


def sentence_texts(path):
    with open(path) as fh:
        texts = [line.strip() for line in fh if line.strip()]
    return sorted(set(texts)), Counter(texts), [], []


def parse_cache_path():
    return os.path.join(CACHE, "parse_%s.json" % file_hash(GRAMMAR))


def load_parse_cache():
    path = parse_cache_path()
    if os.path.exists(path):
        with open(path) as fh:
            cache = json.load(fh)
        # drop entries keyed by the old protected-list sentence form
        stale = [k for k in cache if '@@' in k]
        for k in stale:
            cache.pop(k)
        return cache, path
    return {}, path


def tree_cache_path(grammar16):
    return os.path.join(CACHE, "trees", "trees_%s.pkl.gz" % grammar16)


def load_trees(path):
    if not os.path.exists(path):
        return {}
    with gzip.open(path, "rb") as fh:
        return pickle.load(fh)


def save_trees(path, trees):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with gzip.open(tmp, "wb", compresslevel=6) as fh:
        pickle.dump(trees, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def save_parse_cache(cache, path):
    os.makedirs(CACHE, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(cache, fh)
    os.replace(tmp, path)


# --------------------------------------------------------------------- build
def build(args):
    t0 = time.time()
    sources_start = source_hashes()
    commit = created_from_commit()
    if args.sentences:
        texts, occurrences, types, names = sentence_texts(args.sentences)
        corpus = os.path.splitext(os.path.basename(args.sentences))[0]
        cache, cache_path = None, None
    else:
        if not args.data:
            sys.exit("build: one of --data or --sentences is required")
        texts, occurrences, types, names = corpus_texts(args.data)
        corpus = os.path.splitext(os.path.basename(_paths.data(args.data)))[0]
        cache, cache_path = load_parse_cache()

    taken = texts[:args.limit] if args.limit else texts
    known_fail = [t for t in taken if cache and cache.get(t) == 0]
    todo = [t for t in taken if not (cache and cache.get(t) == 0)]
    if cache is None:
        known_fail = []

    jobs = args.jobs or max(1, (os.cpu_count() or 4) - 2)
    parsed = {}
    failures = list(known_fail)

    # Tree cache is keyed by the grammar hash only: an interpreter-only change
    # re-uses every tree.  Trees are pickled (not coverage bits), so a cache hit
    # skips parsing entirely.
    trees = load_trees(tree_cache_path(sources_start["grammar_sha1"]))
    missing = [t for t in todo if t not in trees]
    if missing:
        chunks = [missing[i:i + 8] for i in range(0, len(missing), 8)]
        with _pool_context().Pool(jobs, initializer=_init_worker,
                                  initargs=(types, names, args.timeout)) as pool:
            for i, result in enumerate(pool.imap_unordered(_work_parse, chunks), 1):
                for text, ok, tree in result:
                    if not ok:
                        failures.append(text)
                        if cache is not None:
                            cache[text] = 0
                        continue
                    trees[text] = tree
                    if cache is not None:
                        cache[text] = 1
                if i % 100 == 0:
                    print("  ...%d/%d parse batches" % (i, len(chunks)),
                          file=sys.stderr, flush=True)
        save_trees(tree_cache_path(sources_start["grammar_sha1"]), trees)
    if cache is not None and missing:
        save_parse_cache(cache, cache_path)

    interpretable = [t for t in todo if t in trees]
    chunks = [interpretable[i:i + 8] for i in range(0, len(interpretable), 8)]
    if chunks:
        global _TREES
        _TREES = trees
        # fork lets children inherit _TREES copy-on-write; no re-pickling
        with _pool_context().Pool(jobs, initializer=_init_worker_cached,
                                  initargs=(types, names)) as pool:
            for i, result in enumerate(pool.imap_unordered(_work_cached, chunks), 1):
                for text, ok, output, sig in result:
                    if not ok:
                        failures.append(text)
                        continue
                    out_sha1, shape_sha1 = out_hashes(output)
                    parsed[text] = {
                        "out_sha1": out_sha1,
                        "shape_sha1": shape_sha1,
                        "cluster": sig,
                        "output": output,
                    }
                if i % 100 == 0:
                    print("  ...%d/%d interpret batches" % (i, len(chunks)),
                          file=sys.stderr, flush=True)
        _TREES = None

    sentences = {}
    outputs = {}
    digest = hashlib.sha256()
    for text in sorted(parsed):
        rec = parsed[text]
        sentences[text] = {"out_sha1": rec["out_sha1"],
                           "shape_sha1": rec["shape_sha1"],
                           "cluster": rec["cluster"]}
        outputs[text] = rec["output"]
        digest.update(text.encode())
        digest.update(b"\0")
        digest.update(rec["out_sha1"].encode())
        digest.update(b"\0")
        digest.update(rec["shape_sha1"].encode())
        digest.update(b"\0")
        digest.update(rec["cluster"].encode())
        digest.update(b"\n")

    meta = {"corpus": corpus,
            "created_from_commit": commit,
            "count": len(sentences),
            "digest": digest.hexdigest(),
            "occurrences": {t: occurrences.get(t, 0) for t in sorted(parsed)}}
    meta.update(sources_start)
    blob = {"meta": meta, "sentences": sentences, "outputs": outputs}
    if args.unparsed:
        blob["unparsed"] = sorted(set(failures))

    sources_end = source_hashes()
    stale = sources_start != sources_end
    if stale:
        meta["stale"] = True
        meta["sources_at_start"] = sources_start
        meta["sources_at_end"] = sources_end

    out = args.out or os.path.join(CACHE, "snapshots",
                                   "%s_%s_%s.json" % (corpus, meta["grammar_sha1"],
                                                      meta["interp_sha1"]))
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(blob, fh, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=False)
    os.replace(tmp, out)
    print(json.dumps({
        "out": out,
        "corpus": corpus,
        "sentences": len(sentences),
        "unparsed": len(set(failures)),
        "bytes": os.path.getsize(out),
        "digest": meta["digest"],
        "stale": stale,
        "wall_s": round(time.time() - t0, 1),
    }, indent=1))
    if stale:
        changed = sorted(k for k in sources_start if sources_start[k] != sources_end[k])
        print("ERROR: sources changed during build; re-run "
              "(snapshot marked stale): %s" % ", ".join(changed), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------- diff
CLASSES = ("cluster", "shape", "output", "added", "removed", "unchanged")


def classify(a, b):
    """Return {class: [ {sentence, before, after} ... ]} + summary counts."""
    sa, sb = a.get("sentences", {}), b.get("sentences", {})
    out = {c: [] for c in CLASSES}
    for text in sorted(set(sa) | set(sb)):
        if text not in sa:
            out["added"].append({"sentence": text, "before": None,
                                 "after": _brief(sb[text])})
            continue
        if text not in sb:
            out["removed"].append({"sentence": text,
                                   "before": _brief(sa[text]), "after": None})
            continue
        x, y = sa[text], sb[text]
        if x.get("cluster") != y.get("cluster"):
            out["cluster"].append({"sentence": text,
                                   "before": x.get("cluster"), "after": y.get("cluster")})
        elif x.get("shape_sha1") != y.get("shape_sha1"):
            out["shape"].append({"sentence": text,
                                 "before": x.get("shape_sha1"), "after": y.get("shape_sha1")})
        elif x.get("out_sha1") != y.get("out_sha1"):
            out["output"].append({"sentence": text,
                                  "before": x.get("out_sha1"), "after": y.get("out_sha1")})
        else:
            out["unchanged"].append({"sentence": text, "before": None, "after": None})
    return out


def _brief(rec):
    return {k: rec.get(k) for k in ("cluster", "shape_sha1", "out_sha1")}


def diff(args):
    with open(args.a) as fh:
        a = json.load(fh)
    with open(args.b) as fh:
        b = json.load(fh)
    classes = classify(a, b)
    counts = {c: len(classes[c]) for c in CLASSES}
    changed = sum(counts[c] for c in CLASSES if c != "unchanged")
    if args.json:
        print(json.dumps({"a": args.a, "b": args.b,
                          "counts": counts, "changed": changed,
                          "details": {c: classes[c] for c in CLASSES}},
                         indent=1))
    else:
        print("counts: " + "  ".join("%s=%d" % (c, counts[c]) for c in CLASSES))
        print("changed sentences: %d" % changed)
        limit = args.limit if args.limit is not None else 20
        for c in ("cluster", "shape", "output", "added", "removed"):
            rows = classes[c]
            if not rows:
                continue
            print("\n== %s (%d) ==" % (c, len(rows)))
            shown = rows if limit == 0 else rows[:limit]
            for row in shown:
                print("  " + row["sentence"])
                if c in ("cluster", "shape", "output"):
                    print("      %s -> %s" % (row["before"], row["after"]))
                elif c == "added":
                    print("      + %s" % (row["after"],))
                else:
                    print("      - %s" % (row["before"],))
            if limit and len(rows) > len(shown):
                print("  ... %d more" % (len(rows) - len(shown)))
    return 1 if changed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Deterministic parse+interpret output snapshots.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build a snapshot")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--data", help="corpus (Standard.json, classic.json, FDN.json)")
    g.add_argument("--sentences", help="text file, one sentence per line (testing)")
    b.add_argument("--out", default=None,
                   help="output path (default .cache/snapshots/<corpus>_<gh>_<ih>.json)")
    b.add_argument("--jobs", type=int, default=0, help="workers (default cpu-2)")
    b.add_argument("--limit", type=int, default=0, help="cap unique texts (testing)")
    b.add_argument("--timeout", type=float, default=0, help="per-sentence cap (0=off)")
    b.add_argument("--unparsed", action="store_true",
                   help="record texts known/observed to fail parsing")

    d = sub.add_parser("diff", help="classify changes between two snapshots")
    d.add_argument("a")
    d.add_argument("b")
    d.add_argument("--json", action="store_true", help="machine-readable output")
    d.add_argument("--limit", type=int, default=None,
                   help="examples printed per class (0 = all, default 20)")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        return build(args)
    return diff(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:          # e.g. `snapshot.py diff ... | head`
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(1)
