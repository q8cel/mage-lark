#!/usr/bin/env python3
"""Assemble compile_standard.jsonl into one card IR record per card.

The sentence artifact stays the source of the atomic parses; this tool groups
it by card and adds deterministic cross-segment links (If you do, this way,
that many, the rest, those cards, pronouns, self references).
"""

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import re
import signal
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
paths.bootstrap()

import card_ir
from setdata import load, normalize_text


_WHOLE = {}


def _init_whole():
    from larkparser import build_parser
    _WHOLE['parser'] = build_parser('ptree')


def _whole_one(text):
    parser = _WHOLE['parser']
    t = re.sub(r'\n+', '. ', text)
    t = re.sub(r'\.\s*\.', '.', t).strip('. ')
    if not t:
        return {'ok': False, 'sentences': []}
    def _alarm(_signum, _frame):
        raise TimeoutError
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(6)
    try:
        tree = parser.parse(t)
        spans = []
        for node in tree.find_data('sentence'):
            starts = getattr(node.meta, 'start_pos', None)
            ends = getattr(node.meta, 'end_pos', None)
            if starts is None or ends is None:
                continue
            spans.append({'start': starts, 'end': ends,
                          'text': t[starts:ends]})
        return {'ok': True, 'sentences': spans}
    except Exception:
        return {'ok': False, 'sentences': []}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifact', default='compile_standard.jsonl')
    ap.add_argument('--data', default='Standard.json')
    ap.add_argument('--out', default='compile_cards.jsonl')
    ap.add_argument('--whole-parse', action='store_true',
                    help='attempt the whole-card grammar path and report it')
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()

    by_card = defaultdict(list)
    with open(args.artifact) as fh:
        for line in fh:
            r = json.loads(line)
            segs = by_card[r['card']]
            key = (r['sentence_index'], r['original_text'])
            if any((x['index'], x['text']) == key for x in segs):
                continue
            segs.append({
                'index': r['sentence_index'], 'text': r['original_text'],
                'resolved_text': r.get('resolved_text'),
                'output': r.get('output'), 'anaphora': r.get('anaphora')})
    items, _types, names, _sets = load(args.data)
    raw = {}
    for name, text, _code in items:
        raw.setdefault(name, normalize_text(text, names))

    whole = {}
    if args.whole_parse:
        names_sorted = sorted(by_card)
        texts = [raw.get(n, '') for n in names_sorted]
        with mp.Pool(args.workers, initializer=_init_whole) as pool:
            flags = pool.map(_whole_one, texts)
        whole = dict(zip(names_sorted, flags))
    out = []
    with_link = 0
    for name in sorted(by_card):
        segs = by_card[name]
        rec = card_ir.build_card(name, raw.get(name, ''), segs,
                                 whole=whole.get(name))
        if rec['links']:
            with_link += 1
        out.append(rec)

    payload = b''.join((json.dumps(r, ensure_ascii=False, sort_keys=True)
                        + '\n').encode() for r in out)
    with open(args.out, 'wb') as fh:
        fh.write(payload)
    dig = hashlib.sha256(payload).hexdigest()
    print(json.dumps({'cards': len(out), 'with_links': with_link,
                      'links': sum(len(r['links']) for r in out),
                      'whole_text_parse': (sum(1 for v in whole.values()
                                                if v.get('ok'))
                                            if whole else None),
                      'sha256': dig, 'out': args.out}, indent=1))


if __name__ == '__main__':
    main()
