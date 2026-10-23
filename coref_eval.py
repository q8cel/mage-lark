#!/usr/bin/env python3
"""Unified, entity-aware coreference evaluation.

Both the deterministic resolver and the attention baseline are scored against
the same fixed candidate pool, the same anaphor occurrences, and the same gold
labels.  This replaces the separate `rulecoref --eval` / `--bench` scoring loops
and `resolve.eval_benchmark`, which built slightly different pools and reported
different metrics.

Metrics per labelled anaphor:

    exact  predicted candidate index == gold candidate index
    entity predicted candidate shares a gold cluster with the gold candidate

A gold cluster is the union-find closure of all gold antecedent labels.  Entity
accuracy is the primary number; exact is kept because span choice still matters
for rewriting.

Usage:
    python coref_eval.py --dataset coref_standard.json
    python coref_eval.py --bench --mentions parser
    python coref_eval.py --dataset coref_standard.json --resolver attention --model ...
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from anaphora import find_anaphors


# --------------------------------------------------------------------- helpers
def _exact_index(pool, span):
    for i, cand in enumerate(pool):
        if (cand["start"], cand["end"]) == span:
            return i
    return None


def _overlap_index(pool, span):
    """Exact span, else the pool mention with the largest positive overlap."""
    idx = _exact_index(pool, span)
    if idx is not None:
        return idx
    best, best_ov = None, 0
    for i, cand in enumerate(pool):
        ov = min(span[1], cand["end"]) - max(span[0], cand["start"])
        if ov > best_ov:
            best, best_ov = i, ov
    return best


def _find_gold_index(pool, gold, aspan):
    """Map a human-gold surface to a candidate index, preferring preceding NPs."""
    g = gold.lower()

    def matches(cand):
        ss = cand["surface"].lower()
        return g in ss or ss in g

    before = [i for i, c in enumerate(pool)
              if c["end"] <= aspan[0] and matches(c)]
    if before:
        return before[0]
    any_idx = [i for i, c in enumerate(pool) if matches(c)]
    return any_idx[0] if any_idx else None


def _pool(mentions):
    return [{"surface": m["surface"], "start": m["start"], "end": m["end"]}
            for m in mentions]


def _gold_uf(case):
    """Union-find over the common candidate pool using mapped gold labels."""
    from rulecoref import UF
    from refs import is_self

    uf = UF(len(case["candidates"]))
    # All self references ("~", "this creature", ...) denote the same card.
    # This is objective card semantics, not a resolver guess, and it prevents
    # a correct self-binding from being scored as a different mention.
    selfs = [i for i, c in enumerate(case["candidates"])
             if is_self(c["surface"])]
    for i in selfs[1:]:
        uf.union(selfs[0], i)

    for i, target in case["targets"].items():
        gi = target.get("gold_index")
        if gi is None:
            continue
        ana = case["anaphors"][i]
        ai = _overlap_index(case["candidates"], (ana["start"], ana["end"]))
        if ai is not None:
            uf.union(ai, gi)
    return uf


# --------------------------------------------------------------------- loading
def load_dataset_cases(path, require_struct=False):
    """Dataset cases.  Candidate indices in the file are the gold coordinate
    system; the common pool is the cleaned runtime inventory."""
    import refs

    with open(path) as fh:
        data = json.load(fh)
    if require_struct:
        import ptree
        data = [c for c in data if ptree.has_structure(c["text"])]

    cases = []
    for rec in data:
        text = rec["text"]
        raw = rec.get("candidates") or []
        anaphors = [dict(a) for a in (rec.get("anaphors") or [])]
        mentions = refs.annotate(text, refs.clean(raw))
        pool = _pool(mentions)

        raw_to_pool = {}
        for old_i, cand in enumerate(raw):
            if not isinstance(cand, dict):
                continue
            idx = _exact_index(pool, (cand.get("start"), cand.get("end")))
            if idx is not None:
                raw_to_pool[old_i] = idx

        targets = {}
        for i, ana in enumerate(anaphors):
            g = ana.get("antecedent")
            if g is None or g < 0:
                targets[i] = {"no_gold": True, "gold_index": None,
                              "kind": ana.get("kind"), "gold_surface": None}
                continue
            gi = raw_to_pool.get(g)
            gold_surface = None
            if 0 <= g < len(raw) and isinstance(raw[g], dict):
                gold_surface = raw[g].get("surface")
            targets[i] = {"no_gold": False, "gold_index": gi,
                          "gold_surface": gold_surface,
                          "kind": ana.get("kind")}
        cases.append({
            "card": rec.get("card"), "text": text,
            "mentions": mentions, "candidates": pool,
            "anaphors": anaphors, "targets": targets, "source": "dataset",
        })
    return cases


def load_bench_cases(path=None, data_path=None, mentions="parser"):
    """Benchmark cases: one target occurrence per row, fixed pool per card."""
    import refs
    from setdata import card_text

    path = path or os.path.join(BASE, "coref_benchmark.json")
    with open(path) as fh:
        labels = json.load(fh)
    use_parser = (mentions == "parser")
    cases, skipped, duplicates = [], 0, 0
    by_key = {}

    for card, ana, occ, gold in labels:
        text = card_text(card, data_path)
        if not text:
            skipped += 1
            continue
        hits = [m for m in re.finditer(
            r"(?<![A-Za-z])" + re.escape(ana) + r"(?![A-Za-z])", text, re.I)]
        if len(hits) <= occ:
            skipped += 1
            continue
        aspan = (hits[occ].start(), hits[occ].end())
        all_anas = find_anaphors(text)
        target_i = next((i for i, a in enumerate(all_anas)
                         if (a["start"], a["end"]) == aspan), None)
        if target_i is None:
            skipped += 1
            continue

        key = (card, text)
        case = by_key.get(key)
        if case is None:
            built = refs.build(text, parser=use_parser)
            case = {
                "card": card, "text": text, "mentions": built,
                "candidates": _pool(built), "anaphors": all_anas,
                "targets": {}, "source": "bench",
            }
            by_key[key] = case
            cases.append(case)
        elif target_i in case["targets"]:
            duplicates += 1

        gi = _find_gold_index(case["candidates"], gold, aspan)
        if gi is None:
            skipped += 1
            continue
        case["targets"][target_i] = {
            "no_gold": False, "gold_index": gi,
            "gold_surface": gold, "kind": all_anas[target_i].get("kind"),
        }

    return cases, {"skipped": skipped, "duplicate_cases": duplicates}


# ------------------------------------------------------------------- resolvers
def rule_predictions(case, rules=None):
    import rulecoref

    res = rulecoref.resolve(case["text"], case["mentions"], case["anaphors"],
                            rewrite=False, rules=rules)
    out = []
    for rec in res["anaphors"]:
        ant = rec.get("antecedent")
        idx = (_overlap_index(case["candidates"], (ant["start"], ant["end"]))
               if ant else None)
        out.append({"index": idx, "status": rec.get("status"),
                    "canonical": rec.get("canonical")})
    return out


def attention_predictions(case, resolver):
    out = []
    for ana in case["anaphors"]:
        if not case["candidates"]:
            out.append({"index": None, "status": "no-candidates",
                        "canonical": None})
            continue
        scores = resolver.score(
            case["text"], (ana["start"], ana["end"]),
            [(c["start"], c["end"]) for c in case["candidates"]])
        best = max(range(len(scores)), key=lambda i: scores[i])
        out.append({"index": best, "status": "predicted",
                    "canonical": case["candidates"][best]["surface"]})
    return out


# ------------------------------------------------------------------= scoring
def evaluate_cases(cases, predict, resolver, verbose=0):
    stats = Counter()
    per_kind = defaultdict(Counter)
    misses = []
    statuses = Counter()

    for case in cases:
        preds = predict(case)
        uf = _gold_uf(case)
        for i, target in case["targets"].items():
            if i >= len(preds):
                preds.append({"index": None, "status": "missing"})
            pred = preds[i]
            st = pred.get("status")
            statuses[st] += 1

            if target.get("no_gold"):
                stats["no_gold"] += 1
                if pred.get("index") is None:
                    stats["no_gold_abstained"] += 1
                continue

            stats["total"] += 1
            kind = target.get("kind") or "?"
            per_kind[kind]["total"] += 1
            gi = target.get("gold_index")
            if gi is None:
                # The gold mention did not survive inventory cleaning.  Keep it
                # in the denominator (it is a real label), but there is no
                # entity cluster to score against.
                stats["gold_missing"] += 1
                if len(misses) < verbose:
                    misses.append((case["card"], target.get("gold_surface"),
                                   target.get("gold_surface"), None,
                                   "gold-missing"))
                continue

            pred_i = pred.get("index")
            exact = pred_i == gi
            entity = (pred_i is not None and
                      uf.find(pred_i) == uf.find(gi))
            stats["exact"] += exact
            stats["entity"] += entity
            per_kind[kind]["exact"] += exact
            per_kind[kind]["entity"] += entity
            if not entity and len(misses) < verbose:
                misses.append((
                    case["card"], target.get("gold_surface"),
                    case["candidates"][gi]["surface"],
                    (case["candidates"][pred_i]["surface"]
                     if pred_i is not None else None),
                    st,
                ))

    n = stats["total"]
    stats["resolver"] = resolver
    print(f"resolver={resolver}  cases={len(cases)}  labelled={n}")
    print(f"  entity-aware: {stats['entity']}/{n} = "
          f"{100*stats['entity']/max(1,n):.1f}%   (primary)")
    print(f"  exact span:   {stats['exact']}/{n} = "
          f"{100*stats['exact']/max(1,n):.1f}%")
    print(f"  gold span missing from pool: {stats['gold_missing']}")
    print(f"  gold says 'no antecedent': {stats['no_gold']}  "
          f"(abstained on {stats['no_gold_abstained']})")
    if statuses:
        print("  statuses: " + ", ".join(f"{k}={v}" for k, v in
                                         statuses.most_common()))
    print("  per kind:")
    for kind, d in sorted(per_kind.items(), key=lambda kv: -kv[1]["total"]):
        print(f"    {kind:<14} entity {d['entity']}/{d['total']} = "
              f"{100*d['entity']/max(1,d['total']):4.0f}%   "
              f"exact {d['exact']}/{d['total']}")
    for card, ana, gold, pred, status in misses:
        print(f"    MISS {card}: {ana!r} gold={gold!r} pred={pred!r} [{status}]")
    return dict(stats)


def _make_predictor(args):
    if args.resolver == "rule":
        rules = set()
        for chunk in args.ablate.split(","):
            chunk = chunk.strip()
            if chunk:
                rules[chunk] = False
        return lambda case: rule_predictions(case, rules)

    from resolve import AttentionResolver
    resolver = AttentionResolver(args.model, args.layer, args.head, args.max_length)
    return lambda case: attention_predictions(case, resolver)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dataset", help="dataset json (teacher labels)")
    src.add_argument("--bench", nargs="?", const="", default=None,
                     help="human benchmark (default coref_benchmark.json)")
    ap.add_argument("--resolver", choices=("rule", "attention"), default="rule")
    ap.add_argument("--mentions", choices=("parser", "regex"), default="parser",
                    help="candidate pool for benchmark cases (dataset pools are fixed)")
    ap.add_argument("--data", default=None, help="source data for benchmark texts")
    ap.add_argument("--ablate", default="", help="comma-separated rule names to disable")
    ap.add_argument("--structured-only", action="store_true")
    ap.add_argument("--show-misses", type=int, default=8)
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    ap.add_argument("--layer", type=int, default=2)
    ap.add_argument("--head", default="max")
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if args.dataset:
        cases = load_dataset_cases(args.dataset,
                                   require_struct=args.structured_only)
        extra = {}
    else:
        path = args.bench or None
        cases, extra = load_bench_cases(path, data_path=args.data,
                                        mentions=args.mentions)

    predict = _make_predictor(args)
    stats = evaluate_cases(cases, predict, args.resolver, args.show_misses)
    stats.update(extra)
    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(stats, fh, indent=1)
        print(f"  wrote {args.json_out}")


if __name__ == "__main__":
    main()
