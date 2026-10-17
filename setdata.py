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

def _extract(data):
    """Return (cards_iter, sets) regardless of shape."""
    if isinstance(data.get('cards'), list):
        # FDN style: data.cards directly
        return data['cards'], ['<single>']
    # mtgjson: data[SET].cards
    sets = []
    for code, blk in data.items():
        if isinstance(blk, dict) and isinstance(blk.get('cards'), list):
            sets.append(code)
    return sets

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

    # drop card names that are common MTG words (basic lands / keywords) so
    # they don't get normalized to '~' and clobber the common vocabulary
    names = {n for n in names if n and not _is_common_word(n)}

    for x in ('Legendary', 'Basic', 'Soul', 'Snow', 'Snowman'):
        types.discard(x)
    return items, types, names, sets

_TEXTS = {}


def card_text(name, path=None):
    """Normalized oracle text for `name`: reminders stripped, card names masked
    to `~`, whitespace collapsed. Cached per data file. Torch-free, so the
    deterministic coref path can use it without importing resolve.py."""
    path = path or os.path.join(BASE, 'FDN.json')
    if path not in _TEXTS:
        from preprocess import normalize_names, strip_reminders
        items, _, names, _ = load(path)
        _TEXTS[path] = {
            n: ' '.join(normalize_names(strip_reminders(t), names).split())
            for n, t, _ in items if t
        }
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
