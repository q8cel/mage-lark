#!/usr/bin/env python3
"""Add card-local link ids to sentence outputs; additive keys only.

Run after a fresh compile_standard.jsonl. The per-card link derivation is the
same card_ir.build_card pass used by compile_cards, but this tool only inserts
`link` keys; it never rewrites a scalar or removes a field.
"""
import json, sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
paths.bootstrap()
from card_ir import build_card


PHRASES = ('that many', 'this way', 'the rest', 'those cards', 'that card', 'them')


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def add_paths(obj, phrase, lid):
    added = 0
    for d in walk(obj):
        if not isinstance(d, dict):
            continue
        take = False
        if phrase == 'that many' and d.get('kind') == 'that_many':
            take = True
        elif phrase == 'this way' and d.get('kind') == 'count_of':
            take = True
        elif phrase == 'that card':
            ct = d.get('card_type')
            take = (isinstance(ct, dict) and ct.get('ref') == 'that_card') or \
                   (d.get('this_that') == 'that' and isinstance(ct, dict)
                    and ct.get('value') in ('card', 'cards'))
        elif phrase in ('the rest', 'those cards', 'them'):
            ct = d.get('card_type')
            take = (isinstance(ct, dict) and
                    ct.get('ref') in ('that_card', 'the_rest', 'those_cards')) or \
                   str(d.get('raw', '')).lower() in ('them', 'the rest', 'those cards') or \
                   (d.get('this_that') == 'the' and isinstance(ct, dict)
                    and ct.get('value') in ('card', 'cards', 'creature', 'creatures'))
        if take and 'link' not in d:
            d['link'] = lid
            added += 1
    # Keep the linkage visible even when the scalar is only present as prose.
    if added == 0 and isinstance(obj, dict):
        obj['link'] = lid
        added = 1
    return added


def verify(fresh, post):
    """No removed/changed values; only extra link keys allowed."""
    changed = removed = 0
    added = 0
    def cmp(a, b):
        nonlocal changed, removed, added
        if isinstance(a, dict) and isinstance(b, dict):
            for k, v in a.items():
                if k not in b:
                    removed += 1
                elif k == 'link' and b[k] != v:
                    changed += 1
                else:
                    cmp(v, b[k])
            for k in b:
                if k not in a:
                    added += 1
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                changed += 1
            for x, y in zip(a, b):
                cmp(x, y)
        elif a != b:
            changed += 1
    cmp(fresh.get('output'), post.get('output'))
    return added, removed, changed


def main():
    art = sys.argv[1] if len(sys.argv) > 1 else 'compile_standard.jsonl'
    out = sys.argv[2] if len(sys.argv) > 2 else art + '.linked'
    records = [json.loads(l) for l in open(art)]
    by = {}
    for i, r in enumerate(records):
        by.setdefault(r['card'], []).append(i)
    added = 0
    phrases = {}
    for card, idxs in by.items():
        segs = [{'index': records[i]['sentence_index'],
                 'text': records[i]['original_text'],
                 'resolved_text': records[i].get('resolved_text'),
                 'output': copy.deepcopy(records[i]['output']),
                 'anaphora': records[i].get('anaphora')} for i in idxs]
        ir = build_card(card, '', segs, whole=None)
        for link in ir['links']:
            phrase = link.get('detail')
            if phrase not in PHRASES:
                continue
            lid = link['id']
            for i in idxs:
                r = records[i]
                if r['sentence_index'] != link['from']:
                    continue
                if phrase not in r['original_text'].lower():
                    continue
                n = add_paths(r['output'], phrase, lid)
                added += n
                phrases[phrase] = phrases.get(phrase, 0) + n
    # Verify additive-only against the original
    fresh = [json.loads(l) for l in open(art)]
    post = records
    removed = changed = 0
    for a, b in zip(fresh, post):
        _, rem, ch = verify(a, b)
        removed += rem; changed += ch
    payload = b''.join((json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n').encode()
                       for r in records)
    open(out, 'wb').write(payload)
    print(json.dumps({'records': len(records), 'added': added,
                      'removed': removed, 'changed': changed,
                      'phrases': phrases, 'out': out,
                      'idempotent_second_run': added == 0}, indent=1))

if __name__ == '__main__':
    main()
