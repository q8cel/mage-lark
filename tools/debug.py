#!/usr/bin/env python3
"""Debug: parse specific sentences and show the first error / interpreted output.

Uses the same parser configuration and `Interpreter` as the main pipeline, so
what you see here is what `test_output`/`show.py`/`demo_output.py` see.  The legacy
`OracleTransformer` is intentionally not used.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys

from lark import LarkError

from larkparser import build_parser
from preprocess import segment
from mtd import card_type_set, name_set
from interpret import Interpreter

PARSER = build_parser("interp")
TYPES = card_type_set()
NAMES = name_set()
INTERP = Interpreter(types=TYPES, names=NAMES)


def try_parse(s):
    try:
        tree = PARSER.parse(s)
        return ("OK", INTERP.interp(tree))
    except LarkError as e:
        return ("ERR", str(e))
    except Exception as e:  # interpreter bug: show it instead of crashing debug
        return ("INTERP-ERR", f"{type(e).__name__}: {e}")


def main():
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            st, r = try_parse(s)
            print(f"### {s}\n  {st}: {str(r)[:600]}\n")
        return

    tests = [
        'Flying',
        'Flash',
        'This land enters tapped.',
        'When this creature enters, draw a card.',
        'Whenever this creature attacks, you gain 1 life.',
        '~ deals damage to target creature.',
        '~ deals 3 damage to target creature.',
        'Create a token that\'s a copy of target creature you control.',
        'Equip {2}',
        'Creatures you control get +1/+1.',
        'Put a +1/+1 counter on target creature you control.',
        'Put two +1/+1 counters on it.',
        '{T}: Add {C}.',
        'Choose one —',
        'Enchant creature',
        'This spell can\'t be countered.',
        'This creature enters with a +1/+1 counter on it.',
        'Ward—Pay 2 life.',
        'Raid — At the beginning of your end step, if you attacked this turn, draw a card.',
        'At the beginning of your upkeep, draw a card.',
        'Draw a card, then discard a card.',
    ]
    for raw in tests:
        for it in segment(raw, NAMES):
            st, r = try_parse(it["text"])
            print(f"### {it['text']}\n  {st}: {str(r)[:600]}\n")


if __name__ == "__main__":
    main()
