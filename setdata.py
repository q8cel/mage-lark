#!/usr/bin/env python3
"""Unified loader for FDN.json (custom) and mtgjson (Standard.json / single set).

Handles two shapes:
  FDN.json            -> data.cards = [ {name, text, types, subtypes, ...}, ... ]
  mtgjson (Standard)  -> data[SET] = { cards: [ {name, oracleText, types, ...} ] }
                         (a single-set file is just one such entry)

Returns:
  items   -> list of (card_name, oracle_text)
  types   -> set of type/subtype/supertype strings (for the interpreter)
  names   -> set of name strings to normalize to '~'
  sets    -> list of set codes present (for reporting)
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# Card names that are also common MTG vocabulary. These must NOT be normalized
# to '~': in ability text the word refers to the common concept (a land type or
# a keyword), not a specific card. E.g. M10 has an enchantment literally named
# "Lifelink" and the basic lands are cards; normalizing them would clobber the
# keyword "lifelink" and walk keywords like "Swampwalk". Only basic lands and
# keywords are excluded (the words that are both real card names AND common
# ability-text vocabulary); ordinary card names still normalize.
_STOPWORDS = {
    # the five basic lands (cards whose names are also land types)
    'plains', 'island', 'swamp', 'mountain', 'forest',
    # real MTG keywords (a card may be named after one)
    'flying', 'first strike', 'double strike', 'trample', 'deathtouch',
    'lifelink', 'reach', 'vigilance', 'haste', 'defender', 'hexproof',
    'indestructible', 'menace', 'prowess', 'infect', 'blight', 'wither',
    'toxic', 'flashback', 'flash', 'ward', 'changeling', 'cumulative',
    'cascade', 'delirium', 'delve', 'enrage', 'evoke', 'exalt', 'exalted',
    'exorcism', 'exert', 'explore', 'foretell', 'fortitude', 'guardian',
    'heroic', 'hellbent', 'highland', 'horizon', 'husk', 'ichor',
    'islandwalk', 'swampwalk', 'forestwalk', 'mountainwalk', 'plainswalk',
    'phasing', 'proliferate', 'landfall', 'morbid', 'annihilate', 'banding',
}


def _is_common_word(name):
    return name.lower() in _STOPWORDS

def _card_fields(c):
    """Yield (name, text, [type strings]) from a card dict of either format."""
    name = c.get('name') or ''
    text = c.get('oracleText') or c.get('text') or ''
    t = []
    for k in ('types', 'subtypes', 'supertypes'):
        t.extend(c.get(k) or [])
    return name, text, t

def load(path):
    d = json.load(open(path))
    data = d['data']
    items, types, names = [], set(), set()
    sets = []

    cards_iter = []
    if isinstance(data.get('cards'), list):
        cards_iter = [( '<fdn>', c) for c in data['cards']]
        sets = ['<fdn>']
    else:
        for code, blk in data.items():
            if isinstance(blk, dict) and isinstance(blk.get('cards'), list):
                sets.append(code)
                for c in blk['cards']:
                    cards_iter.append((code, c))

    for code, c in cards_iter:
        name, text, t = _card_fields(c)
        if not text:
            continue
        names.add(name)
        names.add(name.split(',')[0].strip())
        types.update(t)
        items.append((name, text, code))

    # Drop card names that are common MTG vocabulary so they don't get
    # normalized to '~' and clobber the text.  Besides the curated stopwords
    # (basic lands/keywords), any name that is also a card type/subtype must be
    # excluded.  Important: this applies to *short* names too, e.g. the
    # legendary `Beast, Erudite Aerialist` must not make every `Beast` token a
    # `~` self-reference.
    type_words = {t.lower() for t in types if isinstance(t, str)}
    names = {n for n in names
             if n and n.lower() not in type_words and not _is_common_word(n)}

    for x in ('Legendary', 'Basic', 'Soul', 'Snow', 'Snowman'):
        types.discard(x)
    return items, types, names, sets

_TEXTS = {}


class OffsetMap:
    """Map character spans in normalized text back to the original oracle text.

    Normalization deletes reminder text and collapses whitespace, so the two
    coordinate systems are not interchangeable.  Each normalized character has
    an original `(start, end)` span; a normalized slice maps to the original span
    from its first character's start to its last character's end.
    """

    def __init__(self, text, spans, source_length):
        self.text = text
        self.spans = spans
        self.source_length = source_length

    def __len__(self):
        return len(self.spans)

    def to_original(self, start, end=None):
        """Map normalized half-open `[start, end)` to an original half-open span."""
        if end is None:
            end = start
        if start < 0 or end < start or end > len(self.spans):
            raise ValueError(f"normalized span [{start}, {end}) out of range")
        if start == end:
            if not self.spans:
                return (0, 0)
            if start < len(self.spans):
                p = self.spans[start][0]
            else:
                p = self.spans[-1][1]
            return (p, p)
        return (self.spans[start][0], self.spans[end - 1][1])

    def char_span(self, pos):
        """Original span of one normalized character."""
        return self.spans[pos]

    def to_normalized(self, start, end):
        """Map an original span to the normalized span that overlaps it.

        Returns None if the original span contains no normalized characters
        (e.g. it lies entirely inside stripped reminder text).
        """
        if start < 0 or end < start or end > self.source_length:
            raise ValueError(f"original span [{start}, {end}) out of range")
        if start == end:
            for i, (s, _e) in enumerate(self.spans):
                if s >= start:
                    return (i, i)
            return (len(self.spans), len(self.spans))
        hits = [i for i, (s, e) in enumerate(self.spans)
                if e > start and s < end]
        if not hits:
            return None
        return (hits[0], hits[-1] + 1)


def _char_units(raw):
    return [(ch, i, i + 1) for i, ch in enumerate(raw)]


def _strip_reminder_units(units):
    """`preprocess.strip_reminders`, but carrying source offsets."""
    out = []
    depth = 0
    for ch, start, end in units:
        if ch == '(':
            depth += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append((ch, start, end))

    # `strip_reminders` collapses horizontal whitespace around newlines.
    remove = set()
    for i, (ch, _s, _e) in enumerate(out):
        if ch != '\n':
            continue
        j = i - 1
        while j >= 0 and out[j][0] in ' \t':
            remove.add(j)
            j -= 1
        j = i + 1
        while j < len(out) and out[j][0] in ' \t':
            remove.add(j)
            j += 1
    if remove:
        out = [u for i, u in enumerate(out) if i not in remove]

    # `strip()` at both ends.
    i, j = 0, len(out)
    while i < j and out[i][0].isspace():
        i += 1
    while j > i and out[j - 1][0].isspace():
        j -= 1
    return out[i:j]


def _replace_name_units(units, pattern):
    """`normalize_names`, but replace each match with one mapped `~` unit."""
    if pattern is None or not units:
        return units
    text = ''.join(u[0] for u in units)
    matches = list(pattern.finditer(text))
    if not matches:
        return units
    out, last = [], 0
    for m in matches:
        start, end = m.start(), m.end()
        out.extend(units[last:start])
        out.append(('~', units[start][1], units[end - 1][2]))
        last = end
    out.extend(units[last:])
    return out


def _collapse_line(line):
    i, j = 0, len(line)
    while i < j and line[i][0].isspace():
        i += 1
    while j > i and line[j - 1][0].isspace():
        j -= 1
    out, k = [], i
    while k < j:
        if not line[k][0].isspace():
            out.append(line[k])
            k += 1
            continue
        run_end = k + 1
        while run_end < j and line[run_end][0].isspace():
            run_end += 1
        out.append((' ', line[k][1], line[run_end - 1][2]))
        k = run_end
    return out


def _collapse_units(units):
    """`" ".join(line.split())`, preserving line breaks and offsets."""
    out, line = [], []
    for u in units:
        if u[0] == '\n':
            out.extend(_collapse_line(line))
            line = []
            out.append(u)
        else:
            line.append(u)
    out.extend(_collapse_line(line))
    return out


def normalize_with_map(raw, names=None):
    """Canonical text plus an `OffsetMap` back to `raw`.

    This is the canonical normalizer.  The output text is identical to the old
    `normalize_text`; the map is what lets callers translate spans to the
    original oracle text instead of repairing them by surface matching.
    """
    from preprocess import name_pattern
    units = _strip_reminder_units(_char_units(raw))
    units = _replace_name_units(units, name_pattern(names))
    units = _collapse_units(units)
    text = ''.join(u[0] for u in units)
    return text, OffsetMap(text, [(u[1], u[2]) for u in units], len(raw))


def normalize_text(raw, names=None):
    """Canonical text form: reminders stripped, card names masked to `~`,
    spaces collapsed **but line breaks preserved**.

    Preserving the newline is what keeps ability boundaries: oracle text puts one
    ability per line, and collapsing them merges e.g. `Trample, haste` with the
    `When this Vehicle enters, ...` trigger that follows it, which then parses as
    neither.  Use `normalize_with_map` when you also need original offsets.
    """
    return normalize_with_map(raw, names)[0]


def card_text(name, path=None):
    """Normalized oracle text for `name` (see `normalize_text`). Cached per data
    file. Torch-free, so the deterministic coref path never imports resolve.py."""
    path = path or os.path.join(BASE, 'FDN.json')
    if path not in _TEXTS:
        items, _, names, _ = load(path)
        by_name = {}
        for n, t, _code in items:
            if not t:
                continue
            # Normalize the card's own name even when it collides with a
            # type/subtype word (e.g. the short name "Chandra").  The global
            # name set excludes type words to protect ordinary type text; the
            # card's own text should still use `~`.
            own = {x for x in (n, n.split(',')[0].strip())
                   if x and not _is_common_word(x)}
            by_name[n] = normalize_text(t, names | own)
        _TEXTS[path] = by_name
    d = _TEXTS[path]
    if name in d:
        return d[name]
    low = name.lower()
    for k, v in d.items():
        if k.lower() == low:
            return v
    return None


# backward-compatible loader (items as 2-tuples)
def load3(path):
    items, types, names, _ = load(path)
    return [(n, t) for n, t, _ in items], types, names
