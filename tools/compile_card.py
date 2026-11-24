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
import re
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

# ---------------------------------------------------------------------------
# Target-set quantifier contract.  Enforced on every emitted record (including
# cached interpretations) so the engine always sees an explicit quantifier for
# an effect target set.  Mirrors Interpreter._normalize_effect_quantifiers; the
# compiler is the boundary that guarantees the IR contract.

TARGET_KEYS = ('card', 'target', 'object', 'spell', 'on')
_WORD_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
             'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
             'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
             'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
             'nineteen': 19, 'twenty': 20}


def _is_target_set(v):
    if not isinstance(v, dict):
        return False
    if any(k in v for k in ('card_type', 'quantifier', 'colors',
                             'this_that', 'ref', 'status', 'controller')):
        return True
    return v.get('kind') in ('set', 'property') and (
        'items' in v or 'label' in v)


def _type_values(ct):
    out = []
    if isinstance(ct, dict):
        if isinstance(ct.get('value'), str):
            out.append(ct['value'])
    elif isinstance(ct, list):
        for item in ct:
            out.extend(_type_values(item))
    return out


def _normalize_card_types(ts):
    ct = ts.get('card_type')
    if not isinstance(ct, list):
        return
    out = []
    for item in ct:
        if (isinstance(item, dict) and isinstance(item.get('value'), str)
                and re.search(r'\s+or\s+', item['value'])):
            for part in re.split(r'\s+or\s+', item['value']):
                part = part.strip()
                if not part:
                    continue
                entry = {'kind': item.get('kind', 'type'), 'value': part}
                if entry not in out:
                    out.append(entry)
        elif item not in out:
            out.append(item)
    ct[:] = out


def _normalize_quantifier_shape(ts):
    _normalize_card_types(ts)
    q = ts.get('quantifier')
    if not isinstance(q, dict):
        return
    if 'at_least' in q and 'at_most' in q:
        ts['quantifier'] = {'up_to': q['at_most']}
    elif set(q) == {'kind'}:
        if str(q.get('kind')).lower() == 'x':
            ts['quantifier'] = 'any'
    elif 'up_to' in q:
        val = q['up_to']
        if isinstance(val, dict) and str(val.get('kind')).lower() == 'x':
            ts['quantifier'] = 'any'
        elif isinstance(val, str) and val.lower() in _WORD_NUM:
            ts['quantifier'] = {'up_to': _WORD_NUM[val.lower()]}


def _infer_quantifier(ts):
    if ts.get('quantifier') is not None:
        return
    ct = ts.get('card_type')
    if isinstance(ct, dict) and ct.get('kind') == 'this_card':
        ts['quantifier'] = 'a'
        return
    if isinstance(ct, dict) and ct.get('ref') == 'anaphora':
        raw = str(ct.get('raw') or '').lower()
        ts['quantifier'] = ('all' if raw in ('they', 'them', 'their')
                            else 'a')
        return
    values = ' '.join(_type_values(ct)).lower()
    words = [w for w in re.split(r'[^a-z+]+', values) if w]
    plural = any(w.endswith('s') and not w.endswith('ss')
                 and w not in ('this', 'its') for w in words)
    ts['quantifier'] = 'all' if plural else 'a'


ZONE_WORDS = {'hand', 'library', 'battlefield', 'graveyard', 'exile', 'stack'}
# These verbs' effect-level `zone` is the destination, not the source.
DEST_VERBS = {'put', 'return', 'shuffle', 'mill'}


def _effect_source_zone(obj):
    if obj.get('verb') in DEST_VERBS:
        return None
    z = obj.get('zone')
    if isinstance(z, str) and z in ZONE_WORDS:
        return {'prep': 'from', 'zone': z}
    if isinstance(z, dict) and z.get('zone') in ZONE_WORDS:
        out = dict(z)
        out.setdefault('prep', 'from')
        return out
    return None


# Exact-semantics controller mappings.  Anything not listed keeps the
# {kind:"controller", ref, unresolved:true} form instead of a guessed shape.
CONTROLLER_MAP = {
    "you don't control": {'kind': 'player', 'ref': 'you',
                          'relation': 'controls', 'negated': True},
    "you don't own": {'kind': 'player', 'ref': 'you',
                      'relation': 'own', 'negated': True},
    'target player controls': {'kind': 'player', 'ref': 'target player',
                               'relation': 'controls'},
    'its controller': {'kind': 'player', 'ref': 'its controller'},
    # owner semantics: keep the relation, but the owner of X is not resolved
    # unless the text names X.
    'owner': {'kind': 'controller', 'ref': 'owner',
              'relation': 'owner', 'unresolved': True},
    'their owners': {'kind': 'controller', 'ref': 'owner',
                     'relation': 'owner', 'plural': True},
    'her owner': {'kind': 'controller', 'ref': 'owner',
                  'relation': 'owner', 'possessive': 'her'},
    'controlled by different players': {
        'kind': 'controller', 'ref': 'different players',
        'relation': 'controls', 'distinct': True},
}
WHO_REF_FIX = {"that creature 's controller": 'its controller',
               "that land 's controller": 'its controller'}


