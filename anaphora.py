"""Lexical anaphor detection.

The grammar/interpreter only surfaces a pronoun when it lands in a typed slot
(card_kind), so its `ref:anaphora` field is a partial, slot-dependent signal.
Anaphora resolution needs the COMPLETE list of anaphoric occurrences in the
text, independent of parse structure. This module scans raw text and returns
every anaphor occurrence with an exact span.

Deterministic, no model, no parse. JSON-friendly output so it can sit behind a
plain interface (future C++/Rust/Go port).
"""
import re

from mentions import HEADS

# Bare pronouns (+ contractions / possessives) that refer to an entity.
PRONOUNS = {
    "it", "its", "it's",
    "they", "them", "their", "theirs",
    "itself", "themselves",
}

# Multiword anaphoric expressions (definite reference to a previously
# introduced set/entity). Kept separate so callers can toggle them.
PHRASES = {
    "the rest",
}

# Demonstrative determiners + a head noun (e.g. "that creature", "those
# cards"). "this" is excluded by default: "this creature"/"this artifact"
# normally names the card itself, not a previous mention.
DEMONSTRATIVE_DET = "that|those|these"

# Single regex, longest alternatives first so "it's"/"its" win over "it".
_PRON_RE = re.compile(
    r"\b(?:it['\u2019]s|its|it|they|them|their|theirs|itself|themselves)\b",
    re.I,
)
_PHRASE_RE = re.compile(r"\bthe rest\b", re.I)
_DEM_RE = re.compile(
    rf"\b(?:{DEMONSTRATIVE_DET})\s+(?:[\w,'\-]+\s+){{0,2}}(?:{HEADS})\b",
    re.I,
)


def find_anaphors(text, phrases=True, demonstratives=True):
    """Return every anaphor occurrence in `text`, in order of appearance.

    Each entry: {"surface", "start", "end", "kind"} where kind is one of
    "pronoun", "phrase", "demonstrative". Overlapping matches are resolved by
    keeping the earliest-starting, longest match.
    """
    hits = []
    for m in _PRON_RE.finditer(text):
        hits.append((m.start(), m.end(), m.group(0), "pronoun"))
    if phrases:
        for m in _PHRASE_RE.finditer(text):
            hits.append((m.start(), m.end(), m.group(0), "phrase"))
    if demonstratives:
        for m in _DEM_RE.finditer(text):
            hits.append((m.start(), m.end(), m.group(0), "demonstrative"))
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out = []
    last_end = -1
    for start, end, surface, kind in hits:
        if start < last_end:  # overlap: keep the first
            continue
        last_end = end
        out.append({"surface": surface, "start": start, "end": end, "kind": kind})
    return out


def count_by_surface(text):
    """Convenience: {lowercased surface: count} for quick inspection."""
    c = {}
    for a in find_anaphors(text):
        k = a["surface"].lower().replace("\u2019", "'")
        c[k] = c.get(k, 0) + 1
    return c


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        s = sys.argv[1]
    else:
        s = ("This creature enters with eight revival counters on it if you cast "
             "it. When this creature dies, if it had a revival counter on it, "
             "return it to the battlefield with one fewer revival counter on it.")
    for i, a in enumerate(find_anaphors(s)):
        print(f"[{i}] {a['surface']!r:8} {a['start']:3}-{a['end']:3}  {a['kind']}")
