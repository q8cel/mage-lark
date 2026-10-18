#!/usr/bin/env python3
"""Measure what resolution does to the compiler's output (the --resolve seam).

For each card we interpret the text twice:

    original  text  -> segment -> Lark -> Interpreter -> dicts
    rewritten text  -> segment -> Lark -> Interpreter -> dicts

where the rewritten text is `rulecoref`'s output with the resolved anaphors
replaced by their antecedent surface. The interesting quantities are how many
anaphora markers survive in the semantic output and how many parses/values are
lost, before vs after.

This is the measurement behind the opt-in `--resolve` mode; it is also usable as
the pipeline entry point:

    python resolve_pipeline.py --data FDN.json --limit 60
    python resolve_pipeline.py --data FDN.json --limit 60 --example "Fiery Annihilation"

Torch-free.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import refs
import rulecoref
from anaphora import find_anaphors
from preprocess import segment

_P = {}
_T = {}


_INIT = {}


def _init(_unused=None):
    from lark import Lark
    from interpret import Interpreter
    _P["lark"] = Lark.open(_INIT["grammar"], parser="earley", start="start",
                           ambiguity="resolve", keep_all_tokens=True)
    _T["interp"] = Interpreter(types=_INIT["types"], names=_INIT["names"])


def _walk(obj):
    """Yield every dict/list node in the interpreted output."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk(v)


def _count(obj):
    refs_n = nulls = 0
    for node in _walk(obj):
        if isinstance(node, dict) and node.get("ref") == "anaphora":
            refs_n += 1
        for v in (node.values() if isinstance(node, dict) else ()):
            if v is None:
                nulls += 1
    return refs_n, nulls


def _interpret(text):
    out = []
    for it in segment(text):
        s = it["text"]
        if not s or it["modal"]:
            continue
        try:
            tree = _P["lark"].parse(s)
        except Exception:
            out.append({"type": "unparsed", "text": s})
            continue
        got = _T["interp"].interp(tree)
        for item in got:                     # interp() can return nested lists
            if isinstance(item, (list, tuple)):
                out.extend(item)
            else:
                out.append(item)
    return out


def _work(card):
    name, text = card
    try:
        return _work_inner(name, text)
    except Exception as exc:               # one bad card must not kill the run
        return {"card": name, "error": f"{type(exc).__name__}: {exc}",
                "anaphors": 0, "status": {}, "refs_before": 0, "refs_after": 0,
                "nulls_before": 0, "nulls_after": 0, "unparsed_before": 0,
                "unparsed_after": 0, "changed": False, "rewritten": "",
                "resolutions": [], "rw_applied": 0, "rw_reverted": 0,
                "skip_slot": 0, "skip_number": 0, "skip_possessive": 0,
                "skip_set": 0}


def _parse_ok(sentence):
    """True if the sentence still parses — after the same preprocessing the
    pipeline applies (segment() strips trailing punctuation and split bullets;
    parsing the raw sentence would fail on its final period alone)."""
    segs = [it["text"] for it in segment(sentence) if it["text"]]
    if not segs:
        return True
    for s in segs:
        try:
            _P["lark"].parse(s)
        except Exception:
            return False
    return True