PLAYER_CARD_WORDS = {
    'you': 'you', 'opponent': 'opponent', 'an opponent': 'opponent',
    'each opponent': 'each opponent', 'each player': 'each player',
    'all players': 'each player', 'every player': 'each player',
    'players': 'each player', 'target player': 'opponent',
    'target opponent': 'opponent', 'defending player': 'opponent',
    'that player': 'opponent', 'its controller': 'opponent',
    'any player': 'each player', 'a player': 'each player',
    'another player': 'each player',
}


def _normalize_refs(obj):
    if (obj.get('verb') == 'put'
            and isinstance(obj.get('counter'), dict)
            and obj.get('object') is not None):
        # "Whenever you put one or more +1/+1 counters on this creature":
        # a counters-placed event, with the permanent as its subject.
        actor = obj.pop('subject', None)
        obj['subject'] = obj.pop('object')
        if actor is not None:
            obj['actor'] = actor
        obj['verb'] = 'counters_placed'
    if isinstance(obj.get('verb'), str):
        for key in ('to', 'card', 'object', 'target', 'spell'):
            ts = obj.get(key)
            ct = ts.get('card_type') if isinstance(ts, dict) else None
            if not isinstance(ct, dict) or ct.get('kind') != 'type':
                continue
            mapped = PLAYER_CARD_WORDS.get(str(ct.get('value', '')).lower())
            if mapped:
                obj['player_target'] = mapped
                del obj[key]
    # Trigger event subjects and for_each/count slots that name a player are
    # player refs, not card types.
    for key in ('subject', 'on', 'of'):
        v = obj.get(key)
        ct = v.get('card_type') if isinstance(v, dict) else None
        if not isinstance(ct, dict) or ct.get('kind') != 'type':
            continue
        mapped = PLAYER_CARD_WORDS.get(str(ct.get('value', '')).lower())
        if not mapped:
            continue
        new = {'kind': 'player', 'ref': mapped}
        if key == 'subject' and isinstance(v.get('quantifier'), dict):
            new['quantifier'] = v['quantifier']
        obj[key] = new
    if obj.get('type') in ('if', 'branch') and isinstance(obj.get('effect'), list):
        obj['then'] = obj.pop('effect')
    co = obj.get('copy_of')
    if isinstance(co, dict) and not co.get('link'):
        ct = co.get('card_type')
        if isinstance(ct, dict) and ct.get('ref') == 'anaphora':
            ct.setdefault('kind', 'anaphora')
            ct.setdefault('status', 'unresolved')
            co.setdefault('status', 'unresolved')
    w = obj.get('who')
    if isinstance(w, dict) and w.get('kind') == 'player':
        fixed = WHO_REF_FIX.get(str(w.get('ref')))
        if fixed:
            w['ref'] = fixed
            if 'selection' in w:
                w['selection'] = fixed
    c = obj.get('controller')
    if isinstance(c, dict) and c.get('unresolved') is True:
        ref, rel = str(c.get('ref')), str(c.get('relation') or '')
        if ref == 'you' and rel == 'cast':
            obj['controller'] = {'kind': 'player', 'ref': 'you',
                                 'relation': 'cast'}
        elif ref == 'they' and rel == 'controls':
            obj['controller'] = {'kind': 'player', 'ref': 'they',
                                 'relation': 'controls'}
        elif ref == 'those players' and rel == 'controls':
            obj['controller'] = {'kind': 'player', 'ref': 'those players',
                                 'relation': 'controls'}
        else:
            repl = CONTROLLER_MAP.get(ref)
            if repl:
                obj['controller'] = dict(repl)


