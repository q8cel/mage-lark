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


def _extract_segment(sentence, base):
    from lark import Tree
    try:
        tree = _parser().parse(sentence)
    except Exception:
        tree = None

    if tree is None:
        # regex fallback for a segment the grammar cannot handle
        return [{"start": base + m["start"], "end": base + m["end"],
                 "node": None, "role": None, "verb": None,
                 "predicate": False, "in_condition": False}
                for m in _regex_mentions(sentence)]

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
        return out
    # A parse can SUCCEED while yielding no mention node (e.g. "If you do, that
    # creature gains first strike..." parses as predicate material). The legacy
    # extractor fell back to regex in that case and the merged module must too,
    # otherwise such mentions vanish from the inventory.
    return [{"start": base + m["start"], "end": base + m["end"],
             "node": None, "role": None, "verb": None,
             "predicate": False, "in_condition": False}
            for m in _regex_mentions(sentence)]


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
        out.extend(_extract_segment(s, pos))
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


def precompute(texts, workers=None, quiet=False):
    """Fill the cache for `texts` in parallel. Eager: no progress until chunks land."""
    import multiprocessing as mp
    cache = _load_cache()
    todo = sorted({t.strip() for t in texts if t and t.strip()} - {""})
    todo = [t for t in todo if key(t) not in cache]
    if not todo:
        return 0
    workers = workers or max(1, (os.cpu_count() or 4) - 1)
    done = 0
    with mp.Pool(workers) as pool:
        for text, recs in zip(todo, pool.imap(_compute, todo, chunksize=1)):
            cache[key(text)] = recs
            done += 1
            if not quiet and done % 25 == 0:
                print(f"  ...parsed {done}/{len(todo)}", flush=True)
    global _DIRTY
    _DIRTY = True
    save_cache()
    return done


def card_texts(data="FDN.json", dataset=None, limit=0):
    """Texts to build for: a dataset's cards, or a card-data file."""
    if dataset:
        with open(dataset) as fh:
            texts = sorted({c["text"] for c in json.load(fh)})
    else:
        from preprocess import normalize_names, strip_reminders
        from setdata import load
        items, _, names, _ = load(data)
        texts = sorted({(" ".join(normalize_names(strip_reminders(t), names).split())).strip()
                        for _, t, _ in items if t} - {""})
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
    ap.add_argument("--status", action="store_true", help="cache coverage report")
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
        n = precompute(texts, workers=args.workers or None)
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
