#!/usr/bin/env python3
"""Show the full transformed (dict) output for one or more raw sentences.

Usage:  python show.py "Draw a card" "Tap an untapped creature you control"
Runs preprocessing (sentence split) + parse + transform, prints JSON.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys, json
from lark import LarkError
from preprocess import segment
from mtd import card_type_set, name_set
from interpret import Interpreter
from larkparser import build_parser

parser = build_parser('interp')
NAMES = name_set()
interp = Interpreter(types=card_type_set(), names=NAMES)


def clean(o):
    """Make the tree/dict JSON-serialisable."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(x) for x in o]
    if hasattr(o, 'data') and hasattr(o, 'children'):  # lark Tree
        return {'rule': o.data, 'children': [clean(c) for c in o.children]}
    if hasattr(o, 'value') and hasattr(o, 'type'):  # lark Token
        return str(o)
    return o


for raw in sys.argv[1:]:
    print(f"\n===== {raw} =====")
    for it in segment(raw, NAMES):
        s = it['text']
        try:
            tree = parser.parse(s)
            out = interp.interp(tree)
            print(json.dumps(clean(out), indent=2, ensure_ascii=False))
        except LarkError as e:
            print(f"  [UNPARSED] {str(e).splitlines()[0][:80]}")
