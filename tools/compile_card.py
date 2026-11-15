#!/usr/bin/env python3
"""Per-card compiler: resolve one card at a time and emit card-local records.

This is the no-collision path for downstream consumers.  Unlike the
sentence-keyed snapshot, which dedupes across the corpus and must pick one
resolution per sentence, this command keeps every card's own context:

    {"card", "sentence_index", "sid", "original_text", "resolved_text",
     "anaphora": [...], "output": [...]}

Resolution is on by default; use --no-resolve for parity. A rewritten
sentence is used only when it parses and its interpretation has no unparsed
marker; otherwise the original sentence is compiled. No grammar or interpreter
schema changes.
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
    ap.add_argument('--resolve', dest='resolve', action='store_true', default=True,
                    help='resolve card context before compiling (default)')
    ap.add_argument('--no-resolve', dest='resolve', action='store_false',
                    help='compile the original text only (parity mode)')
    ap.add_argument('--anaphora-only', action='store_true',
                    help='only cards containing an anaphor')
    ap.add_argument('--no-out-cache', action='store_true',
                    help='do not read/write the persistent text->output cache')
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

    out_cache = {}
    cache_stats = {'lookups': 0, 'hits': 0, 'misses': 0,
                   'disk_hits': 0, 'disk_misses': 0}
    disk_cache = {}
    disk_path = None
    if not args.no_out_cache:
        def _fh(path):
            h = hashlib.sha1()
            with open(path, 'rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    h.update(block)
            return h.hexdigest()[:16]
        key = _fh(_paths.source('interpret.py')) + '_' + _fh(_paths.GRAMMAR)
        disk_path = _os.path.join(_paths.CACHE, 'compile_out_%s.json' % key)
        if _os.path.exists(disk_path):
            try:
                disk_cache = json.load(open(disk_path))
            except Exception:
                disk_cache = {}
    _MISSING = object()

    def interpret(text):
        cache_stats['lookups'] += 1
        if text in out_cache:
            cache_stats['hits'] += 1
            return out_cache[text]
        sentinel = disk_cache.get(text, _MISSING)
        if sentinel is not _MISSING:
            cache_stats['disk_hits'] += 1
            out_cache[text] = sentinel
            return sentinel
        cache_stats['disk_misses'] += 1
        cache_stats['misses'] += 1
        try:
            out = interp.interp(parser.parse(text))
        except Exception:
            out = None
        out_cache[text] = out
        return out

    cards = 0
    records = 0
    with open(args.out, 'w') as fh:
        for name, raw, _code in items:
            if args.card and name.lower() != args.card.lower():
                continue
            if not raw:
                continue
            text = normalize_text(raw, names)
            anas = find_anaphors(text)
            if args.anaphora_only and not anas:
                continue
            cards += 1
            rewritten = text
            metas = []
            if anas and args.resolve:
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
    if disk_path:
        try:
            disk_cache.update(out_cache)
            _os.makedirs(_os.path.dirname(disk_path), exist_ok=True)
            tmp = disk_path + '.tmp'
            json.dump(disk_cache, open(tmp, 'w'))
            _os.replace(tmp, disk_path)
        except Exception:
            pass
    print(json.dumps({'cards': cards, 'records': records,
                      'unique_texts': len(out_cache),
                      'text_cache': cache_stats,
                      'out_cache': disk_path, 'out': args.out},
                     indent=1))


if __name__ == '__main__':
    main()
