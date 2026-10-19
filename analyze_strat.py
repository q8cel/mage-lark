#!/usr/bin/env python3
"""Turn ensemble labels on the stratified sample into (a) an accuracy estimate for
the resolver and (b) a human-review queue of the contested cases.

Scoring is entity-aware, exactly as the resolver's own evaluation: the ensemble picks
a mention, we map it to the resolver's entity, and match that entity's spans against
the ensemble majority.
"""
import collections, json, sys
sys.path.insert(0, "/home/q6/Documents/mage-attn")
import refs, rulecoref
from anaphora import find_anaphors

LAB = "/tmp/opencode/strat_labels.json"
SAMPLE = "/tmp/opencode/strat_sample.json"
DEV = "/home/q6/Documents/mage-attn/coref_standard.json"


def match(x, g):
    if not x:
        return False
    x, g = x.lower(), g.lower()
    return g in x or x in g


def main():
    lab = json.load(open(LAB))
    sample = {(c["card"], c["surface"], c["start"]): c for c in json.load(open(SAMPLE))}
    dev = {}
    for c in json.load(open(DEV)):
        dev.setdefault(c["card"], c)

    cache = {}

    def resolve(card, text):
        if card not in cache:
            cache[card] = rulecoref.resolve(text, refs.build(text),
                                            find_anaphors(text), rewrite=False)
        return cache[card]

    stats = collections.Counter()
    by_stratum = collections.defaultdict(lambda: collections.Counter())
    review = []
    for r in lab:
        key = (r.get("card"), r.get("surface"), r.get("start"))
        case = sample.get(key)
        res = resolve(r["card"], case["text"] if case else None or "")
        mine = next((a for a in res["anaphors"]
                     if a["start"] == r["start"] and a["surface"].lower() == r["surface"].lower()),
                    None)
        maj = r.get("majority")
        agree = r.get("agreement") or 0
        if mine is None or not maj:
            stats["no_comparable"] += 1
            continue
        eid = mine.get("entity")
        ent = res["entities"][eid] if eid is not None else None
        # correct iff the ensemble's majority mention falls inside the entity the
        # resolver bound the anaphor to (entity-aware, same as our own scoring)
        ours_ok = bool(ent) and any(match(sp["surface"], maj) for sp in ent["spans"])
        stratum = f"{r.get('kind','?')}/{'unanimous' if agree == 3 else 'contested'}"
        stats["total"] += 1
        stats["ours_correct"] += ours_ok
        by_stratum[stratum]["total"] += 1
        by_stratum[stratum]["ok"] += ours_ok
        if not ours_ok or agree < 3:
            review.append({
                "card": r["card"], "surface": r["surface"],
                "span": [r["start"], r["end"]],
                "context": (case or {}).get("text", "")[max(0, r["start"] - 160):r["start"] + 60],
                "our_answer": mine.get("canonical"), "our_status": mine["status"],
                "ensemble_majority": maj, "agreement": f"{agree}/3",
                "ensemble_votes": [(v.get("config"), v.get("pick")) for v in r.get("votes", [])],
                "teacher": (case or {}).get("teacher"),
                "resolver_matches_majority": bool(ours_ok),
            })

    n = stats["total"] or 1
    print(f"labelled cases: {n}")
    print(f"  resolver vs ensemble majority (entity-scored): {stats['ours_correct']}/{n} = "
          f"{100*stats['ours_correct']/n:.1f}%")
    print("  by stratum:")
    for s, c in sorted(by_stratum.items(), key=lambda kv: -kv[1]["total"]):
        print(f"    {s:<28} {c['ok']:>3}/{c['total']:<3} = {100*c['ok']/max(1,c['total']):5.1f}%")
    json.dump(review, open("/tmp/opencode/review_queue.json", "w"), indent=1)
    print(f"\nreview queue: {len(review)} cases -> /tmp/opencode/review_queue.json")
    print("  (sorted by how much the ensemble disagrees with us)")
    for r in sorted(review, key=lambda r: r["resolver_matches_majority"])[:8]:
        print(f"    {r['card'][:22]:<22} {r['surface']!r:<16} ours={r['our_answer']!r:<26} "
              f"ensemble={r['ensemble_majority']!r} ({r['agreement']})")


main()
