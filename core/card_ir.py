"""Card-level IR over the sentence compiler.

The grammar/interpreter remains segment-oriented.  This module only assembles
the already-compiled segments into one card record and adds deterministic
cross-segment links.  Links never invent a semantic parse: they point at the
previous segment whose output contains the relevant action/event.
"""

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


def build_card(name, text, segments, whole=False):
    segments = sorted(segments, key=lambda s: s['index'])
    links = []
    for i, seg in enumerate(segments):
        low = seg['text'].strip().lower()
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
            # "that many" / "this way" normally count an action in the same
            # segment (discard two, draw that many); cross-segment is only
            # right for "the rest"/"those cards" of a prior look/reveal.
            target = (seg['index'] if phrase in ('that many', 'this way')
                      and prev is None else prev)
            if phrase in ('that many', 'this way') and prev is not None:
                source = seg['text'].lower()
                if any(w in source for w in (
                        'discard', 'exile', 'look at', 'reveal', 'draw',
                        'sacrifice', 'mill', 'search')):
                    target = seg['index']
            if target is not None:
                links.append({'from': seg['index'], 'to': target,
                              'kind': kind, 'detail': phrase})
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
    # links are emitted deterministically, one per (from,to,kind,detail)
    uniq = []
    seen = set()
    for link in links:
        key = repr(sorted(link.items()))
        if key not in seen:
            seen.add(key)
            uniq.append(link)
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
