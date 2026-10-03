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
    seen = set()
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
        key = (name, text)
        if key in seen:
            continue
        seen.add(key)
        names.add(name)
        names.add(name.split(',')[0].strip())
        types.update(t)
        items.append((name, text))

    for x in ('Legendary', 'Basic', 'Soul', 'Snow', 'Snowman'):
        types.discard(x)
    return items, types, names, sets

# backward-compatible 3-tuple loader
def load3(path):
    items, types, names, _ = load(path)
    return items, types, names
