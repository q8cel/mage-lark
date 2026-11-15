#!/usr/bin/env python3
"""Per-card compiler: resolve one card at a time and emit card-local records.

This is the no-collision path for downstream consumers.  Unlike the
sentence-keyed snapshot, which dedupes across the corpus and must pick one
resolution per sentence, this command keeps every card's own context:

    {"card", "sentence_index", "sid", "original_text", "resolved_text",
     "anaphora": [...], "output": [...]}

A rewritten sentence is used only when it parses and its interpretation has no
unparsed marker; otherwise the original sentence is compiled.  No grammar or
interpreter schema changes.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import argparse
import hashlib
import json
import sys

from anaphora import find_anaphors
from preprocess import segment
from setdata import load, normalize_text
import refs
import rulecoref


def _has_unparsed(obj):
    if isinstance(obj, dict):
        return (bool(obj.get('unparsed')) or obj.get('type') == 'unparsed'
                or 'text' in obj
                or any(_has_unparsed(v) for v in obj.values()))
    if isinstance(obj, list):
        return any(_has_unparsed(v) for v in obj)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True, help='JSONL output')
    ap.add_argument('--card', default=None, help='only this card name')
    ap.add_argument('--limit', type=int, default=0, help='card cap (testing)')
    ap.add_argument('--mentions', choices=('regex', 'parser'), default='regex')
    args = ap.parse_args()

    from larkparser import build_parser
    from interpret import Interpreter
    items, types, names, _sets = load(args.data)
    parser = build_parser('interp')
    interp = Interpreter(types=types, names=names)

    def parse_ok(sentence):
        segs = [it['text'] for it in segment(sentence) if it['text']]
        if not segs:
            return True
        try:
            for s in segs:
                parser.parse(s)
            return True
        except Exception:
            return False

    def interpret(text):
        try:
            return interp.interp(parser.parse(text))
        except Exception:
            return None

    cards = 0
    records = 0
    with open(args.out, 'w') as fh:
        for name, raw, _code in items:
            if args.card and name.lower() != args.card.lower():
                continue
            if not raw:
                continue
            cards += 1
            text = normalize_text(raw, names)
            anas = find_anaphors(text)
            rewritten = text
            metas = []
            if anas:
                try:
                    res = rulecoref.resolve(
                        text, refs.build(text, parser=args.mentions == 'parser'),
                        anas, parse_ok=parse_ok)
                    rewritten = res.get('rewritten_text', text)
                    metas = [
                        {'surface': a.get('surface'),
                         'antecedent': (a.get('antecedent') or {}).get('surface'),
                         'status': a.get('status')}
                        for a in res.get('anaphors', [])]
                except Exception:
                    rewritten = text
            orig = [it['text'] for it in segment(text, names)
                    if it['text'] and not it['modal']]
            rewr = [it['text'] for it in segment(rewritten, names)
                    if it['text'] and not it['modal']]
            for idx, otext in enumerate(orig):
                rtext = rewr[idx] if idx < len(rewr) else otext
                out = interpret(rtext) if rtext != otext else None
                if out is None or _has_unparsed(out):
                    rtext = otext
                    out = interpret(otext)
                if out is None:
                    out = [{'type': 'unparsed', 'reason': 'parse_fail',
                            'fragment': otext, 'source': 'compile_card'}]
                rec = {
                    'card': name,
                    'sentence_index': idx,
                    'sid': hashlib.sha1(otext.encode()).hexdigest()[:12],
                    'original_text': otext,
                    'resolved_text': rtext,
                    'anaphora': [m for m in metas
                                 if m.get('surface') and m['surface'].lower()
                                 in otext.lower()],
                    'output': out,
                }
                fh.write(json.dumps(rec, sort_keys=True) + '\n')
                records += 1
            if args.limit and cards >= args.limit:
                break
    print(json.dumps({'cards': cards, 'records': records, 'out': args.out},
                     indent=1))


if __name__ == '__main__':
    main()
