#!/usr/bin/env python3
"""Shared, opt-in card-context resolution for the interpretation path.

The resolver works on a whole card; run.py/snapshot.py work on unique
sentences.  This module builds the bridge:

    original segmented sentence -> (resolved_text, anaphora metadata)

The mapping is keyed by the *original* segmented sentence, so coverage caches,
ledgers and snapshots keep their existing keys.  Resolution never adds a
sentence: original and rewritten card texts are segmented and paired by index,
and any pairing mismatch leaves the original sentence unresolved.
"""

import os as _os, sys as _sys, json, hashlib, time
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()

from collections import Counter

from anaphora import find_anaphors
from preprocess import segment
from setdata import normalize_text
import refs
import rulecoref

_PARSER = None


def _parse_ok(text):
    global _PARSER
    segs = [it['text'] for it in segment(text) if it['text']]
    if not segs:
        return True
    if _PARSER is None:
        from larkparser import build_parser
        _PARSER = build_parser('interp')
    for s in segs:
        try:
            _PARSER.parse(s)
        except Exception:
            return False
    return True


def _segments(text, names):
    return [it for it in segment(text, names) if it['text'] and not it['modal']]


def _file_hash(path):
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()[:16]


def _plan_cache_path(data_path, mentions):
    key = _file_hash(data_path) + '_' + mentions
    for name in ('rulecoref.py', 'refs.py', 'anaphora.py', 'interpret_resolve.py'):
        key += '_' + _file_hash(_paths.source(name))
    return _os.path.join(_paths.CACHE, 'resolve_plan_%s.json' % key)


def build_plan(items, names, mentions='regex', data_path=None):
    """Return (plan, stats). plan[sentence] = {resolved_text, anaphora}.

    items: [(name, raw_text, code)] from setdata.load.
    Only cards with anaphors are resolved; every other sentence is absent from
    the plan (the caller falls back to the original text).
    """
    parser_mentions = mentions == 'parser'
    cache_path = _plan_cache_path(data_path, mentions) if data_path else None
    if cache_path and _os.path.exists(cache_path):
        try:
            blob = json.load(open(cache_path))
            if blob.get('mentions') == mentions:
                blob['stats']['plan_cache'] = 'hit'
                return blob['plan'], blob['stats']
        except Exception:
            pass
    plan = {}
    stats = Counter()
    stats['cards'] = 0
    errors = []
    for name, raw, _code in items:
        if not raw:
            continue
        text = normalize_text(raw, names)
        anas = find_anaphors(text)
        if not anas:
            continue
        stats['cards'] += 1
        stats['anaphors'] += len(anas)
        try:
            res = rulecoref.resolve(
                text, refs.build(text, parser=parser_mentions), anas,
                parse_ok=_parse_ok)
        except Exception as exc:
            stats['errors'] += 1
            if len(errors) < 5:
                errors.append(f'{name}: {type(exc).__name__}')
            continue
        stats['rewritten_cards'] += bool(res.get('rewritten_text') != text)
        rs = res.get('rewrite_stats') or {}
        stats['applied'] += rs.get('applied', 0)
        stats['reverted'] += rs.get('reverted', 0)
        for k in ('skip_slot', 'skip_number', 'skip_possessive', 'skip_set'):
            stats[k] += rs.get(k, 0)
        for a in res.get('anaphors', []):
            stats['status_' + a.get('status', 'unknown')] += 1

        orig = _segments(text, names)
        rewritten = _segments(res.get('rewritten_text', text), names)
        if len(orig) != len(rewritten):
            stats['pairing_mismatch'] += 1
            continue

        # Original character spans, so anaphora metadata follows its sentence.
        spans = refs.sentence_spans(text)
        for idx, (a, b) in enumerate(zip(orig, rewritten)):
            otext = a['text']
            rtext = b['text']
            lo, hi = (spans[idx] if idx < len(spans) else (0, len(text)))
            metas = []
            for an in res.get('anaphors', []):
                if lo <= an.get('start', -1) < hi:
                    ant = an.get('antecedent') or {}
                    metas.append({
                        'surface': an.get('surface'),
                        'antecedent': ant.get('surface'),
                        'status': an.get('status'),
                    })
            if otext in plan:
                stats['sentence_collisions'] += 1
                if plan[otext]['resolved_text'] != rtext:
                    plan[otext]['collision'] = True
                continue
            if rtext != otext or metas:
                plan[otext] = {'resolved_text': rtext,
                               'anaphora': metas}
            if rtext != otext:
                stats['sentences_changed'] += 1
    stats['plan_sentences'] = len(plan)
    stats['collisions'] = stats['sentence_collisions']
    if errors:
        stats['error_examples'] = errors
    stats = dict(stats)
    stats['plan_cache'] = 'miss'
    if cache_path:
        try:
            _os.makedirs(_os.path.dirname(cache_path), exist_ok=True)
            tmp = cache_path + '.tmp'
            json.dump({'mentions': mentions, 'plan': plan, 'stats': stats},
                      open(tmp, 'w'))
            _os.replace(tmp, cache_path)
        except Exception:
            pass
    return plan, stats
