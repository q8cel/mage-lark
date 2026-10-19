"""Mention inventory: spans + the annotations the deterministic resolver needs.

Layers, all torch-free and JSON-friendly:

    text ──► raw candidates (regex ∪ parse-tree spans)      [mentions.py]
         ──► clean()   maximal spans, deduped, no bare determiner junk
         ──► annotate()  head_type, number, definiteness, self/target flags,
                         sentence + clause index

Why the cleaning matters (measured on 3,403 labelled occurrences): 8% of raw
candidates are nested inside another candidate and 10% are duplicate surfaces
within the same card. Cleaning them alone was worth ~8 accuracy points.

This module deliberately does NOT read `interpret.py` output: with the parser's
default `keep_all_tokens=False` an anaphor token such as the `it` in `Exile it`
is dropped from the tree entirely (the `card_target` node comes back empty), so
the semantic form is lossy exactly where the anaphors are.

Usage:
    python refs.py --card "Fiery Annihilation"
"""
import argparse
import re
import sys

BASE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, BASE)

from preprocess import split_sentences
from mentions import candidate_mentions
from anaphora import find_anaphors, PRONOUNS

# ---------------------------------------------------------------- type lattice
# Most specific first: the FIRST matching type wins for a surface.
TYPE_ORDER = (
    "equipment", "aura", "planeswalker", "battle", "creature", "token",
    "permanent", "card", "spell", "land", "artifact", "enchantment",
    "player", "opponent", "source", "object", "pile", "counter",
)
_TYPE_RE = {t: re.compile(rf"\b{t}s?\b", re.I) for t in TYPE_ORDER}

# `a` may be referred to by `b` (candidate type b is compatible with anaphor
# head type a). Entity types are a lattice: a creature is a permanent is a card.
LATTICE = {
    "creature":    {"creature", "token", "permanent", "card", "object", "source"},
    "token":       {"token", "creature", "permanent", "card", "object"},
    "equipment":   {"equipment", "artifact", "permanent", "card", "object"},
    "artifact":    {"artifact", "permanent", "card", "object"},
    "enchantment": {"enchantment", "permanent", "card", "object"},
    "aura":        {"aura", "enchantment", "permanent", "card", "object"},
    "land":        {"land", "permanent", "card", "object"},
    "planeswalker": {"planeswalker", "permanent", "card", "object"},
    "battle":      {"battle", "permanent", "card", "object"},
    "permanent":   {"permanent", "card", "object"},
    "card":        {"card", "object"},
    "spell":       {"spell", "object"},
    "player":      {"player", "opponent"},
    "opponent":    {"opponent", "player"},
    "source":      {"source", "object"},
    "object":      {"object"},
    "pile":        {"pile"},
    "counter":     {"counter"},
}

# Heads that can never be a pronoun's antecedent (the pronoun refers to an
# object, not to a counter or an amount).
NON_ENTITY = {"counter"}

SELF_RE = re.compile(
    r"^(~|this\s+(creature|artifact|enchantment|land|permanent|planeswalker|"
    r"battle|token|spell|equipment|aura|card|object))$", re.I)

DEFINITE = {"~", "the", "this", "that", "those", "these"}
INDEFINITE = {"a", "an", "another", "each", "every", "any", "no", "some"}
PLURAL_DET = {"those", "these", "they", "them", "their", "theirs", "themselves",
              "all", "both", "each", "every", "any", "two", "three", "four",
              "five", "six", "seven", "eight", "nine", "ten"}
DET_JUNK = re.compile(
    r"^(target|that|this|those|these|the|a|an|another|each|every|all|other|"
    r"any|no|some|both|one|two|three)$", re.I)

CLAUSE_SEP = re.compile(r"[,;:]\s+|\s+\u2014\s+|\s+--\s+")


# ------------------------------------------------------------------ annotation
def surface_head(surface):
    """Last type word in the surface, or None."""
    best, best_pos = None, -1
    low = surface.lower()
    for t in TYPE_ORDER:
        for m in _TYPE_RE[t].finditer(low):
            if m.start() > best_pos:
                best, best_pos = t, m.start()
    return best


def head_type(surface):
    """Type of the mention, by specificity order (equipment beats artifact)."""
    low = surface.lower()
    for t in TYPE_ORDER:
        if _TYPE_RE[t].search(low):
            return t
    return None


# Pronouns carry their number intrinsically; the "ends with s" heuristic below
# must not touch them. It classified `its` as plural (and would mis-handle any
# future word ending in -s), which silently broke every singular possessive.
PRONOUN_NUMBER = {
    "it": "sg", "its": "sg", "it's": "sg", "itself": "sg",
    "they": "pl", "them": "pl", "their": "pl", "theirs": "pl",
    "themselves": "pl",
}


