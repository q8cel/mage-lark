#!/usr/bin/env python3
"""Repository layout, import bootstrap, and data-file resolution.

The repository is organised as::

    grammar/grammar.lark        the oracle-text grammar
    core/                       parse + interpret pipeline
    coref/                      anaphora detection, resolver, models, eval
    tools/                      runners and maintenance scripts
    tests/                      golden/regression suites
    data/                       corpora and labelled datasets
    docs/                       design notes and audit logs
    mtd/                        FDN convenience accessors

Modules are still imported by their bare names (``import rulecoref``) so the
whole code base keeps working unchanged; `bootstrap()` puts the repository
root plus ``core/`` and ``coref/`` on ``sys.path``.  Scripts call it once, at
import time::

    import paths; paths.bootstrap()

Paths come from here rather than from the caller's ``__file__`` dir, so moving
a script between ``tools/`` and ``tests/`` cannot break the data it reads.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(ROOT, "core")
COREF = os.path.join(ROOT, "coref")
TOOLS = os.path.join(ROOT, "tools")
TESTS = os.path.join(ROOT, "tests")
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
GRAMMAR_DIR = os.path.join(ROOT, "grammar")

GRAMMAR = os.path.join(GRAMMAR_DIR, "grammar.lark")
CACHE = os.environ.get("MLARK_CACHE") or os.path.join(ROOT, ".cache")

_SEARCH = (CORE, COREF, TOOLS, TESTS)


def bootstrap():
    """Put the repo root and the module directories on ``sys.path`` (idempotent)."""
    for path in (ROOT, CORE, COREF):
        if path not in sys.path:
            sys.path.insert(0, path)


def ensure_cache():
    os.makedirs(CACHE, exist_ok=True)
    return CACHE


def data(name, must_exist=True):
    """Resolve a corpus/dataset path.

    Accepts an absolute path, a path relative to the working directory, or a
    bare filename (``FDN.json``) that lives in ``data/``.  Returns the input
    unchanged when nothing matches so callers keep their own error messages.
    """
    if not name:
        return name
    name = str(name)
    if os.path.isabs(name):
        return name
    if os.path.exists(name):
        return name
    cand = os.path.join(DATA, name)
    if os.path.exists(cand):
        return cand
    cand = os.path.join(ROOT, name)
    if os.path.exists(cand):
        return cand
    if must_exist:
        raise FileNotFoundError(
            f"{name!r} not found in the working directory, data/ or the repo root")
    return name


def source(name):
    """Path to a source file by bare name (``interpret.py``), wherever it lives."""
    for directory in (CORE, COREF, TOOLS, TESTS, ROOT):
        cand = os.path.join(directory, name)
        if os.path.exists(cand):
            return cand
    cand = os.path.join(GRAMMAR_DIR, name)
    if os.path.exists(cand):
        return cand
    raise FileNotFoundError(name)
