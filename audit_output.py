#!/usr/bin/env python3
"""AUDIT output QUALITY, not just parse success.

The coverage metric counts a sentence as "covered" if it parses. But the
interpreter can still emit incomplete or wrong structures (empty keyword lists,
pronouns like 'it' mistaken for card types, empty dicts, the 'raw' fallback).
This script re-parses every successfully-parsed unique sentence and flags
outputs that look suspicious, so we can see the real quality gap.
"""
import sys, os, json
from multiprocessing import Pool
from functools import partial
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from lark import Lark, LarkError
GRAMMAR = os.path.join(BASE, 'grammar.lark')
from setdata import load
from preprocess import segment, normalize_names
from interpret import Interpreter

_PRONOUN_TYPES = {'it', 'them', 'its', 'it\'s', 'they', 'their', 'one',
                  'other', 'another', 'each', 'either', 'the rest'}
_parser = None
_interp = None

def init(t, n):
    global _parser, _interp
    _parser = Lark.open(GRAMMAR, parser='earley', start='start',
                        ambiguity='resolve', keep_all_tokens=True)
    _interp = Interpreter(types=t, names=n)

def _flag(obj, acc):
    """Recursively inspect an interpreted output for red flags."""
    if isinstance(obj, dict):
        if obj == {}:
            acc['empty_dict'] += 1
        for k, v in obj.items():
            if k == 'card_type' and isinstance(v, dict):
                val = v.get('value', '')
                if isinstance(val, str) and val.lower() in _PRONOUN_TYPES:
                    acc['pronoun_type'] += 1
            if k == 'verb' and v == 'raw':
                acc['raw_verb'] += 1
            if k == 'keywords' and v == []:
                acc['empty_keywords'] += 1
            _flag(v, acc)
    elif isinstance(obj, list):
        for x in obj:
            _flag(x, acc)

def work(sent, names, t, n):
    """Return (parsed_ok, flags, output)."""
    s = normalize_names(sent, names)
    try:
        tree = _parser.parse(s)
    except LarkError:
        return (0, {}, None)
    out = _interp.interp(tree)
    acc = {'empty_dict': 0, 'pronoun_type': 0, 'raw_verb': 0, 'empty_keywords': 0}
    _flag(out, acc)
    return (1, acc, out)

def main():
    data = sys.argv[1] if len(sys.argv) > 1 else 'classic.json'
    items, types, names, sets = load(data)
    unique = []
    seen = set()
    for name, text, code in items:
        for seg in segment(text, names):
            if seg['text'] and seg['text'] not in seen and not seg['modal']:
                seen.add(seg['text']); unique.append(seg['text'])
    print(f'auditing {len(unique)} unique parsed sentences from {data}...')
    fn = partial(work, names=names, t=types, n=names)
    with Pool(24, initializer=init, initargs=(types, names)) as pool:
        res = pool.map(fn, unique, chunksize=8)

    ok = [r for r in res if r[0] == 1]
    print(f'parsed OK: {len(ok)}')
    total = {k: 0 for k in ['empty_dict', 'pronoun_type', 'raw_verb', 'empty_keywords']}
    flagged_sentences = 0
    for _, acc, out in ok:
        for k in total: total[k] += acc[k]
        if any(acc.values()):
            flagged_sentences += 1
    print(f'\n== flag totals (a sentence can have several) ==')
    for k, v in total.items():
        print(f'  {k:16s}: {v}')
    print(f'\n== {flagged_sentences}/{len(ok)} ({100*flagged_sentences/max(len(ok),1):.1f}%) '
          f'of parsed sentences have at least one red flag ==')

    # show a few examples of each flag type
    import itertools
    shown = {k: 0 for k in total}
    print('\n== examples ==')
    for sent, (flag, acc, out) in zip(unique, res):
        if flag != 1: continue
        for k in total:
            if acc[k] and shown[k] < 3:
                shown[k] += 1
                print(f'\n  [{k}] {sent}')
                if k in ('empty_keywords',):
                    print(f'      -> {json.dumps(out)[:120]}')
    return total, flagged_sentences, len(ok)

if __name__ == '__main__':
    main()
