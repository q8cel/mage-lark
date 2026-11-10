"""Regex candidate-mention extraction (torch-free).

Kept separate from resolve.py so data-builders / the LLM labeler can use it
without importing torch or loading any model.

`candidate_mentions(text, parser=True)` unions these regex mentions with the
grammar-based mentions from pmentions.py (card_target/player/token nodes), which
captures coordinated, hyphenated/negated and embedded-object NPs the regex misses.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import re

HEADS = (
    r"creatures?|tokens?|cards?|permanents?|lands?|artifacts?|equipment|"
    r"enchantments?|spells?|planeswalkers?|players?|opponents?|piles?|sources?|"
    r"objects?|auras?|counters?"
)
DET = (r"one or more|this|that|these|those|the|a|an|another|each|all|other|target|any|no|"
       r"enchanted|equipped|attacking|blocking|tapped|untapped|chosen|"
       r"revealed|exiled|sacrificed|discarded|returned|created|milled|"
       r"blocked|unblocked|face-up|face-down")
# intervening modifiers: alphabetic words only (no commas / clause punctuation),
# at most two, so spans don't swallow clause boundaries.
_MID = r"(?:[A-Za-z][\w'\-]*[ \t]+){0,2}"
CAND = re.compile(
    rf"(?:~'s)|(?:~)|\b(?:{DET})[ \t]+{_MID}(?:{HEADS})\b|\bthe rest\b",
    re.I,
)
# Player NPs are often embedded in a larger permanent NP ("all creatures
# target player controls"); capture them separately so "that player" can bind
# to the player, not to the creature collection.
PLAYER_CAND = re.compile(
    rf"\b(?:{DET}|your|our|their|defending|attacking|active)\s+"
    rf"(?:players?|opponents?)\b", re.I)
OWNER_CAND = re.compile(
    r"\b(?:its|their|his|her|target \w+'s|target [A-Z][\w'\-]*'s|each \w+'s)\s+owners?\b", re.I)
CONTROLLER_CAND = re.compile(
    rf"\b(?:{DET}|its|their)\s+(?:[A-Za-z][\w'\-]*\s+){{0,2}}controllers?\b", re.I)
# A spell/ability is often embedded in a larger event NP ("the target of a
# spell"); keep the inner NP so "that spell" has a real antecedent.
LIST_CAND = re.compile(
    r"\b(?:a|an|the|target|another|each|any|no|one or more)\s+"
    r"(?:[A-Za-z][\w'\-]*\s*,\s*)+"
    r"(?!(?:destroy|exile|return|sacrifice|put|draw|discard|mill|create|target|"
    r"deal|deals|damage|gain|lose|tap|untap|counter|reveal|search|shuffle|"
    r"attach|choose|remove|add|copy|cast|play|scry|surveil|fight|become|"
    r"get|gets|has|have|is|are|was|were|can|cannot|can't|with|from|into|onto|"
    r"to|and|or|this|that|these|those|the|a|an)\b)"
    r"(?:[A-Za-z][\w'\-]*\s+){0,3}"
    r"(?:cards?|creatures?|permanents?|spells?|artifacts?|enchantments?|"
    r"lands?|planeswalkers?|tokens?)\b", re.I)
COLOR_CARD_CAND = re.compile(
    r"\b(?:a|an|the|target|another|each|any)\s+"
    r"(?:white|blue|black|red|green|colorless)"
    r"(?:\s+(?:or|and/or)\s+(?:white|blue|black|red|green|colorless))+"
    r"\s+(?:creature|permanent|artifact|enchantment|land|planeswalker|"
    r"instant|sorcery|card)\s+cards?\b", re.I)
UP_TO_CAND = re.compile(
    r"\bup to (?:X|\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:[A-Za-z][\w'\-]*\s+){0,2}"
    r"(?:cards?|creatures?|permanents?|lands?|artifacts?|enchantments?|spells?|"
    r"planeswalkers?|tokens?)\b", re.I)
TYPE_CARD_CAND = re.compile(
    r"\b(?:all|target|each|another|a|an|the|any)\s+"
    r"(?:artifact|creature|enchantment|land|permanent|planeswalker|instant|sorcery)"
    r"(?:\s*(?:,|and|or)\s*(?:artifact|creature|enchantment|land|permanent|"
    r"planeswalker|instant|sorcery))+"
    r"\s+cards?\b", re.I)
ZONE_CAND = re.compile(
    r"\b(?:your|their|its|his|her|our|my|a player's|target player's|target opponent's)\s+"
    r"(?:hands?|graveyards?|librar(?:y|ies)|exile|battlefield)\b", re.I)
BARE_ZONE_CAND = re.compile(
    r"\b(?:a|an|the|each|target)\s+"
    r"(?:hands?|graveyards?|librar(?:y|ies)|battlefield|exile)\b", re.I)
SPELL_CAND = re.compile(
    r"\b(?:a|an|the|that|this|those|these)\s+"
    r"(?:(?:[A-Za-z][\w'\-]*\s+)?(?:instant|sorcery)\s+(?:or|and/or)\s+(?:instant|sorcery)\s+)?"
    r"(?:[A-Za-z][\w'\-]*\s+){0,2}(?:spells?|abilit(?:y|ies))\b", re.I)
# "an instant or sorcery card" / "target red instant or sorcery card": the
# regular 0-2 modifier window is too short for the disjunction.
# Bare plural after "with"/"controls" is an event collection ("attacks with
# creatures", "two or more of those creatures").
BARE_COLLECTION = re.compile(
    r"\b(?:with|control(?:s)?|mills?|exiles?|reveals?|discards?|draws?)\s+"
    r"((?:[A-Za-z0-9]+\s+)?"
    r"(?:creatures|permanents|cards|lands|artifacts|enchantments|spells|tokens))\b",
    re.I)
STATUS_NAME = re.compile(r"\b(?:Enchanted|Equipped)\s+[A-Z][\w'\-]+\b")
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
    for m in OWNER_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in CONTROLLER_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in LIST_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in COLOR_CARD_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in UP_TO_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in TYPE_CARD_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in ZONE_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in BARE_ZONE_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in SPELL_CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
    for m in STATUS_NAME.finditer(text):
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
    # A comma list after "choose" is often the selected card ("a
    # noncreature, nonland card").  Expose that NP so a following "that card"
    # can bind to it; do not add every list to every candidate pool.
    try:
        from lists import capture as _capture_lists
        for st, en, _obj in _capture_lists(text):
            prefix = text[max(0, st - 24):st].lower()
            if re.search(r"\bchooses?\s+$", prefix):
                s = text[st:en].strip()
                if s:
                    out.append({"surface": s, "start": st, "end": en})
    except Exception:
        pass
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
