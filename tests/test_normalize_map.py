#!/usr/bin/env python3
"""Tests for `setdata.normalize_with_map` (regex-free, no parser needed)."""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import os
import sys

BASE = _paths.ROOT
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


def t_nested_parens():
    names = {"Test Card"}
    raw = ("Flying (this creature can't be blocked "
           "(except by creatures with flying))\nTrample")
    text, omap = normalize_with_map(raw, names)
    assert text == "Flying\nTrample", repr(text)
    # Text outside the spans is untouched, on both sides of the newline.
    s, e = omap.to_original(0, len("Flying"))
    assert raw[s:e] == "Flying"
    p = text.index("Trample")
    s, e = omap.to_original(p, p + len("Trample"))
    assert raw[s:e] == "Trample"


def t_sole_reminder_unwrap():
    # Basic lands ship as one parenthetical span holding the whole rules text;
    # dropping it would leave the card empty, so only the parentheses go.
    raw = "({T}: Add {W}.)"
    text, omap = normalize_with_map(raw)
    assert text == "{T}: Add {W}.", repr(text)
    assert omap.to_original(0, 3) == (1, 4), omap.to_original(0, 3)
    assert all(raw[s:e] == ch for (s, e), ch in zip(omap.spans, text))
    assert normalize_text(raw) == "{T}: Add {W}."
    # Nested groups drop only the outer pair; the inner text is unchanged.
    assert normalize_text("((nested))") == "(nested)"
    # A span plus real text still behaves like ordinary reminder text.
    assert normalize_text("({T}: Add {W}.)\nTrample") == "Trample"


def t_keep_reminders_flag():
    raw = ("Ward {2} (Whenever this creature becomes the target of a spell or "
           "ability an opponent controls, counter it unless that player pays "
           "{2}.)")
    assert normalize_text(raw) == "Ward {2}", normalize_text(raw)
    kept = normalize_text(raw, keep_reminders=True)
    assert "counter it unless" in kept, kept
    from preprocess import segment
    assert [d["text"] for d in segment(raw)] == ["Ward {2}"]
    kept_segments = [d["text"] for d in segment(raw, keep_reminders=True)]
    assert any("counter it unless" in s for s in kept_segments), kept_segments


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
        try:
            _paths.data(path)
        except FileNotFoundError:
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
