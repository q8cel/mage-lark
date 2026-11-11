#!/usr/bin/env python3
"""Tests for `grammar_hoist`: optionals must move into helper rules, and the
language (accepted input + parse trees) must not change.

The transform exists only for speed, so the property that matters is
*equivalence*: for every test sentence the raw and hoisted grammars must accept
the same input and produce the same tree.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import sys

from grammar_hoist import hoist, HOISTED_PREFIX, tokenize

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


SNIPPET = r'''
start: sentence
sentence: "draw" ("a" | "two") ("card" | "cards") ("now" | "immediately")?
        | "gain" LIFE "life" ("and" "draw" "a" "card")?
LIFE: /[0-9]+/
%ignore WS
WS: /[ \t\n]+/
'''


def _build(text):
    from lark import Lark
    return Lark(text, parser="earley", start="start", ambiguity="resolve",
                keep_all_tokens=True)


@case
def test_optionals_are_hoisted():
    out, rules = hoist(SNIPPET)
    assert rules, "no optionals found"
    for name, body in rules:
        assert name.startswith(HOISTED_PREFIX), name
        assert body.strip(), "hoisted rule must keep its body"
    # the parent rules no longer carry a `?` operator
    for line in out.split("\n"):
        if line.startswith(("start:", "sentence:")):
            assert "?" not in line.replace('"?"', ""), line


@case
def test_language_and_trees_unchanged():
    out, rules = hoist(SNIPPET)
    raw, new = _build(SNIPPET), _build(out)
    for text in ("draw a card", "draw two cards now", "gain 3 life",
                 "gain 3 life and draw a card", "draw a card immediately"):
        assert raw.parse(text).pretty() == new.parse(text).pretty(), text
    for bad in ("draw a cards now now", "gain life", "draw cards immediately"):
        errs = []
        for p in (raw, new):
            try:
                p.parse(bad)
                errs.append(None)
            except Exception as exc:
                errs.append(type(exc).__name__)
        assert errs[0] == errs[1] and errs[0] is not None, (bad, errs)


@case
def test_question_marks_in_literals_and_comments_are_inert():
    src = ('// a comment with (parens)? and a "?"\n'
           'start: "who?" WORD "it?"\n'
           'WORD: /[a-z]+/\n')
    out, rules = hoist(src)
    assert "// a comment with (parens)? and a \"?\"" in out, "comment was rewritten"
    assert '"who?"' in out and '"it?"' in out, "literal was rewritten"
    assert not rules, rules


@case
def test_regex_terminal_is_not_touched():
    src = 'start: NAME ("x")?\nNAME: /[a-z()?]+/\n'
    out, rules = hoist(src)
    assert '/[a-z()?]+/' in out, out
    assert len(rules) == 1, rules


@case
def test_real_grammar_shrinks_and_still_parses():
    from lark import Lark
    text, n = None, None
    with open(_paths.GRAMMAR) as fh:
        src = fh.read()
    out, rules = hoist(src)
    assert len(rules) > 100, len(rules)
    kw = dict(parser="earley", start="start", ambiguity="resolve",
              keep_all_tokens=True)
    new = Lark(out, **kw)
    # ratio guard: hoisting must actually remove the exponential blow-up
    assert len(new.rules) < 4000, len(new.rules)
    tree = new.parse("Flying")
    assert tree is not None
    heads = [str(t.data) for t in tree.iter_subtrees()]
    assert "static_keyword" in heads or "sentence" in heads, heads


def main():
    failed = []
    for fn in CASES:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception as exc:
            failed.append((fn.__name__, exc))
            print(f"  FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\nhoist tests: {len(CASES) - len(failed)}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
