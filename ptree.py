"""One parse per text: mention spans **and** structure, from a single tree.

Why this module exists
----------------------
`pmentions` and `pstruct` used to parse the same sentences twice with different
`Lark` flags:

    pmentions: keep_all_tokens=False, propagate_positions=True   -> spans only
    pstruct:   keep_all_tokens=True,  propagate_positions=True   -> structure only

Verified equivalent: the two configurations produce **byte-identical spans** for
mention nodes (checked on Fiery Annihilation), and `keep_all_tokens=True` has the
bonus that a bare pronoun keeps its span instead of collapsing to an empty
`card_target`. So one parse serves both, and the `keep_all_tokens` trap described
in PIPELINE.md disappears from the deterministic path.

One tree, one cache entry per card text, records of:

    {"start", "end", "node", "role", "verb", "predicate", "in_condition"}

`node` is the grammar node (`card_target` / `player` / `token`); `role` is
`subject` / `object` derived from the ordered children of the nearest
`*_action` ancestor (everything before the verb token is the subject side);
`predicate` marks a copula complement (`it's an artifact`); `in_condition` marks
material inside `any_text`.

Migration
---------
The new cache is `ptree_<grammarhash>.json`. While it is being rebuilt (that is
an hour of Earley), `mentions()` **reads through** the legacy
`pmentions_<grammarhash>.json` so nothing regresses. `structure()` never falls
back and never parses: callers get `None`/`[]` and simply run without structural
rules. That keeps evaluation deterministic and fast until the rebuild lands.

    python ptree.py --build --data FDN.json             # fill from a data file
    python ptree.py --build --sample coref_standard.json  # fill from a dataset

Torch-free.
"""
import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from preprocess import segment
from mentions import _regex_mentions

MENTION_NODES = ("card_target", "player", "token")
COND_NODES = ("any_text",)
ACTION_RE = re.compile(r"^(.+)_action$")
COPULA = {"is", "are", "be", "isn't", "aren't", "becomes", "become"}

_P = None
_CACHE = None
_DIRTY = False
_LEGACY = None
_SENT = None
_SENT_DIRTY = False
TIMEOUT = 0           # per-sentence wall-clock cap; 0 = off. Measured: a
                      # 60s cap saves ~28% build time but costs 3 points of
                      # benchmark accuracy (parses legitimately need 20-60s)


