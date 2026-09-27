#!/usr/bin/env python3
"""Show the full transformed (dict) output for one or more raw sentences.

Usage:  python show.py "Draw a card" "Tap an untapped creature you control"
Runs preprocessing (sentence split) + parse + transform, prints JSON.
"""
import sys, json
from lark import Lark, LarkError
from preprocess import segment
from mtd import card_type_set, name_set
from interpret import Interpreter
import os

BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')

parser = Lark.open(GRAMMAR, parser='earley', start='start',
                   ambiguity='resolve', keep_all_tokens=True)
interp = Interpreter(types=card_type_set(), names=name_set())


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
    for it in segment(raw):
        s = it['text']
        try:
            tree = parser.parse(s)
            out = interp.interp(tree)
            print(json.dumps(clean(out), indent=2, ensure_ascii=False))
        except LarkError as e:
            print(f"  [UNPARSED] {str(e).splitlines()[0][:80]}")
