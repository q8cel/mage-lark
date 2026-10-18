"""Deterministic anaphora resolution: mention graph + rule cascade. No model.

Design (see DETERMINISTIC-COREF.md):

  1. build the mention inventory                       [refs.py]
  2. add every anaphor occurrence as a mention (anaphors are aliases, never
     antecedents themselves)
  3. walk the anaphors left to right; for each one:
        hard filters   same-card precedence, self-exclusion, number agreement,
                       entity-type lattice, counters are not entities
        soft rules     possessive object binding, then recency
        decision       resolved / ambiguous / no-resolution
     a resolved anaphor is UNIONED with its antecedent, so later anaphors chain
     through the entity rather than through the text span
  4. emit entities (clusters of coreferring spans) + an optional rewritten text
     with the pronoun replaced by the antecedent surface (so the parser can be
     re-run on a fully concrete sentence)

Everything is JSON-in / JSON-out so the same rules can be ported to C++/Rust/Go.

    python rulecoref.py --card "Fiery Annihilation"
    python rulecoref.py --eval coref_standard.json
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import refs
from anaphora import find_anaphors

POSSESSIVE = {"its", "their", "itself", "themselves"}
POSSESSED_RE = re.compile(
    r"^\s*(?:'s\s+)?(owner|controller|power|toughness|mana value|mana cost|"
    r"color|colors|name|type|types|abilities|subtypes)", re.I)


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def _atoi(d, key, default=0):
    v = d.get(key)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return default


def _struct_for(text, struct):
    """Structure records for `text`, or None. Never triggers a parse."""
    if struct is not None:
        return struct
    try:
        import ptree
        return ptree.peek(text)
    except Exception:
        return None


def _as_anaphor_record(a, text):
    """Normalise an anaphor dict: needs surface/start/end/kind (+ optional gold)."""
    rec = dict(a)
    s, e = rec["start"], rec["end"]
    rec.setdefault("kind", "pronoun")
    if "clause" not in rec or "sentence" not in rec:
        env = refs.annotate(text, [{"surface": rec["surface"], "start": s, "end": e}])[0]
        rec["sentence"] = env["sentence"]
        rec["clause"] = env["clause"]
    rec["head_type"] = refs.head_type(rec["surface"]) if rec["kind"] == "demonstrative" else None
    rec["number"] = refs.number(rec["surface"])
    rec["is_possessive"] = rec["surface"].lower() in POSSESSIVE
    rec["possesses"] = bool(POSSESSED_RE.match(text[e:e + 32]))
    rec["verb_type"] = refs.predicate_type(text, s, e)
    return rec


def _container(struct, start):
    """Tightest mention record containing `start` (the NP the anaphor sits in)."""
    if not struct:
        return None
    best = None
    for r in struct:
        if r["start"] <= start < r["end"]:
            if best is None or (r["end"] - r["start"]) < (best["end"] - best["start"]):
                best = r
    return best


def resolve(text, mentions, anaphors, rewrite=True, rules=None, struct=None):
    """Resolve every anaphor occurrence in `text`.

    mentions: annotated mention dicts (refs.build). Anaphor spans are appended
              automatically when they are not already present.
    anaphors: dicts with surface/start/end/kind (extra keys are preserved, so a
              gold `antecedent` survives into the output for evaluation).
    rules:    ablation switches, e.g. {'possessive': False, 'number': False,
              'type': False, 'nonentity': False}.
    """
    on = {"possessive": True, "number": True, "type": True, "nonentity": True,
          "set_rest": True,
          "verb": False,      # lexical verb prior: measured to hurt, opt-in only
          # structural rule, needs the parse tree (ptree): a copula complement
          # ("it's an artifact") is a description, never an antecedent.
          # sound but inert in practice: only 2 mention records corpus-wide are
          # copula complements. Kept because it can only ever remove noise.
          "predicate": True}
    on.update(rules or {})
    struct = _struct_for(text, struct)
    ms = [dict(m) for m in mentions]
    if struct:
        for m in ms:
            if "role" not in m:
                hit = None
                for r in struct:
                    if r["start"] <= m["start"] and m["start"] < r["end"]:
                        if hit is None or (r["end"] - r["start"]) < (hit["end"] - hit["start"]):
                            hit = r
                m["role"] = hit["role"] if hit else None
                m["verb"] = hit["verb"] if hit else None
                m["predicate"] = bool(hit["predicate"]) if hit else False
                m["in_condition"] = bool(hit["in_condition"]) if hit else False
    for m in ms:
        m.setdefault("is_anaphor", False)
        m.setdefault("head_type", refs.head_type(m["surface"]))
        m.setdefault("number", refs.number(m["surface"]))
        m.setdefault("is_self", refs.is_self(m["surface"]))
        m.setdefault("is_target", refs.is_target(m["surface"]))
        m.setdefault("is_pronoun", refs.is_pronoun_span(m["surface"]))
        if "sentence" not in m or "clause" not in m:
            env = refs.annotate(text, [{"surface": m["surface"],
                                        "start": m["start"], "end": m["end"]}])[0]
            m["sentence"], m["clause"] = env["sentence"], env["clause"]

    span_index = {(m["start"], m["end"]): i for i, m in enumerate(ms)}
    anas = []
    for a in anaphors:
        rec = _as_anaphor_record(a, text)
        box = _container(struct, rec["start"])
        rec["container_role"] = box["role"] if box else None
        key = (rec["start"], rec["end"])
        if key not in span_index:
            env = refs.annotate(text, [{"surface": rec["surface"], "start": key[0],
                                        "end": key[1]}])[0]
            env.update({"src": None, "is_anaphor": True, "head_type": rec["head_type"],
                        "number": rec["number"], "is_self": False, "is_target": False,
                        "is_pronoun": rec["kind"] == "pronoun"})
            ms.append(env)
            span_index[key] = len(ms) - 1
        else:
            ms[span_index[key]]["is_anaphor"] = True
        rec["_mi"] = span_index[key]
        anas.append(rec)

    uf = UF(len(ms))
    # every self-reference in a card denotes the same object (the card), so it is
    # sound to cluster them before any prediction: `~` twice is one entity.
    selfs = [i for i, m in enumerate(ms) if m.get("is_self")]
    for i in selfs[1:]:
        uf.union(selfs[0], i)

    for rec in anas:
        a_from = rec["_mi"]
        atype = rec["head_type"]
        anum = None if rec["kind"] == "phrase" else rec["number"]

        # ---- candidate pool: strictly preceding, never the anaphor itself
        pool = [i for i, m in enumerate(ms) if m["end"] <= rec["start"] and i != a_from]
        evidence = []

        # ---- hard filters
        n0 = len(pool)
        pool = [i for i in pool if not ms[i]["is_pronoun"]]
        if len(pool) != n0:
            evidence.append("drop-pronoun-aliases")
        if anum and on["number"]:
            f = [i for i in pool if ms[i]["number"] == anum]
            if f:
                pool = f
                evidence.append(f"number={anum}")
        if on["type"] and atype:
            f = [i for i in pool if refs.type_compatible(atype, ms[i]["head_type"])]
            if f:
                pool = f
                evidence.append(f"type={atype}")
        elif on["nonentity"]:
            f = [i for i in pool if ms[i]["head_type"] not in refs.NON_ENTITY]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("drop-non-entities")

        # ---- predicate prior: the governing verb narrows what the pronoun is
        if on["verb"] and atype is None:
            vtype = rec.get("verb_type")
            if vtype:
                f = [i for i in pool if refs.type_expected(vtype, ms[i]["head_type"])]
                if f and len(f) != len(pool):
                    pool = f
                    evidence.append(f"verb={vtype}")

        # ---- structural rules (need the parse tree; skipped without it)
        if on["predicate"] and any(ms[i].get("predicate") for i in pool):
            f = [i for i in pool if not ms[i].get("predicate")]
            if f:
                pool = f
                evidence.append("drop-predicate-nominals")

# (a "self mention as clause subject wins" rule was measured here: it fired 18x
#  on the structured sample, changed 8 picks, fixed 4 and broke 4. Removed.)

        # ---- set-valued anaphors ("the rest", "the others")
        # The referent is a COLLECTION minus what was just singled out, so the
        # antecedent is the last plural collection NP, not the last mention.
        if on["set_rest"] and rec["kind"] == "phrase":
            f = [i for i in pool if ms[i]["number"] == "pl" and ms[i]["head_type"]]
            if f:
                pool = f
                evidence.append("set-rest")

        # ---- possessive binding
        # `their` inside an object NP ("the top N cards of their library") belongs
        # to the clause SUBJECT; a possessive beside the object ("to its owner's
        # hand") belongs to the OBJECT. The tree tells us which by whether the
        # anaphor sits inside the object mention or next to it.
        # A role-based variant ("possessive inside the object NP belongs to the
        # subject") was implemented and measured here: -1 occurrence on dev, and
        # its precondition held for only 6 of 755 possessive anaphors, because
        # those clauses do not parse at all (see DETERMINISTIC-COREF.md).
        if on["possessive"] and rec["is_possessive"] and rec["possesses"]:
            f = [i for i in pool if ms[i]["sentence"] == rec["sentence"]
                 and ms[i]["clause"] == rec["clause"]]
            if f:
                pool = f
                evidence.append("possessive-same-clause")

        # ---- decision
        status, pred = None, None
        if not pool:
            status = "no-resolution"
        else:
            last = max(range(len(pool)), key=lambda k: (ms[pool[k]]["end"], k))
            pred = pool[last]
            # ambiguous when the two most recent survivors are indistinguishable
            # on every hard criterion, i.e. only recency separates them
            if len(pool) >= 2:
                a1, a2 = ms[pool[last]], ms[pool[last - 1]]
                same = (a1["head_type"] == a2["head_type"]
                        and a1["number"] == a2["number"]
                        and a1["sentence"] == rec["sentence"]
                        and a2["sentence"] == rec["sentence"])
                status = "ambiguous" if same else "resolved"
            else:
                status = "resolved"
            if status == "resolved":
                evidence.append("recency")
            uf.union(a_from, pred)

        rec["set_valued"] = rec["kind"] == "phrase"
        if rec["set_valued"]:
            rec["op"] = "minus"     # <collection> minus the singled-out subset
        rec["status"] = status
        rec["_pred"] = pred
        rec["evidence"] = evidence
        rec["candidates"] = len(pool)

    # ---- entities
    groups = defaultdict(list)
    for i in range(len(ms)):
        groups[uf.find(i)].append(i)
    root_to_id, entities, groups_by_id = {}, [], {}
    for root, idxs in sorted(groups.items(), key=lambda kv: min(ms[i]["start"] for i in kv[1])):
        eid = len(entities)
        groups_by_id[eid] = idxs
        root_to_id[root] = eid
        spans = sorted(idxs, key=lambda i: ms[i]["start"])
        canonical = max((ms[i] for i in spans if not ms[i]["is_anaphor"]),
                        key=lambda m: (m["is_target"], len(m["surface"])),
                        default=ms[spans[0]])
        entities.append({
            "id": eid,
            "canonical": canonical["surface"],
            "spans": [{"surface": ms[i]["surface"], "start": ms[i]["start"],
                       "end": ms[i]["end"], "is_anaphor": ms[i]["is_anaphor"]}
                      for i in spans],
        })

    # ---- per-anaphor output
    out_anas = []
    def entity_src(eid):
        """A dataset index for an entity: prefer a non-anaphor span with a src."""
        best = None
        for i in groups_by_id[eid]:
            if ms[i].get("src") is not None and not ms[i]["is_anaphor"]:
                if best is None or ms[i]["start"] < ms[best]["start"]:
                    best = i
        if best is None:
            for i in groups_by_id[eid]:
                if ms[i].get("src") is not None:
                    return ms[i]["src"]
            return None
        return ms[best]["src"]

    for rec in anas:
        pred = rec["_pred"]
        item = {k: v for k, v in rec.items() if not k.startswith("_")}
        if pred is None:
            item.update({"entity": None, "antecedent": None, "antecedent_src": None,
                         "canonical": None})
        else:
            eid = root_to_id[uf.find(pred)]
            item.update({
                "entity": eid,
                "antecedent": {"surface": ms[pred]["surface"],
                               "start": ms[pred]["start"], "end": ms[pred]["end"]},
                "antecedent_src": (ms[pred].get("src")
                                    if ms[pred].get("src") is not None
                                    else entity_src(eid)),
                "canonical": entities[eid]["canonical"],
            })
        out_anas.append(item)

    result = {
        "text": text,
        "mentions": [{k: v for k, v in m.items()} for m in ms],
        "entities": entities,
        "anaphors": out_anas,
    }
    if rewrite:
        result["rewritten_text"] = rewrite_text(text, out_anas)
    return result


def rewrite_text(text, anas, require_number_match=True):
    """Replace resolved anaphors with their antecedent surface.

    Possessive pronouns are left alone: the grammar only accepts `its/their/
    your/...` in possessor position, so `target creature's owner` would not
    parse. Everything else becomes a concrete NP the parser already handles.
    """
    edits = []
    for a in anas:
        if a["status"] == "no-resolution" or not a.get("antecedent"):
            continue
        surf = a["surface"].lower()
        if surf in POSSESSIVE or a["kind"] == "phrase":
            continue
        ant = a.get("canonical") or a["antecedent"]["surface"]
        if require_number_match:
            an, nn = refs.number(ant), a.get("number")
            if nn and an and nn != an:
                continue
        edits.append((a["start"], a["end"], ant))
    if not edits:
        return text
    edits.sort()
    out, cur = [], 0
    for s, e, rep in edits:
        if s < cur:
            continue
        out.append(text[cur:s])
        out.append(rep)
        cur = e
    out.append(text[cur:])
    return "".join(out)


# ------------------------------------------------------------------- evaluation
def _cand_for(cands, span):
    """Index of the candidate matching `span` (exact, else max overlap)."""
    best, bo = None, 0
    for i, c in enumerate(cands):
        if c["start"] == span[0] and c["end"] == span[1]:
            return i
        ov = min(span[1], c["end"]) - max(span[0], c["start"])
        if ov > bo:
            best, bo = i, ov
    return best


def gold_clusters(cands, anaphors):
    """Union-find over candidate indices using the gold antecedent labels."""
    uf = UF(len(cands))
    for a in anaphors:
        g = a.get("antecedent")
        if g is None or g < 0:
            continue
        j = _cand_for(cands, (a["start"], a["end"]))
        if j is not None:
            uf.union(j, g)
    return uf


def eval_dataset(path, verbose=0, rewrite=False, rules=None, require_struct=False):
    """Score the rules against teacher labels, entity-aware.

    A prediction is correct when the predicted antecedent belongs to the same
    gold cluster as the gold antecedent — so a correct answer that picked a
    different mention of the same object still counts.
    """
    rules = rules or {}
    data = json.load(open(path))
    stats = defaultdict(int)
    per_kind = defaultdict(lambda: defaultdict(int))
    buckets = defaultdict(int)
    misses = []
    if require_struct:
        import ptree
        data = [c for c in data if ptree.has_structure(c["text"])]

    for case in data:
        text, cands = case["text"], case["candidates"]
        gold_uf = gold_clusters(cands, case["anaphors"])

        ms = refs.annotate(text, refs.clean(cands))
        live = {m["src"] for m in ms}
        res = resolve(text, ms, case["anaphors"], rewrite=rewrite, rules=rules)

        for out, gold in zip(res["anaphors"], case["anaphors"]):
            g = gold.get("antecedent")
            st = out["status"]
            if g is None or g < 0:
                # gold says "no antecedent": the only thing to measure is
                # whether we abstained too
                stats["gold_none"] += 1
                stats["gold_none_abstained"] += (st == "no-resolution")
                continue
            stats["total"] += 1
            gj = _cand_for(cands, (gold["start"], gold["end"]))
            gold_ok = g in live
            stats["gold_span_survived"] += gold_ok
            stats[f"status_{st}"] += 1
            per_kind[gold["kind"]]["total"] += 1
            per_kind[gold["kind"]][f"status_{st}"] += 1
            if not gold_ok:
                buckets["gold span dropped by cleaning"] += 1
                continue
            src = out.get("antecedent_src")
            ok = src is not None and gold_uf.find(src) == gold_uf.find(g)
            stats["correct"] += ok
            per_kind[gold["kind"]]["correct"] += ok
            if not ok:
                if src is None:
                    buckets["no-resolution"] += 1
                elif refs.head_type(cands[g]["surface"]) != refs.head_type(cands[src]["surface"]):
                    buckets["type mismatch"] += 1
                else:
                    buckets["wrong pick, same type"] += 1
                if len(misses) < verbose:
                    misses.append((text, gold["surface"],
                                   cands[g]["surface"],
                                   cands[src]["surface"] if src is not None else None,
                                   out["status"], out["evidence"]))

    n = stats["total"]
    scaled = stats["correct"] / max(1, n)
    print(f"n={n}  correct={stats['correct']} = {100*scaled:.1f}%   (teacher labels)")
    print(f"  gold span dropped by inventory cleaning: {n - stats['gold_span_survived']}")
    print(f"  gold said 'no antecedent': {stats['gold_none']}  "
          f"(we abstained on {stats['gold_none_abstained']})")
    for st in ("resolved", "ambiguous", "no-resolution"):
        c = stats[f"status_{st}"]
        print(f"  status {st:<14} {c:>5}  ({100*c/max(1,n):4.1f}%)")
    print("  per kind:")
    for k, d in sorted(per_kind.items(), key=lambda kv: -kv[1]["total"]):
        print(f"    {k:<14} {d['correct']}/{d['total']} = "
              f"{100*d['correct']/max(1,d['total']):4.0f}%   "
              f"({d['status_ambiguous']} ambiguous, {d['status_no-resolution']} none)")
    print("  residual buckets:")
    for k, c in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"    {c:>5}  {k}")
    for m in misses:
        print(f"    MISS {m[1]!r} gold={m[2]!r} pred={m[3]!r} ({m[4]})")
    return scaled


def eval_benchmark(path=None, verbose=0):
    """Score the rules on the 72-case human gold (coref_benchmark.json).

    Gold here is a surface string, not a candidate index, so we match by
    containment (the same rule resolve.eval_benchmark uses).
    """
    path = path or os.path.join(BASE, "coref_benchmark.json")
    from setdata import card_text
    labels = json.load(open(path))
    ok = miss = skip = 0
    rows = []
    for card, ana, occ, gold in labels:
        text = card_text(card)
        if not text:
            skip += 1
            continue
        hits = [m for m in re.finditer(r"(?<![A-Za-z])" + re.escape(ana) + r"(?![A-Za-z])",
                                       text, re.I)]
        if len(hits) <= occ:
            skip += 1
            continue
        span = (hits[occ].start(), hits[occ].end())
        all_anas = find_anaphors(text)
        if not any((a["start"], a["end"]) == span for a in all_anas):
            skip += 1
            continue
        # resolve the WHOLE card: later anaphors chain through earlier ones
        res = resolve(text, refs.build(text), all_anas, rewrite=False)
        pred = next(p for p in res["anaphors"]
                    if (p["start"], p["end"]) == span)
        g = gold.lower()
        got = (pred["canonical"] or "").lower()
        eid = pred.get("entity")
        surfaces = ([sp["surface"].lower() for sp in res["entities"][eid]["spans"]]
                    if eid is not None else ([got] if got else []))
        hit = any(s and (g in s or s in g) for s in surfaces)
        if hit:
            ok += 1
        else:
            miss += 1
            rows.append((card, ana, gold, pred["canonical"], pred["status"]))
    n = ok + miss
    print(f"bench: n={n} (skipped {skip})  rules={ok}/{n} = {100*ok/max(1,n):.0f}%")
    for card, ana, gold, got, st in rows[:verbose]:
        print(f"  MISS {card[:28]:<28} {ana!r:<10} gold={gold!r:<30} got={got!r} ({st})")
    return ok, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="?")
    ap.add_argument("--data", default=None)
    ap.add_argument("--eval", default=None, metavar="DATASET.json")
    ap.add_argument("--bench", nargs="?", const="", default=None,
                    metavar="BENCH.json", help="score on the human gold set")
    ap.add_argument("--show-misses", type=int, default=0)
    ap.add_argument("--structured-only", action="store_true",
                    help="evaluate only cards already in the pstruct cache")
    ap.add_argument("--ablate", default="",
                    help="comma list of rules to disable: possessive,number,type,"
                         "nonentity,verb,predicate,possessive_role")
    ap.add_argument("--enable", default="",
                    help="comma list of default-off rules to switch on")
    ap.add_argument("--json", action="store_true", help="dump full JSON result")
    args = ap.parse_args()

    if args.eval:
        off = {r.strip() for r in args.ablate.split(",") if r.strip()}
        ons = {r.strip() for r in args.enable.split(",") if r.strip()}
        rules = {k: False for k in off}
        rules.update({k: True for k in ons})
        eval_dataset(args.eval, verbose=args.show_misses, rules=rules,
                     require_struct=args.structured_only)
        return
    if args.bench is not None:
        eval_benchmark(args.bench or None, verbose=args.show_misses or 20)
        return
    if not args.card:
        ap.error("give a card name or --eval DATASET.json")

    from setdata import card_text
    text = card_text(args.card, args.data)
    if not text:
        print("card not found")
        return
    res = resolve(text, refs.build(text), find_anaphors(text))
    if args.json:
        print(json.dumps(res, indent=1))
        return
    print(text)
    for a in res["anaphors"]:
        ant = a["antecedent"]["surface"] if a["antecedent"] else "—"
        print(f"  {a['surface']!r:<22} -> {ant!r:<34} "
              f"[{a['status']}] entity={a['entity']} rules={','.join(a['evidence'])}")
    print("\nentities:")
    for e in res["entities"]:
        print(f"  #{e['id']} {e['canonical']!r} <- "
              + ", ".join(f"{s['surface']!r}" for s in e["spans"]))
    if res.get("rewritten_text") and res["rewritten_text"] != text:
        print(f"\nrewritten:\n{res['rewritten_text']}")


if __name__ == "__main__":
    main()