def number(surface):
    """'pl' / 'sg' / None (unknown)."""
    w = surface.lower().replace("\u2019", "'").split()
    if not w:
        return None
    if len(w) == 1 and w[0] in PRONOUN_NUMBER:
        return PRONOUN_NUMBER[w[0]]
    # Distributive determiners agree plurally for anaphora ("Each player ...
    # their library"), so they must be checked before the head noun: "Each
    # player" is not singular just because "player" has no -s.
    if w[0] in PLURAL_DET:
        return "pl"
    ht = head_type(surface)
    if ht:
        return "pl" if re.search(rf"\b{ht}s\b", surface.lower()) else "sg"
    return "pl" if w[-1].endswith("s") and not w[-1].endswith("ss") else "sg"


def definiteness(surface):
    w = surface.lower().split()
    if not w:
        return None
    if surface.strip() == "~" or w[0] in DEFINITE:
        return "def"
    if w[0] in INDEFINITE:
        return "indef"
    return None


def is_self(surface):
    return bool(SELF_RE.match(surface.strip()))


def is_target(surface):
    return bool(re.search(r"\btarget\b", surface, re.I))


def is_pronoun_span(surface):
    return surface.lower().replace("\u2019", "'") in PRONOUNS


def type_compatible(anaphor_type, candidate_type):
    if anaphor_type is None or candidate_type is None:
        return True
    return candidate_type in LATTICE.get(anaphor_type, {anaphor_type})


def type_expected(expected, candidate_type):
    """Inverse direction of the lattice: a mention of `candidate_type` can be the
    thing the predicate expects (`expects('card', 'creature')` is True, because a
    creature is a card). Used for verb priors."""
    if expected is None or candidate_type is None:
        return True
    return candidate_type == expected or expected in LATTICE.get(candidate_type, set())


# Verbs that constrain what their argument can be. Everything else is neutral.
VERB_TYPE = {
    "die": "permanent", "dies": "permanent", "died": "permanent",
    "sacrifice": "permanent", "sacrifices": "permanent",
    "sacrificed": "permanent",
    "cast": "spell", "casts": "spell", "countered": "spell",
    "attach": "equipment", "attached": "equipment", "equip": "equipment",
    "create": "token", "creates": "token", "created": "token",
    "draw": "card", "draws": "card", "drawn": "card",
    "mill": "card", "mills": "card", "milled": "card",
    "exile": "card", "exiles": "card", "exiled": "card",
    "return": "card", "returns": "card", "returned": "card",
    "discard": "card", "discards": "card", "discarded": "card",
    "reveal": "card", "reveals": "card", "revealed": "card",
    "control": "permanent", "controls": "permanent",
    "enters": "permanent", "leaves": "permanent",
}
_VERB_RE = re.compile(
    r"\b(" + "|".join(sorted(VERB_TYPE, key=len, reverse=True)) + r")\b", re.I)


def predicate_type(text, start, end):
    """Type implied by the verb governing `text[start:end]` (or None).

    Looks inside the anaphor's own clause and takes the nearest verb *before* it,
    falling back to the first verb in the clause. Deliberately conservative: a
    wrong prior is worse than no prior, so callers must treat this as a soft
    filter that is ignored when it would empty the candidate pool.
    """
    si, ci = None, None
    for k, (a, b) in enumerate(sentence_spans(text)):
        if a <= start < b:
            si = (a, b)
            for c_i, (ca, cb) in enumerate(clause_spans(text, a, b)):
                if ca <= start < cb:
                    ci = (ca, cb)
                    break
            break
    if ci is None:
        ci = si or (0, len(text))
    clause = text[ci[0]:ci[1]]
    before, after = [], []
    for m in _VERB_RE.finditer(clause):
        gstart = ci[0] + m.start()
        (before if gstart < start else after).append((gstart, m.group(0)))
    if before:
        return VERB_TYPE[before[-1][1].lower()]
    if after:
        return VERB_TYPE[after[0][1].lower()]
    return None


# ---------------------------------------------------------------- text layout
def sentence_spans(text):
    """[(start, end)] for each sentence, in order.

    Line breaks are sentence boundaries: oracle text puts one ability per line,
    and `setdata.normalize_text` preserves the newline for exactly this reason.
    """
    out = []
    pos = 0
    for line in text.split("\n"):
        start = pos
        pos += len(line) + 1
        if not line.strip():
            continue
        cur = start
        for s in split_sentences(line):
            i = text.find(s, cur)
            if i < 0:
                i = cur
            out.append((i, i + len(s)))
            cur = i + len(s)
    if not out:
        out = [(0, len(text))]
    return out


