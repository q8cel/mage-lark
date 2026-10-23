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

POSSESSIVE = {"its", "their"}
REFLEXIVE = {"itself", "themselves"}
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


# "put a +1/+1 counter on it" - counters go on permanents, not on players.
_COUNTER_ON = re.compile(r"counters?\s+on\s*$", re.I)
# "create a token that's a copy of X, except it ..." - the "it" is the new token.
_COPY_EXCEPT = re.compile(r"except\s*$", re.I)
# "create a token that's a copy of IT" - the anaphor is the copied thing, so the
# newly created token must not be its own antecedent.
_COPY_OF = re.compile(r"copy\s+of\s*$", re.I)
# "a source would deal damage ..., it deals double that damage instead"
_DMG_SUBJECT = re.compile(r"^\s*(deals?|would\s+deal)\b", re.I)
# Lexical copula-complement detection: "If it's a land card", "except it's an
# artifact", "if it was a creature".  These NPs describe the current object;
# they are not introduced antecedents for the pronoun that precedes them.
_PREDICATE_LEAD = re.compile(
    r"\b(?:is|was|are|were|becomes?|be|it's|that's|they're)\s+"
    r"(?:(?:not|no\s+longer)\s+)?(?:a|an|the|another|one|each|all)?\s*$", re.I)
# A card name after "named" is a name reference, not the card itself.
_NAMED_LEAD = re.compile(r"\bnamed\s+$", re.I)
# "from it" / "in it" normally points at a container/player, not the object NP
# immediately before the preposition.
_CONTAINER_LEAD = re.compile(r"\b(?:from|in|into|of)\s*$", re.I)
# "the number of artifacts", "the total power of ..." are quantities, not entities.
_AMOUNT_PHRASE = re.compile(r"^(?:the\s+)?(?:number|total|amount)\b", re.I)
_MODIFIER_LEAD = re.compile(r"\b(?:with|from|in|of|on|under)\s*$", re.I)
_PUT_LEAD = re.compile(r"\bputs?(?:ting)?\s*$", re.I)
_OBJECT_VERB_LEAD = re.compile(
    r"\b(?:exile|exiles|exiled|sacrifice|sacrifices|sacrificed|return|returns|"
    r"returned|destroy|destroys|destroyed|put|puts|tap|taps|tapped|untap|"
    r"untaps|untapped)\s*$", re.I)
PERMANENTS = {"creature", "artifact", "enchantment", "land", "planeswalker",
              "battle", "permanent", "token", "equipment", "aura"}

QUOTE_CHARS = '"\u201c\u201d'


def quoted_region(text, pos):
    """(open, close) of the quoted ability containing `pos`, or None.

    MTG grants abilities as quoted text: `target creature gains "When this
    creature dies, return it to ..."`. Inside that quote, `this creature`/`it`
    refer to the GRANTED-TO permanent, not to the card.
    """
    q = [i for i, ch in enumerate(text) if ch in QUOTE_CHARS]
    for k in range(0, len(q) - 1, 2):
        if q[k] < pos < q[k + 1]:
            return (q[k], q[k + 1])
    return None


