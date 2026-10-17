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
DET = r"this|that|these|those|the|a|an|another|each|all|other|target|any|no"
# intervening modifiers: alphabetic words only (no commas / clause punctuation),
# at most two, so spans don't swallow clause boundaries.
_MID = r"(?:[A-Za-z][\w'\-]*\s+){0,2}"
CAND = re.compile(
    rf"(?:~)|(?:~'s)|\b(?:{DET})\s+{_MID}(?:{HEADS})\b|\bthe rest\b",
    re.I,
)


def _regex_mentions(text):
    """Ordered, de-duplicated candidate mention spans in `text`."""
    out = []
    for m in CAND.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append({"surface": s, "start": m.start(), "end": m.end()})
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