def clause_spans(text, s_start, s_end):
    """[(start, end)] for the comma/semicolon-separated clauses of a sentence."""
    out, cur = [], s_start
    for m in CLAUSE_SEP.finditer(text, s_start, s_end):
        out.append((cur, m.start()))
        cur = m.end()
    out.append((cur, s_end))
    return [(a, b) for a, b in out if b > a]


# ------------------------------------------------------------------- pipeline
def clean(cands):
    """Maximal, de-duplicated, junk-free candidate list.

    Keeps `src` (the index in the input list) so callers can map decisions back
    to their own numbering.
    """
    tagged = []
    for i, c in enumerate(cands):
        surf = (c.get("surface") or "").strip()
        if not surf or DET_JUNK.match(surf):
            continue
        tagged.append((i, c["start"], c["end"], surf))
    kept = []
    for i, s, e, surf in tagged:
        dominated = any(
            k != i and s2 <= s and e <= e2 and (s2, e2) != (s, e)
            for k, s2, e2, _ in tagged)
        if dominated:
            continue
        if any(s2 == s and e2 == e for _, s2, e2, _ in kept):
            continue
        kept.append((i, s, e, surf))
    kept.sort(key=lambda t: (t[1], -(t[2] - t[1])))
    return [{"surface": surf, "start": s, "end": e, "src": i}
            for i, s, e, surf in kept]


def annotate(text, mentions, struct=None):
    """Add head_type / number / definiteness / flags / sentence / clause.

    If `struct` (pstruct records for this text) is given, mentions also carry
    `role` (subject/object), `verb`, `predicate` (copula complement) and
    `in_condition`, taken from the parse tree.
    """
    sents = sentence_spans(text)
    out = []
    for m in mentions:
        s = m["start"]
        si, cl = None, None
        for k, (a, b) in enumerate(sents):
            if a <= s < b:
                si = k
                for c_i, (ca, cb) in enumerate(clause_spans(text, a, b)):
                    if ca <= s < cb:
                        cl = c_i
                        break
                break
        surf = m["surface"]
        rec = dict(m)
        rec.update({
            "head_type": head_type(surf),
            "number": number(surf),
            "definiteness": definiteness(surf),
            "is_self": is_self(surf),
            "is_target": is_target(surf),
            "is_pronoun": is_pronoun_span(surf),
            "sentence": si,
            "clause": cl,
        })
        if struct:
            hit = None
            for r in struct:
                if r["start"] <= s and s < r["end"]:
                    if hit is None or (r["end"] - r["start"]) < (hit["end"] - hit["start"]):
                        hit = r
            rec["role"] = hit["role"] if hit else None
            rec["verb"] = hit["verb"] if hit else None
            rec["predicate"] = bool(hit["predicate"]) if hit else False
            rec["in_condition"] = bool(hit["in_condition"]) if hit else False
        out.append(rec)
    return out


def build(text, parser=True, struct=None):
    """Live inventory for a card text (regex ∪ parse-tree spans, then clean)."""
    raw = candidate_mentions(text, parser=parser)
    return annotate(text, clean(raw), struct=struct)


def anaphor_mentions(text, annotate_them=True):
    """Anaphor occurrences as mention-shaped dicts (so they can join the graph)."""
    anas = find_anaphors(text)
    if not annotate_them:
        return anas
    return annotate(text, anas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    ap.add_argument("--data", default=None)
    ap.add_argument("--no-parser", action="store_true")
    ap.add_argument("--raw", action="store_true", help="show pre-clean candidates")
    args = ap.parse_args()

    from setdata import card_text
    text = card_text(args.card, args.data)
    if not text:
        print("card not found")
        return
    print(text)
    if args.raw:
        cands = candidate_mentions(text, parser=not args.no_parser)
        print(f"\nraw candidates ({len(cands)}):")
        for i, c in enumerate(cands):
            print(f"  [{i:2}] {c['start']:3}-{c['end']:3} {c['surface']!r}")
    ms = build(text, parser=not args.no_parser)
    print(f"\ninventory ({len(ms)}):")
    for m in ms:
        print(f"  {m['start']:3}-{m['end']:3} {m['surface']!r:<34} "
              f"type={str(m['head_type']):<10} num={str(m['number']):<3} "
              f"def={str(m['definiteness']):<5} s={m['sentence']} c={m['clause']}"
              f"{' TARGET' if m['is_target'] else ''}{' SELF' if m['is_self'] else ''}")
    print("\nanaphors:")
    for a in find_anaphors(text):
        print(f"  {a['start']:3}-{a['end']:3} {a['surface']!r:<20} {a['kind']}")


if __name__ == "__main__":
    main()
