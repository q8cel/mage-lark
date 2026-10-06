#!/usr/bin/env python3
"""Golden output tests: lock in the interpreter fixes (regression guard).

Each case is (name, sentence, predicate); predicate(output) is True iff the
interpreted output has the expected structure. Hand-written for the known
silent-bug classes, so a regressing fix fails loudly here.

Usage:  python test_output.py [data.json]      # default classic.json
"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from lark import Lark, LarkError
GRAMMAR = os.path.join(BASE, 'grammar.lark')
from setdata import load
from preprocess import segment
from interpret import Interpreter

def has(obj, pred):
    """Recursively: does any node satisfy pred?"""
    if isinstance(obj, dict):
        try:
            if pred(obj):
                return True
        except Exception:
            pass
        return any(has(v, pred) for v in obj.values())
    if isinstance(obj, list):
        return any(has(v, pred) for v in obj)
    try:
        return bool(pred(obj))
    except Exception:
        return False

T = []
def add(name, sent, pred):
    T.append((name, sent, pred))

add("keywords-list", "Flying, first strike, and deathtouch",
    lambda o: has(o, lambda d: isinstance(d.get('keywords'), list)
                  and {'Flying', 'first strike', 'deathtouch'} <= set(d['keywords'])))
add("anaphora-not-type", "It gains haste until end of turn",
    lambda o: has(o, lambda d: d.get('ref') == 'anaphora'))
add("draw-amount-int", "Draw two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('amount') == 2))
add("deal-damage", "this enchantment deals 2 damage to that player",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage' and d.get('amount') == 2 and d.get('to')))
add("enters-counters", "This creature enters with three wish counters on it",
    lambda o: has(o, lambda d: d.get('verb') == 'enters' and d.get('with', {}).get('count') == 3))
add("put-zone", "put it into your hand",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'hand'))
add("token-color-type", "Create a white Avatar creature token",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('colors') == 'white'
                  and 'creature' in d.get('token', {}).get('types', [])))
add("stat-for-each", "This creature gets +1/+1 for each other creature on the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and 'battlefield' in str(d.get('for_each', ''))))
add("cant-except", "This creature can't be blocked except by black creatures",
    lambda o: has(o, lambda d: d.get('verb') == "can't" and d.get('predicate') == 'be blocked'
                  and d.get('except_by')))
add("search-zone", "Search your library for a card named Test Card",
    lambda o: has(o, lambda d: d.get('verb') == 'search' and d.get('zone') == 'library'))
add("put-counter", "put a -1/-1 counter on it",
    lambda o: has(o, lambda d: d.get('verb') == 'put_counter'
                  and '-1/-1' in str(d.get('counter', ''))))
add("token-pt-kw", "Create a 1/1 colorless Thopter artifact creature token with flying",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('power_toughness') == '1/1'
                  and 'flying' in str(d.get('token', {}).get('kw', []))))
add("counter-unless", "Counter target spell unless its controller pays {1}",
    lambda o: has(o, lambda d: d.get('verb') == 'counter' and '{1}' in str(d.get('unless', ''))))
add("become-pt", "Target land you control becomes a 4/4 Elemental creature with trample",
    lambda o: has(o, lambda d: d.get('verb') == 'become' and d.get('pt') == '4/4'))
add("stat-condition", "This creature gets +4/+4 as long as an opponent has ten or more cards in their graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and 'graveyard' in str(d.get('condition', ''))))
add("if-decomposed", "If you control three or more creatures, draw a card",
    lambda o: has(o, lambda d: d.get('type') == 'if' and 'condition' in d
                  and isinstance(d.get('effect'), dict)
                  and d['effect'].get('verb') == 'draw'))

def main():
    data = sys.argv[1] if len(sys.argv) > 1 else 'classic.json'
    items, types, card_names, sets = load(data)
    names = sorted(card_names, key=len, reverse=True)
    parser = Lark(open(GRAMMAR), start='start', parser='earley',
                  ambiguity='resolve', keep_all_tokens=True)
    interp = Interpreter(types=types, names=card_names)
    passed = failed = 0
    for name, sent, pred in T:
        try:
            sents = [d['text'] for d in segment(sent, names)
                     if d['text'] and not d['modal']]
            if not sents:
                raise ValueError('no sentence produced')
            out = interp.interp(parser.parse(sents[0]))
        except Exception as e:
            print(f"  FAIL {name:20s} (parse) {e}")
            failed += 1
            continue
        if pred(out):
            print(f"  PASS {name}")
            passed += 1
        else:
            print(f"  FAIL {name:20s}  {sent}")
            print(f"       {json.dumps(out)[:200]}")
            failed += 1
    print(f"\n{passed}/{passed+failed} golden tests passed")
    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    import json
    main()
