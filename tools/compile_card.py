#!/usr/bin/env python3
"""Per-card compiler: resolve one card at a time and emit card-local records.

This is the no-collision engine path.  Unlike the sentence-keyed snapshot,
which dedupes across the corpus and must pick one resolution per sentence, this
command keeps every card's own context:

    {"card", "sentence_index", "sid", "original_text", "resolved_text",
     "anaphora": [...], "output": [...]}

Resolution is on by default (--no-resolve for parity). A rewritten sentence is
used only when it parses and its interpretation has no unparsed marker;
otherwise the original sentence is compiled. Interpretations are memoised by
text in-process and persisted in .cache/compile_out_<interp>_<grammar>.json.
Records are sorted by (card, sentence_index, sid) before writing, so the JSONL
is deterministic for any --workers value. No grammar or interpreter schema
changes.
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

import argparse
import copy
import hashlib
import json
import multiprocessing as mp
import os
import sys
from collections import Counter

from anaphora import find_anaphors
from preprocess import segment
from setdata import load, normalize_text
import refs
import rulecoref

_W = {}


def _has_unparsed(obj):
    if isinstance(obj, dict):
        if obj.get('kind') == 'quoted_ability':
            return False
        return (bool(obj.get('unparsed')) or obj.get('type') == 'unparsed'
                or 'text' in obj
                or any(_has_unparsed(v) for v in obj.values()))
    if isinstance(obj, list):
        return any(_has_unparsed(v) for v in obj)
    return False


def _file_hash(path):
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()[:16]


def _load_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        return json.load(open(path))
    except Exception:
        return {}


def _init_worker(types, names, mentions, resolve, disk_cache):
    from larkparser import build_parser
    from interpret import Interpreter
    _W.clear()
    _W.update({
        'parser': build_parser('interp'),
        'interp': Interpreter(types=types, names=names),
        'names': set(names),
        'mentions': mentions,
        'resolve': resolve,
        'disk': disk_cache,
        'out': {},
        'new': {},
        'stats': Counter(lookups=0, hits=0, misses=0,
                         disk_hits=0, disk_misses=0),
    })


def _compile_card(card):
    name, raw, _code = card
    W = _W
    parser = W['parser']
    interp = W['interp']
    stats = Counter(lookups=0, hits=0, misses=0,
                    disk_hits=0, disk_misses=0)
    W['stats'] = stats
    out_cache = W['out']
    new_cache = W['new']
    disk = W['disk']
    mentions = W['mentions']
    do_resolve = W['resolve']

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
        stats['lookups'] += 1
        if text in out_cache:
            stats['hits'] += 1
            return out_cache[text]
        if text in disk:
            stats['disk_hits'] += 1
            out_cache[text] = disk[text]
            return disk[text]
        stats['disk_misses'] += 1
        stats['misses'] += 1
        try:
            out = interp.interp(parser.parse(text))
        except Exception:
            out = None
        out_cache[text] = out
        new_cache[text] = out
        return out

    text = normalize_text(raw, W.get('names') or set())
    anas = find_anaphors(text)
    rewritten = text
    metas = []
    if anas and do_resolve:
        try:
            res = rulecoref.resolve(
                text, refs.build(text, parser=mentions == 'parser'),
                anas, parse_ok=parse_ok)
            rewritten = res.get('rewritten_text', text)
            metas = [
                {'surface': a.get('surface'),
                 'antecedent': (a.get('antecedent') or {}).get('surface'),
                 'status': a.get('status'),
                 'start': a.get('start'), 'end': a.get('end')}
                for a in res.get('anaphors', [])]
        except Exception:
            rewritten = text
    orig = [it['text'] for it in segment(text, W.get('names') or set())
            if it['text'] and not it['modal']]
    rewr = [it['text'] for it in segment(rewritten, W.get('names') or set())
            if it['text'] and not it['modal']]
    records = []
    cursor = 0
    spans = []
    for otext in orig:
        pos = text.find(otext, cursor)
        if pos < 0:
            pos = text.find(otext)
        if pos < 0:
            spans.append((0, len(text)))
        else:
            spans.append((pos, pos + len(otext)))
            cursor = pos + len(otext)
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
                         if m.get('surface')
                         and ((idx < len(spans)
                               and spans[idx][0] <= (m.get('start') or -1)
                               < spans[idx][1])
                              if m.get('start') is not None
                              else m['surface'].lower() in otext.lower())],
            'output': out,
        }
        records.append(rec)
    return records, dict(stats), new_cache


def _iter_cards(items, names, anaphora_only, limit):
    out = []
    for name, raw, code in items:
        if not raw:
            continue
        if anaphora_only:
            text = normalize_text(raw, names)
            if not find_anaphors(text):
                continue
        out.append((name, raw, code))
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True, help='JSONL output')
    ap.add_argument('--card', default=None, help='only this card name')
    ap.add_argument('--limit', type=int, default=0, help='card cap (testing)')
    ap.add_argument('--sets', default=None,
                    help='comma list of set codes to compile (slice for chunking)')
    ap.add_argument('--mentions', choices=('regex', 'parser'), default='regex')
    ap.add_argument('--resolve', dest='resolve', action='store_true', default=True,
                    help='resolve card context before compiling (default)')
    ap.add_argument('--no-resolve', dest='resolve', action='store_false',
                    help='compile the original text only (parity mode)')
    ap.add_argument('--anaphora-only', action='store_true',
                    help='only cards containing an anaphor')
    ap.add_argument('--workers', type=int, default=1,
                    help='card-level worker processes (default 1)')
    ap.add_argument('--no-out-cache', action='store_true',
                    help='do not read/write the persistent text->output cache')
    args = ap.parse_args()

    items, types, names, _sets = load(args.data)
    if args.sets:
        keep = set(args.sets.split(','))
        items = [it for it in items if it[2] in keep]
    if args.card:
        items = [it for it in items if it[0].lower() == args.card.lower()]
    work = _iter_cards(items, names, args.anaphora_only, args.limit)

    disk_path = None
    disk_cache = {}
    if not args.no_out_cache:
        key = (_file_hash(_paths.source('interpret.py')) + '_'
               + _file_hash(_paths.GRAMMAR))
        disk_path = os.path.join(_paths.CACHE, 'compile_out_%s.json' % key)
        disk_cache = _load_cache(disk_path)

    global _W
    _W = {'types': types, 'names': names, 'mentions': args.mentions,
          'resolve': args.resolve, 'disk': disk_cache}
    # Put names/types where _init_worker can see them via fork.
    _W['types'], _W['names'] = types, names
    if args.workers <= 1:
        _init_worker(types, names, args.mentions, args.resolve, disk_cache)
        _W['names'] = names
        results = [_compile_card(card) for card in work]
    else:
        # fork inherits the disk cache read-only; workers return their misses.
        ctx = mp.get_context()
        with ctx.Pool(args.workers, initializer=_init_worker,
                      initargs=(types, names, args.mentions, args.resolve,
                                disk_cache)) as pool:
            results = list(pool.imap_unordered(_compile_card, work,
                                               chunksize=1))

    records = []
    stats = Counter()
    new_cache = {}
    for recs, st, nc in results:
        records.extend(recs)
        stats.update(st)
        new_cache.update(nc)

    # Deterministic regardless of worker completion order.
    records.sort(key=lambda r: (r['card'], r['sentence_index'], r['sid'],
                                json.dumps(r, sort_keys=True)))
    with open(args.out, 'w') as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + '\n')

    if disk_path:
        try:
            disk_cache.update(new_cache)
            os.makedirs(os.path.dirname(disk_path), exist_ok=True)
            tmp = disk_path + '.tmp'
            json.dump(disk_cache, open(tmp, 'w'))
            os.replace(tmp, disk_path)
        except Exception:
            pass
    print(json.dumps({'cards': len(work), 'records': len(records),
                      'unique_texts': len(new_cache),
                      'text_cache': dict(stats),
                      'workers': args.workers,
                      'out_cache': disk_path, 'out': args.out},
                     indent=1))


if __name__ == '__main__':
    main()
