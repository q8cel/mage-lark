#!/usr/bin/env python3
"""Tests for `setdata.normalize_with_map` (regex-free, no parser needed)."""

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from preprocess import normalize_names, strip_reminders
from setdata import load, normalize_text, normalize_with_map


def _reference(raw, names):
    t = normalize_names(strip_reminders(raw), names)
    return "\n".join(" ".join(line.split()) for line in t.split("\n"))


def check(name, fn):
    fn()
    print(f"  PASS {name}")


def t_basic_and_name_span():
    names = {"Test Card"}
    raw = "Test Card deals 3 damage. (Reminder text.) Draw a card."
    text, omap = normalize_with_map(raw, names)
    assert text == "~ deals 3 damage. Draw a card.", repr(text)
    assert omap.to_original(0, 1) == (0, len("Test Card"))
    start = text.index("Draw a card")
    assert omap.text == text
    os_, oe = omap.to_original(start, start + len("Draw a card"))
    assert raw[os_:oe] == "Draw a card"


def t_newline_preserved():
    names = {"Test Card"}
    raw = "Flying\nWhenever Test Card attacks, draw a card."
    text, omap = normalize_with_map(raw, names)
    assert text == "Flying\nWhenever ~ attacks, draw a card.", repr(text)
    pos = text.index("~")
    assert omap.to_original(pos, pos + 1) == (16, 25)


def t_name_boundaries():
    names = {"Sear"}
    raw = "Search your library for a card."
    text, _ = normalize_with_map(raw, names)
    assert text == raw, repr(text)


def t_reminder_inside_span():
    names = set()
    raw = "target (a reminder) creature gets +1/+1."
    text, omap = normalize_with_map(raw, names)
    assert text == "target creature gets +1/+1.", repr(text)
    start = text.index("target creature")
    os_, oe = omap.to_original(start, start + len("target creature"))
    assert raw[os_:oe] == "target (a reminder) creature"
    assert normalize_text(raw[os_:oe], names) == "target creature"


def t_whitespace_and_roundtrip():
    names = {"Test Card"}
    raw = "  a  \t b\n c  Test Card  "
    text, omap = normalize_with_map(raw, names)
    assert text == "a b\nc ~", repr(text)
    pos = text.index("~")
    assert raw[slice(*omap.to_original(pos, pos + 1))] == "Test Card"
    # Every normalized span maps to a valid original span.
    for i in range(len(text)):
        s, e = omap.to_original(i, i + 1)
        assert 0 <= s < e <= len(raw), (i, s, e)


def t_corpus_matches_reference():
    for path in ("FDN.json", "classic.json"):
        if not os.path.exists(os.path.join(BASE, path)):
            continue
        items, _types, names, _sets = load(path)
        for _name, raw, _code in items:
            got = normalize_with_map(raw, names)[0]
            exp = _reference(raw, names)
            assert got == exp, (path, _name, got[:80], exp[:80])
        print(f"    {path}: {len(items)} cards match the reference normalizer")


CASES = [(k[2:], v) for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    for name, fn in CASES:
        check(name, fn)
    print(f"\nnormalize-map tests: {len(CASES)}/{len(CASES)} passed")
