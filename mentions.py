"""Regex candidate-mention extraction (torch-free).

Kept separate from resolve.py so data-builders / the LLM labeler can use it
without importing torch or loading any model.

`candidate_mentions(text, parser=True)` unions these regex mentions with the
grammar-based mentions from pmentions.py (card_target/player/token nodes), which
captures coordinated, hyphenated/negated and embedded-object NPs the regex misses.
"""
import re

HEADS = (
    r"creatures?|tokens?|cards?|permanents?|lands?|artifacts?|equipment|"
    r"enchantments?|spells?|planeswalkers?|players?|opponents?|piles?|sources?|"
    r"objects?|auras?|counters?"
)
DET = (r"this|that|these|those|the|a|an|another|each|all|other|target|any|no|"
       r"enchanted|equipped|attacking|blocking|tapped|untapped|chosen|"
       r"revealed|exiled|sacrificed|discarded|returned|created|milled|"
       r"blocked|unblocked|face-up|face-down")
# intervening modifiers: alphabetic words only (no commas / clause punctuation),
# at most two, so spans don't swallow clause boundaries.
_MID = r"(?:[A-Za-z][\w'\-]*\s+){0,2}"
CAND = re.compile(
    rf"(?:~'s)|(?:~)|\b(?:{DET})\s+{_MID}(?:{HEADS})\b|\bthe rest\b",
    re.I,
)
# Player NPs are often embedded in a larger permanent NP ("all creatures
# target player controls"); capture them separately so "that player" can bind
# to the player, not to the creature collection.
PLAYER_CAND = re.compile(
    rf"\b(?:{DET}|your|our|their|defending|attacking|active)\s+"
    rf"(?:players?|opponents?)\b", re.I)
CONTROLLER_CAND = re.compile(
    rf"\b(?:{DET}|its|their)\s+(?:[A-Za-z][\w'\-]*\s+){{0,2}}controllers?\b", re.I)
# A spell/ability is often embedded in a larger event NP ("the target of a
# spell"); keep the inner NP so "that spell" has a real antecedent.
SPELL_CAND = re.compile(
    r"\b(?:a|an|the|that|this|those|these)\s+"
    r"(?:(?:[A-Za-z][\w'\-]*\s+)?(?:instant|sorcery)\s+(?:or|and/or)\s+(?:instant|sorcery)\s+)?"
    r"(?:[A-Za-z][\w'\-]*\s+){0,2}(?:spells?|abilities?)\b", re.I)
# "an instant or sorcery card" / "target red instant or sorcery card": the
# regular 0-2 modifier window is too short for the disjunction.
# Bare plural after "with"/"controls" is an event collection ("attacks with
# creatures", "two or more of those creatures").
BARE_COLLECTION = re.compile(
    r"\b(?:with|control(?:s)?)\s+"
    r"(creatures|permanents|cards|lands|artifacts|enchantments|spells|tokens)\b",
    re.I)
INSTANT_SORCERY_SPELL = re.compile(
    r"\b(?:a|an|the|that|this|those|these|target)\s+"
    r"(?:[A-Za-z][\w'\-]*\s+){0,2}"
    r"(?:instant|sorcery)\s+(?:or|and/or)\s+(?:instant|sorcery)\s+spells?\b",
    re.I)
INSTANT_SORCERY_CARD = re.compile(
    r"\b(?:a|an|the|that|this|those|these|target)\s+"
    r"(?:[A-Za-z][\w'\-]*\s+){0,2}"
    r"(?:instant|sorcery)\s+(?:or|and/or)\s+(?:instant|sorcery)\s+cards?\b",
    re.I)


def _regex_mentions(text):
    """Ordered, de-duplicated candidate mention spans in `text`."""
    out = []
    for m in CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in PLAYER_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in CONTROLLER_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in SPELL_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in INSTANT_SORCERY_SPELL.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in INSTANT_SORCERY_CARD.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in BARE_COLLECTION.finditer(text):
        # Keep only the plural noun, not the introducing preposition/verb.
        s = m.group(1)
        st = m.start(1)
        out.append({"surface": s, "start": st, "end": st + len(s)})
    return out


def _dedup(ms):
    seen = set()
    uniq = []
    for c in sorted(ms, key=lambda m: (m["start"], -(m["end"] - m["start"]))):
        k = (c["start"], c["end"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    return uniq


def candidate_mentions(text, parser=False):
    """Candidate mention spans. `parser=True` adds grammar-based mentions.

    Bare pronouns (the parser surfaces them as card_target nodes) are dropped:
    an entity mention can never be a bare pronoun.
    """
    out = _regex_mentions(text)
    if parser:
        try:
            from pmentions import parser_mentions
            out = out + parser_mentions(text)
        except Exception:
            pass
    uniq = _dedup(out)
    try:
        from anaphora import PRONOUNS
    except Exception:
        return uniq
    return [c for c in uniq
            if c["surface"].lower().replace("\u2019", "'") not in PRONOUNS]