def default_workers():
    """Physical cores, not logical: measured on this Xeon, 14 workers beat 27 by 12%
    in wall time (7.5 vs 8.5 min for the same 60 sentences; efficiency 55% vs 39%)
    because hyperthreads contend for cache/memory on a parse this memory-heavy."""
    logical = os.cpu_count() or 4
    try:
        physical = len(os.sched_getaffinity(0)) // 2 or 1
    except Exception:
        physical = logical // 2 or 1
    return max(1, min(logical // 2, physical))


def _grammar_hash():
    with open(os.path.join(BASE, "grammar.lark"), "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:10]


def _parser():
    global _P
    if _P is None:
        from lark import Lark
        _P = Lark.open(os.path.join(BASE, "grammar.lark"), parser="earley",
                       start="start", ambiguity="resolve",
                       keep_all_tokens=True, propagate_positions=True)
    return _P


def cache_path():
    return os.path.join(BASE, ".cache", f"ptree_{_grammar_hash()}.json")


def sent_cache_path():
    """Sentence-level cache: the unit of parsing is a sentence, not a card text.

    Two wins: (a) the same sentence recurs across cards (FDN: 703 unique from
    ~1,650 occurrences), so it is parsed once; (b) a card only needs re-assembly,
    which is milliseconds.
    """
    return os.path.join(BASE, ".cache", f"psent_{_grammar_hash()}.json")


def legacy_path():
    return os.path.join(BASE, ".cache", f"pmentions_{_grammar_hash()}.json")


def _load_cache():
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.load(open(cache_path()))
        except Exception:
            _CACHE = {}
    return _CACHE


def _load_legacy():
    global _LEGACY
    if _LEGACY is None:
        try:
            _LEGACY = json.load(open(legacy_path()))
        except Exception:
            _LEGACY = {}
    return _LEGACY


def _load_sent():
    global _SENT
    if _SENT is None:
        try:
            _SENT = json.load(open(sent_cache_path()))
        except Exception:
            _SENT = {}
    return _SENT


def save_cache():
    global _DIRTY
    if _CACHE is None or not _DIRTY:
        return
    os.makedirs(os.path.join(BASE, ".cache"), exist_ok=True)
    tmp = cache_path() + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(_CACHE, fh)
    os.replace(tmp, cache_path())
    _DIRTY = False
    global _SENT_DIRTY
    if _SENT is not None and _SENT_DIRTY:
        tmp = sent_cache_path() + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(_SENT, fh)
        os.replace(tmp, sent_cache_path())
        _SENT_DIRTY = False


def key(text):
    return hashlib.sha1(text.encode()).hexdigest()[:16]


# --------------------------------------------------------------------- extract
def _walk(tree):
    from lark import Tree
    stack = [(tree, None)]
    while stack:
        n, parent = stack.pop()
        yield n, parent
        for ch in n.children:
            if isinstance(ch, Tree):
                stack.append((ch, n))


def _verb_index(action):
    """(index, token) of the verb among an action's ordered children."""
    from lark import Token
    for i, ch in enumerate(action.children):
        if isinstance(ch, Token) and ch.value[:1].isalpha():
            return i, ch.value.lower()
    return None, None


class _ParseTimeout(Exception):
    pass


def _alarm(sig, frm):
    raise _ParseTimeout()


def _parse_with_timeout(sentence):
    """Parse one sentence, honouring the per-sentence cap.

    Returns (tree_or_None, timed_out). A timed-out parse may leave the Lark
    parser in an inconsistent state, so the parser is dropped and rebuilt on the
    next call (a grammar compile costs ~1s, far less than the runaway parse).
    """
    global _P
    if not TIMEOUT:
        try:
            return _parser().parse(sentence), False
        except Exception:
            return None, False
    import signal
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    try:
        return _parser().parse(sentence), False
    except _ParseTimeout:
        _P = None
        return None, True
    except Exception:
        return None, False
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _extract_segment(sentence, base):
    """-> (records, status) where status is 'ok' | 'fail' | 'timeout'."""
    from lark import Tree
    tree, timed_out = _parse_with_timeout(sentence)
    if timed_out:
        return [], "timeout"

    if tree is None:
        # regex fallback for a segment the grammar cannot handle
        return [{"start": base + m["start"], "end": base + m["end"],
                 "node": None, "role": None, "verb": None,
                 "predicate": False, "in_condition": False}
                for m in _regex_mentions(sentence)], "fail"

    parent = {}
    for n, p in _walk(tree):
        parent[id(n)] = p

    out = []
    for n, _ in _walk(tree):
        if n.data not in MENTION_NODES:
            continue
        meta = getattr(n, "meta", None)
        if meta is None or not hasattr(meta, "start_pos"):
            continue
        verb = role = None
        in_cond = predicate = False
        cur, child = parent.get(id(n)), n
        while cur is not None:
            name = cur.data
            m = ACTION_RE.match(name)
            if m:
                if verb is None:
                    verb = m.group(1)
                vi, vtok = _verb_index(cur)
                if vi is not None and child in cur.children:
                    idx = cur.children.index(child)
                    role = "subject" if idx < vi else "object"
                    if role == "object" and vtok in COPULA:
                        predicate = True
            if name in COND_NODES:
                in_cond = True
            child, cur = cur, parent.get(id(cur))
        out.append({"start": base + meta.start_pos,
                    "end": base + meta.end_pos,
                    "node": str(n.data), "role": role, "verb": verb,
                    "predicate": predicate, "in_condition": in_cond})
    if out:
        return out, "ok"
    # A parse can SUCCEED while yielding no mention node (e.g. "If you do, that
    # creature gains first strike..." parses as predicate material). The legacy
    # extractor fell back to regex in that case and the merged module must too,
    # otherwise such mentions vanish from the inventory.
    return [{"start": base + m["start"], "end": base + m["end"],
             "node": None, "role": None, "verb": None,
             "predicate": False, "in_condition": False}
            for m in _regex_mentions(sentence)], "fail"


def _sentence_records(sentence):
    """Records for one sentence, offsets relative to the sentence start.

    Cached — including failures and timeouts, which are the expensive ones.
    """
    global _SENT_DIRTY
    cache = _load_sent()
    k = key(sentence)
    ent = cache.get(k)
    if ent is None:
        recs, status = _extract_segment(sentence, 0)
        ent = {"status": status, "cap": TIMEOUT, "recs": recs}
        cache[k] = ent
        _SENT_DIRTY = True
    return ent["recs"]


def _compute(text):
    out, cursor = [], 0
    for it in segment(text):
        s = it["text"]
        if not s:
            continue
        pos = text.find(s, cursor)
        if pos < 0:
            pos = cursor
        cursor = pos + len(s)
        for r in _sentence_records(s):
            rec = dict(r)
            rec["start"] = r["start"] + pos
            rec["end"] = r["end"] + pos
            out.append(rec)
    return out


# ------------------------------------------------------------------ public API
def nodes(text):
    """Full records for `text`; parses and caches on a miss."""
    global _DIRTY
    cache = _load_cache()
    k = key(text)
    if k in cache:
        return cache[k]
    out = _compute(text)
    cache[k] = out
    _DIRTY = True
    return out


def peek(text):
    """Cached records, or None. Never parses (safe for evaluation paths)."""
    return _load_cache().get(key(text))


def has_structure(text):
    return key(text) in _load_cache()


def _surface(text, rec):
    raw = text[rec["start"]:rec["end"]]
    lead = len(raw) - len(raw.lstrip())
    surf = raw.strip()
    if not surf:
        return None
    return {"surface": surf, "start": rec["start"] + lead,
            "end": rec["start"] + lead + len(surf)}


def mentions(text):
    """Mention spans: new cache, else the legacy span cache, else parse now."""
    recs = peek(text)
    if recs is None:
        legacy = _load_legacy().get(key(text))
        if legacy is not None:
            return [dict(m) for m in legacy]
        recs = nodes(text)
    out = []
    for r in recs:
        m = _surface(text, r)
        if m:
            out.append(m)
    return out


def structure(text):
    """Structure records, read from the cache only (no parse, no legacy)."""
    return peek(text) or []


def lookup(recs, start, end=None):
    """Tightest record containing `start`."""
    best = None
    for r in recs:
        if r["start"] <= start and (end is None or start < r["end"]):
            if best is None or (r["end"] - r["start"]) < (best["end"] - best["start"]):
                best = r
    return best


FIELDS = ("start", "end", "node", "role", "verb", "predicate", "in_condition")


def _init_worker(timeout):
    global TIMEOUT
    TIMEOUT = timeout


def _same_records(a, b):
    """True if two record lists are identical field for field."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        for f in FIELDS:
            if x.get(f) != y.get(f):
                return False
    return True


def seed_from(seed_path, texts, workers=None, sample=40, quiet=False):
    """Reuse an older ptree cache for texts whose parse is provably unchanged.

    An additive grammar edit usually leaves every previously-parsed text with the
    same tree, but `ambiguity='resolve'` may legitimately pick a different
    derivation, so structure cannot be trusted wholesale. We parse a random
    sample of the seedable texts and compare records field for field; only if
    they are *identical* do we copy the seed's records for the rest.

    Returns the number of texts seeded (0 means "not safe, parse everything").
    """
    import random
    try:
        seed = json.load(open(seed_path))
    except Exception:
        return 0
    cache = _load_cache()
    seedable = [t for t in texts if key(t) in seed and key(t) not in cache]
    if not seedable:
        return 0
    pick = random.Random(1234).sample(seedable, min(sample, len(seedable)))
    if not quiet:
        print(f"[seed] {len(seedable)} seedable texts; verifying structure on {len(pick)}")
    import multiprocessing as mp
    workers = workers or default_workers()
    with mp.Pool(workers, initializer=_init_worker, initargs=(TIMEOUT,)) as pool:
        got = pool.map(_compute, pick, chunksize=1)
    bad = [t for t, recs in zip(pick, got) if not _same_records(seed[key(t)], recs)]
    if bad:
        print(f"[seed] structure changed on {len(bad)}/{len(pick)} sampled texts "
              f"-> refusing to seed, full parse required")
        for t in bad[:3]:
            print(f"        {t[:90]}")
        return 0
    for t in seedable:
        cache[key(t)] = seed[key(t)]
    global _DIRTY
    _DIRTY = True
    save_cache()
    if not quiet:
        print(f"[seed] verified identical structure on the sample; seeded {len(seedable)} texts")
    return len(seedable)


def _parse_sentence(sentence):
    """Worker: parse one sentence -> (sentence, entry) with relative offsets."""
    recs, status = _extract_segment(sentence, 0)
    return sentence, {"status": status, "cap": TIMEOUT, "recs": recs}


def precompute(texts, workers=None, quiet=False, timeout=None):
    """Build the cache for `texts`.

    The unit of work is the SENTENCE, not the card text: the same sentence recurs
    across cards (FDN 1.08x, dev corpus 1.24x) and, more importantly, a sentence
    cache survives text-set changes, so adding cards later only parses the
    sentences that are genuinely new.

    Assembly (segmentation + offset stitching) then happens in the parent and
    costs milliseconds per card.
    """
    import multiprocessing as mp
    if timeout is not None:
        globals()["TIMEOUT"] = timeout
    texts = sorted({t.strip() for t in texts if t and t.strip()} - {""})
    cache = _load_cache()
    todo_texts = [t for t in texts if key(t) not in cache]
    if not todo_texts:
        return 0

    sent = _load_sent()
    uniq, seen = [], set()
    for t in todo_texts:
        for it in segment(t):
            s = it["text"]
            if s and s not in seen:
                seen.add(s)
                uniq.append(s)
    # A time-outed sentence is not a failure: with a larger cap (or no cap) it may
    # parse. Retry it then, otherwise the cap would silently degrade the cache.
    def _needs_work(s):
        e = sent.get(key(s))
        if e is None:
            return True
        return e.get("status") == "timeout" and (not TIMEOUT or TIMEOUT > e.get("cap", 0))

    todo = [s for s in uniq if _needs_work(s)]
    workers = workers or default_workers()
    if not quiet:
        print(f"[ptree] {len(todo_texts)} texts, {len(uniq)} sentences, "
              f"{len(uniq)-len(todo)} cached, {len(todo)} to parse "
              f"(timeout={TIMEOUT}s, workers={workers})", flush=True)

    global _SENT_DIRTY
    done = 0
    if todo:
        with mp.Pool(workers, initializer=_init_worker, initargs=(TIMEOUT,)) as pool:
            for sentence, entry in pool.imap(_parse_sentence, todo, chunksize=1):
                sent[key(sentence)] = entry
                done += 1
                _SENT_DIRTY = True
                if not quiet and done % 50 == 0:
                    print(f"  ...parsed {done}/{len(todo)} sentences", flush=True)
        save_cache()

    # assemble texts from the sentence cache (parent, cheap)
    for t in todo_texts:
        cache[key(t)] = _compute(t)
    _DIRTY_GLOBAL()
    save_cache()
    return len(todo_texts)


def _DIRTY_GLOBAL():
    global _DIRTY
    _DIRTY = True


def card_texts(data="FDN.json", dataset=None, limit=0):
    """Texts to build for: a dataset's cards, or a card-data file."""
    if dataset:
        with open(dataset) as fh:
            texts = sorted({c["text"] for c in json.load(fh)})
    else:
        from preprocess import normalize_names, strip_reminders
        from setdata import load
        items, _, names, _ = load(data)
        from setdata import normalize_text
        texts = sorted({normalize_text(t, names) for _, t, _ in items if t} - {""})
    if limit and limit < len(texts):
        stride = max(1, len(texts) // limit)
        texts = texts[::stride][:limit]
    return texts


def verify(limit=0):
    """Compare the new cache against the legacy span cache; report drift.

    Spans from the regex fallback are included: the legacy cache never recorded
    whether a span came from the grammar or the fallback, so comparing only
    parsed spans produces false drift (measured: 1,455 "drifting" texts that
    were byte-identical).

    Returns the number of drifting texts (0 = clean) so it can gate a migration.
    """
    new, old = _load_cache(), _load_legacy()
    shared = [k for k in new if k in old]
    if limit:
        shared = shared[:limit]
    if not shared:
        print("no overlapping texts yet — rebuild the cache first "
              "(python ptree.py --build ...)")
        return 0
    drift, checked = [], 0
    for k in shared:
        all_new = sorted((r["start"], r["end"]) for r in new[k])
        legacy = sorted((m["start"], m["end"]) for m in old[k])
        checked += 1
        if all_new != legacy:
            drift.append((k, len(legacy), len(all_new)))
    n = len(new)
    parsed_texts = sum(1 for v in new.values() if any(r["node"] for r in v))
    empty_texts = sum(1 for v in new.values() if not any(r["node"] for r in v))
    print(f"new cache: {n} texts   compared: {checked}   drifting: {len(drift)}")
    print(f"  texts with at least one parsed mention: {parsed_texts} "
          f"({100*parsed_texts/n:.1f}%)")
    print(f"  texts parsed nowhere (regex fallback only): {empty_texts} "
          f"({100*empty_texts/n:.1f}%)")
    if drift:
        for k, a, b in drift[:10]:
            print(f"  DRIFT {k}: legacy {a} spans -> new {b}")
    tot = sum(len(v) for v in new.values()) or 1
    role = sum(1 for v in new.values() for r in v if r.get("role"))
    verb = sum(1 for v in new.values() for r in v if r.get("verb"))
    pred = sum(1 for v in new.values() for r in v if r.get("predicate"))
    cond = sum(1 for v in new.values() for r in v if r.get("in_condition"))
    fallback = sum(1 for v in new.values() for r in v if not r.get("node"))
    print(f"\nstructural coverage over {tot} mention records "
          f"({100*fallback/tot:.1f}% from the regex fallback):")
    for name, c in (("role (subject/object)", role), ("governing verb", verb),
                    ("copula complement", pred), ("inside a condition", cond)):
        print(f"  {name:<22} {100*c/tot:5.1f}%  ({c})")
    return len(drift)


def stale_texts(sources=None, limit=0):
    """Texts whose cached spans disagree with the legacy span cache.

    `sources` is a list of (data_file, dataset_file) pairs used to recover the
    text for a cache key; the cache itself stores only records.
    """
    new, old = _load_cache(), _load_legacy()
    texts = {}
    for data, dataset in (sources or []):
        for t in card_texts(data or "FDN.json", dataset=dataset):
            texts[key(t)] = t
    out = []
    for k, recs in new.items():
        if k not in old or k not in texts:
            continue
        if sorted((r["start"], r["end"]) for r in recs) != \
           sorted((m["start"], m["end"]) for m in old[k]):
            out.append(texts[k])
    return out[:limit] if limit else out


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="*")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--data", default="FDN.json")
    ap.add_argument("--sample", default=None, help="dataset json to take texts from")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=0,
                    help="per-sentence parse cap in seconds (0 = no cap). A cap "
                         "saves build time but drops parses that need longer")
    ap.add_argument("--status", action="store_true", help="cache coverage report")
    ap.add_argument("--force", action="store_true",
                    help="drop the text cache for these texts and re-assemble them "
                         "(needed to retry sentences that previously timed out)")
    ap.add_argument("--seed", default=None,
                    help="older ptree_<hash>.json to seed from (verified by sampling)")
    ap.add_argument("--verify", action="store_true",
                    help="compare the new cache against the legacy span cache")
    ap.add_argument("--rebuild-stale", action="store_true",
                    help="re-parse only the texts whose spans drift from legacy")
    args = ap.parse_args()

    if args.rebuild_stale:
        sources = [("FDN.json", None), (None, "coref_standard.json"),
                   (None, "coref_dataset.json")]
        texts = stale_texts(sources, args.limit)
        print(f"stale texts: {len(texts)}")
        cache = _load_cache()
        for t in texts:
            cache.pop(key(t), None)
        global _DIRTY
        _DIRTY = True
        save_cache()
        n = precompute(texts, workers=args.workers or None)
        print(f"re-parsed {n} of {len(texts)} -> {cache_path()}")
        return

    if args.verify:
        bad = verify(args.limit)
        raise SystemExit(1 if bad else 0)

    if args.status:
        print(f"ptree cache:   {len(_load_cache())} texts  ({cache_path()})")
        print(f"legacy cache:  {len(_load_legacy())} texts  ({legacy_path()})")
        return

    if args.build:
        texts = card_texts(args.data, args.sample, args.limit)
        if args.force:
            globals()["TIMEOUT"] = args.timeout
            c = _load_cache()
            n = 0
            for t in texts:
                if c.pop(key(t), None) is not None:
                    n += 1
            if n:
                globals()["_DIRTY"] = True
                save_cache()
            print(f"[force] dropped {n} cached texts")
        if args.seed:
            seed_from(args.seed, texts, workers=args.workers or None)
        n = precompute(texts, workers=args.workers or None, timeout=args.timeout)
        print(f"parsed {n} new / {len(texts)} texts -> {cache_path()}")
        return

    if not args.card:
        ap.print_help()
        return
    from setdata import card_text
    for name in args.card:
        text = card_text(name)
        if not text:
            print(f"card not found: {name}")
            continue
        print(text)
        for r in nodes(text):
            m = _surface(text, r) or {"surface": "", "start": r["start"], "end": r["end"]}
            print(f"  {m['start']:3}-{m['end']:3} {str(r['node']):<12} "
                  f"{m['surface']!r:<34} verb={str(r['verb']):<14} "
                  f"role={str(r['role']):<8} pred={r['predicate']} cond={r['in_condition']}")


if __name__ == "__main__":
    main()
