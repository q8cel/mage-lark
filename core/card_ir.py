"""Card-level IR over the sentence compiler.

The grammar/interpreter remains segment-oriented.  This module assembles the
already-compiled segments into one card record and adds deterministic links.
A demonstrative/reference link always points at a *preceding* segment.  When
the quantity is genuinely inside one segment (a trigger's "one or more" and
its effect's "that many"), the link is explicitly kind=intra and the scalar
points at that link id; it is never emitted as a self-link in the quantity
namespace.
"""

import json
import re


def _iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def _entity_names(segments):
    names = []
    for seg in segments:
        for d in _iter_dicts(seg.get('output')):
            named = d.get('named')
            if isinstance(named, list):
                names.extend(str(x) for x in named if x)
            tok = d.get('token')
            if isinstance(tok, str):
                names.append(tok)
        for m in re.finditer(r"\btoken named ([A-Z][\w'-]+)", seg['text']):
            names.append(m.group(1))
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append({'id': n, 'kind': 'token', 'self': False})
    out.append({'id': '~', 'kind': 'self', 'self': True})
    return out


def _low(seg):
    return (seg.get('text') or '').strip().lower()


def _has_quantity(seg):
    """An action that can be the antecedent of 'that many'/'this way'."""
    return bool(re.search(
        r'\b(discard|mill|exile|look at|reveal|draw|sacrifice|search)\b',
        _low(seg)))


def _is_source(seg):
    """A set-producing action for 'the rest'/'those cards'."""
    return bool(re.search(
        r'(look at|reveal|exile|search|top .*library|from among them)',
        _low(seg)))


def _pick_back(segments, i, predicate):
    for j in range(i - 1, -1, -1):
        if predicate(segments[j]):
            return segments[j]['index']
    return None


def _assign_link_ids(links):
    seen = {}
    for link in links:
        detail = link.get('detail')
        if isinstance(detail, dict):
            slug = str(detail.get('surface') or detail.get('antecedent') or 'ref')
        else:
            slug = str(detail or '')
        slug = re.sub(r'[^a-z0-9]+', '_', slug.lower()).strip('_')
        base = 'L{}->{}:{}:{}'.format(link['from'], link['to'],
                                      link['kind'], slug or 'ref')
        n = seen.get(base, 0)
        seen[base] = n + 1
        link['id'] = base if n == 0 else base + ':' + str(n)
    return links


def _ref_key(link):
    return (link['from'], link.get('detail'))


def _apply_scalars(segments, links):
    """Make prose demonstratives point at their link id."""
    by_from = {}
    for link in links:
        by_from.setdefault(link['from'], []).append(link)
    for seg in segments:
        out = seg.get('output')
        if not out:
            continue
        ls = by_from.get(seg['index'], [])
        ids = {str(l.get('detail')).lower(): l['id'] for l in ls}
        for d in _iter_dicts(out):
            # A095: "cards discarded this way" -> count_of.of.link
            if d.get('kind') == 'count_of' and 'this way' in json.dumps(
                    d, ensure_ascii=False).lower():
                lid = ids.get('this way')
                if lid:
                    d.clear()
                    d.update({'kind': 'count_of', 'relation': 'equal',
                              'of': {'link': lid}})
                    continue
            # A033/A070: that many scalar points at the link.
            if d.get('kind') == 'that_many' and 'that many' in ids:
                d['link'] = ids['that many']
            # A004/A070: that card points at its link instead of prose.
            ct = d.get('card_type')
            if isinstance(ct, dict) and ct.get('ref') == 'that_card' \
                    and 'that card' in ids:
                d['link'] = ids['that card']
                d['card_type'] = {'kind': 'link',
                                  'link': ids['that card']}
                d.pop('this_that', None)
                d['anaphor'] = True


def build_card(name, text, segments, whole=False):
    segments = sorted(segments, key=lambda s: s['index'])
    links = []
    for i, seg in enumerate(segments):
        low = _low(seg)
        prev = segments[i - 1]['index'] if i else None
        if re.match(r'^if you (do|don\'t)\b', low) and prev is not None:
            links.append({
                'from': seg['index'], 'to': prev,
                'kind': ('event_negative' if "don't" in low.split()[2:3]
                         else 'event_positive'),
                'detail': 'condition refers to the previous segment event'})
        for phrase, kind in (
                ('this way', 'quantity'),
                ('that many', 'quantity'),
                ('the rest', 'anaphora'),
                ('those cards', 'anaphora'),
                ('that card', 'anaphora')):
            if phrase not in low:
                continue
            if phrase == 'this way':
                target = prev
                lkind = 'quantity'
            elif phrase == 'that many':
                target = _pick_back(segments, i, _has_quantity)
                lkind = 'quantity' if target is not None else 'intra'
            elif phrase in ('the rest', 'those cards'):
                # Prefer the actual set-producing action (look at/top of
                # library); reveal-from-among is only a fallback.
                target = _pick_back(
                    segments, i,
                    lambda x: bool(re.search(
                        r'(look at|top .*library)', _low(x))))
                if target is None:
                    target = _pick_back(segments, i, _is_source)
                lkind = 'anaphora'
            else:  # that card
                target = _pick_back(segments, i, _has_quantity)
                lkind = 'anaphora'
            if target is not None:
                links.append({'from': seg['index'], 'to': target,
                              'kind': lkind, 'detail': phrase})
            elif phrase == 'that many':
                links.append({'from': seg['index'], 'to': seg['index'],
                              'kind': 'intra', 'detail': phrase})
        if re.search(r'\b(this creature|this card)\b', low):
            links.append({'from': seg['index'], 'to': seg['index'],
                          'kind': 'self', 'detail': '~'})
        for an in seg.get('anaphora') or []:
            if not isinstance(an, dict) or an.get('status') != 'resolved':
                continue
            if prev is None:
                continue
            links.append({
                'from': seg['index'], 'to': prev, 'kind': 'anaphora',
                'detail': {'surface': an.get('surface'),
                           'antecedent': an.get('antecedent')}})
    uniq = []
    seen = set()
    for link in links:
        key = repr(sorted(link.items()))
        if key not in seen:
            seen.add(key)
            uniq.append(link)
    _assign_link_ids(uniq)
    _apply_scalars(segments, uniq)
    return {
        'card': name,
        'text': text,
        'segments': [{'index': s['index'], 'text': s['text'],
                      'resolved_text': s.get('resolved_text'),
                      'output': s.get('output')} for s in segments],
        'links': uniq,
        'entities': _entity_names(segments),
        'whole_text_parse': bool(whole),
    }
