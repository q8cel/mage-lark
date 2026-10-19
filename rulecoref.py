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
# Direction of the type lattice used for demonstratives ("that creature"):
#   lattice  - candidate type must be inside LATTICE[anaphor]  (current default)
#   expected - anaphor type must be inside LATTICE[candidate]  (the "is a" direction)
#   either   - union of both
TYPE_MODE = "either"
# First words that are determiners, not proper nouns: their case can be adapted
# to the slot they are substituted into ("if This spell" -> "if this spell").
CASE_FREE = {"this", "that", "those", "these", "the", "a", "an", "target",
             "each", "every", "all", "any", "no", "another", "other", "up",
             "you", "your", "its", "their", "one", "two", "three"}
# Which entity a possessive refers to, by the phrase that introduces it. Derived
# from the corpus (755 possessive occurrences with a gold antecedent):
#   "creatures of their choice", "damage equal to its power"  -> the clause SUBJECT
#   "under its owner's control", "into their graveyard"       -> the OBJECT
_POSS_SUBJECT = re.compile(r"(\bof|\bequal\s+to|\bwith|\bfor)\s*$", re.I)
_POSS_OBJECT = re.compile(r"(\bunder|\binto|\bonto)\s*$", re.I)


def possessive_role(text, start):
    """Preferred antecedent role for a possessive anaphor at `start`, or None."""
    before = text[max(0, start - 24):start]
    if _POSS_OBJECT.search(before):
        return "object"
    if _POSS_SUBJECT.search(before):
        return "subject"
    return None


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


def resolve_auto(text, anaphors, rewrite=True, rules=None, parse_ok=None):
    """Level 0-3 first (regex mentions, no parse tree); escalate to the parser only
    if some anaphor ends up `ambiguous` or `no-resolution`.

    Measured on the 71-case human bench: parser mentions buy 1 case (77% vs 76%),
    but every escalation costs a real parse (trivial sentences take 12-20s here), so
    paying for the tree on *every* card is a bad trade. This pays only where the
    rules say they are unsure.
    """
    fast = resolve(text, refs.build(text, parser=False), anaphors,
                   rewrite=rewrite, rules=rules)
    unsure = any(a["status"] != "resolved" for a in fast["anaphors"])
    if not unsure:
        fast["mentions_source"] = "regex"
        return fast
    slow = resolve(text, refs.build(text, parser=True), anaphors,
                   rewrite=rewrite, rules=rules)
    slow["mentions_source"] = "regex+parser"
    return slow


def resolve(text, mentions, anaphors, rewrite=True, rules=None, struct=None,
            parse_ok=None):
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
          "possessive_role": True,
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
        # Is the anaphor itself occupying a nominal slot (a whole card_target /
        # player / token node), and not merely embedded in a larger NP's modifier
        # ("from among them") or in a place where a pronoun is grammatically
        # required ("as though they had flash")? Only nominal slots may be
        # rewritten to a concrete NP.
        rec["slot"] = None
        if struct:
            tight = None
            for r in struct:
                if r["start"] <= rec["start"] and rec["end"] <= r["end"]:
                    if tight is None or (r["end"] - r["start"]) < (tight["end"] - tight["start"]):
                        tight = r
            if tight is not None:
                if (tight["node"] in ("card_target", "player", "token")
                        and (tight["end"] - tight["start"]) <= (rec["end"] - rec["start"]) + 2):
                    rec["slot"] = "nominal"
                else:
                    # the anaphor sits inside a larger NP's modifier
                    # ("from among them") -> substituting an NP there produces
                    # nonsense, always skip
                    rec["slot"] = "embedded"
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
        def _type_ok(cand_type):
            if atype is None or cand_type is None:
                return True
            if TYPE_MODE == "lattice":
                return refs.type_compatible(atype, cand_type)
            if TYPE_MODE == "expected":
                return refs.type_expected(atype, cand_type)
            return (refs.type_compatible(atype, cand_type)
                    or refs.type_expected(atype, cand_type))

        if on["type"] and atype:
            # A demonstrative names its own head ("that card"), so a mention whose
            # head type is unknown (a bare "You", "~", a fragment) is a much worse
            # fit than any typed mention - prefer typed ones whenever they exist.
            f = [i for i in pool
                 if ms[i]["head_type"] is not None and _type_ok(ms[i]["head_type"])]
            if not f:
                f = [i for i in pool if _type_ok(ms[i]["head_type"])]
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
        if on["possessive"] and rec["is_possessive"]:
            f = [i for i in pool if ms[i]["sentence"] == rec["sentence"]
                 and ms[i]["clause"] == rec["clause"]]
            if f:
                pool = f
                evidence.append("possessive-same-clause")
            if on["possessive_role"]:
                want = possessive_role(text, rec["start"])
                if want:
                    g = [i for i in pool if ms[i].get("role") == want]
                    if g:
                        pool = g
                        evidence.append(f"possessive-{want}")

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
        result["rewrite_stats"] = {}
        result["rewritten_text"] = rewrite_text(text, out_anas, parse_ok=parse_ok,
                                                stats=result["rewrite_stats"])
    return result