def _split_multi_event(node):
    """Duplicate a triggered ability once per event verb.

    The builder reads a single event; "enters or attacks" therefore becomes
    two triggered abilities that share the same effect.
    """
    if isinstance(node, list):
        out = []
        for x in node:
            xs = _split_multi_event(x)
            out.extend(xs if isinstance(xs, list) else [xs])
        return out
    if isinstance(node, dict):
        for k, v in list(node.items()):
            node[k] = _split_multi_event(v)
        if node.get('type') != 'triggered':
            return node
        tr = node.get('trigger')
        ev = tr.get('event') if isinstance(tr, dict) else node.get('event')
        if not isinstance(ev, dict):
            return node
        verb = ev.get('verb')
        if not (isinstance(verb, dict) and verb.get('kind') == 'event'
                and isinstance(verb.get('verbs'), list)
                and len(verb['verbs']) > 1):
            return node
        out = []
        for v in verb['verbs']:
            w = json.loads(json.dumps(node))
            if isinstance(w.get('trigger'), dict):
                w['trigger']['event']['verb'] = v
            else:
                w['event']['verb'] = v
            out.append(w)
        return out
    return node


def _ensure_target_quantifiers(obj, in_effect=False):
    if isinstance(obj, dict):
        _normalize_refs(obj)
        if _is_target_set(obj):
            _normalize_card_types(obj)
            if isinstance(obj.get('quantifier'), dict):
                _normalize_quantifier_shape(obj)
        if in_effect and isinstance(obj.get('verb'), str):
            sets = [obj.get(k) for k in TARGET_KEYS]
            cards = obj.get('cards')
            if isinstance(cards, list):
                sets.extend(cards)
            src = _effect_source_zone(obj)
            if src:
                for ts in sets:
                    if _is_target_set(ts) and not ts.get('zone'):
                        ts['zone'] = dict(src)
            for ts in sets:
                if _is_target_set(ts):
                    _normalize_quantifier_shape(ts)
                    _infer_quantifier(ts)
        for k, v in obj.items():
            if k == 'text':
                continue
            _ensure_target_quantifiers(v, in_effect or k == 'effect')
    elif isinstance(obj, list):
        for v in obj:
            _ensure_target_quantifiers(v, in_effect)


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
        else:
            _ensure_target_quantifiers(out)
            out = _split_multi_event(out)
        rec = {
            'card': name,
            'set_code': _code,
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
    # Keep choose-one options nested on the parent sentence record.
    try:
        pieces = segment(text, W.get('names') or set())
        def is_modal(p):
            return bool(p.get('modal') or re.search(
                r'\bchoose\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b',
                p.get('text', ''), re.I))
        by_text = {r['original_text']: r for r in records}
        consume = set()
        groups = []
        i = 0
        while i < len(pieces):
            if not is_modal(pieces[i]):
                i += 1
                continue
            opts = []
            j = i + 1
            while j < len(pieces):
                p = pieces[j]
                if is_modal(p):
                    break
                if p.get('bullet'):
                    opts.append({'text': p['text'],
                                 'output': (by_text.get(p['text']) or {}).get('output'),
                                 'continuations': []})
                elif opts:
                    opts[-1]['continuations'].append({
                        'text': p['text'],
                        'output': (by_text.get(p['text']) or {}).get('output')})
                else:
                    break
                j += 1
            if opts:
                groups.append((pieces[i]['text'], opts))
                for opt in opts:
                    consume.add(opt['text'])
                    for c in opt['continuations']:
                        consume.add(c['text'])
                i = j
            else:
                i += 1
        if groups:
            records = [r for r in records if r['original_text'] not in consume]
            for text0, opts in groups:
                def cont_item(c):
                    out = c.get('output') or []
                    if out and isinstance(out[0], dict) and out[0].get('type') == 'effect':
                        return {'type': 'effect', 'effect': out[0].get('effect'),
                                'text': c['text']}
                    return {'type': 'effect', 'effect': {}, 'text': c['text'],
                            'output': out}
                nested = [{'text': o['text'], 'output': o['output'],
                           'continuations': [cont_item(c)
                                             for c in o['continuations']]}
                          for o in opts]
                parent = next((r for r in records
                               if r['original_text'] == text0), None)
                if parent is None:
                    idx0 = min((o.get('sentence_index', 0) for o in
                                [by_text.get(x) for x in consume] if o), default=0)
                    parent = {'card': name, 'set_code': _code,
                              'sentence_index': idx0,
                              'sid': hashlib.sha1(text0.encode()).hexdigest()[:12],
                              'original_text': text0, 'resolved_text': text0,
                              'anaphora': [],
                              'output': [{'type': 'choose_one', 'options': nested}]}
                    records.append(parent)
                else:
                    parent['output'] = [{'type': 'choose_one', 'options': nested}]
            records.sort(key=lambda r: r['sentence_index'])
    except Exception:
        pass
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
        # The contract pass lives in this file and runs after cache lookup, but
        # a change here must never silently reuse outputs from a different
        # compiler contract.
        key = (_file_hash(_paths.source('interpret.py')) + '_'
               + _file_hash(_paths.GRAMMAR) + '_'
               + _file_hash(os.path.abspath(__file__)))
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
