#!/usr/bin/env python3
"""FDN convenience accessors, backed by the unified `setdata` loader.

Kept for the FDN-only survey/test tools (`test_parse`, `quick_test`, `debug`,
`vocab`).  New code should use `setdata.load(path)` directly; in particular,
do not use this module as an implicit default for Standard/classic data.
"""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDN = os.path.join(BASE, "FDN.json")

_data = None


def _load():
    global _data
    if _data is None:
        from setdata import load

        items, types, names, _sets = load(FDN)
        _data = (items, types, names)
    return _data


def name_set():
    """Set of FDN names (already filtered for basic lands/keyword collisions)."""
    return set(_load()[2])


def card_type_set():
    """Set of FDN card types, subtypes and supertypes."""
    return set(_load()[1])


def all_oracle_text():
    """[(card_name, raw_oracle_text)] for every FDN card with text."""
    return [(name, text) for name, text, _code in _load()[0]]
