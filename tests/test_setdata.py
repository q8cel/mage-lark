#!/usr/bin/env python3
"""Tests for `setdata.load`: printing rows, set codes, and `dedupe_printings`."""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

from setdata import load, load_cards, normalize_text


def check(name, fn):
    fn()
    print(f"  PASS {name}")


def t_fdn_rows_carry_set_code():
    items, _types, _names, sets = load('FDN.json')
    assert sets == ['FDN'], sets
    assert items, 'FDN corpus is empty'
    for _name, _text, code in items:
        assert code == 'FDN', code
    cards, _ct, _cn, _cs = load_cards('FDN.json')
    for card in cards:
        assert set(card) == {'name', 'text', 'set_code', 'collector_number'}
        assert card['set_code'] == 'FDN'
        assert card['collector_number'], card


def t_mtgjson_rows_carry_printing_set_code():
    items, _types, _names, sets = load('classic.json')
    codes = {code for _n, _t, code in items}
    assert codes <= set(sets), (sorted(codes - set(sets))[:5], sets[:5])
    # Rows are ordered by printing, not by set: each row keeps its own code.
    cards, _ct, _cn, _cs = load_cards('classic.json')
    assert {c['set_code'] for c in cards} == codes
    assert all(c['collector_number'] for c in cards)


def t_default_keeps_every_printing():
    items, types, names, sets = load('FDN.json')
    cards, _ct, _cn, _cs = load_cards('FDN.json')
    assert len(items) == len(cards)
    plains = [c for c in cards if c['name'] == 'Plains']
    assert len(plains) > 1, len(plains)
    assert len({c['collector_number'] for c in plains}) == len(plains)
    # The loader's vocabulary is independent of de-duplication.
    deduped, dtypes, dnames, dsets = load('FDN.json', dedupe_printings=True)
    assert (types, names, sets) == (dtypes, dnames, dsets)


def t_dedupe_collapses_identical_text():
    items, _types, names, _sets = load('FDN.json')
    deduped, _dtypes, _dnames, _dsets = load('FDN.json', dedupe_printings=True)
    assert len(deduped) < len(items)
    # A duplicate is exactly a repeated (name, normalized text) key.
    keys = [(n, normalize_text(t, names)) for n, t, _c in items]
    assert len(deduped) == len(set(keys))
    dkeys = [(n, normalize_text(t, names)) for n, t, _c in deduped]
    assert len(dkeys) == len(set(dkeys))
    # ...and rows keep the corpus order of the winning printing.
    assert [n for n, _t, _c in deduped] == list(dict.fromkeys(n for n, _t, _c in items))


def t_dedupe_winner_rule():
    # Alphabetically first set code, then numerically smallest collector number.
    cards, _ct, _cn, _cs = load_cards('FDN.json', dedupe_printings=True)
    plains = [c for c in cards if c['name'] == 'Plains']
    assert len(plains) == 1, plains
    assert plains[0]['set_code'] == 'FDN'
    assert plains[0]['collector_number'] == '272', plains[0]
    # Cards that differ only by name are never merged (masked text alone would
    # collapse every vanilla `Flying` creature into one).
    classic, _ct2, _cn2, _cs2 = load_cards('classic.json', dedupe_printings=True)
    by_name = {c['name'] for c in classic}
    assert 'Blinding Mage' in by_name and "Gideon's Lawkeeper" in by_name


CASES = [(k[2:], v) for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    for name, fn in CASES:
        check(name, fn)
    print(f"\nsetdata tests: {len(CASES)}/{len(CASES)} passed")
