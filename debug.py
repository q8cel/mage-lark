#!/usr/bin/env python3
"""Debug: parse specific sentences and show the first error / tree."""
import sys
from lark import Lark, LarkError
from preprocess import segment
from mtd import all_oracle_text, card_type_set, name_set
from transformer import OracleTransformer

p = Lark.open('grammar.lark', parser='earley', start='start', ambiguity='resolve')
types = card_type_set(); names = name_set()

def try_parse(s):
    try:
        t = p.parse(s)
        r = OracleTransformer(types=types, names=names).transform(t)
        return ('OK', r)
    except LarkError as e:
        return ('ERR', str(e))

def main():
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            st, r = try_parse(s)
            print(f"### {s}\n  {st}: {str(r)[:300]}\n")
    else:
        # test a batch of representative failing patterns
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
        for s in tests:
            st, r = try_parse(s)
            print(f"### {s}\n  {st}: {str(r)[:400]}\n")

if __name__ == '__main__':
    main()