def _work_inner(name, text):
    res = rulecoref.resolve(text, refs.build(text), find_anaphors(text),
                            parse_ok=_parse_ok)
    before = _interpret(text)
    after = _interpret(res["rewritten_text"])
    rb, nb = _count(before)
    ra, na = _count(after)
    stat = Counter()
    for a in res["anaphors"]:
        stat[a["status"]] += 1
    rs = res.get("rewrite_stats") or {}
    return {
        "card": name,
        "rw_applied": rs.get("applied", 0), "rw_reverted": rs.get("reverted", 0),
        "skip_slot": rs.get("skip_slot", 0), "skip_number": rs.get("skip_number", 0),
        "skip_possessive": rs.get("skip_possessive", 0), "skip_set": rs.get("skip_set", 0),
        "anaphors": len(res["anaphors"]),
        "status": dict(stat),
        "refs_before": rb, "refs_after": ra,
        "nulls_before": nb, "nulls_after": na,
        "unparsed_before": sum(1 for d in before
                               if isinstance(d, dict) and d.get("type") == "unparsed"),
        "unparsed_after": sum(1 for d in after
                              if isinstance(d, dict) and d.get("type") == "unparsed"),
        "changed": res["rewritten_text"] != text,
        "rewritten": res["rewritten_text"],
        "resolutions": [(a["surface"], a["canonical"], a["status"]) for a in res["anaphors"]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="FDN.json")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--example", default=None, help="print full detail for this card")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    from setdata import load
    items, types, names, _ = load(args.data)
    from preprocess import normalize_names, strip_reminders
    cards = []
    seen = set()
    for name, raw, _code in items:
        if not raw:
            continue
        t = " ".join(normalize_names(strip_reminders(raw), names).split())
        if t in seen or not find_anaphors(t):
            continue
        seen.add(t)
        cards.append((name, t))
    if args.example:
        cards = [c for c in cards if c[0].lower() == args.example.lower()]
    else:
        total = len(cards)
        cards = cards[:args.limit]
        print(f"cards with anaphora: {total}, measuring {len(cards)}")

    workers = max(1, (args.workers or (os.cpu_count() or 4)) - 2)
    _INIT["grammar"] = os.path.join(BASE, "grammar.lark")
    _INIT["types"], _INIT["names"] = types, names
    with mp.Pool(workers, initializer=_init) as pool:
        rows = pool.map(_work, cards)

    if args.json_out:
        json.dump(rows, open(args.json_out, "w"), indent=1)

    tot = Counter()
    for r in rows:
        for k in ("anaphors", "refs_before", "refs_after", "nulls_before",
                  "nulls_after", "unparsed_before", "unparsed_after"):
            tot[k] += r[k]
        tot["changed"] += r["changed"]
        for k in ("rw_applied", "rw_reverted", "skip_slot", "skip_number",
                  "skip_possessive", "skip_set"):
            tot[k] += r.get(k, 0)
        for k, v in r["status"].items():
            tot[f"status_{k}"] += v

    errs = [r for r in rows if r.get("error")]
    print(f"\ncards measured: {len(rows)}   rewritten: {tot['changed']}   "
          f"errors: {len(errs)}")
    for r in errs[:5]:
        print(f"  ERROR {r['card']}: {r['error']}")
    print(f"anaphor occurrences: {tot['anaphors']}")
    for k in ("resolved", "ambiguous", "no-resolution"):
        v = tot[f"status_{k}"]
        print(f"  status {k:<14} {v:>4}  ({100*v/max(1,tot['anaphors']):4.1f}%)")
    print(f"\n{'':26}{'before':>8}{'after':>8}")
    print(f"{'anaphora markers in output':<26}{tot['refs_before']:>8}{tot['refs_after']:>8}")
    print(f"{'null values (dropped)':<26}{tot['nulls_before']:>8}{tot['nulls_after']:>8}")
    print(f"{'unparsed sentences':<26}{tot['unparsed_before']:>8}{tot['unparsed_after']:>8}")
    print(f"\nrewrite decisions:")
    print(f"  applied (kept)        {tot['rw_applied']:>5}")
    print(f"  reverted (broke parse){tot['rw_reverted']:>5}")
    print(f"  skipped, non-nominal  {tot['skip_slot']:>5}")
    print(f"  skipped, possessive   {tot['skip_possessive']:>5}")
    print(f"  skipped, number       {tot['skip_number']:>5}")
    print(f"  skipped, set anaphora {tot['skip_set']:>5}")

    if args.example and rows:
        r = rows[0]
        print(f"\n=== {r['card']}")
        for s, ant, st in r["resolutions"]:
            print(f"  {s!r:<18} -> {ant!r:<34} [{st}]")
        print(f"\nrewritten:\n  {r['rewritten']}")


if __name__ == "__main__":
    main()
