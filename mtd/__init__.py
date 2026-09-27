#!/usr/bin/env python3
"""Load FDN.json: extract card names, creature/card types, and oracle lines."""
import json, re, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDN = os.path.join(BASE, 'FDN.json')

_data = None

def load_cards():
    global _data
    if _data is not None:
        return _data
    d = json.load(open(FDN))
    cards = d['data']['cards']
    _data = {
        'cards': cards,
        'names': sorted({c['name'] for c in cards}),
        'short_names': sorted({n.split(',')[0].strip() for c in cards for n in [c['name']]}),
    }
    return _data

def name_set():
    """Set of strings (full + short names) to replace with ~."""
    d = load_cards()
    s = set()
    for n in d['names']:
        s.add(n)
        s.add(n.split(',')[0].strip())
    return s

def card_type_set():
    """Set of all creature types + card types + supertypes appearing in the set."""
    d = load_cards()
    types = set()
    for c in d['cards']:
        types.update(c.get('types') or [])
        types.update(c.get('subtypes') or [])
        types.update(c.get('supertypes') or [])
    # drop basic card-type words that clash with grammar keywords
    types.discard('Legendary')
    types.discard('Basic')
    types.discard('Soul')
    types.discard('Snow')
    types.discard('Snowman')
    return types

def all_oracle_text():
    d = load_cards()
    return [ (c['name'], c.get('text') or '') for c in d['cards'] ]