# "Choose one of them. ... you may play that card." - the anaphor is an ELEMENT of
# that collection, so the collection is its antecedent even though the collection is
# plural and the anaphor is singular.
_ONE_OF = re.compile(r"\bone\s+of\s+(them|those|these)\b", re.I)
COLLECTION_TYPES = {"card", "creature", "permanent", "artifact", "land",
                    "enchantment", "token", "spell", "pile"}

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
    lower = rec["surface"].lower()
    rec["is_possessive"] = lower in POSSESSIVE
    rec["is_reflexive"] = lower in REFLEXIVE
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
          "argtype": True,
          "granted": True,
          "set_element": True,
          "verb": False,      # lexical verb prior: measured to hurt, opt-in only
          # structural rule, needs the parse tree (ptree): a copula complement
          # ("it's an artifact") is a description, never an antecedent.
          "possessive_role": True,
          # sound but inert in practice: only 2 mention records corpus-wide are
          # copula complements. Kept because it can only ever remove noise.
          "predicate": True}
    on.update(rules or {})
    struct = _struct_for(text, struct)
    sents = refs.sentence_spans(text)
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
    # Every self-reference in a card denotes the same object (the card) - EXCEPT
    # inside a granted ability: `target creature gains "When this creature dies,
    # return it ..."` - there, "this creature" is the recipient of the grant, not
    # the card. Those mentions are aliased to the recipient instead.
    selfs = []
    for i, m in enumerate(ms):
        if not m.get("is_self"):
            continue
        if quoted_region(text, m["start"]):
            continue
        selfs.append(i)
    for i in selfs[1:]:
        uf.union(selfs[0], i)
    if on.get("granted"):
        for i, m in enumerate(ms):
            if not m.get("is_self"):
                continue
            reg = quoted_region(text, m["start"])
            if not reg:
                continue
            recips = [j for j, o in enumerate(ms) if o["end"] <= reg[0]]
            if recips:
                uf.union(i, max(recips, key=lambda j: ms[j]["end"]))

    for rec in anas:
        a_from = rec["_mi"]
        atype = rec["head_type"]
        anum = None if rec["kind"] == "phrase" else rec["number"]

        # ---- candidate pool: strictly preceding, never the anaphor itself
        pool = [i for i, m in enumerate(ms) if m["end"] <= rec["start"] and i != a_from]
        evidence = []

        # ---- lexical predicate/nominal filters
        if on["predicate"]:
            f = [i for i in pool
                 if not _PREDICATE_LEAD.search(text[max(0, ms[i]["start"] - 18):ms[i]["start"]])]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("drop-predicate-nominals")
        f = [i for i in pool
             if not (ms[i]["surface"].strip() == "~"
                     and _NAMED_LEAD.search(text[max(0, ms[i]["start"] - 12):ms[i]["start"]]))]
        if f and len(f) != len(pool):
            pool = f
            evidence.append("drop-named-self")
        if on["nonentity"]:
            f = [i for i in pool
                 if not _AMOUNT_PHRASE.match(ms[i]["surface"].strip())]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("drop-amount-phrases")

        # ---- element of a collection ("choose one of them ... that card")
        if on["set_element"] and _ONE_OF.search(text[max(0, rec["start"] - 130):rec["start"]]):
            f = [i for i in pool if ms[i]["number"] == "pl"
                 and ms[i]["head_type"] in COLLECTION_TYPES]
            if f:
                pool = f
                evidence.append("element-of-collection")

        # ---- hard filters
        n0 = len(pool)
        pool = [i for i in pool if not ms[i]["is_pronoun"]]
        if len(pool) != n0:
            evidence.append("drop-pronoun-aliases")

        def _type_ok(cand_type):
            if atype is None or cand_type is None:
                return True
            if TYPE_MODE == "lattice":
                return refs.type_compatible(atype, cand_type)
            if TYPE_MODE == "expected":
                return refs.type_expected(atype, cand_type)
            return (refs.type_compatible(atype, cand_type)
                    or refs.type_expected(atype, cand_type))

        def _apply_type():
            nonlocal pool
            f = [i for i in pool
                 if ms[i]["head_type"] is not None and _type_ok(ms[i]["head_type"])]
            if not f:
                f = [i for i in pool if _type_ok(ms[i]["head_type"])]
            if f:
                pool = f
                evidence.append(f"type={atype}")

        def _apply_number():
            nonlocal pool
            f = [i for i in pool if ms[i]["number"] == anum]
            if f:
                pool = f
                evidence.append(f"number={anum}")

        # A demonstrative names its own head ("those cards"), which is a stronger
        # constraint than number; for a bare pronoun number is all we have.
        if on["type"] and atype:
            _apply_type()
            if anum and on["number"]:
                _apply_number()
        else:
            if anum and on["number"]:
                _apply_number()
            if on["nonentity"]:
                f = [i for i in pool if ms[i]["head_type"] not in refs.NON_ENTITY]
                if f and len(f) != len(pool):
                    pool = f
                    evidence.append("drop-non-entities")

        # ---- demonstratives: "that/those X" normally points at a previous
        # mention, not at the card itself, and "those cards" prefers a card NP.
        if rec["kind"] == "demonstrative" and on["type"]:
            f = [i for i in pool if not ms[i].get("is_self")]
            if f:
                pool = f
                evidence.append("drop-self-for-demonstrative")
            surf = rec["surface"].lower()
            if "card" in surf:
                f = [i for i in pool if "card" in ms[i]["surface"].lower()]
                if f:
                    pool = f
                    evidence.append("card-demonstrative")

        # ---- set-valued anaphors ("the rest", "the others")
        # The referent is a COLLECTION minus what was just singled out, so the
        # antecedent is the last plural collection NP, not the last mention.
        if on["set_rest"] and rec["kind"] == "phrase":
            f = [i for i in pool if ms[i]["number"] == "pl" and ms[i]["head_type"]]
            if f:
                pool = f
                evidence.append("set-rest")

        # ---- quoted granted ability
        if on["granted"]:
            reg = quoted_region(text, rec["start"])
            if reg:
                # 1) the ability's own mentions first ("that player" inside the
                #    quoted trigger refers to something the trigger introduces)
                f = [i for i in pool if ms[i]["start"] > reg[0]]
                if f:
                    pool = f
                    evidence.append("quote-local")
                else:
                    # 2) otherwise the recipient of the grant
                    f = [i for i in pool if ms[i]["end"] <= reg[0]]
                    if f:
                        pool = f
                        evidence.append("granted-recipient")

        # ---- argument-type rules (narrow, from the bench miss audit)
        if on["argtype"] and atype is None:
            before = text[max(0, rec["start"] - 18):rec["start"]]
            if _COUNTER_ON.search(before):
                f = [i for i in pool if ms[i]["head_type"] in PERMANENTS]
                if f:
                    pool = f
                    evidence.append("counter-target-is-permanent")
            elif _COPY_EXCEPT.search(before):
                f = [i for i in pool if "token" in ms[i]["surface"].lower()]
                if f:
                    pool = f
                    evidence.append("copy-token")
            elif _COPY_OF.search(before):
                f = [i for i in pool if "token" not in ms[i]["surface"].lower()]
                if f:
                    pool = f
                    evidence.append("copy-of-not-the-token")
            elif _DMG_SUBJECT.match(text[rec["end"]:rec["end"] + 22]):
                f = [i for i in pool if ms[i]["head_type"] == "source"]
                if f:
                    pool = f
                    evidence.append("damage-source")

        # ---- "from it" points at a container/player, not the object NP
        if rec["kind"] == "pronoun" and _CONTAINER_LEAD.search(text[max(0, rec["start"] - 10):rec["start"]]):
            f = [i for i in pool if ms[i]["head_type"] in ("player", "opponent")]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("container-player")

        # ---- object of "put": skip NPs that are only PP modifiers
        if rec["kind"] == "pronoun" and _PUT_LEAD.search(
                text[max(0, rec["start"] - 14):rec["start"]]):
            f = [i for i in pool
                 if not _MODIFIER_LEAD.search(
                     text[max(0, ms[i]["start"] - 14):ms[i]["start"]])]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("put-object")

        # ---- direct object of a verb: singular "it" is not a player
        if (rec["kind"] == "pronoun"
                and rec["surface"].lower() in ("it", "its", "it's", "itself")
                and _OBJECT_VERB_LEAD.search(text[max(0, rec["start"] - 18):rec["start"]])):
            f = [i for i in pool if ms[i]["head_type"] not in ("player", "opponent")]
            if f and len(f) != len(pool):
                pool = f
                evidence.append("object-not-player")

        # ---- search "for A or B, reveal it": the teacher convention is the
        # first card NP in the search target, not the last disjunct.
        if rec["kind"] == "pronoun" and rec["surface"].lower() in ("it", "them"):
            si = rec.get("sentence")
            s0 = sents[si][0] if si is not None and si < len(sents) else 0
            before_sentence = text[s0:rec["start"]].lower()
            sp = before_sentence.rfind("search your library for")
            if sp >= 0 and " or " in before_sentence[sp:]:
                f = [i for i in pool
                     if ms[i]["start"] > s0 + sp and ms[i]["head_type"] == "card"]
                if f:
                    pool = [min(f, key=lambda i: ms[i]["start"])]
                    evidence.append("search-or-first")

        # ---- "this creature or another creature ... if it": prefer the named
        # self subject when both are offered as the same trigger source.
        if rec["kind"] == "pronoun":
            si = rec.get("sentence")
            s0 = sents[si][0] if si is not None and si < len(sents) else 0
            if re.search(r"\bor\s+another\s+creature\b", text[s0:rec["start"]], re.I):
                f = [i for i in pool if ms[i].get("is_self")]
                if f and len(f) != len(pool):
                    pool = f
                    evidence.append("self-before-another")

        # ---- plural pronoun with an explicit player subject in the clause
        if rec["kind"] == "pronoun" and rec["surface"].lower() in ("they", "them", "their"):
            si = rec.get("sentence")
            s0 = sents[si][0] if si is not None and si < len(sents) else 0
            if re.search(r"\b(?:players?|opponents?)\b", text[s0:rec["start"]], re.I):
                f = [i for i in pool if ms[i]["head_type"] in ("player", "opponent")]
                if f:
                    pool = f
                    evidence.append("player-subject")

        # ---- created/copied token context
        si = rec.get("sentence")
        s0 = sents[si][0] if si is not None and si < len(sents) else 0
        before = text[s0:rec["start"]].lower()
        token_ctx = ("token" in before and ("create" in before or "copy" in before))
        # Pronouns in the sentence after a token-creation sentence usually still
        # refer to that token ("Create a token ... It gains haste").
        if (not token_ctx and si is not None and si > 0
                and not any(ms[i].get("sentence") == si for i in pool)):
            for back in (1, 2):
                if si - back < 0:
                    break
                p0, p1 = sents[si - back]
                prev = text[p0:p1].lower()
                if "token" in prev and ("create" in prev or "copy" in prev):
                    token_ctx = True
                    break
                if any(ms[i].get("sentence") == si - back for i in pool):
                    break
        if (token_ctx and rec["kind"] == "pronoun"
                and not rec["is_possessive"]):
            f = [i for i in pool
                 if "token" in ms[i]["surface"].lower() or ms[i]["head_type"] == "token"]
            if f:
                pool = f
                evidence.append("created-token")

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
                    elif want == "subject" and not any(ms[i].get("role") for i in pool):
                        # No parse structure cached: the subject is normally the
                        # earliest candidate in the clause ("Each player exiles
                        # the top seven cards of their library").
                        g = [min(pool, key=lambda i: ms[i]["start"])]
                        pool = g
                        evidence.append("possessive-subject-earliest")

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
        if surf in POSSESSIVE or surf in REFLEXIVE:
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
    """Unified entity-aware evaluation (see coref_eval.py)."""
    from coref_eval import load_dataset_cases, evaluate_cases, rule_predictions

    cases = load_dataset_cases(path, require_struct=require_struct)
    stats = evaluate_cases(
        cases, lambda case: rule_predictions(case, rules),
        resolver="rule", verbose=verbose)
    return stats["entity"] / max(1, stats["total"])


