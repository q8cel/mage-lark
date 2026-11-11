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

The grammar handed to Lark is the *hoisted* form (see `grammar_hoist.py`): Lark
expands every `(...)?` into a copy of its parent rule, which turned this grammar
into 9,644 rules and made each parse cost ~5.7 s.  Hoisting the optionals into
`_opt_N` helper rules gives ~2,800 rules and ~0.34 s, with identical trees.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import os

BASE = _paths.ROOT
GRAMMAR = _paths.GRAMMAR

KINDS = ("interp", "ptree")
_CACHE = {}

# Bumped when `grammar_hoist` changes shape, so stale .cache files are not reused.
HOIST_VERSION = 1


def grammar_path(path=None):
    return os.path.abspath(path or GRAMMAR)


def hoisted_path(path):
    """Return the cached, optional-hoisted form of grammar `path`.

    Lark duplicates a rule once per `(...)?` in it, which explodes the grammar
    (9,644 rules) and makes every Earley chart position predict the whole rule
    set.  `grammar_hoist` moves each optional into its own `_opt_N` rule; the
    language and the parse trees are unchanged, the rule count drops to ~2,800.
    Set MLARK_RAW_GRAMMAR=1 to parse with the source grammar instead (only
    needed to reproduce pre-hoist behaviour).
    """
    if os.environ.get("MLARK_RAW_GRAMMAR"):
        return path
    import hashlib
    with open(path, "rb") as fh:
        digest = hashlib.sha1(fh.read()).hexdigest()[:16]
    out = os.path.join(_paths.CACHE,
                       f"grammar_hoisted_{HOIST_VERSION}_{digest}.lark")
    if not os.path.exists(out):
        from grammar_hoist import hoisted_grammar
        text, _ = hoisted_grammar(path)
        os.makedirs(_paths.CACHE, exist_ok=True)
        tmp = f"{out}.{os.getpid()}.tmp"
        with open(tmp, "w") as fh:
            fh.write(text)
        os.replace(tmp, out)   # atomic: several workers may race here
    return out


def build_parser(kind="interp", grammar=None):
    """Return a cached Lark parser for `kind` ('interp' or 'ptree')."""
    if kind not in KINDS:
        raise ValueError(f"unknown parser kind {kind!r}; expected one of {KINDS}")
    src = grammar_path(grammar)
    path = hoisted_path(src)
    key = (kind, src, os.stat(src).st_mtime_ns)
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
