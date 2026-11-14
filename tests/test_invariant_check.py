#!/usr/bin/env python3
"""Guard tests for tools/invariant_check.py: free text may not masquerade as structure.

Runs plain asserts like the other suites; no parser is invoked.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys
sys.path.insert(0, _os.path.join(_paths.ROOT, 'tools'))
import invariant_check as ic

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append(True)
        print(f"  PASS {name}")
    except AssertionError as e:
        RESULTS.append(False)
        print(f"  FAIL {name}: {e}")


def t_bare_fragment_flagged():
    out = [{'fragment': 'while saddled', 'reason': 'condition_text', 'source': 'i_if'}]
    flags = []
    ic.check(out, 'synthetic', flags)
    assert any(f[0] == 'bare_fragment' for f in flags), flags


def t_fragment_on_unparsed_flag_ok():
    out = [{'unparsed': True, 'fragment': 'while saddled', 'reason': 'condition_text',
            'source': 'i_if'}]
    flags = []
    ic.check(out, 'synthetic', flags)
    assert not any(f[0] == 'bare_fragment' for f in flags), flags


def t_fragment_on_type_unparsed_ok():
    out = [{'type': 'unparsed', 'reason': 'static_text', 'fragment': 'activate only'}]
    flags = []
    ic.check(out, 'synthetic', flags)
    assert not any(f[0] == 'bare_fragment' for f in flags), flags


def t_text_key_flagged():
    out = [{'nested': {'text': 'raw action'}}]
    flags = []
    ic.check(out, 'synthetic', flags)
    assert any(f[0] == 'fallback_text' for f in flags), flags


CASES = [(k[2:], v) for k, v in sorted(globals().items()) if k.startswith('t_')]

if __name__ == '__main__':
    for name, fn in CASES:
        check(name, fn)
    passed = sum(RESULTS)
    print(f"\ninvariant-check tests: {passed}/{len(CASES)} passed")
    sys.exit(0 if passed == len(CASES) else 1)
