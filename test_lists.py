#!/usr/bin/env python3
"""Regression tests for deterministic list capture and list-token integration."""
import sys
BASE = __import__('os').path.dirname(__import__('os').path.abspath(__file__))
sys.path.insert(0, BASE)

from lists import capture, protect, decode
from preprocess import segment, normalize_names
from larkparser import build_parser
from interpret import Interpreter
from setdata import load


def one(text):
    got = capture(text)
    assert len(got) == 1, (text, got)
    return got[0][2]


def main():
    # Set/type lists: surface 'and' still means union.
    x = one('Birds and Frogs you control get +1/+1')
    assert x['kind'] == 'set' and x['logic'] == 'union'
    assert x['connector'] == 'and'
    assert x['items'] == ['Birds', 'Frogs']
    assert x['shared_suffix'] == 'you control'

    x = one('Birds, Frogs, Otters, and Rats you control get +1/+1')
    assert x['kind'] == 'set' and x['logic'] == 'union'
    assert x['items'] == ['Birds', 'Frogs', 'Otters', 'Rats']
    assert x['shared_suffix'] == 'you control'

    x = one('If that creature is a Bird, Frog, Otter, or Rat, draw a card')
    assert x['kind'] == 'set' and x['logic'] == 'union'
    assert x['items'] == ['a Bird', 'Frog', 'Otter', 'Rat']

    # Property lists: implicit comma or 'and' means intersection.
    x = one("If it's a noncreature, nonland card, you gain 2 life")
    assert x['kind'] == 'property' and x['logic'] == 'intersection'
    assert x['items'] == ['a noncreature', 'nonland card']
    assert x['head'] == 'card'

    x = one('red, white, and blue creature')
    assert x['kind'] == 'property' and x['logic'] == 'intersection'

    # Property lists with 'or' are union.
    x = one('white, blue, black, or red')
    assert x['kind'] == 'property' and x['logic'] == 'union'

    # Target/type alternatives are set union.
    x = one('target artifact, creature, or planeswalker an opponent controls loses all abilities')
    assert x['kind'] == 'set' and x['logic'] == 'union'
    assert x['shared_suffix'] == 'an opponent controls'

    # Shared quantifier and suffix.
    x = one('Whenever one or more other Rabbits, Bats, Birds, and/or Mice you control enter, scry 1')
    assert x['kind'] == 'set' and x['logic'] == 'union'
    assert x['shared_prefix'] == 'other'
    assert x['shared_suffix'] == 'you control'

    # Chrome Replicator's asyndetic property list.
    x = one('If you control two or more nonland, nontoken permanents with the same name as one another, create a token')
    assert x['kind'] == 'property' and x['logic'] == 'intersection'

    # Keyword lists and effect sequencing are not list objects.
    assert capture('Flying, first strike, and deathtouch') == []
    assert capture('draw a card, then discard a card') == []
    assert capture('target creature with mana value 2 or less') == []

    # Names with commas are normalized before list detection, so they never split.
    _, types, names, _ = load('Standard.json')
    s = normalize_names('Destroy Quicksilver, Brash Blur', names)
    assert s == 'Destroy ~', s
    assert capture(s) == []

    # Token round-trip.
    x = one('Birds and Frogs you control get +1/+1')
    token = protect('Birds and Frogs you control get +1/+1').split()[0]
    assert decode(token) == x

    # Parser integration: list token occupies a complete NP slot.
    parser = build_parser('interp')
    interp = Interpreter(types=types, names=names)

    def parse(sentence):
        segs = [d['text'] for d in segment(sentence, names)
                if d['text'] and not d['modal']]
        return interp.interp(parser.parse(segs[0]))

    out = parse('If that creature is a Bird, Frog, Otter, or Rat, draw a card')
    assert out[0]['type'] == 'if'
    cond = out[0]['condition']
    assert cond['lists'][0]['logic'] == 'union'
    assert 'Bird, Frog, Otter, or Rat' in cond['text']

    out = parse("If it's a noncreature, nonland card, you gain 2 life")
    assert out[0]['condition']['lists'][0]['logic'] == 'intersection'

    out = parse('Birds and Frogs you control get +1/+1')
    stat = out[0]['effect']
    assert stat['verb'] == 'stat_change'
    assert stat['target']['kind'] == 'set'
    assert stat['target']['logic'] == 'union'

    out = parse('Whenever one or more other Rabbits, Bats, Birds, and/or Mice you control enter, scry 1')
    trig = out[0]['trigger']['event']['subject']
    assert trig['kind'] == 'set' and trig['logic'] == 'union'

    print('list tests passed')


if __name__ == '__main__':
    main()