def rewrite_text(text, anas, require_number_match=True, parse_ok=None, stats=None):
    """Replace resolved anaphors with their antecedent surface.

    Possessive pronouns are left alone: the grammar only accepts `its/their/
    your/...` in possessor position, so `target creature's owner` would not
    parse. Everything else becomes a concrete NP.

    `parse_ok` (optional callable: sentence -> bool) enables per-sentence
    validation: a sentence whose edit breaks the parse is reverted as a whole.
    Resolution should only ever claim rewrites that compile.
    """
    if stats is None:
        stats = {}
    for k in ("applied", "reverted", "skip_possessive", "skip_set",
              "skip_number", "skip_slot"):
        stats.setdefault(k, 0)
    sents = refs.sentence_spans(text)

    def sent_of(pos):
        for a, b in sents:
            if a <= pos < b:
                return a, b
        return 0, len(text)

    by_sent = {}
    for a in anas:
        if a["status"] == "no-resolution" or not a.get("antecedent"):
            continue
        surf = a["surface"].lower()
        if surf in POSSESSIVE:
            stats["skip_possessive"] += 1
            continue
        if a["kind"] == "phrase":
            stats["skip_set"] += 1
            continue
        if a.get("slot") == "embedded":
            stats["skip_slot"] += 1
            continue
        ant = a.get("canonical") or a["antecedent"]["surface"]
        if require_number_match:
            an, nn = refs.number(ant), a.get("number")
            if nn and an and nn != an:
                stats["skip_number"] += 1
                continue
        # fit the case to the slot: sentence-initial gets a capital, mid-sentence
        # a determiner-led antecedent gets lowercased (proper nouns untouched)
        before = text[:a["start"]].rstrip()
        initial = (not before) or before[-1] in ".!?\u2014"
        head = ant.split(" ", 1)[0].lower().strip("'")
        if initial:
            ant = ant[:1].upper() + ant[1:] if ant[:1].islower() else ant
        elif head in CASE_FREE:
            ant = ant[:1].lower() + ant[1:]
        by_sent.setdefault(sent_of(a["start"]), []).append((a["start"], a["end"], ant))

    out, reverted, applied = [], 0, 0
    for a, b in sents:
        edits = sorted(by_sent.get((a, b), []))
        if not edits:
            continue
        piece, cur, ok = [], a, True
        for s0, e0, rep in edits:
            if s0 < cur:
                continue
            piece.append(text[cur:s0])
            piece.append(rep)
            cur = e0
        piece.append(text[cur:b])
        candidate = "".join(piece)
        if parse_ok is not None:
            try:
                ok = bool(parse_ok(candidate))
            except Exception:
                ok = False
        if ok:
            applied += len(edits)
            stats["applied"] += len(edits)
        else:
            reverted += len(edits)
            stats["reverted"] += len(edits)
            candidate = text[a:b]
        out.append((a, b, candidate))

    if not out:
        return text
    result, cur = [], 0
    for a, b, piece in out:
        result.append(text[cur:a])
        result.append(piece)
        cur = b
    result.append(text[cur:])
    return "".join(result)


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


def eval_benchmark(path=None, verbose=0, parser=True):
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
        if parser == "auto":
            res = resolve_auto(text, all_anas, rewrite=False)
        else:
            res = resolve(text, refs.build(text, parser=parser), all_anas, rewrite=False)
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
    ap.add_argument("--no-parser", action="store_true",
                    help="use regex mentions only (no parse tree) - the level-0/1 coref path")
    ap.add_argument("--type-mode", choices=("lattice", "expected", "either"),
                    default="either",
                    help="direction of the type lattice for demonstratives; `either` "
                         "(union) measured best and is safest with a coarse vocabulary")
    ap.add_argument("--parser", choices=("always", "auto", "never"), default="always",
                    help="mention source: always=parse every card, auto=parse only "
                         "when a decision is unsure, never=regex only")
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
        globals()["TYPE_MODE"] = args.type_mode
        parser = {"always": True, "never": False, "auto": "auto"}[args.parser]
        if args.no_parser:
            parser = False
        eval_benchmark(args.bench or None, verbose=args.show_misses or 20, parser=parser)
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