def eval_benchmark(path=None, verbose=0, parser=True, rules=None):
    """Unified entity-aware benchmark evaluation (see coref_eval.py).

    `parser` controls the common candidate pool: False/'never' -> regex,
    True/'always'/'auto' -> parser mentions.  Both candidate pools are fixed
    before scoring, so every resolver sees the same mentions.
    """
    from coref_eval import load_bench_cases, evaluate_cases, rule_predictions

    mentions = "regex" if parser is False or parser == "never" else "parser"
    cases, extra = load_bench_cases(path, mentions=mentions)
    stats = evaluate_cases(
        cases, lambda case: rule_predictions(case, rules),
        resolver="rule", verbose=verbose)
    print(f"  skipped={extra['skipped']}  duplicate_cases={extra['duplicate_cases']}")
    return stats["entity"], stats["total"]


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

    off = {r.strip() for r in args.ablate.split(",") if r.strip()}
    ons = {r.strip() for r in args.enable.split(",") if r.strip()}
    rules = {k: False for k in off}
    rules.update({k: True for k in ons})

    if args.eval:
        eval_dataset(args.eval, verbose=args.show_misses, rules=rules,
                     require_struct=args.structured_only)
        return
    if args.bench is not None:
        globals()["TYPE_MODE"] = args.type_mode
        parser = {"always": True, "never": False, "auto": "auto"}[args.parser]
        if args.no_parser:
            parser = False
        eval_benchmark(args.bench or None, verbose=args.show_misses or 20,
                       parser=parser, rules=rules)
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
