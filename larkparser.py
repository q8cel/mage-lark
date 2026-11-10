"""Canonical Lark parser construction.

The project used to open `grammar.lark` in several places with subtly different
flags (`keep_all_tokens`, `propagate_positions`).  Those differences are easy to
miss and produce different trees from the same grammar.  Keep the two supported
configurations here:

    interp   keep all tokens, no position metadata (interpreter/coverage)
    ptree    keep all tokens + positions (mention/structure extraction)

Both use the same Earley configuration and grammar file.  Parsers are cached per
process so callers like `interpret.interpret()` do not recompile the grammar on
every sentence.
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, "grammar.lark")

KINDS = ("interp", "ptree")
_CACHE = {}


def grammar_path(path=None):
    return os.path.abspath(path or GRAMMAR)


def build_parser(kind="interp", grammar=None):
    """Return a cached Lark parser for `kind` ('interp' or 'ptree')."""
    if kind not in KINDS:
        raise ValueError(f"unknown parser kind {kind!r}; expected one of {KINDS}")
    path = grammar_path(grammar)
    key = (kind, path, os.stat(path).st_mtime_ns)
    parser = _CACHE.get(key)
    if parser is not None:
        return parser

    from lark import Lark

    parser = Lark.open(
        path,
        parser="earley",
        start="start",
        ambiguity="resolve",
        keep_all_tokens=True,
        propagate_positions=(kind == "ptree"),
    )
    _CACHE[key] = parser
    return parser
