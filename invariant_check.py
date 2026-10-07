#!/usr/bin/env python3
"""Invariant checker: free structural audit of the interpreted output (no LLM).

Walks every already-interpreted sentence (from the content_check output cache)
and flags structural anomalies that indicate a silent parse bug:

  raw_action    the effect is {'verb':'raw',...} -> parsed but NOT decomposed.
                This is the headline "silent structure loss" metric; recurring
                raw texts reveal the grammar patterns still missing.
  pt_format     a power/toughness value that is not well-formed (e.g. "2/2", "+1/+1")
  unknown_zone  a zone value outside the MTG zone vocabulary
  bad_quantifier a quantifier outside the expected set
  bad_amount    an amount that is neither a number nor a word-number
  empty_target  a card/card_type target with no kind/type/value

Usage:
  python invariant_check.py [data.json]
  python invariant_check.py classic.json --min 2     # only show >=2 occurrences
"""
import sys, os, re, json, argparse, glob
from collections import Counter, defaultdict
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

ZONE      = {'battlefield', 'hand', 'library', 'graveyard', 'exile', 'stack', 'yard',
             'hands', 'libraries', 'graveyards', 'stacks', 'battlefields'}
QUANT     = {'a', 'an', 'each', 'all', 'other', 'target', 'up', 'no', 'x', 'that', 'their',
             'the', 'any', 'every', 'any number of', 'up to', 'some'}
WORD_AMT  = {'a', 'an', 'x', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
             'nine', 'ten', 'each', 'equal'}
PT_RE     = re.compile(r'^[+-]?(x|\d+)/[+-]?(x|\d+)$')         # 2/2, +1/+1, -x/-x, +10/+10
MANA_RE   = re.compile(r'^\{[^{}]+\}(\s*\{[^{}]+\})*$')        # {1}, {R}, {1}{B}, {2} {U}
NUNIT_RE  = re.compile(r'^[0-9x]+\s+\w+$')                     # "1 life", "X damage"
REL_AMT   = re.compile(r'\b(that|these|this|such|equal to)\b')  # relative: "double that", "...plus 1"


def load_my_outputs():
    cands = [os.path.join(BASE, '.cache', f) for f in os.listdir(os.path.join(BASE, '.cache'))
             if f.startswith('out_')]
    if not cands:
        return {}
    blob = json.load(open(sorted(cands, key=os.path.getmtime)[-1]))
    out = {}
    for s, b in blob.items():
        if b and not b.startswith('\x00'):
            try:
                out[s] = json.loads(b)
            except Exception:
                pass
    return out


def check(out, sent, flags):
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'verb' and v == 'raw':
                    flags.append(('raw_action', sent, (o.get('text') or '').strip()))
                elif k in ('pt', 'change', 'power', 'toughness') and isinstance(v, str):
                    if '/' in v and not PT_RE.match(v.strip()):
                        flags.append(('pt_format', sent, f"{k}={v!r}"))
                elif k == 'zone':
                    z = v.get('zone') if isinstance(v, dict) else v
                    if isinstance(z, str) and z.lower() not in ZONE:
                        flags.append(('unknown_zone', sent, f"zone={z!r}"))
                elif k == 'quantifier' and isinstance(v, str):
                    if v.lower() not in QUANT:
                        flags.append(('bad_quantifier', sent, f"q={v!r}"))
                elif k == 'amount' and isinstance(v, str):
                    a = v.strip()
                    if (a.lower() not in WORD_AMT and not a.isdigit()
                            and not MANA_RE.match(a) and not NUNIT_RE.match(a)
                            and not REL_AMT.search(a)):
                        flags.append(('bad_amount', sent, f"amount={v!r}"))
                elif k in ('card_type', 'card') and isinstance(v, dict):
                    if not any(x in v for x in ('kind', 'value', 'type', 'card_type', 'this_that', 'ref')):
                        flags.append(('empty_target', sent, f"{k}={{}}"))
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(out)


def flagged(my_out):
    """{sentence: sorted list of flag-type strings} for structurally-suspect (parsed-wrong) sentences."""
    res = {}
    for s, o in my_out.items():
        fl = []
        check(o, s, fl)
        if fl:
            res[s] = sorted({f[0] for f in fl})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data', nargs='?', default='classic.json')
    ap.add_argument('--min', type=int, default=1)
    args = ap.parse_args()

    my_out = load_my_outputs()
    if not my_out:
        print("No output cache. Run content_check.py once first."); sys.exit(1)

    flags = []
    for s, o in my_out.items():
        check(o, s, flags)

    print(f"audited {len(my_out)} interpreted sentences -> {len(flags)} flags")
    by_type = Counter(f[0] for f in flags)
    print("\n== flags by type ==")
    for t, c in by_type.most_common():
        print(f"  {c:5d}  {t}")

    # headline: recurring raw (undeconposed) actions -> the grammar gaps to fix
    raw = Counter(f[2] for f in flags if f[0] == 'raw_action' and f[2])
    if raw:
        print(f"\n== {sum(raw.values())} raw (undeconposed) actions; "
              f"{len(raw)} distinct shapes (top 20 by frequency) ==")
        for text, c in raw.most_common(20):
            print(f"  {c:4d}x  {text[:90]}")

    # other anomalies, deduped by (type, detail)
    others = [(f[0], f[2], f[1]) for f in flags if f[0] != 'raw_action']
    oc = Counter((a, b) for a, b, _ in others)
    if oc:
        print("\n== other anomalies (type, detail) -> count, example sentence ==")
        ex = {}
        for a, b, s in others:
            ex.setdefault((a, b), s)
        for (a, b), c in oc.most_common(20):
            print(f"  {c:4d}  [{a}] {b}   e.g. {ex[(a,b)][:70]}")

    with open('invariant_flags.tsv', 'w') as fh:
        for t, s, d in flags:
            if t == 'raw_action':
                fh.write(f"raw_action\t{d}\t{s}\n")
            else:
                fh.write(f"{t}\t{d}\t{s}\n")
    print(f"\n[dumped {len(flags)} flags to invariant_flags.tsv]")


if __name__ == '__main__':
    main()
