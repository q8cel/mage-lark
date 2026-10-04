#!/usr/bin/env python3
"""Content-preservation checker: find SILENT bugs (parsed but info lost).

For every successfully-parsed sentence, extract the "hard content" of the input
(colors, numbers, power/toughness, mana, card types, keywords, zones, card names)
and assert each survives in the serialized interpreted output. Any content unit
that is missing from the output is a candidate silent bug.

This does NOT need to know which rule is wrong -- it only detects that
information was dropped, which is exactly the class of bug we care about.

Usage:  python content_check.py classic.json
        python content_check.py classic.json --min 5     # only units missing >=5 times
"""
import sys, os, re, json
from collections import Counter
from multiprocessing import Pool
from functools import partial
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from lark import Lark, LarkError
GRAMMAR = os.path.join(BASE, 'grammar.lark')
from setdata import load
from preprocess import segment, normalize_names
from interpret import Interpreter

WORD_NUM = {w: n for w, n in
            [('one',1),('two',2),('three',3),('four',4),('five',5),('six',6),
             ('seven',7),('eight',8),('nine',9),('ten',10),('eleven',11),('twelve',12),
             ('thirteen',13),('fourteen',14),('fifteen',15),('sixteen',16),
             ('seventeen',17),('eighteen',18),('nineteen',19),('twenty',20)]}
DIGIT_WORD = {str(n): w for w, n in WORD_NUM.items()}
COLORS = {'white', 'blue', 'black', 'red', 'green'}
ZONES = {'hand', 'library', 'battlefield', 'graveyard', 'exile', 'stack',
         'tombstone', 'rules', 'piles', 'anywhere', 'zone'}
# words that are content but legitimately may be transformed, so we check a
# normalized form; anything here is REQUIRED to appear in the output.

def content_units(raw, names, types, kws):
    """Return the set of content tokens (canonical form) that must survive."""
    units = set()
    low = raw.lower()
    words = re.findall(r"[a-z']+", low)
    rem = raw
    # power/toughness first, then remove so their digits aren't re-counted
    for m in re.findall(r'[+-]?\d+/[+-]?\d+', rem):
        units.add(m); rem = rem.replace(m, ' ')
    # mana symbols
    for m in re.findall(r'\{[^}]+\}', rem):
        units.add(m.lower()); rem = rem.replace(m, ' ')
    # digit numbers (from the remainder, so P/T digits are excluded)
    for m in re.findall(r'\b\d+\b', rem):
        units.add(m)
    # word numbers -> digit
    for w in words:
        if w in WORD_NUM:
            units.add(str(WORD_NUM[w]))
    # colors, zones
    for w in words:
        if w in COLORS or w in ZONES:
            units.add(w)
    # card type words (single-word, from the set's type vocabulary)
    for w in words:
        if w in types:
            units.add(w)
    # keywords (single- and multi-word)
    for kw in kws:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', low):
            units.add(kw.lower())
    # card names -> the self token
    for name in names:
        if re.search(r'\b' + re.escape(name.lower()) + r'\b', low):
            units.add('~')
    return units

_parser = None
_interp = None
_ctx = None
def init(t, n, kws):
    global _parser, _interp, _ctx
    _parser = Lark.open(GRAMMAR, parser='earley', start='start',
                        ambiguity='resolve', keep_all_tokens=True)
    _interp = Interpreter(types=t, names=n)
    _ctx = (set(n), t, kws)

def work(sent):
    names, types, kws = _ctx
    s = normalize_names(sent, names)
    try:
        tree = _parser.parse(s)
    except LarkError:
        return (0, sent, [], None)
    out = _interp.interp(tree)
    blob = json.dumps(out, ensure_ascii=False).lower()
    def present(u):
        if u in blob:
            return True
        # a number is preserved if its word form appears (e.g. "two" for "2")
        if u.isdigit() and DIGIT_WORD.get(u, '') in blob:
            return True
        return False
    missing = [u for u in content_units(sent, names, types, kws) if not present(u)]
    return (1, sent, missing, out)

def main():
    args = [a for a in sys.argv[1:]]
    data = 'classic.json'
    mincnt = 1
    if '--min' in args:
        i = args.index('--min'); mincnt = int(args[i+1]); args = args[:i] + args[i+2:]
    if args and not args[0].startswith('--'):
        data = args[0]
    items, types, names, sets = load(data)
    # keyword vocabulary = KEYWORD-ish words we treat as content
    kws = set(w for w in types if ' ' in w)  # multi-word types as "keyword-ish"
    kws |= {'flying','first strike','double strike','trample','deathtouch','lifelink',
            'reach','menace','vigilance','haste','defender','hexproof','indestructible',
            'changeling','prowess','infect','blight','wither','toxic','flashback','flash',
            'ward','cumulative','cascade','delve','delirium','enrage','evoke','explore',
            'heroic','horizon','ichor','proliferate','landfall','morbid','annihilate',
            'banding','highland','exalt','exalted','exorcism','exert','foretell','guardian'}
    unique, seen = [], set()
    for name, text, code in items:
        for seg in segment(text, names):
            if seg['text'] and seg['text'] not in seen and not seg['modal']:
                seen.add(seg['text']); unique.append(seg['text'])
    print(f'content-checking {len(unique)} unique sentences from {data}...')
    with Pool(24, initializer=init, initargs=(types, names, kws)) as pool:
        res = pool.map(work, unique, chunksize=8)

    ok = [r for r in res if r[0] == 1]
    miss_counter = Counter()
    affected = 0
    for _, sent, missing, out in ok:
        if missing:
            affected += 1
            for m in missing:
                miss_counter[m] += 1
    print(f'parsed OK: {len(ok)}')
    print(f'\n== {affected}/{len(ok)} ({100*affected/max(len(ok),1):.1f}%) of parsed '
          f'sentences LOSE at least one content unit ==\n')
    print('== most-missing content units (>= %d) ==' % mincnt)
    for unit, c in miss_counter.most_common():
        if c >= mincnt:
            print(f'  {c:4d}  {unit}')

    if '--dump' in sys.argv:
        with open('content_missing.tsv', 'w') as f:
            for _, sent, missing, out in ok:
                for m in sorted(set(missing)):
                    f.write(f'{m}\t{sent}\n')
        print('\n[dumped all (unit, sentence) pairs to content_missing.tsv]')

    # examples for the top missing units
    print('\n== examples (up to 3 per top-8 unit) ==')
    top = [u for u, _ in miss_counter.most_common(8)]
    per = {u: 0 for u in top}
    for _, sent, missing, out in ok:
        for u in missing:
            if u in top and per[u] < 3:
                per[u] += 1
                print(f'\n  missing [{u}]: {sent}')
    return affected, len(ok), miss_counter

if __name__ == '__main__':
    main()
