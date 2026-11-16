#!/usr/bin/env python3
"""Tree-walker interpreter: parse tree  ->  atomic, structured dicts.

Why a walker and not a Lark Transformer?
    Lark's Transformer works bottom-up: a rule's method receives children that
    are ALREADY transformed. If a child rule has its own method (returning a
    dict/list/str), the parent can no longer tell it apart by `tree.data` —
    every `c.data == 'x'` check silently fails and the atomic decomposition is
    lost (card_target would collapse to {}).
    A top-down walker keeps the full parse tree intact and inspects `node.data`
    on the raw tree, so identification is always reliable.

Usage:
    from interpret import Interpreter
    it = Interpreter()                      # loads the FDN type/name sets
    out = it.interp(parser.parse(sentence)) # -> list of sentence dicts
"""

import os as _os, sys as _sys, re
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
from lark import Token, Tree

from lists import decode as decode_list_token, KEYWORDS as LIST_KEYWORDS
from mtd import card_type_set, name_set
from clause_metric import classify_clause, CLAUSE, EXPRESSION


def _tree_text(node):
    """All the terminal text under `node`, space-joined."""
    parts = []

    def walk(n):
        if isinstance(n, Token):
            parts.append(n.value)
        elif isinstance(n, Tree):
            for ch in n.children:
                walk(ch)

    walk(node)
    return ' '.join(p for p in parts if p)


class Interpreter:
    def __init__(self, types=None, names=None):
        self._types = types or card_type_set()
        self._names = names or name_set()

    # ------------------------------------------------------------------ tokens
    def _tok(self, t):
        if t.type == 'NUMBER':
            return int(t.value)
        if t.type == 'THIS_CARD':
            return {'kind': 'this_card', 'value': '~'}
        if t.type == 'CARDNAME':
            return self._resolve_kind(t.value)
        if t.type == 'GENERIC_TYPE':
            return {'kind': 'type', 'value': t.value.lower()}
        if t.type == 'COLOR':
            return t.value.lower()
        if t.type == 'INSTANT_SORCERY':
            return {'kind': 'type', 'value': 'instant or sorcery'}
        return t.value

    ANAPHORA = {'it', 'its', "it's", 'they', 'them', 'their',
                'he', 'him', 'his', 'she', 'her'}
    # card_kind's literal ability alternatives produce these keyword tokens; the
    # target is an ability ("activated abilities"), never the first word as a type.
    ABILITY_TOKENS = {'ACTIVATED', 'TRIGGERED', 'ABILITY', 'ABILITIES',
                      'SPELL', 'SPELLS', 'OR', 'AND'}
    WORD_NUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
                'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
                'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
                'twenty': 20}
    def _resolve_kind(self, name):
        # Pronouns are references to an entity in context, NOT card types.
        # We mark them honestly; cross-sentence resolution is a later discourse pass.
        if name.lower() in self.ANAPHORA:
            return {'ref': 'anaphora', 'raw': name}
        if name in self._types:
            return {'kind': 'type', 'value': name}
        if name in self._names:
            return {'kind': 'name', 'value': name}
        return {'kind': 'type', 'value': name, 'note': 'unresolved'}

    # ------------------------------------------------------------------ helpers
    def _text(self, children):
        parts = []
        for ch in children:
            if isinstance(ch, Token):
                parts.append(ch.value)
            elif isinstance(ch, Tree):
                parts.append(_tree_text(ch))
        return ' '.join(p for p in parts if p)

    def _find(self, children, name):
        return [c for c in children if isinstance(c, Tree) and c.data == name]

    def _find_one(self, children, name):
        f = self._find(children, name)
        return f[0] if f else None

    def _find_all(self, children, name):
        """Recursively find every Tree named `name` anywhere in the subtree."""
        out = []
        for c in children:
            if isinstance(c, Tree):
                if c.data == name:
                    out.append(c)
                out.extend(self._find_all(c.children, name))
        return out

    # Duration/timing clauses are matched by the grammar as literal tokens
    # (e.g. gain_kw_action's `("until" "end" "of" "turn")?`). The handlers
    # must read them back out: a keyword grant without its time limit says
    # something different, and a delayed sacrifice without its timing loses
    # *when* it happens. Canonical, lower-case values.
    DURATION_VERBS = {'stat_change', 'gain_kw', 'gain_quote', 'lose_keywords',
                      'set_base_pt', 'become', "can't", 'play', 'cast', 'exile',
                      'gain_control', 'no_max_hand_size', 'prevent_damage'}
    DURATION_TAILS = (
        (('until', 'end', 'of', 'turn'), 'until end of turn'),
        (('until', 'the', 'end', 'of', 'your', 'next', 'turn'),
         'until the end of your next turn'),
        (('until', 'the', 'end', 'of', 'their', 'next', 'turn'),
         'until the end of their next turn'),
        (('until', 'your', 'next', 'turn'), 'until your next turn'),
        (('until', 'their', 'next', 'turn'), 'until their next turn'),
    )
    TIMING_TAILS = (
        (('at', 'the', 'beginning', 'of', 'the', 'next', 'end', 'step'),
         'at the beginning of the next end step'),
        (('at', 'the', 'beginning', 'of', 'your', 'next', 'end', 'step'),
         'at the beginning of your next end step'),
        (('at', 'the', 'beginning', 'of', 'their', 'next', 'end', 'step'),
         'at the beginning of their next end step'),
        (('at', 'end', 'of', 'combat'), 'at end of combat'),
    )

    @staticmethod
    def _match_tail(words, tails):
        for i in range(len(words)):
            for tail, phrase in tails:
                if tuple(words[i:i + len(tail)]) == tail:
                    return phrase
        return None

    def _duration(self, children):
        found = self._match_tail(self._token_words(children), self.DURATION_TAILS)
        if found:
            return found
        # "play card_target until any_text" / "for as long as any_text": the
        # tail is a subtree, not literal tokens.
        for i, ch in enumerate(children):
            if not isinstance(ch, Token):
                continue
            lead = str(ch).lower()
            rest = [str(c).lower() for c in children[i + 1:i + 4]
                    if isinstance(c, Token)]
            if lead == 'until':
                prefix = 'until'
            elif lead == 'for' and rest[:3] == ['as', 'long', 'as']:
                prefix = 'for as long as'
            else:
                continue
            for nxt in children[i + 1:]:
                if isinstance(nxt, Tree) and nxt.data == 'any_text':
                    txt = self.interp(nxt)
                    if isinstance(txt, dict):
                        txt = txt.get('text', '')
                    return (prefix + ' ' + str(txt)).strip()
        return None

    def _timing(self, children):
        return self._match_tail(self._token_words(children), self.TIMING_TAILS)

    def _placement(self, children):
        """Top/bottom of a library, rest-of-set objects, and ordering.

        The grammar matches these as literal sibling tokens ("the top card of
        your library", "on the bottom … in a random order"); without this the
        action keeps only `zone: library` and loses where in the library.
        """
        words = self._token_words(children)
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'order_mod':
                words += [str(c).lower() for c in ch.children
                          if isinstance(c, Token)]
        d = {}
        if 'top' in words:
            i = words.index('top')
            if 'on' in words and words.index('on') < i:
                d['placement'] = 'top'
            else:
                d['top'] = True
            if 'second' in words:
                d['from_top'] = 2
            elif 'third' in words:
                d['from_top'] = 3
        if 'bottom' in words:
            d['placement'] = 'bottom'
        if 'order' in words:
            if 'random' in words:
                d['order'] = 'random'
            elif 'any' in words:
                d['order'] = 'any'
        if 'rest' in words:
            d['rest'] = True
        return d

    def _for_each(self, children):
        """The "for each <set>" multiplier, as a direct or cost_qual subtree."""
        words = self._token_words(children)
        if 'for' not in words or 'each' not in words:
            # cost_mod keeps the phrase in a cost_qual subtree.
            for ch in children:
                if isinstance(ch, Tree) and ch.data == 'cost_qual':
                    qw = self._token_words(ch.children)
                    if 'for' in qw and 'each' in qw:
                        for sub in ch.children:
                            if isinstance(sub, Tree) and sub.data in ('card_target', 'any_text'):
                                return self.interp(sub)
            return None
        start = next(i for i, ch in enumerate(children)
                     if isinstance(ch, Token) and str(ch).lower() == 'for')
        for nxt in children[start + 1:]:
            if not isinstance(nxt, Tree):
                continue
            if nxt.data in ('card_target', 'any_text'):
                val = self.interp(nxt)
                if isinstance(val, dict) and 'colors' in words:
                    val = dict(val); val['colors'] = True
                return val
            if nxt.data == 'cost_qual':
                for sub in nxt.children:
                    if isinstance(sub, Tree) and sub.data in ('card_target', 'any_text'):
                        return self.interp(sub)
        return None

    @staticmethod
    def _token_words(children):
        return [str(ch).lower() for ch in children if isinstance(ch, Token)]

    def _first_number(self, children):
        for ch in children:
            if isinstance(ch, Token):
                if ch.type == 'NUMBER':
                    try:
                        return int(ch.value)
                    except ValueError:
                        return ch.value
                v = ch.value.lower()
                if v in self.WORD_NUM:
                    return self.WORD_NUM[v]
            if isinstance(ch, Tree) and ch.data == 'amount':
                return self.interp(ch)
        return None

    # ------------------------------------------------------------------ dispatch
    def interp(self, node):
        if isinstance(node, Token):
            return self._tok(node)
        if isinstance(node, Tree):
            h = getattr(self, 'i_' + node.data, None)
            if h is not None:
                return h(node.children)
            return self._default(node.children)
        return node

    def _default(self, children):
        vals = [self.interp(c) for c in children]
        vals = [v for v in vals if v is not None]
        if len(vals) == 1:
            return vals[0]
        return vals

    # ------------------------------------------------------------------ top
    # Ability words / dispatch prefixes that the generic keyword fallback can
    # steal from the sentence that owns them ("Waterbend {4}: …", "Activated
    # abilities … cost …"). They are markers, not keywords.
    ABILITY_WORDS = {
        'waterbend', 'activated', 'threshold', 'delirium', 'celebration',
        'valiant', 'flurry', 'alliance', 'landfall', 'descend', 'renew',
        'bargain', 'evidence', 'domain', 'metalcraft', 'revolt', 'raid',
        'ferocious', 'formidable', 'morbid', 'hellbent', 'spell mastery',
    }

    def _spurious_static_word(self, item):
        if not isinstance(item, dict) or item.get('type') != 'static_keyword':
            return None
        kw = item.get('keywords')
        words = kw if isinstance(kw, list) else [kw]
        vals = []
        for w in words:
            if isinstance(w, dict) and w.get('kind') == 'type':
                vals.append(str(w.get('value', '')).lower())
            elif isinstance(w, str):
                vals.append(w.lower())
        if len(vals) == 1 and vals[0] in self.ABILITY_WORDS:
            return vals[0]
        return None

    def i_start(self, children):
        out = []
        for ch in children:
            v = self.interp(ch)
            if v is not None:
                out.append(v)
        # A stray ability-word "sentence" immediately before the real sentence
        # is a dispatch artefact; attach it as that sentence's marker.
        cleaned = []
        for idx, item in enumerate(out):
            word = self._spurious_static_word(item)
            if word is not None and idx + 1 < len(out):
                if word != 'activated':
                    nxt = out[idx + 1]
                    if isinstance(nxt, dict):
                        label = item['keywords']
                        if isinstance(label, dict):
                            label = label.get('value')
                        nxt.setdefault('ability_word', label)
                continue
            cleaned.append(item)
        # "Enchant creature you control" is split into enchant_action +
        # a static "you control" sentence by the grammar; join the qualifier.
        merged = []
        for item in cleaned:
            if (merged and isinstance(item, dict)
                    and item.get('type') == 'static'
                    and 'text' in item
                    and item['text'].strip().lower() == 'you control'):
                prev = merged[-1]
                eff = prev.get('effect') if isinstance(prev, dict) else None
                inner = eff.get('effect') if isinstance(eff, dict) else eff
                if inner is None:
                    inner = eff
                if isinstance(inner, dict) and inner.get('verb') == 'enchant':
                    inner['controller'] = 'you control'
                    continue
            merged.append(item)
        cleaned = merged
        out = [self._finalize(x, top=True) for x in cleaned]
        for x in out:
            self._late_normalize(x)
        return out

    @staticmethod
    def _unparsed_tag(d):
        v = d.get('verb')
        t = d.get('type')
        if v == 'raw':
            return 'raw_action', 'i_raw_action'
        if v == 'axis':
            return 'raw_action', 'i_raw_action'
        if v == 'double':
            return 'raw_action', 'i_double_action'
        if v == 'for_each':
            return 'object_text', 'i_for_each_sentence'
        if v in ('distribute',):
            return 'object_text', 'i_distribute_action'
        if t == 'static':
            return 'static_text', 'i_static_sentence'
        if t == 'modal':
            return 'static_text', 'i_modal_sentence'
        if 'when' in d or 'event' in d:
            return 'trigger_text', 'i_trigger_clause'
        if 'owner' in d or 'destination' in d:
            return 'object_text', 'i_put_library_action'
        return 'no_handler', 'i_' + str(v or t or 'sentence')

    @staticmethod
    def _simple_target(text):
        """A permissive card_target for short condition nouns."""
        t = text.strip()
        if not t:
            return None
        controller = None
        zone = None
        low0 = t.lower()
        for suf, ctl in ((' you control', 'you control'),
                         (' an opponent controls', 'an opponent controls'),
                         (" an opponent's control", "an opponent's control")):
            if low0.endswith(suf):
                t = t[:-len(suf)]
                controller = ctl
                low0 = t.lower()
                break
        mzone = re.match(r'^(.*) in (your|their|a|an) (graveyard|library|hand|exile)$', low0)
        if mzone:
            t = t[:mzone.end(1)].strip()
            zone = {'prep': 'in', 'zone': mzone.group(3),
                    'possessor': 'you' if mzone.group(2) == 'your' else 'their'}
        q = None
        mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
              'six': 6, 'seven': 7, 'eight': 8}
        lowt = t.lower()
        for w, n in mp.items():
            if lowt.startswith(w + ' or more '):
                q = {'at_least': n}
                t = t[len(w + ' or more '):]
                break
        if q is None:
            for qw in ('a', 'an', 'each', 'target', 'up to'):
                if t.lower().startswith(qw + ' '):
                    q = qw
                    t = t[len(qw) + 1:]
                    break
        mod = None
        for sep in (' with ', ' that ', ' whose ', ' without '):
            if sep in t.lower():
                cut = t.lower().index(sep)
                t, mod = t[:cut], t[cut + 1:]
                break
        if not t:
            return None
        if t.strip().lower() in ('this creature', 'this permanent',
                                 'this enchantment', 'this artifact',
                                 'this land', 'this card'):
            return {'card_type': {'kind': 'this_card', 'value': '~'}}
        d = {'card_type': {'kind': 'type', 'value': t.strip()}}
        if q:
            d['quantifier'] = q
        if controller:
            d['controller'] = controller
        if zone:
            d['zone'] = zone
        if mod:
            d['modifier'] = mod.strip()
        return d

    def _event_this_turn(self, val):
        norm = ' '.join(val.lower().split()).rstrip('.')
        if not norm.endswith('this turn'):
            return None
        body = norm[:-len('this turn')].strip()
        orig = val.strip()[:-len('this turn')].strip()
        words = body.split()
        def numq(ws):
            mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                  'six': 6, 'seven': 7, 'eight': 8}
            for i, w in enumerate(ws):
                if w in mp:
                    if i + 1 < len(ws) and ws[i + 1] == 'or':
                        return {'at_least': mp[w]}
                    return mp[w]
                if w.isdigit():
                    return int(w)
            return None
        if body.startswith("you've drawn ") or body.startswith('you drew '):
            rest = body.split('drawn ', 1)[-1].split('drew ', 1)[-1]
            q = numq(rest.split()) or ('a' if 'a card' in rest else 'cards')
            return {'kind': 'event',
                    'event': {'subject': 'you', 'verb': 'draw',
                              'object': {'card': {
                                  'card_type': {'kind': 'type', 'value': 'cards'},
                                  'quantifier': q}}},
                    'this_turn': True}
        if body.startswith('you attacked'):
            ev = {'subject': 'you', 'verb': 'attacks'}
            if ' with ' in body:
                tgt = self._simple_target(orig.split(' with ', 1)[-1])
                if tgt:
                    ev['object'] = {'with': {'card_target': tgt}}
            return {'kind': 'event', 'event': ev, 'this_turn': True}
        if body in ("an opponent lost life", 'an opponent has lost life',
                    'an opponent lost life this turn'):
            return {'kind': 'event',
                    'event': {'subject': 'an opponent', 'verb': 'lose',
                              'object': 'life'},
                    'this_turn': True}
        if body in ('an opponent was dealt noncombat damage',
                    'an opponent was dealt damage'):
            ev = {'subject': 'an opponent', 'verb': 'is dealt',
                  'object': {'damage': ('noncombat'
                                        if 'noncombat' in body else None)}}
            if ev['object']['damage'] is None:
                ev['object'] = 'damage'
            return {'kind': 'event', 'event': ev, 'this_turn': True}
        if body in ("you've lost life", 'you lost life', 'you have lost life'):
            return {'kind': 'event',
                    'event': {'subject': 'you', 'verb': 'lose',
                              'object': 'life'},
                    'this_turn': True}
        if body in ('a creature died', 'one or more creatures died',
                    'a creature has died'):
            return {'kind': 'event',
                    'event': {'subject': {'card_type': {
                                  'kind': 'type', 'value': 'creature'},
                              'quantifier': 'a'},
                              'verb': 'dies'},
                    'this_turn': True}
        if body in ('this creature attacked', 'this permanent attacked'):
            return {'kind': 'event',
                    'event': {'subject': {'card_type': {
                                  'kind': 'this_card', 'value': '~'}},
                              'verb': 'attacks'},
                    'this_turn': True}
        if body in ('this creature died', 'this permanent died'):
            return {'kind': 'event',
                    'event': {'subject': {'card_type': {
                                  'kind': 'this_card', 'value': '~'}},
                              'verb': 'dies'},
                    'this_turn': True}
        if body == 'a permanent left the battlefield':
            return {'kind': 'event',
                    'event': {'subject': {'card_type': {
                                  'kind': 'type', 'value': 'permanent'},
                              'quantifier': 'a'},
                              'verb': 'leaves'},
                    'this_turn': True}
        if body.startswith('you cast ') or body.startswith("you've cast "):
            rest = orig.split('cast ', 1)[-1]
            tgt = self._simple_target(rest)
            if tgt:
                return {'kind': 'event',
                        'event': {'subject': 'you', 'verb': 'cast',
                                  'object': tgt},
                        'this_turn': True}
        return None

    _quote_parser = None
    _quote_depth = 0

    def _quoted_ability(self, text, depth=0):
        if depth >= 2:
            return None
        raw = text.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
            quote = raw[0]
            raw = raw[1:-1].strip()
            if quote == "'":
                raw = raw.replace("\\'", "'")
        raw = raw.rstrip('.').strip()
        if not raw:
            return None
        if Interpreter._quote_parser is None:
            from larkparser import build_parser
            Interpreter._quote_parser = build_parser('interp')
        try:
            tree = Interpreter._quote_parser.parse(raw)
        except Exception:
            return None
        res = self.interp(tree)

        def _has_unparsed(x):
            if isinstance(x, dict):
                return bool(x.get('unparsed')) or 'fragment' in x or any(
                    _has_unparsed(v) for v in x.values())
            if isinstance(x, list):
                return any(_has_unparsed(v) for v in x)
            return False
        if not res or _has_unparsed(res):
            return None

        def _nested_quotes(x, level):
            if isinstance(x, dict):
                for k in ('quote', 'quotes'):
                    v = x.get(k)
                    if isinstance(v, str):
                        q = self._quoted_ability(v, level)
                        if q:
                            x[k] = q
                    elif isinstance(v, list):
                        x[k] = [self._quoted_ability(e, level)
                                if isinstance(e, str) else e for e in v]
                        if any(e is None for e in x[k]):
                            x[k] = [e for e in x[k] if e is not None]
                for v in x.values():
                    _nested_quotes(v, level)
            elif isinstance(x, list):
                for v in x:
                    _nested_quotes(v, level)

        _nested_quotes(res, depth + 1)
        return {'kind': 'quoted_ability', 'sentence': res}

    def _late_normalize(self, obj):
        """Structure values created after the normal child-finalizer pass."""
        if isinstance(obj, dict) and obj.get('verb') == 'raw' \
                and isinstance(obj.get('fragment'), str):
            frag = obj['fragment'].strip()
            low = frag.lower()
            repl = None
            if low == 'it becomes plotted':
                repl = {'verb': 'become', 'state': 'plotted',
                        'target': {'card_type': {'ref': 'anaphora',
                                                 'raw': 'it'}}}
            elif low.startswith('pay life equal to its mana value rather than'):
                repl = {'verb': 'pay_life',
                        'amount': {'kind': 'relative',
                                   'of': {'kind': 'possessive',
                                          'possessive': 'its',
                                          'stat': 'mana_value'}},
                        'instead_of': {'verb': 'pay_mana', 'object': 'mana_cost'}}
            elif low.startswith('return that card under your control with a finality counter'):
                repl = {'verb': 'return',
                        'card': {'this_that': 'that',
                                 'card_type': {'kind': 'type', 'value': 'card'}},
                        'to': {'zone': 'battlefield', 'controller': 'you',
                               'counter': {'kind': 'finality', 'count': 1}}}
            elif low.startswith('put up to three lore counters on it'):
                repl = {'verb': 'put_counter', 'count': {'up_to': 3},
                        'counter': {'kind': 'lore'},
                        'on': {'card_type': {'ref': 'anaphora', 'raw': 'it'}}}
            elif low.startswith('untap him and there is an additional combat phase'):
                repl = {'verb': 'and', 'items': [
                    {'verb': 'untap',
                     'card': {'card_type': {'ref': 'anaphora', 'raw': 'him'}}},
                    {'verb': 'additional_phase', 'phase': 'combat',
                     'position': 'after'}]}
            elif re.fullmatch(r'there is an additional (combat phase|end step) after this (phase|step)', low):
                m = re.match(r'there is an additional (combat phase|end step)', low)
                repl = {'verb': 'additional_phase',
                        'phase': ('combat' if 'combat' in m.group(1)
                                  else 'end_step'),
                        'position': 'after'}
            elif low.startswith('you may cast the exiled nonland card until end of turn'):
                repl = {'verb': 'may', 'inner': {
                    'verb': 'cast',
                    'card': {'status': ['exiled'],
                             'card_type': {'kind': 'type', 'value': 'card'}},
                    'duration': {'kind': 'until', 'event': 'end_of_turn'},
                    'mana_any_type': True}}
            if repl is not None:
                obj.clear()
                obj.update(repl)
        if isinstance(obj, dict):
            qv = obj.get('quantifier')
            if isinstance(qv, str):
                low_q = qv.strip().lower()
                words = {'two': 2, 'three': 3, 'four': 4, 'five': 5,
                         'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
                         'ten': 10}
                if low_q in words:
                    obj['quantifier'] = words[low_q]
                elif low_q.startswith('up_to_'):
                    raw_q = low_q[len('up_to_'):]
                    obj['quantifier'] = {
                        'up_to': int(raw_q) if raw_q.isdigit() else raw_q}
                elif low_q == 'one or two':
                    obj['quantifier'] = {'at_least': 1, 'at_most': 2}
                else:
                    mq = re.fullmatch(
                        r'([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten) or more',
                        low_q)
                    if mq:
                        raw_q = mq.group(1)
                        n = (int(raw_q) if raw_q.isdigit()
                             else {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                                   'five': 5, 'six': 6, 'seven': 7,
                                   'eight': 8, 'nine': 9, 'ten': 10}[raw_q])
                        obj['quantifier'] = {'at_least': n}
            cnv = obj.get('count')
            if isinstance(cnv, str):
                low_cnt = cnv.strip().lower()
                if low_cnt == 'that many':
                    obj['count'] = {'kind': 'relative', 'of': {'kind': 'that_many'}}
                elif low_cnt == 'one or more':
                    obj['count'] = {'kind': 'count', 'at_least': 1}
                elif low_cnt == 'that many plus one':
                    obj['count'] = {'kind': 'relative',
                                    'of': {'kind': 'that_many'}, 'plus': 1}
            tv = obj.get('target')
            if isinstance(tv, str):
                low_t = tv.strip().lower()
                if low_t in ('that ability', 'this ability'):
                    obj['target'] = {'kind': 'target_ref',
                                     'ref': low_t.replace(' ', '_')}
                elif low_t in ('that spell', 'this spell'):
                    obj['target'] = {'kind': 'target_ref',
                                     'ref': low_t.replace(' ', '_')}
            rv = obj.get('relative')
            if isinstance(rv, str):
                low_r = rv.strip().lower()
                mrel = re.fullmatch(r'that (attacked|saddled it|was dealt damage) this turn', low_r)
                if mrel:
                    d = {'kind': 'event_ref', 'time': 'this_turn'}
                    if mrel.group(1) == 'was dealt damage':
                        d['event'] = 'dealt_damage'
                        d['voice'] = 'passive'
                    else:
                        d['event'] = mrel.group(1).split()[0]
                        if 'it' in mrel.group(1):
                            d['object'] = 'it'
                    obj['relative'] = d
            ofv = obj.get('of')
            if isinstance(ofv, str):
                low_of = ofv.strip().lower()
                if low_of == 'target spell or ability with a single target':
                    obj['of'] = {'kind': 'choice',
                                 'options': [{'kind': 'spell'},
                                             {'kind': 'ability'}],
                                 'single_target': True}
            ctr = obj.get('counter')
            if isinstance(ctr, dict) and isinstance(ctr.get('kind'), str):
                k = ctr['kind'].strip().lower()
                mctr = re.fullmatch(r'(.+?)\s+counters?(?:\s+s)?', k)
                if mctr:
                    ctr['kind'] = mctr.group(1)
            own = obj.get('owner')
            if isinstance(own, str) and own.strip().lower().startswith('the owner of '):
                obj['owner'] = self._owner_ref(own)
            ct = obj.get('card_type')
            def _split_type_value(v):
                parts = [x.strip() for x in re.split(
                    r'\s*,\s*(?:or\s+)?|\s+(?:or|and)\s+|\s+and/or\s+',
                    v) if x.strip()]
                parts = [re.sub(r'^both (?:a |an )?', '', x) for x in parts]
                return parts
            if isinstance(ct, dict) and isinstance(ct.get('value'), str) \
                    and (' or ' in ct['value'] or ' and ' in ct['value']
                         or ',' in ct['value']):
                parts = _split_type_value(ct['value'])
                if len(parts) > 1:
                    obj['card_type'] = [{'kind': 'type', 'value': x}
                                        for x in parts]
            elif isinstance(ct, list):
                expanded = []
                changed = False
                for item in ct:
                    if isinstance(item, dict) and isinstance(item.get('value'), str) \
                            and (' or ' in item['value'] or ' and ' in item['value']
                                 or ',' in item['value']):
                        parts = _split_type_value(item['value'])
                        if len(parts) > 1:
                            changed = True
                            expanded.extend({'kind': item.get('kind', 'type'),
                                             'value': x} for x in parts)
                            continue
                    expanded.append(item)
                if changed:
                    obj['card_type'] = expanded
            if isinstance(obj.get('possessor'), str) \
                    and obj['possessor'].lower() in {'its', 'their', 'his', 'her'}:
                obj['possessor'] = {'kind': 'anaphora',
                                    'possessive': obj['possessor'].lower(),
                                    'anaphor': True}
            if isinstance(obj.get('stat'), str) and ' and ' in obj['stat']:
                obj['stat'] = {'kind': 'stats',
                               'values': [x.strip() for x in
                                          obj['stat'].split(' and ')]}
            ctr2 = obj.get('counter')
            if isinstance(ctr2, dict) and isinstance(ctr2.get('kind'), str) \
                    and ' and ' in ctr2['kind']:
                ctr2['kind'] = {'kind': 'counter_list',
                                'values': [x.strip() for x in
                                           ctr2['kind'].split(' and ')]}
            if isinstance(obj.get('possessor'), (str, dict)) \
                    and isinstance(obj.get('stat'), (str, dict)) \
                    and 'kind' not in obj:
                obj['kind'] = 'possessive'
            fev2 = obj.get('for_each')
            if isinstance(fev2, dict):
                item = fev2.get('items')
                if isinstance(item, dict):
                    v = item.get('value')
                    if isinstance(v, str) and v.startswith('color of mana spent to cast '):
                        ref = v[len('color of mana spent to cast '):].strip()
                        obj['for_each'] = {
                            'kind': 'color_of',
                            'of': {'kind': 'mana_spent', 'action': 'cast',
                                   'object': {'kind': 'ref',
                                              'ref': ref.replace(' ', '_'),
                                              'anaphor': True}}}
            mv = obj.get('modifier')
            if isinstance(mv, str):
                low_m = mv.strip().lower()
                mstat = re.fullmatch(
                    r'with (?:total )?(mana value|power|toughness) '
                    r'([0-9]+|x) (?:or less|or greater|or more)', low_m)
                if mstat:
                    raw = mstat.group(2)
                    obj['modifier'] = {
                        'kind': 'stat_filter', 'stat': mstat.group(1),
                        'op': '<=' if 'less' in low_m else '>=',
                        'value': int(raw) if raw.isdigit() else 'X'}
                elif re.fullmatch(r'with (?:total )?mana value (?:[0-9]+|x)', low_m):
                    raw = low_m.rsplit(' ', 1)[-1]
                    obj['modifier'] = {'kind': 'stat_filter',
                                       'stat': 'mana value', 'op': '=',
                                       'value': int(raw) if raw.isdigit() else 'X'}
                else:
                    mcount = re.fullmatch(
                        r'with ([0-9]+|x|one|two|three|four|five|six|seven|eight|nine|ten) '
                        r'or more (.+)', low_m)
                    if mcount:
                        raw = mcount.group(1)
                        n = ({'one': 1, 'two': 2, 'three': 3, 'four': 4,
                              'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                              'nine': 9, 'ten': 10}.get(raw,
                              int(raw) if raw.isdigit() else 'X'))
                        obj['modifier'] = {
                            'kind': 'count_filter', 'min': n,
                            'set': Interpreter._amount_ref(mcount.group(2))}
                    elif low_m.startswith('exiled with '):
                        with_text = low_m[len('exiled with '):]
                        if with_text == '~':
                            ref = {'kind': 'this_card', 'value': '~'}
                        elif with_text == 'it':
                            ref = {'kind': 'anaphora', 'possessive': 'it',
                                   'anaphor': True}
                        elif with_text.startswith('this '):
                            ref = {'kind': 'this',
                                   'card_class': with_text[len('this '):]}
                        else:
                            ref = Interpreter._amount_ref(with_text)
                        obj['modifier'] = {'kind': 'event_filter',
                                           'event': 'exiled', 'with': ref}
                    elif low_m in ('with that name', 'with the chosen name'):
                        obj['modifier'] = {'kind': 'name',
                                           'which': 'that' if 'that' in low_m
                                           else 'chosen'}
                    elif low_m == 'with a single target':
                        obj['modifier'] = {'kind': 'target_limit',
                                           'single': True}
                    else:
                        mcomp = re.fullmatch(
                            r'with (different|the same) (names?|powers?)', low_m)
                        if mcomp:
                            obj['modifier'] = {
                                'kind': 'comparison',
                                'mode': mcomp.group(1).replace('the ', ''),
                                'property': mcomp.group(2).rstrip('s')}
                        else:
                            mctr2 = re.fullmatch(
                                r'with (?:a|an|one|two|three|[0-9]+) (.+?) '
                                r'counter on it', low_m)
                            if mctr2:
                                obj['modifier'] = {
                                    'kind': 'counter_filter',
                                    'counter': {'kind': mctr2.group(1)},
                                    'on': 'it'}
            if isinstance(mv, str) and mv.strip().lower().startswith('that targets '):
                rest = mv.strip().lower()[len('that targets '):]
                only = single = False
                if rest.startswith('only a single '):
                    only = single = True
                    rest = rest[len('only a single '):]
                q = None
                if rest[:2] in ('a ', 'an '):
                    q = rest[:2].strip()
                    rest = rest[2:]
                parts = [x.strip() for x in re.split(r'\s+(?:or|and)\s+', rest)]
                d = {'kind': 'targets',
                     'target': {'card_type': [{'kind': 'type', 'value': x}
                                              for x in parts]}}
                if q:
                    d['target']['quantifier'] = q
                if only:
                    d['only'] = True
                if single:
                    d['single'] = True
                obj['modifier'] = d
            fev = obj.get('for_each')
            if isinstance(fev, dict):
                if isinstance(fev.get('controller'), str):
                    fev['controller'] = {'you control': 'you',
                                         'you already control': 'you',
                                         'you own': 'you_own'}.get(
                        fev['controller'], fev['controller'])
                if isinstance(fev.get('zone'), str):
                    fev['zone'] = fev['zone'].replace('your ', '')
                for item in fev.get('items', []) if isinstance(fev.get('items'), list) else []:
                    if isinstance(item, dict):
                        if isinstance(item.get('controller'), str):
                            item['controller'] = {'you control': 'you',
                                                  'you already control': 'you',
                                                  'you own': 'you_own'}.get(
                                item['controller'], item['controller'])
                        if isinstance(item.get('zone'), str):
                            item['zone'] = item['zone'].replace('your ', '')
            qv = obj.get('quote')
            if isinstance(qv, str):
                qobj = self._quoted_ability(qv)
                if qobj:
                    obj['quote'] = qobj
            qvs = obj.get('quotes')
            if isinstance(qvs, list):
                obj['quotes'] = [self._quoted_ability(x) if isinstance(x, str)
                                 and self._quoted_ability(x) else x
                                 for x in qvs]
            for v in obj.values():
                self._late_normalize(v)
        elif isinstance(obj, list):
            for v in obj:
                self._late_normalize(v)

    def _owner_ref(self, text):
        """Structured owner reference; "owner of X" keeps X as a card target."""
        raw = text.strip()
        low = raw.lower()
        if low.startswith('the owner of '):
            rest = raw[len('The owner of '):]
            ct = self._simple_target(rest)
            if ct:
                status = []
                ctl = None
                val = ct.get('card_type', {}).get('value')
                if isinstance(val, str):
                    v = val
                    for suf, c in ((" you don't control", "you don't control"),
                                   (' an opponent controls', 'opponent controls')):
                        if v.lower().endswith(suf):
                            v = v[:-len(suf)]
                            ctl = c
                            break
                    for st in ('attacking', 'blocking', 'tapped', 'untapped'):
                        if re.search(rf'\b{st}\b', v, re.I):
                            status.append(st)
                            v = re.sub(rf'\b{st}\b', '', v, flags=re.I)
                    ct['card_type']['value'] = ' '.join(v.split())
                    if ctl:
                        ct['controller'] = ctl
                    if status:
                        ct['status'] = status
                return {'kind': 'owner_of', 'of': ct}
        m = re.fullmatch(r'(its|their|his|her) owners?', low)
        if m:
            return {'kind': 'owner_of',
                    'of': {'kind': 'anaphora', 'possessive': m.group(1),
                           'anaphor': True}}
        return {'kind': 'player', 'ref': low.replace(' ', '_')}

    @staticmethod
    def _amount_ref(text):
        low = text.strip().lower()
        d = {}
        target = low.startswith('target ')
        for pre in ('target ', 'other ', 'each ', 'up to ', 'a ', 'an ', 'the '):
            if low.startswith(pre):
                low = low[len(pre):]
                break
        for suf, ctl in ((' you control', 'you'),
                         (' you already control', 'you'),
                         (' an opponent controls', 'opponent'),
                         (" you don't control", 'not_you')):
            if low.endswith(suf):
                d['controller'] = ctl
                low = low[:-len(suf)]
                break
        for suf, zone in ((' in your graveyard', 'graveyard'),
                          (' in your hand', 'hand'),
                          (' in your library', 'library'),
                          (' on the battlefield', 'battlefield')):
            if low.endswith(suf):
                d['zone'] = zone
                low = low[:-len(suf)]
                break
        if low.endswith(' of the chosen type'):
            d['chosen_type'] = True
            low = low[:-len(' of the chosen type')]
        for suf, cls in ((' cards', 'card'), (' card', 'card'),
                         (' creatures', 'creature'), (' creature', 'creature'),
                         (' permanents', 'permanent'), (' permanent', 'permanent')):
            if low.endswith(suf):
                d['card_class'] = cls
                low = low[:-len(suf)]
                break
        parts = [x.strip() for x in re.split(r'\s+(?:and|or|and/or)\s+|,\s*(?:and\s+|or\s+)?', low) if x.strip()]
        types = []
        skip = {'a', 'an', 'the', 'nonland', 'nontoken', 'tapped', 'untapped'}
        for part in parts:
            word = re.sub(r'^(?:a|an|the) ', '', part)
            if word in skip or not word:
                continue
            if word.endswith('s'):
                word = word[:-1]
            types.append({'kind': 'type', 'value': word})
        if types:
            d['card_type'] = types
        if target:
            d['quantifier'] = 'target'
        return d

    @staticmethod
    def _window_obj(text):
        low = text.strip().lower()
        if low == 'your turn':
            return {'kind': 'turn', 'player': 'you'}
        if low == 'each turn':
            return {'kind': 'frequency', 'value': 'each_turn'}
        if low == 'this turn':
            return {'kind': 'turn', 'value': 'this_turn'}
        return None

    def _trigger_event(self, text):
        """Closed trigger-event fragments from a stashed trigger text."""
        low = ' '.join(str(text).lower().split()).rstrip('.')
        if low.startswith('one or more ') and low.endswith(' die'):
            between = low[len('one or more '):-len(' die')].strip()
            other = False
            if between.startswith('other '):
                other = True
                between = between[len('other '):]
            controller = None
            for suf, ctl in ((' you control', 'you control'),
                             (' an opponent controls', 'an opponent controls')):
                if between.endswith(suf):
                    between = between[:-len(suf)]
                    controller = ctl
                    break
            if between:
                subj = {'card_type': {'kind': 'type', 'value': between},
                        'quantifier': 'one or more'}
                if other:
                    subj['otherness'] = 'other'
                if controller:
                    subj['controller'] = controller
                return {'subject': subj, 'verb': 'dies'}
        mcast = re.match(r'^(.*?)\bcas(?:t|ts)\b(.*)$', low)
        if mcast:
            head, tail = mcast.group(1), mcast.group(2)
            subject = None
            if head.strip() in ('you', 'a player', 'an opponent',
                                'each opponent', 'each player'):
                subject = head.strip()
            elif head.strip().startswith('you '):
                subject = 'you'
            if subject:
                rest = tail.strip()
                if rest.startswith(('your ', 'their ', 'a ')):
                    rest = rest.split(' ', 1)[1]
                ordinal = None
                for w in ('first', 'second', 'third', 'fourth'):
                    if rest.startswith(w + ' '):
                        ordinal = w
                        rest = rest[len(w) + 1:]
                        break
                ev = {'subject': subject, 'verb': 'cast'}
                obj = self._simple_target(rest.split(' this turn')[0]
                                          .split(' each turn')[0].strip())
                if obj:
                    ev['object'] = obj
                if ordinal:
                    ev['ordinal'] = ordinal
                if 'each turn' in low:
                    ev['window'] = {'kind': 'frequency', 'value': 'each_turn'}
                elif 'this turn' in low:
                    ev['window'] = {'kind': 'turn', 'value': 'this_turn'}
                return ev
        if low.endswith('is turned face up') or low == 'this creature turns face up':
            return {'subject': {'card_type': {'kind': 'this_card',
                                              'value': '~'}},
                    'verb': 'turn_face_up'}
        if low.startswith('this creature transforms into '):
            return {'subject': {'card_type': {'kind': 'this_card',
                                              'value': '~'}},
                    'verb': 'transforms',
                    'into': low[len('this creature transforms into '):]}
        if low.startswith('you commit a crime'):
            ev = {'subject': 'you', 'verb': 'commit_crime'}
            if 'during your turn' in low:
                ev['window'] = {'kind': 'turn', 'player': 'you'}
            return ev
        m_exp = re.match(r'^you expend ([0-9]+|\w+)$', low)
        if m_exp:
            return {'subject': 'you', 'verb': 'expend',
                    'amount': m_exp.group(1)}
        if low in ('you unlock this door', 'you unlock the door'):
            return {'subject': 'you', 'verb': 'unlock', 'object': 'door'}
        if low in ('you fully unlock a room', 'you unlock a room'):
            return {'subject': 'you', 'verb': 'unlock', 'object': 'room'}
        m_act = re.match(r'^(you|an opponent|a player|each opponent|each player) activates? (.+)$', low)
        if m_act:
            return {'subject': m_act.group(1), 'verb': 'activate',
                    'object': self._simple_target(m_act.group(2))}
        if low in ('~ enter', '~ enters', 'this creature enters'):
            return {'subject': {'card_type': {'kind': 'this_card',
                                              'value': '~'}},
                    'verb': 'enters'}
        if low == 'a creature you control attacks alone':
            return {'subject': {'card_type': {'kind': 'type',
                                              'value': 'creature'},
                                'quantifier': 'a',
                                'controller': 'you control'},
                    'verb': 'attacks', 'alone': True}
        return None

    def _finalize(self, node, top=False):
        """Replace every remaining `text` fallback with an honest marker.

        C1/C2 payloads were migrated/deleted already; anything left is an
        unparsed whole sentence (top-level static/modal/raw effect) or an
        unparsed subtree.
        """
        if isinstance(node, list):
            return [self._finalize(x) for x in node]
        if not isinstance(node, dict):
            return node
        for k in list(node):
            if k != 'text':
                node[k] = self._finalize(node[k])
        # Anaphoric event references: "If they do" / "If you don't".
        for key in ('condition', 'if', 'unless', 'trailing_if'):
            val = node.get(key)
            if isinstance(val, str):
                low = ' '.join(val.lower().split()).rstrip('.')
                parts = low.split()
                if (len(parts) == 2 and parts[0] in ('you', 'they')
                        and parts[1] in ('do', "don't")):
                    node[key] = {'kind': 'event_ref', 'actor': parts[0],
                                 'polarity': ('positive' if parts[1] == 'do'
                                              else 'negative')}
                    continue
                # "you control a Dragon" / "you control a creature with
                # power 4 or greater": a controller condition with a simple
                # card_target. Leave compounds (and/or/spells) to unparsed.
                states = {
                    'this spell was kicked': 'kicked',
                    'this spell was bargained': 'bargained',
                    'this spell was cast using teamwork': 'cast_using_teamwork',
                    'this spell was cast from a graveyard': 'cast_from_graveyard',
                    "this spell's additional cost was paid": 'additional_cost_paid',
                    'this spell was plotted': 'plotted',
                    'this permanent was prepared': 'prepared',
                }
                if low in states:
                    node[key] = {'kind': 'spell_state',
                                 'state': states[low]}
                    continue
                if low == 'this is the first time this ability has resolved this turn':
                    node[key] = {'kind': 'spell_state',
                                 'state': 'first_time_this_turn',
                                 'this_turn': True}
                    continue
                if low == 'the gift was promised':
                    node[key] = {'kind': 'gift', 'state': 'promised'}
                    continue
                if low == "the gift wasn't promised":
                    node[key] = {'kind': 'gift', 'state': 'not_promised'}
                    continue
                if low.startswith('five or more mana was spent'):
                    node[key] = {'kind': 'spell_state',
                                 'state': 'mana_spent_at_least',
                                 'amount': 5}
                    continue
                if low.startswith('x is '):
                    rest = low[5:].strip()
                    q = None
                    mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                          'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                          'nine': 9, 'ten': 10}
                    for w, n in mp.items():
                        if rest.startswith(w + ' or more'):
                            q = {'at_least': n}
                            break
                        if rest.startswith(w + ' or less'):
                            q = {'at_most': n}
                            break
                    if q is None:
                        mm = re.match(r'^(\d+) or (more|less)', rest)
                        if mm:
                            q = ({'at_least': int(mm.group(1))}
                                 if mm.group(2) == 'more' else
                                 {'at_most': int(mm.group(1))})
                    if q:
                        node[key] = {'kind': 'xdef_compare', 'x': True,
                                     'quantity': q}
                        continue
                mpl = re.match(
                    r'^(a|an|each|target) player has (\w+|[0-9]+) or (less|more) life$',
                    low)
                if mpl:
                    mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                          'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                          'nine': 9, 'ten': 10}
                    n = (int(mpl.group(2)) if mpl.group(2).isdigit()
                         else mp.get(mpl.group(2)))
                    if n is not None:
                        node[key] = {
                            'kind': 'count', 'unit': 'life',
                            'subject': {'player': mpl.group(1)},
                            'quantity': ({'at_most': n}
                                         if mpl.group(3) == 'less'
                                         else {'at_least': n})}
                        continue
                if low in ("it's your turn", 'it is your turn'):
                    node[key] = {'kind': 'state', 'subject': 'turn',
                                 'state': {'status': 'your_turn'}}
                    continue
                if low in ("it's not your turn", 'it is not your turn'):
                    node[key] = {'kind': 'state', 'subject': 'turn',
                                 'state': {'status': 'not_your_turn'}}
                    continue
                if (low.startswith('there are ') and ' or more ' in low
                        and ' among ' not in low):
                    body = val.strip()[len('there are '):]
                    num, rest = body.split(' or more ', 1)
                    mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                          'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                          'nine': 9, 'ten': 10}
                    n = int(num) if num.isdigit() else mp.get(num.lower())
                    if n is not None:
                        rlow = rest.lower().strip().rstrip('.')
                        of = None
                        if ' among ' in rlow:
                            continue
                        if ' in ' in rlow:
                            unit, zone = rest.split(' in ', 1)
                            zl = zone.lower()
                            for zname in ('graveyard', 'library', 'hand',
                                          'exile', 'battlefield'):
                                if zname in zl:
                                    of = {'card_target': {
                                              'card_type': {'kind': 'type',
                                                            'value': unit.strip()}},
                                          'zone': {'prep': 'in',
                                                   'zone': zname,
                                                   'possessor': ('you' if 'your' in zl else 'their')}}
                                    break
                        elif ' counter' in rlow:
                            on = None
                            if ' on ' in rlow:
                                unit, on = rest.rsplit(' on ', 1)
                                on = self._simple_target(on)
                            if on:
                                of = {'counter': unit.strip(), 'on': on}
                        if of:
                            node[key] = {'kind': 'count',
                                         'quantity': {'at_least': n},
                                         'of': of}
                            continue
                if low.startswith('you may '):
                    rest = val.strip()[len('you may '):]
                    parts = rest.split(' ', 1)
                    verb = parts[0].lower() if parts else ''
                    if verb in ('behold', 'choose', 'discard', 'sacrifice',
                                'exile', 'pay') and len(parts) > 1:
                        action = {'verb': verb}
                        if verb != 'pay':
                            tgt = self._simple_target(parts[1])
                            if tgt:
                                action['card_target'] = tgt
                            else:
                                action = None
                        else:
                            action['amount'] = parts[1].strip()
                        if action:
                            node[key] = {'kind': 'may', 'actor': 'you',
                                         'action': action}
                            continue
                if low == 'you have an enduring story':
                    node[key] = {'kind': 'state', 'subject': 'you',
                                 'state': {'status': 'enduring story'}}
                    continue
                if (low.startswith('a triggered ability of ')
                        and low.endswith(' triggers')):
                    mid = val.strip()[len('a triggered ability of '):-len(' triggers')]
                    tgt = self._simple_target(mid)
                    if tgt:
                        node[key] = {'kind': 'triggered_ability', 'of': tgt}
                        continue
                if low.startswith('there are ') and ' among ' in low:
                    body = val.strip()[len('there are '):]
                    if ' or more ' in body:
                        num, rest = re.split(r' or more ', body, maxsplit=1, flags=re.I)
                        mp = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                              'five': 5, 'six': 6, 'seven': 7, 'eight': 8}
                        n = int(num) if num.strip().isdigit() else mp.get(num.strip().lower())
                        if n is not None:
                            unit, among = re.split(r' among ', rest, maxsplit=1, flags=re.I)
                            of = None
                            al = among.lower().strip()
                            if al.startswith('cards in '):
                                zone = al[len('cards in '):]
                                z = None
                                for zn in ('graveyard', 'library', 'hand',
                                           'exile', 'battlefield'):
                                    if zn in zone:
                                        z = {'prep': 'in', 'zone': zn,
                                             'possessor': ('you' if 'your' in zone
                                                           else 'their')}
                                        break
                                if z:
                                    of = {'card_target': {
                                              'card_type': {'kind': 'type',
                                                            'value': 'cards'}},
                                          'zone': z}
                            elif al.startswith('cards exiled with '):
                                src = among[len('cards exiled with '):].strip()
                                of = {'card_target': {
                                          'card_type': {'kind': 'type',
                                                        'value': 'cards'}},
                                      'state': 'exiled',
                                      'source': self._simple_target(src)}
                            elif al.startswith('creatures you control'):
                                of = {'card_target': self._simple_target(among)}
                            if of:
                                node[key] = {'kind': 'count',
                                             'quantity': {'at_least': n},
                                             'unit': unit.strip(),
                                             'of': of}
                                continue
                mput = re.match(r"^you (don't )?put (.+)$", low)
                if mput:
                    negative = bool(mput.group(1))
                    rest = val.strip()
                    rest = rest[len("you don't put "):] if negative else rest[len('you put '):]
                    this_way = ' this way' in rest.lower()
                    cut = len(rest)
                    for sep in (' this way', ' into ', ' onto ', ' on ',
                                ' this turn'):
                        idx = rest.lower().find(sep)
                        if 0 <= idx < cut:
                            cut = idx
                    objtxt = rest[:cut].strip()
                    tgt = self._simple_target(objtxt)
                    if tgt:
                        ev = {'subject': 'you', 'verb': 'put', 'object': tgt}
                        if negative:
                            ev['polarity'] = 'negative'
                        if this_way:
                            ev['this_way'] = True
                        if 'this turn' in rest.lower():
                            ev['this_turn'] = True
                        node[key] = {'kind': 'event', 'event': ev}
                        continue
                mcmp = re.match(r'^an opponent (controls|has) more (.+) than you$', low)
                if mcmp:
                    node[key] = {'kind': 'comparison',
                                 'subject': 'an opponent',
                                 'verb': mcmp.group(1),
                                 'object': mcmp.group(2),
                                 'comparison': 'more_than_you'}
                    continue
                mtp = re.match(r'^(creatures you control) have total power (\d+) or (greater|less)$', low)
                if mtp:
                    q = ({'at_least': int(mtp.group(2))}
                         if mtp.group(3) == 'greater'
                         else {'at_most': int(mtp.group(2))})
                    node[key] = {'kind': 'comparison',
                                 'subject': self._simple_target(mtp.group(1)),
                                 'stat': 'total_power', 'quantity': q}
                    continue
                ev = self._event_this_turn(val)
                if ev:
                    node[key] = ev
                    continue
                # Object state: "it's a Mount", "it is a Vehicle",
                # "it's a Zombie card", "it's tapped".
                for pref in ("it's ", 'it is ', 'it was ', 'it wasn\'t ',
                             'this creature is ', 'this creature was ',
                             'this permanent is ', 'this permanent was '):
                    if low.startswith(pref):
                        rest = val.strip()[len(pref):]
                        rlow = rest.lower().rstrip('.')
                        status = None
                        for st in ('tapped', 'untapped', 'attacking',
                                   'blocking', 'saddled', 'prepared'):
                            if rlow == st:
                                status = st
                                break
                        if status:
                            node[key] = {'kind': 'state',
                                         'subject': {'card_type': {
                                             'kind': 'this_card', 'value': '~'}},
                                         'state': {'status': status}}
                            break
                        if rlow.endswith(' card'):
                            rest = rest[:-len(' card')]
                        mq = None
                        for qw in ('a', 'an'):
                            if rlow.startswith(qw + ' '):
                                mq = qw
                                rest = rest[len(qw) + 1:]
                                break
                        if rest and ' ' not in rest.strip().lower():
                            node[key] = {'kind': 'state',
                                         'subject': {'card_type': {
                                             'kind': 'this_card', 'value': '~'}},
                                         'state': {'card_type': {
                                             'kind': 'type', 'value': rest.strip()}}}
                            break
                if low.startswith('you control '):
                    rest = val.strip()[len('you control '):]
                    mod = None
                    for sep in (' with ', ' that ', ' whose ', ' without '):
                        if sep in rest.lower():
                            cut = rest.lower().index(sep)
                            rest, mod = rest[:cut], rest[cut + 1:]
                            break
                    base_low = rest.lower()
                    qty = None
                    mpq = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                           'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                           'nine': 9, 'ten': 10}
                    mqty = re.match(
                        r'^(one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+) or (more|less|fewer) ',
                        base_low)
                    if mqty:
                        n = (int(mqty.group(1)) if mqty.group(1).isdigit()
                             else mpq.get(mqty.group(1)))
                        if n is not None:
                            qty = ({'at_least': n}
                                   if mqty.group(2) == 'more'
                                   else {'at_most': n})
                            rest = rest[mqty.end():]
                            base_low = rest.lower()
                    if ' and ' not in base_low and ' or ' not in base_low:
                        mq = None
                        for qw in ('a', 'an', 'each', 'target', 'up to'):
                            if rest.lower().startswith(qw + ' '):
                                mq = qw
                                rest = rest[len(qw) + 1:]
                                break
                        if rest:
                            ct = {'card_type': {'kind': 'type',
                                                'value': rest.strip()},
                                  'controller': 'you control'}
                            if mq:
                                ct['quantifier'] = mq
                            if mod:
                                ct['modifier'] = mod.strip()
                            cond = {'kind': 'control', 'card_target': ct}
                            if qty:
                                cond['quantity'] = qty
                            node[key] = cond
        src = 'i_' + str(node.get('verb') or node.get('type') or 'sentence')
        for key, reason in (('condition', 'condition_text'),
                            ('if', 'condition_text'),
                            ('unless', 'condition_text'),
                            ('trailing_if', 'condition_text'),
                            ('modifier', 'modifier_text'),
                            ('xdef', 'xdef_text')):
            if key not in node:
                continue
            verdict = classify_clause(key, node[key])
            if verdict in (CLAUSE, EXPRESSION):
                orig = node[key]
                node[key] = {'unparsed': True, 'reason': reason,
                             'fragment': orig, 'source': src}
        av = node.get('amount')
        if isinstance(av, str):
            low_a = av.strip().lower().replace(' ,', ',')
            nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                    'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
                    'nine': 9, 'ten': 10}
            mlife = re.fullmatch(r'([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|x) life', low_a)
            if mlife:
                raw = mlife.group(1)
                val = (int(raw) if raw.isdigit()
                       else 'X' if raw == 'x' else nums[raw])
                node['amount'] = {'kind': 'number', 'value': val,
                                  'unit': 'life'}
            elif re.fullmatch(r'[0-9]+', low_a):
                node['amount'] = int(low_a)
            elif low_a == 'x':
                node['amount'] = {'kind': 'x'}
            elif re.fullmatch(r'(?:\{[^}]+\}\s*)+', low_a):
                syms = re.findall(r'\{[A-Za-z0-9/]+\}', av.strip())
                node['amount'] = {'kind': 'mana', 'symbols': syms}
            elif ' or ' in low_a and all(
                    re.fullmatch(r'(?:\{[^}]+\}\s*)+', x.strip())
                    for x in low_a.split(' or ')):
                node['amount'] = {
                    'kind': 'mana_choice',
                    'options': [re.findall(r'\{[^}]+\}', x)
                                for x in av.strip().split(' or ')]}
            elif low_a == 'one mana of any color':
                node['amount'] = {'kind': 'mana', 'count': 1,
                                  'of': 'any_color'}
            elif low_a == 'one mana of the chosen color':
                node['amount'] = {'kind': 'mana', 'count': 1,
                                  'of': 'chosen_color'}
            mman = re.fullmatch(
                r'([0-9]+|x) mana of (any one color|that color|the chosen color)',
                low_a)
            if mman:
                raw = mman.group(1)
                count = int(raw) if raw.isdigit() else 'X'
                node['amount'] = {'kind': 'mana', 'count': count,
                                  'of': mman.group(2).replace(' ', '_')}
            elif re.fullmatch(r'([0-9]+|x) mana in any combination of colors', low_a):
                raw = low_a.split()[0]
                node['amount'] = {
                    'kind': 'mana',
                    'count': int(raw) if raw.isdigit() else 'X',
                    'of': 'any_combination'}
            if re.fullmatch(
                    r'\{[^}]+\}(?:\s*,\s*(?:or\s+)?\{[^}]+\})+', low_a):
                node['amount'] = {
                    'kind': 'mana_choice',
                    'options': [re.findall(r'\{[^}]+\}', x)
                                for x in re.split(r'\s*,\s*(?:or\s+)?',
                                                  av.strip())]}
            elif low_a.startswith('your devotion to '):
                node['amount'] = {'kind': 'devotion',
                                  'color': low_a[len('your devotion to '):]}
            elif low_a == 'your speed':
                node['amount'] = {'kind': 'stat', 'stat': 'speed'}
            if low_a == 'that much life':
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'that_much'}, 'unit': 'life'}
            elif low_a == 'that much':
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'that_much'}}
            elif low_a == 'that many':
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'that_many'}}
            elif low_a == 'double that':
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'that_much'},
                                  'multiplier': 2}
            elif low_a == 'the difference':
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'difference'}}
            else:
                mposs = re.fullmatch(
                    r"(target [a-z ]+|another [a-z ]+|an? [a-z ]+|the [a-z ]+)'s "
                    r"(power|toughness|mana cost|mana value|loyalty)", low_a)
                if mposs:
                    ref = self._amount_ref(mposs.group(1))
                    node['amount'] = {
                        'kind': 'relative',
                        'of': {**ref,
                               'stat': mposs.group(2).replace(' ', '_')}}
                mref = re.fullmatch(
                    r"(its|his|her|their|that [a-z ]+?'s|the [a-z ]+? ?'s) "
                    r"(power|toughness|mana cost|mana value|loyalty)", low_a)
                if mref:
                    owner = mref.group(1).replace(" 's", "'s")
                    if owner in ('its', 'his', 'her', 'their'):
                        of = {'kind': 'possessive', 'possessor': owner}
                    else:
                        owner_text = owner[:-2]
                        if owner_text.startswith('that '):
                            of = {'kind': 'that', 'noun': owner_text[5:]}
                        elif owner_text.startswith('the '):
                            bits = owner_text[4:].split()
                            of = {'kind': 'the', 'noun': bits[-1]}
                            if len(bits) > 1:
                                of['role'] = ' '.join(bits[:-1])
                        else:
                            of = {'kind': 'ref', 'noun': owner_text}
                    node['amount'] = {'kind': 'relative',
                                      'of': {**of,
                                             'stat': mref.group(2).replace(' ', '_')}}
            mplus = re.fullmatch(
                r'(\d+|x) plus the number of (.+)', low_a)
            if mplus:
                raw = mplus.group(1)
                node['amount'] = {
                    'kind': 'computed',
                    'base': int(raw) if raw.isdigit() else 'X',
                    'op': 'plus',
                    'of': {'kind': 'count_of',
                           'set': self._amount_ref(mplus.group(2))}}
            mnum = re.fullmatch(r'the number of (.+)', low_a)
            if mnum:
                node['amount'] = {'kind': 'count_of',
                                  'set': self._amount_ref(mnum.group(1))}
            msuper = re.fullmatch(
                r'the (greatest|least) (power|toughness|mana value) among (.+)',
                low_a)
            if msuper:
                node['amount'] = {
                    'kind': 'superlative', 'which': msuper.group(1),
                    'stat': msuper.group(2).replace(' ', '_'),
                    'set': self._amount_ref(msuper.group(3))}
            mstatof = re.fullmatch(
                r'the (mana value|power|toughness|loyalty) of (.+)', low_a)
            if mstatof:
                of_text = mstatof.group(2)
                if of_text == 'the exiled card used to craft it':
                    of = {'kind': 'exiled_card', 'used_to': 'craft'}
                elif of_text == 'the chosen creature or card':
                    of = {'kind': 'choice',
                          'options': [{'kind': 'creature'}, {'kind': 'card'}]}
                elif of_text == 'the creature you chose or the card you revealed':
                    of = {'kind': 'choice',
                          'options': [{'kind': 'chosen', 'card_class': 'creature'},
                                      {'kind': 'revealed', 'card_class': 'card'}]}
                else:
                    of = self._amount_ref(of_text)
                node['amount'] = {'kind': 'computed',
                                  'base': {'kind': 'stat',
                                           'stat': mstatof.group(1).replace(' ', '_')},
                                  'of': of}
            mfrac = re.fullmatch(
                r'(half|quarter|third) your starting life total', low_a)
            if mfrac:
                node['amount'] = {'kind': 'fraction', 'fraction': mfrac.group(1),
                                  'of': {'kind': 'life_total', 'player': 'you',
                                         'which': 'starting'}}
            mper = re.fullmatch(
                r'(\{[^}]+\}(?:\s*\{[^}]+\})*) for each (.+)', low_a)
            if mper:
                per_text = mper.group(2)
                if per_text.startswith('{'):
                    import ast
                    try:
                        per = ast.literal_eval(per_text)
                    except (ValueError, SyntaxError):
                        per = self._amount_ref(per_text)
                else:
                    per = self._amount_ref(per_text)
                if isinstance(per, dict) and isinstance(per.get('controller'), str):
                    per = dict(per)
                    per['controller'] = {'you control': 'you'}.get(
                        per['controller'], per['controller'])
                node['amount'] = {'kind': 'mana_per',
                                  'mana': re.findall(r'\{[A-Za-z0-9/]+\}', av.strip()),
                                  'per': per}
            mthatmana = re.fullmatch(r'that much (\{[^}]+\}(?:\s*\{[^}]+\})*)', low_a)
            if mthatmana:
                node['amount'] = {'kind': 'relative',
                                  'of': {'kind': 'that_much'},
                                  'mana': re.findall(r'\{[A-Za-z0-9/]+\}', mthatmana.group(1))}
            mtwice = re.fullmatch(r'twice (its|their|his|her) (power|toughness)', low_a)
            if mtwice:
                node['amount'] = {
                    'kind': 'relative', 'multiplier': 2,
                    'of': {'kind': 'possessive', 'possessor': mtwice.group(1),
                           'stat': mtwice.group(2)}}
            if node.get('amount') != av:
                pass
            elif mhalf := re.fullmatch(
                r'(half|quarter|third) (their|your) (life|library)(?:,\s*rounded (up|down))?',
                low_a):
                d = {'kind': mhalf.group(1),
                     'of': {'possessive': mhalf.group(2).replace('their', 'they'),
                            'stat': mhalf.group(3)}}
                if mhalf.group(4):
                    d['rounding'] = mhalf.group(4)
                node['amount'] = d
        if node.get('kind') in ('half', 'quarter', 'third') and \
                isinstance(node.get('of'), str):
            mof = re.fullmatch(r'(their|your) (life|library)', node['of'])
            if mof:
                node['of'] = {'possessive': mof.group(1).replace('their', 'they'),
                              'stat': mof.group(2)}
        relv = node.get('relative')
        if isinstance(relv, str):
            low_rel = relv.strip().lower()
            if low_rel == 'that was dealt damage this turn':
                node['relative'] = {'kind': 'event_ref', 'event': 'dealt_damage',
                                    'voice': 'passive', 'time': 'this_turn'}
        if 'xdef' in node and isinstance(node.get('of'), str):
            low_xof = node['of'].strip().lower()
            mxof = re.fullmatch(
                r'mana spent to cast (this spell|that spell|it|this creature)',
                low_xof)
            if mxof:
                node['of'] = {'kind': 'mana_spent', 'action': 'cast',
                              'object': mxof.group(1)}
        dv = node.get('duration')
        if isinstance(dv, str):
            low_d = dv.strip().lower()
            dur = None
            if low_d in ('until end of turn', 'end of turn'):
                dur = {'kind': 'until', 'event': 'end_of_turn'}
            elif low_d == 'this turn':
                dur = {'kind': 'for', 'event': 'this_turn'}
            elif low_d == 'until the end of your next turn':
                dur = {'kind': 'until', 'event': 'end_of_turn',
                       'which': 'next', 'player': 'you'}
            elif low_d == 'until the end of their next turn':
                dur = {'kind': 'until', 'event': 'end_of_turn',
                       'which': 'next', 'player': 'they'}
            elif low_d == 'until your next turn':
                dur = {'kind': 'until', 'event': 'next_turn',
                       'player': 'you'}
            elif low_d == 'until your next end step':
                dur = {'kind': 'until', 'event': 'next_end_step',
                       'player': 'you'}
            elif low_d == 'during your turn':
                dur = {'kind': 'for', 'event': 'your_turn'}
            elif low_d == 'for the rest of the game':
                dur = {'kind': 'for', 'event': 'rest_of_game'}
            else:
                mleave = re.fullmatch(
                    r'until this ([a-z ]+?) leaves the battlefield',
                    low_d)
                if mleave:
                    dur = {'kind': 'until',
                           'event': 'leaves_battlefield',
                           'object': mleave.group(1)}
            if dur:
                node['duration'] = dur
        for ckey in ('counter', 'counters'):
            cv = node.get(ckey)
            if not isinstance(cv, str):
                continue
            low_c = cv.strip().lower()
            mcounter = re.fullmatch(
                r'(?:an? )?(.+?)\s+counters?(?:\s+s)?', low_c)
            if not mcounter:
                continue
            kind = mcounter.group(1).strip()
            if kind in ('each kind of', 'those', 'this creature\'s',
                        'plus one of each of those kinds of'):
                continue
            count = node.get('count', 1)
            if isinstance(count, str):
                lc = count.strip().lower()
                words = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
                         'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                         'eight': 8, 'nine': 9, 'ten': 10}
                if lc.isdigit():
                    count = int(lc)
                elif lc in words:
                    count = words[lc]
                elif lc == 'x':
                    count = 'X'
            node[ckey] = {'kind': kind, 'count': count}
        chg = node.get('change')
        if isinstance(chg, str):
            low_ch = chg.strip().lower()
            mpt = re.fullmatch(
                r'(an additional )?([+-]?)(\d+|x)/([+-]?)(\d+|x)', low_ch)
            if mpt:
                def _signed(sign, raw):
                    if raw == 'x':
                        return 'X' if sign != '-' else '-X'
                    v = int(raw)
                    return -v if sign == '-' else v
                dpt = {'power': _signed(mpt.group(2), mpt.group(3)),
                       'toughness': _signed(mpt.group(4), mpt.group(5))}
                if mpt.group(1):
                    dpt['additional'] = True
                node['change'] = dpt
        def _sym_timing(v):
            low_t = v.strip().lower()
            if low_t == 'as a sorcery':
                return {'timing': 'sorcery'}
            if low_t == 'once each turn':
                return {'frequency': 'once_each_turn'}
            if low_t == 'each turn':
                return {'frequency': 'each_turn'}
            if low_t == 'this turn':
                return {'kind': 'this_turn'}
            if low_t == 'during your turn':
                return {'kind': 'turn', 'player': 'you'}
            if low_t == "an opponent's turn":
                return {'kind': 'turn', 'player': 'opponent'}
            if low_t == 'your turn':
                return {'kind': 'turn', 'player': 'you'}
            if low_t == 'at end of combat':
                return {'phase': 'combat', 'position': 'end'}
            mbegin = re.fullmatch(
                r'at the beginning of (?:the )?(.+)', low_t)
            if not mbegin:
                return None
            rest = mbegin.group(1)
            d = {'position': 'beginning'}
            mplayer = re.match(
                r"(your|their|each player's|each opponent's|an opponent's|each) (.+)",
                rest)
            player = None
            if mplayer:
                player = {'your': 'you', 'their': 'they',
                          "each player's": 'each_player',
                          "each opponent's": 'each_opponent',
                          "an opponent's": 'opponent',
                          'each': 'each'}[mplayer.group(1)]
                rest = mplayer.group(2)
            if rest.endswith(' on your turn'):
                player = player or 'you'
                rest = rest[:-len(' on your turn')]
            if player:
                d['player'] = player
            if rest.startswith('next '):
                d['which'] = 'next'
                rest = rest[5:]
            elif rest.startswith('first '):
                d['which'] = 'first'
                rest = rest[6:]
            elif rest.startswith('second '):
                d['which'] = 'second'
                rest = rest[7:]
            rest = rest.replace('end step', 'end_step')
            rest = rest.replace('draw step', 'draw_step')
            rest = rest.replace('main phase', 'main_phase')
            rest = rest.replace('combat on your turn', 'combat')
            d['phase'] = rest
            return d
        for tkey in ('activate_only', 'when', 'timing', 'window'):
            tv = node.get(tkey)
            if not isinstance(tv, str):
                continue
            td = _sym_timing(tv)
            if td:
                node[tkey] = td
        def _sym_dest(v):
            low = v.strip().lower()
            if low in ('any target', 'any other target'):
                return {'kind': 'any_target'}
            if low in ('a player', 'an opponent', 'defending player',
                       'target player', 'target opponent'):
                q = 'a' if low.startswith('a ') else (
                    'an' if low.startswith('an ') else 'target')
                kind = 'player' if 'player' in low else 'opponent'
                d = {'kind': kind, 'quantifier': q}
                if low == 'defending player':
                    d['which'] = 'defending'
                return d
            if low.startswith('their choice of the top or bottom of their library'):
                return {'zone': 'library', 'owner': 'they',
                        'library_position': 'choice_top_or_bottom'}
            if low.startswith('their library second from the top or on the bottom'):
                return {'zone': 'library', 'owner': 'they',
                        'library_position': 'second_from_top_or_bottom'}
            if not low.startswith('to '):
                return None
            rest = low[3:]
            zone = None
            for z in ('battlefield', 'hand', 'graveyard', 'library', 'exile',
                      'stack', 'command zone'):
                if rest.startswith(z) or rest.startswith('the ' + z) or \
                        rest.startswith('their ' + z) or \
                        rest.startswith('your ' + z) or \
                        rest.startswith("its owner's " + z):
                    zone = z
                    break
            if zone is None:
                if rest in ('you', 'them', 'it', 'that player'):
                    return {'kind': 'recipient', 'recipient': rest}
                return None
            d = {'zone': zone}
            if 'under its owner' in rest:
                d['controller'] = 'owner'
            elif 'under your control' in rest:
                d['controller'] = 'you'
            elif "under their owners' control" in rest:
                d['controller'] = 'their owners'
            elif 'under their control' in rest:
                d['controller'] = 'they'
            elif "under her owner's control" in rest:
                d['controller'] = 'her owner'
            if 'tapped' in rest:
                d['tapped'] = True
            if 'transformed' in rest:
                d['transformed'] = True
            if "its owner's hand" in rest or "their owner's hand" in rest:
                d['owner'] = 'owner'
            elif 'your hand' in rest:
                d['owner'] = 'you'
            elif 'their hands' in rest:
                d['owner'] = 'their owners'
            elif 'their hand' in rest:
                d['owner'] = 'they'
            if 'top of' in rest:
                d['library_position'] = 'top'
            elif 'bottom of' in rest:
                d['library_position'] = 'bottom'
            mwith = re.search(
                r'with (?:an? |two |three |four |\d+ )?(?:(additional) )?'
                r'(.+?) counters?(?:\s+s)?(?: on |$)', rest)
            if mwith:
                qraw = mwith.group(0)
                mcount = re.search(r'with (an?|two|three|four|\d+)', qraw)
                count = 1
                if mcount:
                    word = mcount.group(1)
                    count = {'a': 1, 'an': 1, 'two': 2, 'three': 3,
                             'four': 4}.get(word, word)
                    if isinstance(count, str) and count.isdigit():
                        count = int(count)
                ctr = {'kind': mwith.group(2), 'count': count}
                if mwith.group(1):
                    ctr['additional'] = True
                d['counter'] = ctr
            return d
        for dkey in ('to', 'destination'):
            dval = node.get(dkey)
            if isinstance(dval, str):
                dobj = _sym_dest(dval)
                if dobj:
                    node[dkey] = dobj
        for pkey in ('power_toughness', 'pt', 'base_pt'):
            pv = node.get(pkey)
            if not isinstance(pv, str):
                continue
            low_p = pv.strip().lower()
            mptv = re.fullmatch(
                r'([+-]?(?:\d+|x|\*))/([+-]?(?:\d+|x|\*))', low_p)
            if not mptv:
                continue
            def _ptval(raw):
                if raw in ('x', '*'):
                    return raw.upper()
                return int(raw)
            node[pkey] = {'power': _ptval(mptv.group(1)),
                          'toughness': _ptval(mptv.group(2))}
        def _sym_modifier(v):
            low = v.strip().lower()
            mpay = re.fullmatch(
                r'(?:(?:\{[^}]+\}(?:\s*,\s*)?)+ )?pay ([0-9]+|x) life', low)
            if mpay:
                raw = mpay.group(1)
                return {'kind': 'pay_life',
                        'cost': {'kind': 'number',
                                 'value': int(raw) if raw.isdigit() else 'X',
                                 'unit': 'life'}}
            mput = re.fullmatch(r'that was put there this turn', low)
            if mput:
                return {'kind': 'relative', 'event': 'put',
                        'location': 'there', 'time': 'this_turn'}
            mstatle = re.fullmatch(
                r'with (?:total )?(mana value|power|toughness) '
                r'less than or equal to the number of (.+)', low)
            if mstatle:
                return {'kind': 'stat_filter', 'stat': mstatle.group(1),
                        'op': '<=',
                        'value': {'kind': 'computed',
                                  'of': {'kind': 'count_of',
                                         'set': Interpreter._amount_ref(
                                             mstatle.group(2))}}}
            mstat = re.fullmatch(
                r'with (?:total )?(mana value|power|toughness) '
                r'([0-9]+|x) (or less|or greater)', low)
            if mstat:
                raw = mstat.group(2)
                return {'kind': 'stat_filter', 'stat': mstat.group(1),
                        'op': '<=' if mstat.group(3) == 'or less' else '>=',
                        'value': int(raw) if raw.isdigit() else 'X'}
            mkw = re.fullmatch(
                r'with (flying|haste|deathtouch|trample|menace|defender|flash|'
                r'lifelink|vigilance|reach|intimidate|indestructible)', low)
            if mkw:
                return {'kind': 'keyword', 'keyword': mkw.group(1)}
            mtype = re.fullmatch(r'of (the chosen|that|the same) (type|color|name)', low)
            if mtype:
                return {'kind': mtype.group(2), 'which': mtype.group(1)}
            mevent = re.fullmatch(
                r'(exiled|discarded|destroyed|milled|revealed|tapped|sacrificed) this way', low)
            if mevent:
                return {'kind': 'event_filter', 'event': mevent.group(1),
                        'source': 'this_way'}
            mtarget = re.fullmatch(r'that targets (.+)', low)
            if mtarget:
                return {'kind': 'targets', 'target': mtarget.group(1)}
            mname = re.fullmatch(r'(?:named ~|with the chosen name)', low)
            if mname:
                return {'kind': 'name', 'name': 'chosen'}
            mnames = re.fullmatch(r'with (different|the same) names?', low)
            if mnames:
                return {'kind': 'names', 'mode': mnames.group(1)}
            mfrom = re.fullmatch(r"from \['([^']+)'\]", low)
            if mfrom:
                return {'kind': 'from', 'values': [mfrom.group(1)]}
            mother = re.fullmatch(r'other than (.+)', low)
            if mother:
                return {'kind': 'exclude', 'value': mother.group(1)}
            mctr = re.fullmatch(
                r'with (?:an? |two |three |four |\d+ )?(.+?) counters?(?:\s+s)? on (it|them|him|her)', low)
            if mctr:
                return {'kind': 'counter', 'counter': {'kind': mctr.group(1)},
                        'on': mctr.group(2)}
            return None
        for mkey in ('modifier', 'with_modifier'):
            mv = node.get(mkey)
            if isinstance(mv, str):
                mobj = _sym_modifier(mv)
                if mobj:
                    node[mkey] = mobj
        def _sym_object(v):
            low = v.strip().lower()
            if low == 'a noncreature spell':
                return {'kind': 'spell', 'quantifier': 'a',
                        'card_type': {'kind': 'type', 'value': 'spell'},
                        'noncreature': True}
            if low == 'a spell':
                return {'kind': 'spell', 'quantifier': 'a'}
            if low == 'a card':
                return {'kind': 'card', 'quantifier': 'a'}
            if low in ('a creature type', 'a basic land type', 'a card type',
                       'a color', 'a card name', 'a nonland card name'):
                return {'kind': low[2:].replace(' ', '_')}
            if low == 'the battlefield':
                return {'zone': 'battlefield'}
            if low == 'top card of your library':
                return {'kind': 'card', 'position': 'top',
                        'zone': 'library', 'owner': 'you'}
            if low == 'your second card each turn':
                return {'kind': 'card', 'ordinal': 'second',
                        'player': 'you', 'frequency': 'each_turn'}
            if low == 'one or both':
                return {'kind': 'choice', 'options': 'one_or_both'}
            if low in ('odd or even', 'even or odd'):
                return {'kind': 'choice', 'options': 'odd_or_even'}
            if low == 'a player':
                return {'kind': 'player', 'quantifier': 'a'}
            return None
        for okey in ('object',):
            ov = node.get(okey)
            if isinstance(ov, str):
                oobj = _sym_object(ov)
                if oobj:
                    node[okey] = oobj
        colv = node.get('colors')
        if isinstance(colv, str):
            low_col = colv.strip().lower()
            if ' and/or ' in low_col:
                node['colors'] = {'kind': 'and_or',
                                  'values': low_col.split(' and/or ')}
            elif ' and ' in low_col:
                node['colors'] = {'kind': 'all',
                                  'values': low_col.split(' and ')}
            elif ' or ' in low_col:
                node['colors'] = {'kind': 'any',
                                  'values': low_col.split(' or ')}
        pred = node.get('predicate')
        if isinstance(pred, str):
            low_p = pred.strip().lower()
            verbs = [x.strip() for x in low_p.split(' or ')]
            if len(verbs) > 1:
                node['predicate'] = {'kind': 'predicate', 'verbs': verbs}
            elif low_p in ('be blocked', 'be countered'):
                node['predicate'] = {'kind': 'predicate',
                                     'verbs': [low_p[3:]],
                                     'voice': 'passive'}
            elif low_p.startswith('be '):
                node['predicate'] = {'kind': 'predicate',
                                     'verbs': [low_p[3:]],
                                     'voice': 'passive'}
            elif low_p == 'cast spells':
                node['predicate'] = {'kind': 'predicate', 'verbs': ['cast'],
                                     'object': 'spells'}
            elif low_p == 'activate abilities':
                node['predicate'] = {'kind': 'predicate',
                                     'verbs': ['activate'],
                                     'object': 'abilities'}
            elif low_p == 'lose mana':
                node['predicate'] = {'kind': 'predicate', 'verbs': ['lose'],
                                     'object': 'mana'}
        def _sym_label(v):
            low = v.strip().lower()
            low = re.sub(r'^(?:that|this) (?:creature|permanent|card) is (?:a|an) ', '', low)
            low = re.sub(r"^it's (?:a|an) ", '', low)
            q = None
            for pre, qv in (('up to one target ', 'up_to_one'),
                            ('up to two target ', 'up_to_two'),
                            ('target ', 'target'), ('another ', 'another'),
                            ('all ', 'all')):
                if low.startswith(pre):
                    q = qv
                    low = low[len(pre):]
                    break
            if q is None and low[:2] in ('a ', 'an '):
                q = low[:2].strip()
                low = low[2:]
            controller = None
            for suf, cv in ((' you control', 'you control'),
                            (' an opponent controls', 'opponent controls'),
                            (" you don't control", "you don't control"),
                            (' you own', 'you own')):
                if low.endswith(suf):
                    controller = cv
                    low = low[:-len(suf)]
                    break
            card_class = None
            for suf, cv in ((' spells', 'spell'), (' spell', 'spell'),
                            (' cards', 'card'), (' card', 'card'),
                            (' tokens', 'token'), (' token', 'token'),
                            (' permanents', 'permanent'),
                            (' permanent', 'permanent')):
                if low.endswith(suf):
                    card_class = cv
                    low = low[:-len(suf)]
                    break
            parts = [x.strip(' ,') for x in
                     re.split(r'\s*(?:,|\band\b|\bor\b)\s*', low)]
            skip = {'tapped', 'untapped', 'attacking', 'blocking', 'red',
                    'green', 'white', 'blue', 'black', 'colorless',
                    'nontoken', 'legendary', 'basic', 'other', 'another',
                    'each', 'all', 'chosen', 'single', 'first', 'second',
                    'tokenn', 'attacking'}
            types = []
            for part in parts:
                if not part or part in skip:
                    continue
                part = re.sub(r'^non-', '', part)
                part = re.sub(r'^(?:a|an|the) ', '', part)
                part = re.sub(r's$', '', part) if part.endswith('s') else part
                part = part.replace('vehicle', 'vehicle').replace('spacecraft', 'spacecraft')
                types.append({'kind': 'type', 'value': part})
            if not types:
                return None
            d = {}
            if q:
                d['quantifier'] = q
            d['card_type'] = types
            if card_class:
                d['card_class'] = card_class
            if controller:
                d['controller'] = {'you control': 'you',
                                   'opponent controls': 'opponent',
                                   "you don't control": 'not_you',
                                   'you own': 'you_own'}.get(controller, controller)
            return d
        if isinstance(node.get('label'), str):
            lobj = _sym_label(node['label'])
            if lobj:
                node['label'] = lobj
        fev = node.get('for_each')
        if isinstance(fev, str):
            low_fe = fev.strip().lower()
            if low_fe == 'opponent who lost life this turn':
                node['for_each'] = {'kind': 'event_set', 'subject': 'opponent',
                                    'event': 'lost_life', 'time': 'this_turn'}
            elif 'counter on ' in low_fe:
                kind, obj = low_fe.split(' counter on ', 1)
                node['for_each'] = {'kind': 'counter_set',
                                    'counter': {'kind': kind}, 'object': obj}
            else:
                parts = [x.strip() for x in
                         re.split(r'\s+and each\s+|\s+and\s+', low_fe)]
                items = []
                for part in parts:
                    controller = None
                    zone = None
                    for ctl in ('you control', 'you already control',
                                'you own'):
                        if part.endswith(' ' + ctl):
                            controller = ctl
                            part = part[:-len(ctl) - 1]
                            break
                    mzone = re.search(
                        r' (?:in|from) (your graveyard|your hand|your library|exile|the battlefield)$',
                        part)
                    if mzone:
                        zone = mzone.group(1)
                        part = part[:mzone.start()]
                    card_class = None
                    for suf, cv in ((' card', 'card'), (' creature', 'creature'),
                                    (' permanent', 'permanent')):
                        if part.endswith(suf):
                            card_class = cv
                            part = part[:-len(suf)]
                            break
                    part = re.sub(r'^each ', '', part).strip()
                    item = {'kind': 'type', 'value': part}
                    if card_class:
                        item['card_class'] = card_class
                    if controller:
                        item['controller'] = {'you control': 'you',
                                              'you already control': 'you',
                                              'you own': 'you_own'}.get(controller, controller)
                    if zone:
                        item['zone'] = zone.replace('your ', '')
                    items.append(item)
                node['for_each'] = {'kind': 'set',
                                    'items': items if len(items) > 1 else items[0]}
        cntv = node.get('count')
        if isinstance(cntv, str):
            low_cnt = cntv.strip().lower()
            words = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
                     'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                     'eight': 8, 'nine': 9, 'ten': 10}
            if low_cnt == 'that many':
                node['count'] = {'kind': 'relative', 'of': {'kind': 'that_many'}}
            elif low_cnt == 'one or more':
                node['count'] = {'kind': 'count', 'at_least': 1}
            elif low_cnt == 'that many plus one':
                node['count'] = {'kind': 'relative', 'of': {'kind': 'that_many'},
                                 'plus': 1}
            elif low_cnt in words:
                node['count'] = words[low_cnt]
            elif low_cnt.isdigit():
                node['count'] = int(low_cnt)
            elif low_cnt == 'x':
                node['count'] = 'X'
        byv = node.get('by')
        if isinstance(byv, str) and 'in addition to paying' in byv.lower():
            low_by = byv.strip().lower()
            actions = []
            mpay = re.match(r'paying ([0-9]+|x) life', low_by)
            if mpay:
                raw = mpay.group(1)
                actions.append({'action': 'pay_life',
                                'amount': int(raw) if raw.isdigit() else 'X'})
            mdisc = re.match(r'discarding (a|an|one|two|three|[0-9]+) card', low_by)
            if mdisc:
                raw = mdisc.group(1)
                n = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3}.get(
                    raw, int(raw) if raw.isdigit() else 1)
                actions.append({'action': 'discard', 'count': n, 'card': 'card'})
            mrem = re.match(r'removing ([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten) counters', low_by)
            if mrem:
                raw = mrem.group(1)
                n = ({'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                      'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
                     .get(raw, int(raw) if raw.isdigit() else 1))
                actions.append({'action': 'remove_counters', 'count': n,
                                'from': {'kind': 'set',
                                         'card_type': [{'kind': 'type',
                                                        'value': 'creature'}],
                                         'controller': 'you'}})
            if low_by.startswith('foraging'):
                actions.append({'action': 'forage'})
            if actions:
                node['by'] = {'kind': 'cost_phrase', 'actions': actions,
                              'addition_to_other_costs': True}
        if 'text' in node and 'when' in node:
            ev = self._trigger_event(node.get('text'))
            if ev is not None:
                node.setdefault('event', ev)
                node.pop('text', None)
        if 'text' in node:
            frag = node.pop('text')
            reason, source = self._unparsed_tag(node)
            node['unparsed'] = True
            node['reason'] = reason
            node['fragment'] = frag
            node['source'] = source
        if node.get('unparsed') and node.get('reason') == 'no_handler':
            frag = ' '.join(str(node.get('fragment', '')).lower().split()).rstrip('.')
            if frag in ('you do', 'they do'):
                node.clear()
                node.update({'kind': 'event_ref',
                             'actor': 'you' if frag.startswith('you') else 'they',
                             'polarity': 'positive'})
            elif frag.startswith('you cast a spell during '):
                node.clear()
                node.update({'kind': 'event',
                             'event': {'subject': 'you', 'verb': 'cast',
                                       'object': {'card_type': {
                                           'kind': 'type', 'value': 'spell'}}},
                             **({'window': self._window_obj(
                                 frag[len('you cast a spell during '):])}
                                if self._window_obj(frag[len('you cast a spell during '):]) else {})})
        if top:
            if node.get('type') == 'effect':
                eff = node.get('effect')
                if (isinstance(eff, dict) and eff.get('unparsed')
                        and eff.get('reason') == 'raw_action'
                        and set(node) <= {'type', 'effect', 'ability_word'}):
                    return {'type': 'unparsed', 'reason': eff['reason'],
                            'fragment': eff['fragment'],
                            'source': eff['source']}
            if (node.get('type') in ('static', 'modal')
                    and node.get('unparsed') and node.get('fragment')):
                return {'type': 'unparsed', 'reason': node['reason'],
                        'fragment': node['fragment'],
                        'source': node['source']}
        return node

    def i_sentence(self, children):
        for ch in children:
            if isinstance(ch, Tree):
                return self.interp(ch)
        return None

    # ------------------------------------------------------------------ card target
    def i_card_target(self, children):
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'LISTTOK':
                return decode_list_token(ch.value)
        d = {}
        # Fields are grouped under lead/core/zone_mod; search the whole subtree
        # so the grouping is transparent.  Order of the mapping is the precedence
        # when a key can be produced by more than one rule name.
        mapping = [
            ('this_that', 'this_that'), ('possessive', 'possessive'),
            ('quantifier', 'quantifier'), ('otherness', 'otherness'),
            ('nontoken', 'nontoken'), ('status_list', 'status'),
            ('colors', 'colors'), ('card_kind', 'card_type'),
            ('without_mod', 'without_keywords'),
            ('with_modifier', 'modifier'), ('controller', 'controller'),
            ('in_zone', 'zone'), ('relative_mod', 'relative'),
        ]
        for name, key in mapping:
            found = self._find_all(children, name)
            if found:
                d[key] = self.interp(found[0])
        mod = d.get('modifier')
        if (isinstance(mod, str) and 'number of' in mod
                and d.get('controller')):
            # "with mana value <= the number of creatures you control":
            # `you control` delimits the inner count set, not the outer card.
            # Earley may bind it to the outer zone_mod; re-attach it.
            d['modifier'] = mod + ' ' + str(d['controller'])
            d.pop('controller', None)
        if 'otherness' not in d:
            # "up to one other target creature": `other` sits inside the
            # quantifier subtree, so it must be lifted to the target.
            for q in self._find_all(children, 'quantifier'):
                if 'other' in self._token_words(q.children):
                    d['otherness'] = 'other'
                    break
        if d.get('quantifier') == 'each':
            # "each of up to two target creatures": the distributive `each`
            # wraps a nested card_target that carries the real quantifier.
            for inner_tree in self._find_all(children, 'card_target'):
                inner = self.interp(inner_tree)
                if isinstance(inner, dict) and inner.get('quantifier'):
                    inner = dict(inner)
                    d.pop('quantifier', None)
                    d.update(inner)
                    d['each'] = True
                    return d
        return d

    def i_relative_mod(self, children):
        return self._text(children)

    def i_card_kind(self, children):
        toks = [c for c in children if isinstance(c, Token)]
        for t in toks:
            if t.type == 'LISTTOK':
                return decode_list_token(t.value)
        trees = [c for c in children if isinstance(c, Tree)]
        if trees:
            if len(trees) > 1:
                # "artifact or creature" / "creature or land card": keep every
                # conjunct instead of silently narrowing to the first type.
                vals = []
                for tr in trees:
                    v = self.interp(tr)
                    if isinstance(v, dict):
                        v = v.get('value')
                    if v:
                        vals.append(str(v))
                if len(vals) > 1:
                    words = [str(t).lower() for t in toks]
                    if 'or' in words or 'and/or' in words:
                        sep = ' or '
                    elif 'and' in words:
                        sep = ' and '
                    else:
                        # "noncreature, nonland": comma lists are an
                        # intersection of restrictions, not a union.
                        sep = ', '
                    return {'kind': 'type', 'value': sep.join(vals)}
            return self.interp(trees[0])
        if not toks:
            return None
        if toks[0].type == 'THIS_CARD':
            return {'kind': 'this_card', 'value': '~'}
        if toks[0].type == 'CARDNAME':
            base = self._resolve_kind(toks[0].value)
            rest = [t.value.lower() for t in toks[1:]]
            if rest:
                base = dict(base)
                base['value'] = toks[0].value + ' ' + ' '.join(rest)
            return base
        if toks[0].type == 'INSTANT_SORCERY':
            return {'kind': 'type', 'value': 'instant or sorcery'}
        if toks[0].value.lower() in self.ANAPHORA:
            return {'ref': 'anaphora', 'raw': toks[0].value}
        words = [t.value.lower() for t in toks]
        if words and words[0] in ("players'", "opponents'") and 'graveyards' in words:
            return {'kind': 'type', 'value': words[0] + ' graveyards'}
        # "basic land card": `basic` is a modifier, not the type. Reporting
        # toks[0] alone dropped the head noun ('basic' instead of 'basic land').
        if len(words) > 1 and words[0] in ('basic', 'nonbasic') and 'land' in words:
            return {'kind': 'type', 'value': words[0] + ' land'}
        if len(words) > 1 and ('token' in words or 'tokens' in words):
            # "target artifact token" / "creature tokens": keep the token
            # restriction instead of reporting only the first type word.
            head = next((w for w in words if w not in ('token', 'tokens')), None)
            if head:
                return {'kind': 'type', 'value': head + ' token'}
        if all(t.type in self.ABILITY_TOKENS for t in toks):
            has_ability = any(w in ('ability', 'abilities') for w in words)
            has_spell = any(w in ('spell', 'spells') for w in words)
            if has_ability and has_spell:
                kind = 'spell or ability'
            else:
                kind = 'ability' if has_ability else 'spell'
            return {'kind': kind, 'value': ' '.join(words)}
        # Disjunctive type lists ("instant or sorcery spell", "artifact or
        # creature") must keep every conjunct: reporting only the first word
        # silently narrows the target type.
        words = [t.value.lower() for t in toks]
        if len(toks) > 1 and any(w in ('or', 'and', 'and/or', ',') for w in words):
            joins = [w for w in words if w.strip(',')]
            while joins and joins[-1].rstrip('s') in ('spell', 'card'):
                joins.pop()
            if len(joins) > 1:
                return {'kind': 'type', 'value': ' '.join(joins)}
        # "nonlegendary permanent card": the trailing head noun `card` is
        # generic, but the adjective chain before it is the type restriction.
        # Reporting only the first token silently dropped `permanent`.
        if (len(words) > 2 and words[-2] == 'card' and words[-1] == 's'):
            head = ' '.join(words[:-2])
            if head:
                return {'kind': 'type', 'value': head}
        if len(words) > 1 and words[-1] in ('card', 'cards'):
            head = ' '.join(words[:-1])
            if head:
                return {'kind': 'type', 'value': head}
        if len(words) > 1:
            # Adjective + head noun ("legendary creature", "nonartifact
            # creature"): reporting only the first token drops the noun.
            return {'kind': 'type', 'value': ' '.join(words)}
        return {'kind': 'type', 'value': toks[0].value.lower()}

    def i_types(self, children):
        for ch in children:
            if isinstance(ch, Token):
                if ch.type == 'LISTTOK':
                    return decode_list_token(ch.value)
                if ch.type == 'CARDNAME':
                    return self._resolve_kind(ch.value)
                return {'kind': 'type', 'value': ch.value.lower()}
        return None

    def i_quantifier(self, children):
        toks = [c for c in children if isinstance(c, Token)]
        trees = [c for c in children if isinstance(c, Tree)]
        words = [t.value for t in toks]
        low = [w.lower() for w in words]
        # Lark merges adjacent literals ("up to") into one anonymous token;
        # the same phrase also arrives as separate V_UP/V_TO tokens.
        if 'up to' in low or ('up' in low and 'to' in low):
            if 'that' in low and 'many' in low:
                return {'up_to': 'that many'}
            return {'up_to': self._first_number(children)}
        if len(words) == 1 and words[0].isdigit():
            return int(words[0])
        if 'or' in low and 'more' in low:
            # "one or more creatures" is a batched quantity, not the number 1.
            n = self._first_number(children)
            if n == 1:
                return {'one_or_more': 1}
            if n is not None:
                return '%s or more' % n
        if trees:
            return self.interp(trees[0])
        if len(words) > 1:
            # Multi-word quantifier phrases ("one or two", "any number of") are one
            # unit; a trailing "target" belongs to the target, not the quantifier.
            if low == ['that', 'many']:
                return 'that many'
            if 'or' in low or 'of' in low:
                if low[-1] == 'target':
                    low = low[:-1]
                return ' '.join(low)
        return words[0].lower() if words else None

    def i_status_list(self, children):
        return [ch.value for ch in children if isinstance(ch, Token)]

    def i_color(self, children):
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'COLOR':
                return ch.value.lower()
        return None

    def i_colors(self, children):
        out = []
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'color':
                v = self.interp(ch)
                if isinstance(v, str):
                    out.append(v)
            elif isinstance(ch, Token) and ch.type == 'COLOR':
                out.append(ch.value.lower())
        return out

    def i_controller(self, children):
        return self._text(children)

    def i_with_modifier(self, children):
        text = self._text(children)
        # "cards each with mana value 2 or less": "each" is distributive over the
        # targets, not part of the restriction itself.
        if text.lower().startswith('each with '):
            text = text[len('each '):]
        return text

    def i_this_that(self, children):
        # A bare pronoun reaches card_target either through this_that or through
        # card_kind, depending on which alternative the parser resolves.  Report
        # both the same way: an anaphora reference, never a card type.
        text = self._text(children)
        if text.lower() in self.ANAPHORA:
            return {'ref': 'anaphora', 'raw': text}
        return text

    def i_without_mod(self, children):
        return [c.value for c in children
                if isinstance(c, Token) and c.type == 'KEYWORD']

    def i_possessive(self, children):
        return self._text(children)

    def i_otherness(self, children):
        return self._text(children)

    def i_nontoken(self, children):
        return [ch.value for ch in children if isinstance(ch, Token)]

    def i_in_zone(self, children):
        prep = None
        zone = None
        for ch in children:
            if isinstance(ch, Token):
                if ch.value in ('in', 'from', 'on'):
                    prep = ch.value
                else:
                    zone = ch.value
            elif isinstance(ch, Tree) and ch.data == 'zone':
                owner = None
                for sub in ch.children:
                    if isinstance(sub, Token):
                        v = str(sub.value)
                        if sub.type == 'OWNER' or v.endswith("'s"):
                            owner = v
                zone = self.interp(ch)
                if owner:
                    owner_zone = {'zone': zone, 'possessor': owner}
                    return {'prep': prep, 'zone': zone, 'possessor': owner}
        return {'prep': prep, 'zone': zone}

    def i_zone(self, children):
        # prefer the ZONE_WORD (hand/library/...), not a leading OWNER (your/...)
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'ZONE_WORD':
                return ch.value
        for ch in children:
            if isinstance(ch, Token):
                return ch.value
        return None

    def i_zones(self, children):
        out = []
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'zone':
                z = self.interp(ch)
                if z:
                    out.append(z)
        return out

    # ------------------------------------------------------------------ amounts / keywords
    def i_amount(self, children):
        for ch in children:
            if isinstance(ch, Token):
                if ch.type == 'NUMBER':
                    try:
                        return int(ch.value)
                    except ValueError:
                        return ch.value
                if ch.value == 'X':
                    return 'X'
                v = ch.value.lower()
                if v in self.WORD_NUM:
                    return self.WORD_NUM[v]
                return ch.value
            if isinstance(ch, Tree):
                return self.interp(ch)
        return None

    def i_kw_list(self, children):
        # Keywords may be nested under kw_list_item/kw_item, so collect KEYWORD
        # tokens recursively; also capture "protection from X" items as text.
        out = []
        def walk(n):
            if isinstance(n, Token):
                if n.type == 'KEYWORD':
                    out.append(n.value)
                return
            if n.data in ('kw_list_item', 'kw_item'):
                v = self.i_kw_list_item(n.children)
                if v:
                    out.append(v)
                return
            low = [c.value.lower() for c in n.children if isinstance(c, Token)]
            if 'protection' in low:
                out.append(self._text(n.children))
                return
            kws = [c.value for c in n.children
                   if isinstance(c, Token) and c.type == 'KEYWORD']
            if kws:
                number = None
                for c in n.children:
                    if isinstance(c, Token) and c.type == 'NUMBER':
                        number = c.value
                    elif isinstance(c, Tree) and c.data == 'number':
                        number = self.interp(c)
                out.append(f"{kws[0]} {number}" if number is not None else kws[0])
                return
            for c in n.children:
                walk(c)
        for ch in children:
            walk(ch)
        return out

    def i_kw_list_item(self, children):
        head = []
        mana = []
        nums = []
        for ch in children:
            if isinstance(ch, Tree):
                v = self.interp(ch)
                if isinstance(v, list):
                    head.extend(str(x) for x in v)
                elif v is not None:
                    head.append(str(v))
                continue
            if ch.type == 'MANA':
                mana.append(ch.value)
            elif ch.type in ('NUMBER', 'POWER_T'):
                nums.append(ch.value)
            elif ch.value.lower() in (',', 'and', 'or', '—', '–'):
                continue
            else:
                head.append(ch.value)
        text = ' '.join(head)
        if nums:
            text = (text + ' ' + ' '.join(nums)).strip()
        if mana:
            text = (text + ' ' + ''.join(mana)).strip()
        return text

    # kw_list_mod / kw_item are parallel keyword-list rules -> same extraction.
    i_kw_list_mod = i_kw_list
    def i_kw_item(self, children):
        v = self.i_kw_list(children)
        if not v:
            return None
        number = None
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'NUMBER':
                number = ch.value
            elif isinstance(ch, Tree) and ch.data == 'number':
                number = self.interp(ch)
        return f"{v[0]} {number}" if number is not None else v[0]

    def i_kw_with_mod(self, children):
        key = self.interp(children[0]) if children else None
        mods = []
        for ch in children[1:]:
            if isinstance(ch, Token) and ch.value in ('\u2014', '\u2013', ',', '-', ':'):
                continue
            v = self.interp(ch)
            if v is not None:
                mods.append(v)
        if len(mods) == 1:
            modifier = mods[0]
        else:
            modifier = ' '.join(str(m) for m in mods).strip().replace('} {', '}{')
        d = {'keyword': key, 'modifier': modifier}
        if isinstance(modifier, str):
            kc = self._keyword_cost(modifier)
            if kc:
                d.pop('modifier', None)
                d['cost'] = kc
        return d

    def i_player(self, children):
        return self._text(children)

    def i_who(self, children):
        if not children:
            return None
        toks = [ch.value for ch in children if isinstance(ch, Token)]
        if 'controller' in toks:
            return 'its controller'
        if (len(toks) >= 4 and toks[0].lower() == 'any'
                and toks[1].lower() == 'number' and toks[2].lower() == 'of'
                and any(str(t).lower() == 'players' for t in toks)):
            return 'any number of target players'
        first = children[0]
        val = self.interp(first) if isinstance(first, Tree) else first
        # A `who` slot can be filled by an unrelated leading word that the parser
        # had no other home for ("Then copy that spell" -> who = types 'Then').
        # A target made of a single unresolved type word is never a who.
        if (isinstance(val, dict) and set(val) == {'card_type'}
                and isinstance(val['card_type'], dict)
                and val['card_type'].get('note') == 'unresolved'):
            return None
        return val

    # ------------------------------------------------------------------ effect / actions
    def i_effect(self, children):
        out = []
        timing = None
        timing_phrase = None
        instead = any(isinstance(ch, Token) and str(ch).lower() == 'instead'
                      for ch in children)
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'effect_timing':
                    # "{3}: Until end of turn, …" / "At the beginning of the
                    # next end step, …" keeps the clause in its own subtree;
                    # it qualifies every action.
                    timing = self._duration(ch.children)
                    timing_phrase = self._timing(ch.children)
                    continue
                out.append(self.interp(ch))
        # Coordinated actions often share one target: "target creature gets
        # +2/+0 and gains first strike".  The second action's card_target is
        # empty in the tree; carry the first action's target into it.
        last_target = None
        last_who = None
        last_source = None
        who_verbs = {'gain_life', 'lose_life', 'draw', 'mill', 'discard',
                     'scry', 'surveil'}
        for action in out:
            if not isinstance(action, dict):
                continue
            if action.get('target'):
                last_target = action['target']
            elif action.get('card') and isinstance(action['card'], dict):
                last_target = action['card']
            if 'target' in action and not action['target'] and last_target:
                action['target'] = dict(last_target)
            elif 'card' in action and not action['card'] and last_target:
                action['card'] = dict(last_target)
            # "You draw a card and gain 1 life" / "Target player draws … and
            # loses …": the actor is shared, but only the first action kept it.
            who = action.get('who')
            if who:
                last_who = who
            elif action.get('verb') in who_verbs and last_who is not None:
                action['who'] = last_who
            src = action.get('source')
            if src:
                last_source = src
            elif 'source' in action and not src and last_source is not None:
                action['source'] = last_source
            elif (action.get('verb') == 'deal_damage'
                  and 'source' not in action and last_source is not None):
                action['source'] = last_source
        # …and one duration: "gets +1/+0 and gains first strike until end of
        # turn" puts the clause on the last action only, but it qualifies both.
        head_verbs = {'stat_change', 'gain_kw', 'lose_keywords', 'become',
                      'set_base_pt', "can't"}
        # One shared head: condition, coordinated target list, controller.
        conditions = [a['condition'] for a in out
                      if isinstance(a, dict) and a.get('condition')]
        cards = [a['cards'] for a in out
                 if isinstance(a, dict) and a.get('cards')]
        ctrl = None
        for a in out:
            if not isinstance(a, dict):
                continue
            for v in (a.get('target'), a.get('card')):
                if isinstance(v, dict) and v.get('controller'):
                    ctrl = v['controller']
                    break
            if ctrl:
                break
            for c in a.get('cards') or []:
                if isinstance(c, dict) and c.get('controller'):
                    ctrl = c['controller']
                    break
            if ctrl:
                break
        for a in out:
            if not isinstance(a, dict) or a.get('verb') not in head_verbs:
                continue
            if conditions and 'condition' not in a:
                a['condition'] = conditions[0]
            if cards and 'cards' not in a:
                a['cards'] = cards[0]
            for key in ('target', 'card'):
                v = a.get(key)
                if isinstance(v, dict) and ctrl:
                    v.setdefault('controller', ctrl)
            for c in a.get('cards') or []:
                if isinstance(c, dict) and ctrl:
                    c.setdefault('controller', ctrl)
        durations = [timing] if timing else [a['duration'] for a in out
                                             if isinstance(a, dict) and a.get('duration')]
        if durations:
            for action in out:
                if (isinstance(action, dict)
                        and action.get('verb') in self.DURATION_VERBS
                        and 'duration' not in action):
                    action['duration'] = durations[0]
        if timing_phrase:
            for action in out:
                if isinstance(action, dict):
                    action.setdefault('timing', timing_phrase)
        if instead:
            for action in out:
                if isinstance(action, dict):
                    action['instead'] = True
        # "create a token that's a copy of it, except it isn't legendary and is
        # a Mutant in addition to its other types": the residual targetless
        # become/gain actions describe the token's exception, not a new effect.
        if out and isinstance(out[0], dict) and out[0].get('verb') == 'create_token':
            tok = out[0].get('token')
            if isinstance(tok, dict) and tok.get('except'):
                extra = []
                i = 1
                while i < len(out):
                    a = out[i]
                    if (isinstance(a, dict) and a.get('verb') in ('become', 'gain_kw')
                            and not a.get('target')):
                        a = dict(a)
                        a.pop('target', None)
                        extra.append(a)
                        i += 1
                    else:
                        break
                if extra:
                    tok['except_effects'] = extra
                    out = [out[0]] + out[i:]
        # "… enter as a copy of X, except it's a Bird … and it has flying": a
        # trailing grant on the copied permanent belongs to the copy's
        # exception clause, not to a second effect on an unnamed target.
        def _copy_effect(node):
            if not isinstance(node, dict):
                return None
            if node.get('verb') == 'copy':
                return node
            for key in ('inner', 'effect'):
                inner = node.get(key)
                if isinstance(inner, dict):
                    got = _copy_effect(inner)
                    if got is not None:
                        return got
                elif isinstance(inner, list):
                    for it in inner:
                        got = _copy_effect(it)
                        if got is not None:
                            return got
            return None
        if len(out) > 1:
            cp = _copy_effect(out[0])
            if isinstance(cp, dict) and cp.get('except'):
                kws = []
                i = 1
                while i < len(out):
                    a = out[i]
                    tgt = a.get('target') if isinstance(a, dict) else None
                    if (isinstance(a, dict) and a.get('verb') == 'gain_kw'
                            and isinstance(tgt, dict)
                            and isinstance(tgt.get('card_type'), dict)
                            and tgt['card_type'].get('ref') == 'anaphora'):
                        kws.extend(a.get('keywords') or [])
                        i += 1
                    else:
                        break
                if kws:
                    cp['except_keywords'] = kws
                    out = [out[0]] + out[i:]
        if (len(out) == 2 and isinstance(out[0], dict)
                and out[0].get('verb') == 'remove_counter'
                and isinstance(out[1], dict)):
            # "remove those counters and it deals 20 damage": a removal followed
            # by its consequence keeps the pinned one-action shape
            # (remove_counter with an `and` tail), as the raw-consequence path
            # produced before the structured action existed.
            out[0]['and'] = out[1]
            out = [out[0]]
        if len(out) == 1:
            return out[0]
        return out

    def i_action(self, children):
        for ch in children:
            if isinstance(ch, Tree):
                return self.interp(ch)
        return self._default(children)

    ZONE_WORDS = ('library', 'hand', 'graveyard', 'battlefield', 'exile', 'stack',
                  'piles', 'tombstone', 'zone', 'anywhere')

    def _zone_from_tokens(self, children):
        toks = [str(ch).lower() for ch in children
                if isinstance(ch, Token) and not ch.type.startswith('V_')]
        for z in self.ZONE_WORDS:
            if z in toks:
                return z
        return None

    def _card_action(self, verb, children, key='card'):
        d = {'verb': verb}
        who = self._find_one(children, 'who')
        if who is not None:
            who_value = self.interp(who)
            if who_value:
                d['who'] = who_value
        ct = self._find_one(children, 'card_target')
        cts = self._find(children, 'card_target')
        if ct is not None:
            d[key] = self.interp(ct)
        if (len(cts) > 1
                and verb in ('exile', 'destroy', 'sacrifice', 'tap',
                             'untap', 'discard')):
            words = self._token_words(children)
            if 'attached' in words and 'to' in words:
                # "destroy up to one Equipment attached to that creature":
                # the second target is the attachment host, not a second victim.
                d['attached_to'] = self.interp(cts[1])
            elif 'and' in words or 'or' in words or ',' in words:
                # Coordinated object list: "exile up to one target artifact
                # and up to one target enchantment" keeps both targets.
                d['cards'] = [self.interp(c) for c in cts]
        if verb in ('cast', 'play') and len(cts) > 1:
            words = self._token_words(children)
            if 'among' in words:
                # "cast … from among them / the exiled cards": the source set
                # is the second card_target.
                d['from_among'] = self.interp(cts[1])
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        zns = self._find_one(children, 'zones')
        if zns is not None:
            zlist = self.interp(zns)
            if zlist:
                if len(zlist) == 1:
                    d['zone'] = zlist[0]
                else:
                    d['zones'] = zlist
        else:
            zn = self._find_one(children, 'zone') or self._find_one(children, 'in_zone')
            if zn is not None:
                d['zone'] = self.interp(zn)
            else:
                z = self._zone_from_tokens(children)
                if z is not None:
                    d['zone'] = z
        if d.get('cards') and d.get('zone'):
            # "exile A and B from a graveyard": the shared source zone
            # belongs to every conjunct.
            for card in d['cards']:
                if isinstance(card, dict):
                    card.setdefault('zone', d['zone'])
        wm = self._find_one(children, 'with_modifier')
        if wm is not None:
            d['modifier'] = self.interp(wm)
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        timing = self._timing(children)
        if timing:
            d['timing'] = timing
        d.update(self._placement(children))
        toks = self._token_words(children)
        if 'without' in toks and 'paying' in toks:
            # "cast/play it without paying its mana cost": a free cast/play.
            d['without_paying'] = True
        return d

    def i_cast_action(self, children):
        d = self._card_action('cast', children)
        toks = self._token_words(children)
        if 'this' in toks and 'turn' in toks:
            d.setdefault('duration', 'this turn')
        for i, ch in enumerate(children):
            if isinstance(ch, Token) and str(ch).lower() == 'by':
                d['by'] = self._text(children[i + 1:]).strip()
                break
        return d

    def i_play_action(self, children):
        d = self._card_action('play', children)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'additional' in toks and 'land' in toks:
            d['additional_land'] = True
        if 'this' in toks and 'turn' in toks:
            d.setdefault('duration', 'this turn')
        if 'they' in toks and 'exiled' in toks and 'way' in toks:
            d['exiled_this_way'] = True
        return d

    def i_draw_action(self, children):
        d = {'verb': 'draw'}
        who = self._find_one(children, 'who')
        if who is not None:
            who_value = self.interp(who)
            if who_value:
                d['who'] = who_value
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['cards'] = self.interp(ct)
        amt = self._find_one(children, 'draw_amount')
        if amt is not None:
            value = self.interp(amt)
            # "Draw a card" is one card; keep the numeric contract consistent
            # with "Draw two cards" instead of emitting the article "a".
            d['amount'] = 1 if value in ('a', 'an') else value
        xd = self._find_one(children, 'xdef')
        if xd is not None:
            # Keep the amount as the clause text; str()-joining the
            # interpreted list stringifies nested card_target dicts.
            d['amount'] = ' '.join(self._text(xd.children).split())
        ref = self._find_one(children, 'draw_ref')
        if ref is not None:
            d['amount'] = self.i_draw_ref(ref.children)
        words = self._token_words(children)
        fe = self._for_each(children)
        if fe is not None:
            d['for_each'] = fe
            if 'each' in words and 'for' in words and 'type' in words:
                d['per'] = 'card type'
            elif 'each' in words and 'for' in words and 'counter' in words:
                d['per'] = 'counter'
        return d

    def i_draw_ref(self, children):
        # "equal to its power" / "equal to half the number of cards in <zone>".
        zn = self._find_one(children, 'zone')
        if zn is None:
            return {'stat': 'power', 'possessor': 'its'}
        out = {'count': 'half', 'of': 'cards'}
        z = self.interp(zn)
        if z:
            out['zone'] = z
        return out

    def i_discard_action(self, children):
        d = self._card_action('discard', children)
        words = self._token_words(children)
        if 'at' in words and 'random' in words:
            d['random'] = True
        return d

    def i_exile_action(self, children):
        d = self._card_action('exile', children)
        words = self._token_words(children)
        pl = self._find_one(children, 'player')
        if pl is not None and "'s" in words:
            d['possessor'] = self.interp(pl)
        elif "player's" in words:
            d['possessor'] = ('each ' if 'each' in words else '') + 'player'
        elif "opponent's" in words:
            d['possessor'] = ('each ' if 'each' in words else '') + 'opponent'
        if 'face' in words and 'down' in words:
            d['face_down'] = True
        return d

    def i_destroy_action(self, children):
        d = self._card_action('destroy', children)
        if 'except' in self._token_words(children):
            cts = self._find(children, 'card_target')
            if len(cts) > 1:
                d['except'] = self.interp(cts[1])
        return d

    def i_tap_action(self, children):
        return self._card_action('tap', children)

    def i_untap_action(self, children):
        return self._card_action('untap', children)

    def i_sacrifice_action(self, children):
        d = self._card_action('sacrifice', children)
        toks = self._token_words(children)
        if 'pay' in toks:
            # "sacrifice a creature or pay {2}": keep the alternative cost.
            pay = [str(ch.value) for ch in children
                   if isinstance(ch, Token)
                   and (ch.type in ('MANA', 'NUMBER')
                        or str(ch.value).lower() in ('life', 'mana'))]
            if pay:
                d['or_pay'] = ' '.join(pay)
        return d

    def i_return_action(self, children):
        d = {'verb': 'return'}
        cts = self._find(children, 'card_target')
        if cts:
            d['card'] = self.interp(cts[0])
            if len(cts) > 1:
                d['cards'] = [self.interp(c) for c in cts]
        # Stay with the existing string field (`to`), but drop the leading verb
        # that `_text` includes;  callers expect the destination phrase.
        to = self._text([c for c in children
                         if not (isinstance(c, Tree) and c.data == 'card_target')])
        if to.lower().startswith('return '):
            to = to[7:]
        if to.lower().startswith('and '):
            to = to[4:]
        # "Return to the battlefield <target> ... with mana value ...": keep the
        # destination separate from the mana-value restriction.
        cut = to.lower().find(' with mana value')
        if cut > 0:
            d['mana_value'] = to[cut + len(' with mana value'):].strip()
            to = to[:cut]
        timing = self._timing(children)
        if timing:
            d['timing'] = timing
            if to.lower().endswith(timing.lower()):
                to = to[:-len(timing)].strip()
        d['to'] = to
        ca = self._find_one(children, 'counter_amount')
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            w = {'counter': self._text(ck.children)}
            if ca is not None:
                w['count'] = self.interp(ca)
            toks = [str(c).lower() for c in children
                    if isinstance(c, Token)]
            if 'fewer' in toks:
                amt = self._find_one(children, 'amount')
                if amt is not None:
                    w['fewer'] = self.interp(amt)
            d['with'] = w
        return d

    def i_gain_control_action(self, children):
        d = self._card_action('gain_control', children)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'which' in toks and 'chosen' in toks:
            d['for_which_chosen'] = True
        return d

    def i_control_player_action(self, children):
        d = {'verb': 'control_player'}
        pl = self._find_one(children, 'player')
        if pl is not None:
            d['player'] = self.interp(pl)
        else:
            ct = self._find_one(children, 'card_target')
            if ct is not None:
                d['player'] = self.interp(ct)
        d['during_next_turn'] = True
        return d

    def i_extra_turns_action(self, children):
        d = {'verb': 'extra_turns'}
        who = self._find_one(children, 'who')
        if who is not None:
            actor = self.interp(who)
            if actor:
                d['actor'] = actor
        am = self._first_number(children)
        if am:
            d['amount'] = am
        else:
            toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
            if 'a' in toks or 'an' in toks:
                d['amount'] = 1
        return d

    def i_block_do_so_action(self, children):
        d = {'verb': 'block_do_so'}
        cts = self._find(children, 'card_target')
        if cts:
            d['subject'] = self.interp(cts[0])
            if len(cts) > 1:
                d['block'] = self.interp(cts[1])
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'this' in toks and 'turn' in toks:
            d['this_turn'] = True
        return d

    def i_same_action(self, children):
        d = {'verb': 'same'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        return d

    def i_begin_game_action(self, children):
        d = {'verb': 'begin_game'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        return d

    def i_after_phase_action(self, children):
        return {'verb': 'additional_phase'}

    def i_phase_action(self, children):
        d = {'verb': 'phase'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        d['direction'] = 'in' if 'in' in toks else 'out'
        return d

    def i_skip_action(self, children):
        d = {'verb': 'skip'}
        wh = self._find_one(children, 'who')
        if wh is not None:
            who_value = self.interp(wh)
            if who_value:
                d['who'] = who_value
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        for phase in ('combat', 'main', 'beginning', 'ending'):
            if phase in toks:
                d['phase'] = phase
                break
        if 'next' in toks:
            d['next'] = True
        if 'this' in toks and 'turn' in toks:
            d['this_turn'] = True
        return d

    def i_can_target_action(self, children):
        d = {'verb': 'can_be_target'}
        cts = self._find(children, 'card_target')
        if cts:
            d['targets'] = [self.interp(c) for c in cts]
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'spells' in toks and 'abilities' in toks:
            d['by'] = ['spells', 'abilities']
        elif 'spells' in toks:
            d['by'] = ['spells']
        elif 'abilities' in toks:
            d['by'] = ['abilities']
        if 'you' in toks and 'control' in toks:
            d['controller'] = 'you'
        kws = [str(ch) for ch in children
               if isinstance(ch, Token) and ch.type == 'KEYWORD']
        if 'as' in toks and 'though' in toks and kws:
            d['as_though_without'] = kws[-1].lower()
        return d

    def i_enchant_action(self, children):
        d = {'verb': 'enchant'}
        et = self._find_one(children, 'enchant_target')
        if et is not None:
            targets = [c.value for c in et.children
                       if isinstance(c, Token) and c.type == 'GENERIC_TYPE']
            # "Enchant player" / "Enchant artifact or creature": bare literals
            # carry no GENERIC_TYPE type, so keep the surface words as well.
            if not targets:
                targets = [str(c) for c in et.children if isinstance(c, Token)]
            d['targets'] = targets
        return d

    def i_change_target_action(self, children):
        d = {'verb': 'change_target'}
        at = self._find_one(children, 'any_text')
        if at is not None:
            d['of'] = self.interp(at)
        return d

    def i_counter_spell_action(self, children):
        d = self._card_action('counter', children, key='spell')
        at = self._find_one(children, 'any_text')
        if at is not None:
            d['unless'] = self.interp(at)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'all' in toks and 'spells' in toks and 'abilities' in toks:
            d['spells'] = True
            d['abilities'] = True
            ctrl = self._find_one(children, 'controller')
            if ctrl is not None:
                d['controller'] = self._text(ctrl.children).strip()
        elif 'all' in toks and 'spells' in toks:
            d['spells'] = True
        return d

    def i_reveal_action(self, children):
        d = self._card_action('reveal', children)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        cts = self._find(children, 'card_target')
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        elif 'that' in toks and 'many' in toks:
            d['amount'] = 'that many'
        elif (isinstance(d.get('card'), dict)
              and d['card'].get('quantifier') == 'that many'):
            d['amount'] = 'that many'
        elif d.get('top') and 'amount' not in d:
            # "Reveal the top card of your library" is one card.
            d['amount'] = 1
        if len(cts) > 1:
            # "reveal a blue or artifact card": each disjunct is a target; keep
            # all of them instead of silently keeping only the first.
            d['cards'] = [self.interp(c) for c in cts]
            if 'or' in toks or 'and/or' in toks:
                d['any_of'] = True
        if 'until' in toks:
            if len(cts) > 1:
                d['until'] = self.interp(cts[-1])
        if {'from', 'among', 'them'} <= set(toks):
            # The source is the set revealed/exiled earlier, not a zone.  Keep
            # the same {prep, zone} shape as i_in_zone so consumers see one form.
            d['zone'] = {'prep': 'from', 'zone': 'them'}
        return d

    def i_investigate_action(self, children):
        d = {'verb': 'investigate'}
        who = self._find_one(children, 'who')
        if who is not None:
            who_value = self.interp(who)
            if who_value:
                d['who'] = who_value
        toks = [str(c).lower() for c in children if isinstance(c, Token)]
        if 'twice' in toks:
            d['times'] = 2
        else:
            amt = self._find_one(children, 'amount')
            if amt is not None:
                d['times'] = self.interp(amt)
        if 'lost' in toks:
            d['for_each'] = 'opponent who lost life this turn'
        return d

    KW_ACTION_VERBS = ('blight', 'waterbend', 'discover', 'amass', 'connive',
                       'recruit', 'forage', 'airbend', 'devour')

    def i_endure_action(self, children):
        d = {'verb': 'endure'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['who'] = self.interp(ct)
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        return d

    def i_craft_sentence(self, children):
        d = {'type': 'craft'}
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'craft_arg':
                d['with'] = self.interp(ch)
        mana = ''.join(str(c) for c in children
                       if isinstance(c, Token) and c.type == 'MANA')
        if mana:
            d['cost'] = mana
        return d

    def i_level_action(self, children):
        """Level-up frame marker: "{1}{U}: Level 2"."""
        for ch in children:
            if isinstance(ch, Tree):
                n = self._first_number(ch.children)
                if n is not None:
                    return {'verb': 'level', 'level': n}
        return {'verb': 'level', 'level': self._first_number(children)}

    def i_keyword_action(self, children):
        """Keyword actions with an optional parameter: blight N, waterbend {N},
        discover N, amass <type> N, connives, recruit, forage, airbend <target>,
        devour land N."""
        ttypes = {c.type for c in children if isinstance(c, Token)}
        # Each verb has its own terminal (V_CONNIVE, V_BLIGHT, …); use the type,
        # not the token text, so inflected forms ("connives") still name the verb.
        verb = next((v for v in self.KW_ACTION_VERBS
                     if 'V_' + v.upper() in ttypes), None)
        if verb is None:
            toks = [str(c).lower() for c in children if isinstance(c, Token)]
            verb = next((v for v in self.KW_ACTION_VERBS
                         if v in toks or v + 's' in toks or v + 'es' in toks),
                        'keyword_action')
        d = {'verb': verb}
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        mana = ''.join(str(c) for c in children
                       if isinstance(c, Token) and c.type == 'MANA')
        if mana:
            d['mana'] = mana
        wh = self._find_one(children, 'who')
        if wh is not None:
            wv = self.interp(wh)
            if wv:
                d['who'] = wv
        ck = self._find_one(children, 'card_kind')
        if ck is not None:
            d['type'] = self._text(ck.children).strip()
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            key = 'who' if verb == 'connive' else 'target'
            d[key] = self.interp(ct)
        return d

    def i_earthbend_action(self, children):
        d = {'verb': 'earthbend'}
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        return d

    def i_flip_action(self, children):
        return {'verb': 'flip_coin'}

    def i_life_total_action(self, children):
        amt = self._find_one(children, 'amount')
        d = {'verb': 'life_total', 'amount': self.interp(amt) if amt is not None else None}
        words = self._token_words(children)
        if 'starting' in words:
            # "your life total becomes half your starting life total, rounded up"
            d['amount'] = 'half your starting life total'
            if 'up' in words:
                d['rounded'] = 'up'
            elif 'down' in words:
                d['rounded'] = 'down'
        pl = self._find_one(children, 'player')
        if pl is not None:
            d['who'] = self.interp(pl)
        return d

    def i_damage_reduce_action(self, children):
        return {'verb': 'damage_reduce'}

    def i_assign_combat_action(self, children):
        d = self._card_action('assign_combat', children)
        stats = [self.interp(b) for b in self._find(children, 'stat_basis')]
        stats = [st for st in stats if st]
        if stats:
            d['basis'] = stats[0]
            if len(stats) > 1:
                d['instead_of'] = stats[1]
        return d

    def i_stat_basis(self, children):
        return str(children[0]).lower() if children else None

    def i_gift_action(self, children):
        return self._card_action('gift', children)

    def i_explore_action(self, children):
        d = {'verb': 'explore'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['who'] = self.interp(ct)
        toks = [str(c).lower() for c in children if isinstance(c, Token)]
        if 'again' in toks:
            d['again'] = True
        elif 'times' in toks:
            amt = self._find_one(children, 'amount')
            d['times'] = self.interp(amt) if amt is not None else 'X'
        return d

    def i_manifest_action(self, children):
        d = {'verb': 'manifest_dread'}
        own = self._find_one(children, 'owner_subject')
        if own is not None:
            d['who'] = self._text(own.children).strip().replace(" 's", "'s")
        return d

    def i_empower_action(self, children):
        d = self._card_action('empower', children, key='target')
        num = self._first_number(children)
        if num is not None:
            d['amount'] = num
        return d

    def i_collect_evidence_action(self, children):
        d = {'verb': 'collect_evidence'}
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        xd = self._find_one(children, 'xdef')
        if xd is not None:
            d['amount'] = self.interp(xd)
        return d

    def i_cloak_action(self, children):
        return self._card_action('cloak', children)

    def i_exchange_control_action(self, children):
        d = {'verb': 'exchange_control'}
        cts = self._find(children, 'card_target')
        if cts:
            d['object'] = self.interp(cts[0])
        if len(cts) > 1:
            d['with'] = self.interp(cts[1])
        elif cts:
            d['with'] = self.interp(cts[0])
        return d

    def i_must_block_action(self, children):
        d = self._card_action('must_block', children)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'this' in toks and 'turn' in toks:
            d['this_turn'] = True
        if 'if' in toks and 'able' in toks:
            d['if_able'] = True
        return d

    def i_attach_action(self, children):
        d = {'verb': 'attach'}
        cts = self._find(children, 'card_target')
        token = any(isinstance(c, Token) and str(c).lower() == 'token' for c in children)
        if len(cts) >= 2:
            d['object'] = self.interp(cts[0])
            d['to'] = self.interp(cts[1])
            words = self._token_words(children)
            if 'you' in words and 'control' in words and isinstance(d['to'], dict):
                d['to'] = dict(d['to'])
                d['to'].setdefault('controller', 'you control')
        elif cts:
            d['object'] = self.interp(cts[0])
            if token:
                d['to'] = {'card_type': {'kind': 'type', 'value': 'token'}}
            elif 'amassed' in self._token_words(children):
                d['to'] = {'card_type': {'kind': 'type', 'value': 'Army'}}
        return d

    def i_fight_action(self, children):
        d = self._card_action('fight', children, key='target')
        cts = self._find(children, 'card_target')
        if len(cts) > 1:
            # "X fights Y": the second card_target is the other combatant.
            d['fights'] = self.interp(cts[1])
        return d

    def i_cant_action(self, children):
        d = {'verb': "can't"}
        cts = self._find(children, 'card_target')
        if cts:
            card = self.interp(cts[0])
            if card:
                d['card'] = card
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'countered' in toks:
            d['predicate'] = 'be countered'
        elif 'blocked' in toks:
            d['predicate'] = 'be blocked'
        elif 'attack' in toks and 'block' in toks:
            d['predicate'] = 'attack or block'
        elif 'attack' in toks:
            d['predicate'] = 'attack'
        elif 'block' in toks:
            d['predicate'] = 'block'
        elif 'phase' in toks:
            d['predicate'] = 'phase in' if 'in' in toks else 'phase out'
        elif 'gain' in toks and 'life' in toks:
            d['predicate'] = 'gain life'
        elif 'activate' in toks and 'cast' in toks:
            d['predicate'] = 'cast spells or activate abilities'
        elif 'play' in toks:
            d['predicate'] = 'play cards'
            if 'hand' in toks:
                d['from'] = 'their hand' if 'their' in toks else 'your hand'
        elif 'cast' in toks:
            d['predicate'] = 'cast spells'
        elif 'activate' in toks or 'activated' in toks:
            d['predicate'] = 'activate abilities'
        elif 'prevented' in toks:
            d['predicate'] = 'be prevented'
        elif 'lose' in toks and 'mana' in toks:
            d['predicate'] = 'lose mana'
        # "can't block this turn" / "can't cast spells during your turn":
        # the grammar carries the restriction window, the handler must keep it.
        didx = next((i for i, ch in enumerate(children)
                     if isinstance(ch, Token) and str(ch).lower() == 'during'),
                    None)
        after = [str(ch).lower() for ch in children[didx:]
                 if isinstance(ch, Token)] if didx is not None else []
        if 'turn' in after:
            d['duration'] = 'during ' + ' '.join(after[1:])
        elif 'this' in toks and 'turn' in toks:
            d['duration'] = 'this turn'
        if 'except' in toks and len(cts) > 1:
            d['except_by'] = self.interp(cts[-1])
        elif 'by' in toks and len(cts) > 1:
            d['blocked_by'] = self.interp(cts[-1])
        at = self._find_one(children, 'any_text')
        if at is not None:
            if 'unless' in toks:
                d['unless'] = self.interp(at)
            elif 'as' in toks:
                d['condition'] = self.interp(at)
        return d

    def i_attacks_each_combat_action(self, children):
        return self._card_action('attacks_each_combat', children)

    def i_activate_action(self, children):
        return self._card_action('activate', children, key='target')

    def i_can_block_action(self, children):
        d = {'verb': 'can_block'}
        cts = self._find(children, 'card_target')
        if cts:
            d['blocker'] = self.interp(cts[0])
        if len(cts) > 1:
            d['attacker'] = self.interp(cts[-1])
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['max_blockers'] = self.interp(amt)
        return d

    def i_no_untap_action(self, children):
        return self._card_action('no_untap', children)

    def i_regenerate_action(self, children):
        return self._card_action('regenerate', children)

    def i_suspect_action(self, children):
        d = self._card_action('suspect', children)
        if any(isinstance(c, Token) and str(c).lower() == 'otherwise'
               for c in children):
            d['otherwise'] = True
        return d

    def i_reveal_top_action(self, children):
        return {'verb': 'reveal_top'}

    def i_put_library_action(self, children):
        d = {'verb': 'put_library'}
        for name, key in (('owner_subject', 'owner'),
                          ('card_target', 'card'),
                          ('put_library_dest', 'destination')):
            node = self._find_one(children, name)
            if node is not None:
                if name == 'card_target':
                    d[key] = self.interp(node)
                else:
                    d[key] = self._text(node.children)
        if 'card' not in d:
            txt = self._text(children)
            if 'puts it' in txt.lower() or 'put it' in txt.lower():
                d['card'] = {'card_type': {'ref': 'anaphora', 'raw': 'it'}}
            else:
                d['text'] = txt
        return d

    def i_lose_kw_action(self, children):
        d = {'verb': 'lose_keywords'}
        ct = self._find_one(children, 'card_target')
        kind = self._find_one(children, 'card_kind')
        if ct is not None:
            d['target'] = self.interp(ct)
        elif kind is not None:
            target = self.interp(kind)
            qs = self._find_all(children, 'quantifier')
            if isinstance(target, dict) and qs:
                # "target creature loses all abilities": the quantifier sits
                # in lead, apart from the card_kind.
                target = dict(target)
                target['quantifier'] = self.interp(qs[0])
                if 'other' in self._token_words(qs[0].children):
                    target['otherness'] = 'other'
            d['target'] = target
        kws = self._find_one(children, 'kw_list')
        if kws is not None:
            d['keywords'] = self.interp(kws)
        else:
            toks = [str(c).lower() for c in children if isinstance(c, Token)]
            if 'types' in toks:
                # "loses all creature types": the types are dropped, but the
                # abilities are untouched.
                kind = 'creature' if 'creature' in toks else (
                    'land' if 'land' in toks else (
                        'permanent' if 'permanent' in toks else None))
                d['all_types'] = kind or True
            else:
                d['all_abilities'] = True
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        words = self._token_words(children)
        if 'as' in words and 'long' in words:
            at = self._find_one(children, 'any_text')
            if at is not None:
                d['condition'] = self.interp(at)
        return d

    def i_have_action(self, children):
        d = {'verb': 'have'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        life = self._find_one(children, 'life_amount')
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if life is not None:
            d['effect'] = {'verb': 'lose_life', 'amount': self.interp(life)}
        elif 'mill' in toks:
            d['effect'] = {'verb': 'mill'}
        elif 'base' in toks and 'equal' in toks:
            # "have the base power and toughness of each other creature …
            # become equal to ~'s power"
            cts = self._find(children, 'card_target')
            xd = self._find_one(children, 'xdef')
            eff = {'verb': 'set_base_pt'}
            if cts:
                eff['of'] = self.interp(cts[0])
            if 'toughness' not in toks:
                eff['stat'] = 'power'
            elif 'power' not in toks:
                eff['stat'] = 'toughness'
            if xd is not None:
                eff['equal_to'] = self.interp(xd)
            d['effect'] = eff
        elif self._find_one(children, 'become_action') is not None:
            d['effect'] = self.interp(self._find_one(children, 'become_action'))
        elif 'copy' in toks:
            # "have X enter as a copy of Y, except …": keep the copy source and
            # the exception, not just a bare copy marker.
            cts = self._find(children, 'card_target')
            eff = {'verb': 'copy'}
            if len(cts) > 1:
                eff['of'] = self.interp(cts[1])
            exc = self._find_one(children, 'token_except')
            if exc is not None:
                eff['except'] = self._text(exc.children).strip().lstrip(',').strip()
            d['effect'] = eff
        else:
            da = self._find_one(children, 'draw_action')
            if da is not None:
                d['effect'] = self.interp(da)
            else:
                d['text'] = self._text(children)
        return d

    def i_enters_action(self, children):
        d = self._card_action('enters', children)
        ca = self._find_one(children, 'counter_amount')
        ck = self._find_one(children, 'counter_kind')
        pm = [ch for ch in children if isinstance(ch, Token) and ch.type == 'POWER_MOD']
        if ca is not None or ck is not None or pm:
            w = {}
            if ca is not None:
                w['count'] = self.interp(ca)
            if ck is not None:
                w['counter'] = self._counter_text(ck) if isinstance(ck, Tree) else str(ck)
            if pm:
                w['counter'] = pm[0].value + ' counter'
            if 'additional' in [str(c).lower() for c in children
                                if isinstance(c, Token)]:
                w['additional'] = True
            d['with'] = w
        cas = self._find(children, 'counter_amount')
        cks = self._find(children, 'counter_kind')
        if len(cas) > 1 or len(cks) > 1:
            extras = []
            for i in range(1, max(len(cas), len(cks))):
                e = {}
                if i < len(cas):
                    e['count'] = self.interp(cas[i])
                if i < len(cks):
                    e['counter'] = self._counter_text(cks[i])
                extras.append(e)
            if extras and isinstance(d.get('with'), dict):
                d['with']['and'] = extras
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'tapped' in toks:
            d['tapped'] = True
        if 'prepared' in toks:
            d.setdefault('states', []).append('prepared')
        if 'for' in toks and 'each' in toks:
            at = self._find_one(children, 'any_text')
            if at is not None:
                val = self.interp(at)
                if isinstance(d.get('with'), dict):
                    d['with'].setdefault('for_each', val)
                else:
                    d.setdefault('for_each', val)
        for i, ch in enumerate(children):
            if (isinstance(ch, Token)
                    and str(ch).lower() in ('if', 'unless')):
                key = str(ch).lower()
                for nxt in children[i + 1:]:
                    if isinstance(nxt, Tree) and nxt.data == 'any_text':
                        d.setdefault(key, self.interp(nxt))
                        break
        return d

    def i_can_attack_as_though_action(self, children):
        d = {'verb': 'can_attack_as_though'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        kws = self._find_one(children, 'kw_list')
        if kws is not None:
            d['without_keywords'] = self.interp(kws)
        else:
            kws = [str(c) for c in children
                   if isinstance(c, Token) and c.type == 'KEYWORD']
            if kws:
                d['without_keywords'] = kws
        toks = [str(c).lower() for c in children if isinstance(c, Token)]
        if 'this' in toks and 'turn' in toks:
            d['duration'] = 'this turn'
        return d

    def i_gain_kw_action(self, children):
        d = {'verb': 'gain_kw'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        kw = self._find_one(children, 'kw_list')
        if kw is not None:
            d['keywords'] = self.interp(kw)
        toks = [str(ch).lower() for ch in children
                if isinstance(ch, Token) and ch.type != 'KEYWORD']
        if 'loses' in toks and 'abilities' in toks:
            d['loses_all_other_abilities'] = True
        if 'choice' in toks:
            # "gains your choice of deathtouch or lifelink": one keyword is
            # chosen, not all of them.
            d['your_choice'] = True
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        words = self._token_words(children)
        if 'as' in words and 'long' in words:
            at = self._find_one(children, 'any_text')
            if at is not None:
                d['condition'] = self.interp(at)
        return d

    def i_base_pt_action(self, children):
        d = {'verb': 'set_base_pt'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        pt = [c for c in children if isinstance(c, Token) and c.type == 'POWER_T']
        if pt:
            d['base_pt'] = pt[0].value
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        return d

    def i_become_action(self, children):
        d = {'verb': 'become'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        toks = [c for c in children if isinstance(c, Token) and c.type == 'CARDNAME']
        if toks:
            d['types'] = [t.value for t in toks]
        else:
            tp = self._find_one(children, 'types')
            if tp is not None:
                d['type'] = self.interp(tp)
        # "becomes an artifact creature": generic type words are direct tokens,
        # not the CARDNAME/`types` forms above.
        gens = [c.value for c in children
                if isinstance(c, Token) and c.type == 'GENERIC_TYPE']
        if gens:
            d.setdefault('types', []).extend(gens)
        toks_low = [str(c).lower() for c in children if isinstance(c, Token)]
        if 'legendary' in toks_low:
            d.setdefault('types', []).insert(0, 'legendary')
        if 'no' in toks_low and 'longer' in toks_low and 'suspected' in toks_low:
            d['state'] = 'not_suspected'
        if 'prepared' in toks_low:
            d['state'] = 'prepared'
        if 'saddled' in toks_low:
            d['state'] = 'saddled'
            if 'until' in toks_low:
                d['until'] = 'end of turn'
        if any(isinstance(c, Token) and c.value == 'addition' for c in children):
            d['in_addition'] = True
        cts = self._find(children, 'card_target')
        if len(cts) > 1 and 'copy' in [str(c).lower() for c in children
                                       if isinstance(c, Token)]:
            # "becomes a copy of <target>": the second card_target is the source.
            d['copy_of'] = self.interp(cts[1])
        pt = [c for c in children if isinstance(c, Token) and c.type in ('POWER_T', 'POWER_MOD')]
        if not pt:
            pcm = self._find_one(children, 'pt_color_mod')
            if pcm is not None:
                pt = [c for c in pcm.children if isinstance(c, Token) and c.type in ('POWER_T', 'POWER_MOD')]
        if pt:
            d['pt'] = pt[0].value
        tail = self._find_one(children, 'become_tail')
        if tail is not None:
            tail_words = self._token_words(tail.children)
            if 'addition' in tail_words:
                # "… creature in addition to its other types"
                d['in_addition'] = True
            if ('all' in tail_words and 'creature' in tail_words
                    and 'types' in tail_words):
                d['all_creature_types'] = True
            if 'named' in tail_words:
                # "… named Legitimate Businessperson": keep the resulting name.
                idx = tail_words.index('named')
                names = [str(c.value) for c in tail.children[idx + 1:]
                         if isinstance(c, Token)]
                if names:
                    d['named'] = ' '.join(names).replace(' ,', ',')
            for sub in tail.children:
                if isinstance(sub, Token) and sub.type == 'QUOTE':
                    d['quote'] = sub.value
            if ('loses' in tail_words and 'types' in tail_words
                    and 'abilities' in tail_words):
                d['loses_all_other_card_types_and_abilities'] = True
            kws = self._find_one(tail.children, 'kw_list')
            if kws is not None:
                # "becomes … with vigilance": keywords live in the tail.
                d.setdefault('keywords', []).extend(self.interp(kws))
            if 'base' in tail_words and 'toughness' in tail_words:
                bpt = [c for c in tail.children
                       if isinstance(c, Token) and c.type == 'POWER_T']
                if bpt:
                    d['base_pt'] = bpt[0].value
        pcm = self._find_one(children, 'pt_color_mod')
        if pcm is not None:
            def _colors(node):
                out = []
                for c in node.children:
                    if isinstance(c, Token):
                        if c.type == 'COLOR':
                            out.append(c.value)
                    else:
                        out.extend(_colors(c))
                return out
            cols = _colors(pcm)
            if cols:
                d['colors'] = cols
        wm = self._find_one(children, 'with_modifier') or self._find_one(children, 'any_text')
        if wm is not None and any(isinstance(c, Token) and c.value == 'with' for c in children):
            d['modifier'] = self.interp(wm)
        exc = self._find_one(children, 'token_except')
        if exc is not None:
            d['except'] = self._text(exc.children).strip()
        return d

    def i_stat_action(self, children):
        d = {'verb': 'stat_change'}
        cts = self._find(children, 'card_target')
        if cts:
            d['target'] = self.interp(cts[0])   # the subject
            for_idx = next((i for i, ch in enumerate(children)
                            if isinstance(ch, Token) and str(ch).lower() == 'for'), None)
            subject_vals = [self.interp(c) for c in cts
                            if for_idx is None
                            or children.index(c) < for_idx]
            subject_vals = [v for v in subject_vals if v]
            if len(subject_vals) > 1:
                # "Skeletons you control and other Zombies you control get …"
                d['cards'] = subject_vals
        # "gets +1/+0 and gains menace": keep the keyword half when the same
        # action (rather than a separate gain_kw action) carries it.
        kw = self._find_one(children, 'kw_list')
        if kw is not None:
            d['keywords'] = self.interp(kw)
        # "for each X" modifier: a card_target/any_text appearing after 'for'
        for_idx = next((i for i, ch in enumerate(children)
                        if isinstance(ch, Token) and str(ch).lower() == 'for'), None)
        if for_idx is not None:
            for ch in children[for_idx:]:
                if isinstance(ch, Tree) and ch.data in ('card_target', 'any_text'):
                    d['for_each'] = self.interp(ch)
                    break
        # "as long as X" condition
        as_idx = next((i for i, ch in enumerate(children)
                       if isinstance(ch, Token) and str(ch).lower() == 'as'), None)
        if as_idx is not None:
            for ch in children[as_idx:]:
                if isinstance(ch, Tree) and ch.data == 'any_text':
                    d['condition'] = self.interp(ch)
                    break
        sc = self._find_one(children, 'stat_change')
        if sc is not None:
            r = self.interp(sc)
            if isinstance(r, dict):
                d.update(r)          # compound stat: change + gained/lost keywords
            else:
                d['change'] = r
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        return d

    def i_stat_change(self, children):
        # stat_change: POWER_MOD ("and" (loses|gains|has) kw_list)?
        # Decompose the compound form into stat value + gained/lost keywords.
        kw = None
        kw_verb = None
        pt = None
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'POWER_MOD':
                pt = ch.value
            elif isinstance(ch, Token) and str(ch).lower() in ('loses', 'lose', 'gains', 'gain', 'has', 'have'):
                kw_verb = str(ch).lower()
            elif isinstance(ch, Tree) and ch.data == 'kw_list':
                kw = self.interp(ch)
        if kw is None:
            return self._text(children)   # plain stat -> keep as string (backward compat)
        d = {}
        if pt:
            d['change'] = pt
        d[kw_verb if kw_verb else 'change_kw'] = kw
        return d

    def i_gain_life_action(self, children):
        d = {'verb': 'gain_life'}
        who = self._find_one(children, 'who') or self._find_one(children, 'player')
        if who is not None:
            wv = self.interp(who)
            if wv:
                d['who'] = wv
        la = self._find_one(children, 'life_amount')
        if la is not None:
            d['amount'] = self.interp(la)
        else:
            # "gain life equal to <expr>": the grammar keeps the expression as a
            # sibling any_text/xdef, not as a life_amount.
            expr = self._find_one(children, 'xdef') or self._find_one(children, 'any_text')
            if expr is not None:
                amount = self.interp(expr)
                if isinstance(amount, str) and amount.lower() in ('its power', 'its toughness'):
                    # "gain life equal to its power": a stat reference, not free text.
                    amount = {'possessor': 'its', 'stat': amount.lower().split()[1]}
                d['amount'] = amount
        fe = self._for_each(children)
        if fe is not None:
            d['for_each'] = fe
        return d

    def i_lose_life_action(self, children):
        d = {'verb': 'lose_life'}
        who = self._find_one(children, 'who') or self._find_one(children, 'player')
        if who is not None:
            # `who` can match an empty card_target for an elided subject
            # ("... and loses half their life"); omit it instead of {}.
            who_value = self.interp(who)
            if who_value:
                d['who'] = who_value
        la = self._find_one(children, 'life_amount')
        if la is not None:
            d['amount'] = self.interp(la)
        else:
            # "loses life equal to the number of …": the expression is an
            # xdef/any_text sibling.
            expr = self._find_one(children, 'xdef') or self._find_one(children, 'any_text')
            if expr is not None:
                d['amount'] = self.interp(expr)
        toks = self._token_words(children)
        if 'unless' in toks:
            at = self._find_one(children, 'any_text')
            if at is not None:
                # "… loses 5 life unless they discard a card"
                d['unless'] = self.interp(at)
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['for_each'] = self.interp(ct)
        return d

    def i_life_amount(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_dmg_amount(self, children):
        # a bare number/word keeps its structured (int) value; relative forms -> text
        if len(children) == 1 and isinstance(children[0], Tree) and children[0].data == 'amount':
            return self.interp(children[0])
        return self._text(children)

    def i_transform_action(self, children):
        return self._card_action('transform', children)

    def i_end_turn_action(self, children):
        return {'verb': 'end_turn'}

    def i_distribute_action(self, children):
        d = {'verb': 'distribute'}
        at = self._find_one(children, 'any_text')
        if at is not None:
            txt = self.interp(at)
            if isinstance(txt, str):
                m = re.match(r'^(.*?)\s+counters? among (.+)$', txt,
                             re.I)
                if m:
                    left = m.group(1).strip().split()
                    if left:
                        d['count'] = left[0]
                        kind = ' '.join(left[1:]).strip()
                        if kind:
                            d['counter'] = kind
                    tgt = self._simple_target(m.group(2))
                    if tgt:
                        d['among'] = tgt
                        return d
            d['text'] = txt
        return d

    def i_copy_action(self, children):
        d = {'verb': 'copy'}
        wh = self._find_one(children, 'who')
        if wh is not None:
            who_value = self.interp(wh)
            if who_value:
                d['who'] = who_value
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        at = self._find_one(children, 'any_text')
        if at is not None:
            d['for_each'] = self.interp(at)
        elif any(str(c) == 'it' for c in children if not isinstance(c, Tree)):
            d['target'] = {'kind': 'this_card'}
        words = self._token_words(children)
        if 'except' in words and 'legendary' in words:
            d['except'] = 'not legendary'
        return d

    def i_trigger_extra_action(self, children):
        d = {'verb': 'trigger_extra'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        else:
            toks = [str(c) for c in children if isinstance(c, Token)]
            if 'triggers' in toks:
                d['target'] = ' '.join(toks[:toks.index('triggers')]).strip()
        return d

    def i_lose_game_action(self, children):
        verb = 'lose_game'
        for ch in children:
            if isinstance(ch, Token) and getattr(ch, 'type', None) == 'V_WIN':
                verb = 'win_game'
                break
        d = {'verb': verb}
        for ch in children:
            if isinstance(ch, Tree) and ch.data in ('who', 'player', 'card_target'):
                wv = self.interp(ch)
                if wv:
                    d['who'] = wv
                break
        return d

    def i_count_action(self, children):
        d = {'verb': 'count'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        return d

    def i_have_deal_action(self, children):
        d = {'verb': 'deal_damage'}
        cts = self._find(children, 'card_target')
        if cts:
            d['by'] = self.interp(cts[0])
        da = self._find_one(children, 'dmg_amount')
        if da is not None:
            d['amount'] = self.interp(da)
        dw = self._find_one(children, 'damage_who')
        if dw is not None:
            d['to'] = self.interp(dw)
        return d

    def i_choose_new_targets_action(self, children):
        d = {'verb': 'choose_new_targets'}
        may = any(isinstance(c, Token) and str(c).lower() == 'may' for c in children)
        if may:
            d['modal'] = 'may'
        at = self._find_one(children, 'any_text')
        if at is not None:
            val = self.interp(at)
            if isinstance(val, str) and val.strip().lower() == 'the copy':
                d['for'] = {'kind': 'copy'}
            else:
                d['for'] = val
        return d

    def i_gain_poison_action(self, children):
        d = {'verb': 'gain_poison'}
        who = self._find_one(children, 'who')
        if who is not None:
            wv = self.interp(who)
            if wv:
                d['who'] = wv
        am = self._find_one(children, 'amount')
        if am is not None:
            d['amount'] = self.interp(am)
        return d

    def i_deal_damage_action(self, children):
        d = {'verb': 'deal_damage'}
        da = self._find_one(children, 'dmg_amount')
        base = self.interp(da) if da is not None else None
        plus_idx = next((i for i, c in enumerate(children)
                         if isinstance(c, Token) and str(c).lower() == 'plus'), None)
        if plus_idx is not None:
            extra = None
            for c in children[plus_idx + 1:]:
                if isinstance(c, Tree) and c.data == 'amount':
                    extra = self.interp(c); break
            d['amount'] = (f"{base} plus {extra}" if base is not None
                           else (f"plus {extra}" if extra is not None else None))
        elif da is not None:
            d['amount'] = base
        else:
            amt = self._find_one(children, 'amount')
            if amt is not None:
                d['amount'] = self.interp(amt)
            elif 'equal' in self._token_words(children):
                # "deals damage equal to its power": keep the referent.
                expr = (self._find_one(children, 'any_text')
                        or self._find_one(children, 'xdef'))
                if expr is not None:
                    d['amount'] = self.interp(expr)
        # source = a card_target that is a DIRECT child (the dealer)
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'card_target':
                d['source'] = self.interp(ch)
                break
        if 'source' not in d:
            toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
            if any(t in ('it', 'they') for t in toks):
                d['source'] = {'ref': 'anaphora'}
        # target(s) = damage_who
        dw = self._find(children, 'damage_who')
        if dw:
            d['to'] = self.interp(dw[0]) if len(dw) == 1 else [self.interp(x) for x in dw]
        xd = self._find_one(children, 'xdef')
        if xd is not None:
            d['amount'] = {'xdef': self.interp(xd)}
        fe = self._for_each(children)
        if fe is not None:
            d['for_each'] = fe
        return d

    def i_damage_amount(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_damage_who(self, children):
        cards = [self.interp(c) for c in children
                 if isinstance(c, Tree) and c.data == 'card_target']
        if not cards:
            return self._text(children)
        val = cards[0] if len(cards) == 1 else {'or': cards}
        if any(isinstance(c, Token) and str(c).lower() == 'attacking'
               for c in children):
            val = dict(val) if isinstance(val, dict) else {'or': val}
            val['attacking'] = True
        return val

    def i_damage_target(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_replace_counter_action(self, children):
        d = {'verb': 'replace_counter', 'instead': True}
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['extra'] = self.interp(amt)
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            d['counter'] = self._text(ck.children) if isinstance(ck, Tree) else str(ck)
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['on'] = self.interp(ct)
        return d

    def i_put_counter_action(self, children):
        d = {'verb': 'put_counter'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['on'] = self.interp(ct)
        ca = self._find_one(children, 'counter_amount')
        if ca is not None:
            d['count'] = self.interp(ca)
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            d['counter'] = self._text(ck.children)
        # "put a +1/+1 counter on it and a plan counter on this creature":
        # the second counter is a sibling, not part of the first one.
        cts = self._find(children, 'card_target')
        cas = self._find(children, 'counter_amount')
        cks = self._find(children, 'counter_kind')
        words = self._token_words(children)
        if 'for' in words and 'each' in words and 'and' not in words:
            # "… for each of that spell's colors": that card_target is the
            # multiplier set, not a second counter target.
            cts = cts[:1]
        extras = []
        for i in range(1, max(len(cts), len(cas), len(cks))):
            e = {}
            if i < len(cas):
                e['count'] = self.interp(cas[i])
            if i < len(cks):
                e['counter'] = self._text(cks[i].children)
            if i < len(cts):
                e['on'] = self.interp(cts[i])
            extras.append(e)
        if extras:
            d['and'] = extras
        fe = self._for_each(children)
        if fe is not None:
            d['for_each'] = fe
        names = [self._text(ch.children).strip() for ch in children
                 if isinstance(ch, Tree) and ch.data == 'counter_name']
        pmods = [ch.value for ch in children
                 if isinstance(ch, Token) and ch.type == 'POWER_MOD']
        if names or pmods:
            # "a flying, lifelink, or +1/+1 counter": a list of counter kinds.
            d['counters'] = [n for n in names if n.lower() != 'or'] + pmods
        if (not cas and ck is None and 'counters' in words
                and ('its' in words or 'their' in words or 'those' in words
                     or "creature's" in words)):
            # "put its counters on target creature": a moved counter set.
            d['counters'] = ('those' if 'those' in words else
                             'its' if 'its' in words else
                             'their' if 'their' in words else "this creature's")
        return d

    def i_remove_counter_action(self, children):
        d = {'verb': 'remove_counter'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['from'] = self.interp(ct)
        ca = self._find_one(children, 'counter_amount')
        ck = self._find_one(children, 'counter_kind')
        ctext = self._counter_text(ck) if ck is not None else None
        count = self.interp(ca) if ca is not None else None
        if count == 'those' and ctext:
            # "remove those counters": keep the anaphoric object intact.
            d['counter'] = 'those ' + ctext
        else:
            if count is not None:
                d['count'] = count
            if ctext:
                d['counter'] = ctext
        return d

    def _counter_text(self, node):
        txt = ' '.join(self._text(node.children).split())
        if txt.endswith(' s'):
            txt = txt[:-2] + 's'
        return txt

    def i_counter_amount(self, children):
        t = self._text(children).strip().lower()
        if t in self.WORD_NUM:
            return self.WORD_NUM[t]
        if t.isdigit():
            return int(t)
        return t or None

    def i_create_token_action(self, children):
        d = {'verb': 'create_token'}
        tk = self._find_one(children, 'token')
        if tk is not None:
            d['token'] = self.interp(tk)
        who = self._find_one(children, 'who')
        if who is not None:
            actor = self.interp(who)
            if actor:
                d['actor'] = actor
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['count'] = self.interp(amt)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'those' in toks and 'tokens' in toks:
            d['of_those_tokens'] = True
        if 'instead' in toks:
            d['instead'] = True
        at = self._find_one(children, 'any_text')
        if at is not None:
            d['if'] = self.interp(at)
        return d

    def i_token(self, children):
        d = {}
        types = []
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'card_target':
                    d['copy_of'] = self.interp(ch)
                elif ch.data == 'kw_list':
                    d.setdefault('kw', []).append(self.interp(ch))
                elif ch.data == 'tok_colors':
                    d['colors'] = self._text(ch.children).strip()
                elif ch.data == 'token_types':
                    v = self.interp(ch)
                    types.extend(v if isinstance(v, list) else [v])
                elif ch.data == 'token_num':
                    q = self.interp(ch)
                    if q not in (None, 'a', 'an'):
                        d['count'] = q
                elif ch.data == 'xdef':
                    d['xdef'] = self.interp(ch)
                elif ch.data == 'in_zone':
                    d['zone'] = self.interp(ch)
                elif ch.data == 'token_tail':
                    self._token_tail(ch, d)
                elif ch.data == 'token_proper':
                    # "create Darkstar, a legendary … creature token": the name
                    # is a token_proper subtree, not a bare CARDNAME.
                    d.setdefault('named', []).append(self._text(ch.children).strip())
                elif ch.data == 'token_except':
                    # "except it has haste and …" / "except it's a 5/5 …"
                    d['except'] = self._text(ch.children).strip()
            elif isinstance(ch, Token):
                if ch.type == 'POWER_T':
                    d['power_toughness'] = ch.value
                elif ch.type == 'COLOR':
                    d.setdefault('colors', ch.value)
                elif ch.type == 'QUOTE':
                    d['quote'] = ch.value
                elif ch.type == 'CARDNAME':
                    types.append(ch.value)
                elif ch.value.lower() in ('tapped', 'attacking'):
                    d[ch.value.lower()] = True
                elif ch.value.lower() == 'legendary':
                    types.append('legendary')
                elif ch.value.lower() in self.SUPERTYPES:
                    types.append(ch.value.lower())
        if types:
            d['types'] = types
        return d

    def _token_tail(self, ch, d):
        """Extract 'with <kw>' / 'named X' / 'tapped' / zone from a token_tail."""
        seen_for_each = False
        for sub in ch.children:
            if isinstance(sub, Tree):
                if sub.data in ('kw_list', 'kw_with_mod'):
                    d.setdefault('kw', []).append(self.interp(sub))
                elif sub.data == 'in_zone':
                    d['zone'] = self.interp(sub)
                elif sub.data == 'card_target':
                    # "a Role token attached to <target>" / "... for each <target>"
                    if seen_for_each:
                        d['for_each'] = self.interp(sub)
                    else:
                        d['attached_to'] = self.interp(sub)
            elif isinstance(sub, Token):
                if sub.value.lower() == 'tapped':
                    d['tapped'] = True
                elif sub.value.lower() == 'attacking':
                    d['attacking'] = True
                elif sub.value.lower() == 'each':
                    seen_for_each = True
                if sub.type == 'QUOTE':
                    # "with \"A\" and \"B\"": keep every granted quote.
                    if 'quote' in d:
                        d.setdefault('quotes', [d['quote']]).append(sub.value)
                    else:
                        d['quote'] = sub.value
                if sub.type == 'CARDNAME':
                    d.setdefault('named', []).append(sub.value)
                if sub.type == 'MANA':
                    # "… with \"Equipped creature gets +1/+0\" and equip {2}":
                    # the only direct MANA in a token_tail is the equip cost.
                    d['equip_cost'] = sub.value

    def i_token_num(self, children):
        words = [str(c).lower() for c in children if isinstance(c, Token)]
        if words == ['that', 'many']:
            return 'that many'
        return self.interp(children[0]) if children else None

    def i_token_types(self, children):
        return [ch.value if isinstance(ch, Token) else self.interp(ch)
                for ch in children]

    def i_add_mana_action(self, children):
        d = {'verb': 'add_mana'}
        who = self._find_one(children, 'who')
        if who is not None:
            who_value = self.interp(who)
            if who_value:
                d['who'] = who_value
        # "Add an amount of {G} equal to <xdef>": the symbol and the quantity
        # are separate facts, not one amount.
        sym = [str(c) for c in children
               if isinstance(c, Token) and c.type == 'MANA']
        xd = self._find_one(children, 'xdef')
        if sym and xd is not None and self._find_one(children, 'mana_amount') is None:
            d['amount'] = {'symbol': ''.join(sym), 'equal_to': self.interp(xd)}
            return d
        words = self._token_words(children)
        if (sym and 'each' in words and 'for' in words
                and self._find_one(children, 'mana_amount') is None):
            # "add {G} for each charge counter on this enchantment": the symbol
            # and the multiplier set are separate facts.
            d['symbol'] = ''.join(sym)
            ck = self._find_one(children, 'counter_kind')
            if ck is not None:
                d['per'] = self._text(ck.children).strip()
            ct = self._find_one(children, 'card_target')
            if ct is not None:
                d['on'] = self.interp(ct)
            return d
        for name in ('mana_amount', 'xdef', 'amount'):
            node = self._find_one(children, name)
            if node is not None:
                if name == 'xdef':
                    d['amount'] = ' '.join(self._text(node.children).split())
                else:
                    val = self.interp(node)
                    if isinstance(val, list):
                        val = ' '.join(str(v) for v in val)
                    d['amount'] = val
                break
        else:
            if children:
                val = self.interp(children[-1])
                d['amount'] = (' '.join(str(v) for v in val)
                               if isinstance(val, list) else val)
        return d

    def i_scry_action(self, children):
        d = {'verb': 'scry'}
        if children:
            d['amount'] = self.interp(children[-1])
        return d

    def i_surveil_action(self, children):
        d = {'verb': 'surveil'}
        if children:
            d['amount'] = self.interp(children[-1])
        return d

    def i_mill_action(self, children):
        d = {'verb': 'mill'}
        amt = self._find_one(children, 'amount')
        xd = self._find_one(children, 'xdef')
        if amt is not None:
            d['amount'] = self.interp(amt)
        elif xd is not None:
            d['amount'] = self.interp(xd)
        else:
            words = self._token_words(children)
            if 'half' in words and 'library' in words:
                owner = next((w for w in ('their', 'his', 'her', 'a', 'the')
                              if w in words), 'their')
                half = 'half %s library' % owner
                if 'rounded' in words:
                    half += ', rounded ' + ('down' if 'down' in words else 'up')
                d['amount'] = half
            elif 'that' in words and 'many' in words:
                d['amount'] = 'that many'
            elif any(w in ('a', 'an') for w in words) and 'card' in words:
                # "mill a card" is one card.
                d['amount'] = 1
        wh = self._find_one(children, 'who')
        if wh is not None:
            who = self.interp(wh)
            if who:
                d['who'] = who
        else:
            pl = self._find_one(children, 'player')
            if pl is not None:
                who = self.interp(pl)
                if who:
                    d['who'] = who
        return d

    def i_search_action(self, children):
        d = {'verb': 'search'}
        cards = []
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'card_target':
                    cards.append(self.interp(ch))
                elif ch.data == 'search_target':
                    # The target may be wrapped: one or more card_targets joined by
                    # and/or/comma.  Collect in document order; the last one is the
                    # card actually named ("a card named ~ or ~").
                    cards.extend(self.interp(c) for c in ch.children
                                 if isinstance(c, Tree) and c.data == 'card_target')
                elif ch.data == 'amount':
                    d['amount'] = self.interp(ch)
                elif ch.data in ('zone', 'in_zone'):
                    d['zone'] = self.interp(ch)
                elif ch.data == 'zones':
                    # zones wraps one or more zone nodes; keep every disjunct
                    # ("search your hand and/or library").
                    zlist = [self.interp(zc) for zc in ch.children
                             if isinstance(zc, Tree) and zc.data in ('zone', 'in_zone')]
                    zlist = [z for z in zlist if z]
                    if zlist:
                        d['zone'] = zlist[0]
                        if len(zlist) > 1:
                            d['zones'] = zlist
        if cards:
            # An empty card_target is a parser artefact, not the searched card
            # (it can appear as a list separator's optional slot).
            real = [c for c in cards if c]
            if real:
                d['card'] = real[-1]
                if len(real) > 1:
                    # "for a card named ~ and/or a card named ~": keep both.
                    d['cards'] = real
        if 'zone' not in d:
            z = self._zone_from_tokens(children)
            if z is not None:
                d['zone'] = z
        d.update(self._placement(children))
        toks = self._token_words(children)
        if 'reveal' in toks:
            # "search …, reveal it, put it into your hand" keeps the reveal
            # step as direct tokens; without the flag the chain silently
            # becomes search -> put.
            d['reveal'] = True
        if 'shuffle' in toks:
            d['then_shuffle'] = True
        # "search for a card named X": the name is a direct token after `named`.
        for i, ch in enumerate(children):
            if isinstance(ch, Token) and str(ch).lower() == 'named':
                for nxt in children[i + 1:]:
                    if isinstance(nxt, Token) and nxt.type in ('THIS_CARD', 'CARDNAME'):
                        d['named'] = nxt.value
                        break
        return d

    def i_look_action(self, children):
        d = {'verb': 'look'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'amount':
                    d['amount'] = self.interp(ch)
        z = self._zone_from_tokens(children)
        if z is not None:
            d['zone'] = z
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['of'] = self.interp(ct)
        d.update(self._placement(children))
        words = self._token_words(children)
        if 'amount' not in d:
            if 'that' in words and 'many' in words:
                d['amount'] = 'that many'
            elif 'top' in words:
                # "Look at the top card of your library" is one card.
                d['amount'] = 1
        if 'hand' in words and 'at' in words:
            # "look at an opponent's hand": the possessor follows `at`.
            pre = words[words.index('at') + 1:words.index('hand')]
            if pre:
                d['possessor'] = ' '.join(pre)
        return d

    def i_shuffle_action(self, children):
        d = {'verb': 'shuffle'}
        toks = self._token_words(children)
        zones = [t for t in toks
                 if t in ('graveyard', 'library', 'hand', 'battlefield', 'exile')]
        if zones:
            d['from'] = zones[0] if len(zones) == 2 else zones[:-1]
            d['to'] = zones[-1] if len(zones) > 1 else 'library'
        elif 'libraries' in toks:
            d['to'] = 'library'
        own = self._find_one(children, 'owner_subject')
        if own is not None:
            owner = self._text(own.children)
            if owner:
                d['owner'] = owner
        return d

    def i_no_max_hand_action(self, children):
        d = {'verb': 'no_max_hand_size'}
        dur = self._duration(children)
        if dur:
            d['duration'] = dur
        else:
            words = self._token_words(children)
            if 'rest' in words and 'game' in words:
                d['duration'] = 'for the rest of the game'
        return d

    def i_can_gain_life_action(self, children):
        return {'verb': "players_can't_gain_life"}

    def i_choose_action(self, children):
        d = {'verb': 'choose'}
        obj = self._find_one(children, 'choose_obj')
        if obj is not None:
            d['object'] = self.interp(obj)
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'for' in toks and 'each' in toks and 'player' in toks:
            d['per_player'] = True
        return d

    def i_choose_obj(self, children):
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            return self.interp(ct)
        at = self._find_one(children, 'any_text')
        if at is not None:
            for t in at.children:
                if isinstance(t, Token) and t.type == 'LISTTOK':
                    return decode_list_token(t.value)
        return self._text(children)

    def i_may_action(self, children):
        inners = []
        actor_words = []
        actor_tree = None
        seen_may = False
        for ch in children:
            if isinstance(ch, Token):
                if str(ch).lower() == 'may':
                    seen_may = True
                elif not seen_may:
                    actor_words.append(ch.value)
                continue
            if not isinstance(ch, Tree):
                continue
            if seen_may:
                inners.append(self.interp(ch))
            elif ch.data in ('controller_subject', 'owner_subject'):
                actor_tree = self._text([ch]).strip()
            elif ch.data in ('player', 'card_target'):
                actor_tree = self.interp(ch)
            else:
                actor_words.append(self._text([ch]))
        # "you may sacrifice an artifact or discard a card": both alternatives
        # are consequences of the permission, not one action.
        inner = inners[0] if len(inners) == 1 else (inners or None)
        d = {'verb': 'may', 'inner': inner}
        actor = actor_tree if actor_tree is not None else ' '.join(actor_words).strip()
        if actor and str(actor).lower() != 'you':
            # "Its controller may …" / "Each player may …": keep the actor so
            # the permission is not attributed to the spell's controller.
            d['who'] = actor
        who_verbs = {'gain_life', 'lose_life', 'draw', 'mill', 'discard',
                     'scry', 'surveil'}
        if (actor and str(actor).lower() == 'you'
                and isinstance(inner, dict)
                and inner.get('verb') in who_verbs
                and 'who' not in inner):
            # "you may gain N life": the explicit actor belongs to the inner
            # action too (the empty placeholder is not stored).
            inner['who'] = 'You'
        return d

    def i_for_each_sentence(self, children):
        d = {'verb': 'for_each'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            val = self.interp(ct)
            if val:
                d['on'] = val
        at = self._find_one(children, 'any_text')
        if at is not None:
            d['text'] = self.interp(at)
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            d['per'] = self._text(ck.children).strip()
        eff = self._find_one(children, 'effect')
        if eff is not None:
            d['effect'] = self.interp(eff)
        return d

    def i_cost_mod_action(self, children):
        d = {'verb': 'cost_mod'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        cs = self._find_one(children, 'cost_subject')
        toks = self._token_words(children)
        if cs is not None:
            # "Dragon spells you cast cost …" / "Activated abilities of
            # artifacts you control cost …": the affected set is the subject.
            inners = self._find_all(cs.children, 'card_target')
            subj_words = self._token_words(cs.children)
            cast_by = None
            if 'cast' in subj_words:
                idx = subj_words.index('cast')
                actor = subj_words[idx - 1] if idx else 'you'
                if (actor in ('opponents', 'opponent')
                        and idx > 1 and subj_words[idx - 2] == 'your'):
                    actor = 'your ' + actor
                cast_by = actor or 'you'
            freq = next((w for w in subj_words if w in ('first', 'second')), None)
            if freq:
                d['frequency'] = freq + ' each turn'
            if inners:
                targets = []
                for inner in inners:
                    v = self.interp(inner)
                    if cast_by:
                        v = dict(v); v['cast_by'] = cast_by
                    targets.append(v)
                if cast_by is None:
                    ctrl = next((t.get('controller') for t in targets
                                 if t.get('controller')), None)
                    if ctrl and 'cast' in str(ctrl).lower():
                        cast_by = str(ctrl).lower().replace('cast', '').strip() or 'you'
                        for t in targets:
                            t['cast_by'] = cast_by
                d['target'] = targets[0]
                if len(targets) > 1:
                    # "Instant and sorcery spells you cast with mana value 4
                    # or greater": a filter stated once applies to both.
                    shared = [t for t in targets if t.get('controller')]
                    if shared:
                        ctrl = shared[0]['controller']
                        for t in targets:
                            t.setdefault('controller', ctrl)
                    shared = [t for t in targets if t.get('modifier')]
                    if shared:
                        mod = shared[0]['modifier']
                        for t in targets:
                            t.setdefault('modifier', mod)
                    d['cards'] = targets
            else:
                d['target'] = self._text(cs.children).strip()
        # capture the mana/amount that is paid or reduced
        ca = self._find_one(children, 'cost_amount')
        if ca is not None:
            d['amount'] = self._text(ca.children)
        else:
            mana = [ch.value for ch in children
                    if isinstance(ch, Token) and ch.type in ('MANA', 'NUMBER')]
            if mana:
                d['amount'] = ''.join(mana)
        if any(isinstance(ch, Token) and ch.value == 'less' for ch in children):
            d['direction'] = 'less'
        elif any(isinstance(ch, Token) and ch.value == 'more' for ch in children):
            d['direction'] = 'more'
        elif any(isinstance(ch, Token) and ch.value == 'additional' for ch in children):
            d['direction'] = 'additional'
        if 'equal' in toks and 'cost' in toks:
            # "The embalm cost is equal to its mana cost": name the cost and
            # keep the defining expression.
            idx = toks.index('cost')
            if idx > 0 and toks[idx - 1] not in ('the', 'a', 'an'):
                d['cost_name'] = toks[idx - 1]
            expr = self._find_one(children, 'any_text') or self._find_one(children, 'xdef')
            if expr is not None:
                d['amount'] = self.interp(expr)
        fe = self._for_each(children)
        if fe is not None:
            d['for_each'] = fe
        return d

    def i_gain_quote_action(self, children):
        d = {'verb': 'gain_quote'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        kws = self._find_one(children, 'kw_list')
        if kws is not None:
            # "gains trample and \"…\"": the keyword and the quoted grant
            # share one action.
            d['keywords'] = self.interp(kws)
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'card_target':
                d['target'] = self.interp(ch)
            elif isinstance(ch, Token) and ch.type == 'QUOTE':
                d['quote'] = ch.value
        return d

    def i_double_action(self, children):
        triple = any(isinstance(c, Token) and c.type == 'V_TRIPLE'
                     for c in children)
        d = {'verb': 'triple' if triple else 'double',
             'multiplier': 3 if triple else 2}
        txt = ' '.join(self._text(children).split()).strip()
        low = txt.lower()
        body = txt[len('triple '):] if low.startswith('triple ') else (
            txt[len('double '):] if low.startswith('double ') else txt)
        bl = body.lower()
        duration = None
        if bl.endswith(' until end of turn'):
            body = body[:-len(' until end of turn')]
            bl = body.lower()
            duration = 'until end of turn'
        if bl.startswith('the number of '):
            rest = body[len('the number of '):]
            unit, _, on = rest.partition(' on ')
            if unit:
                d['counter'] = unit.strip()
            if on:
                tgt = self._simple_target(on)
                if tgt:
                    d['on'] = tgt
        elif bl.endswith("'s power") or bl.endswith("'s toughness"):
            stat = 'power' if bl.endswith("'s power") else 'toughness'
            tgt = self._simple_target(body[:-len("'s " + stat)])
            if tgt:
                d['target'] = tgt
            d['stat'] = stat
        elif 'power and toughness' in bl:
            tgt = self._simple_target(body.split(' power')[0])
            if tgt:
                d['target'] = tgt
            d['stat'] = 'power and toughness'
        elif bl.startswith('the number of each kind of counter'):
            d['counter'] = 'each kind of counter'
            _, _, on = body.partition(' on ')
            if on:
                tgt = self._simple_target(on)
                if tgt:
                    d['on'] = tgt
        if duration:
            d['duration'] = duration
        return d

    def i_separate_action(self, children):
        return {'verb': 'separate',
                'into': ['a face-down pile', 'a face-up pile']}

    def i_spend_mana_action(self, children):
        d = {'verb': 'spend_mana_only_to_cast'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        words = self._token_words(children)
        if 'any' in words and 'type' in words:
            d['mana'] = 'any type'
        elif 'any' in words and 'color' in words:
            d['mana'] = 'any color'
        return d

    def i_pay_action(self, children):
        d = {'verb': 'pay'}
        mana = [ch.value for ch in children
                if isinstance(ch, Token) and ch.type == 'MANA']
        if mana:
            d['amount'] = ''.join(mana)
        else:
            amt = self._find_one(children, 'amount')
            nums = [str(ch.value) for ch in children
                    if isinstance(ch, Token) and ch.type == 'NUMBER']
            unit = [str(ch.value).lower() for ch in children
                    if isinstance(ch, Token) and str(ch.value).lower() in ('life', 'mana')]
            if amt is not None:
                val = self.interp(amt)
                d['amount'] = (f"{val} {unit[0]}" if unit else val)
            elif nums:
                d['amount'] = ' '.join(nums + unit)
        return d

    def i_stat_define_action(self, children):
        toks = self._token_words(children)
        d = {'verb': 'stat_define'}
        if 'toughness' in toks:
            d['stat'] = 'power_and_toughness'
        elif 'power' in toks:
            d['stat'] = 'power'
        else:
            d['stat'] = 'power_and_toughness'
        d['relation'] = 'each_equal_to' if 'each' in toks else 'equal_to'
        for ch in children:
            if isinstance(ch, Token):
                v = str(ch.value)
                if v.endswith("'s") and v[:-2]:
                    d['subject'] = v[:-2]
                    break
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            target = self.interp(ct)
            if 'subject' not in d and isinstance(target, dict):
                kind = target.get('card_type')
                d['subject'] = (kind.get('value') if isinstance(kind, dict)
                                else target.get('value'))
            d['target'] = target
        xd = self._find_one(children, 'xdef')
        if xd is not None:
            value = self.interp(xd)
            # "… and its toughness is equal to that number plus 1" arrives in
            # the same xdef; split the two definitions instead of leaving the
            # toughness formula inside the power value.
            seq = value if isinstance(value, list) else [value]
            # The whole tail can arrive as one any_text string.
            for k, el in enumerate(seq):
                if isinstance(el, str):
                    marker = ' and its toughness is equal to '
                    pos = el.lower().find(marker)
                    if pos >= 0:
                        seq = seq[:k] + [el[:pos].strip()]
                        d['stat'] = 'power_and_toughness'
                        d['relation'] = 'equal_to'
                        d['value'] = seq
                        d['toughness_value'] = el[pos + len(marker):].strip()
                        return d
            low = [str(x).lower() for x in seq]
            split_at = None
            for i in range(len(low) - 2):
                if low[i] == 'and' and low[i + 1] in ('its', 'their') \
                        and low[i + 2] == 'toughness':
                    split_at = i
                    break
            if split_at is not None:
                tough = seq[split_at:]
                tlow = [str(x).lower() for x in tough]
                if 'to' in tlow:
                    tough = tough[tlow.index('to') + 1:]
                d['stat'] = 'power_and_toughness'
                d['relation'] = 'equal_to'
                d['value'] = seq[:split_at]
                d['toughness_value'] = tough
            else:
                d['value'] = value
        return d

    def i_emblem_action(self, children):
        d = {'verb': 'emblem'}
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'QUOTE':
                d['quote'] = ch.value
        return d

    def i_prevent_action(self, children):
        toks = self._token_words(children)
        if 'prevented' in toks and any(
                w in ("can't", 'cannot', 'cant') for w in toks):
            # "The damage can't be prevented" is a negation, not prevention.
            return {'verb': "can't", 'predicate': 'be prevented',
                    'object': 'damage'}
        d = self._card_action('prevent_damage', children)
        if 'damage' in toks:
            d.setdefault('object', 'damage')
        if 'all' in toks:
            d['all'] = True
        if 'to' in toks and 'you' in toks:
            d['to'] = 'you'
        ct = self._find_one(children, 'card_target')
        if ct is not None and 'by' in toks and 'dealt' in toks:
            # "dealt to and dealt by X" restricts both; "dealt by X" only the source.
            if 'to' in toks and 'and' in toks:
                d['to'] = self.interp(ct)
            d['by'] = self.interp(ct)
            d.pop('card', None)
        if 'combat' in toks:
            d['damage'] = 'combat'
        elif 'noncombat' in toks:
            d['damage'] = 'noncombat'
        if 'this' in toks and 'turn' in toks:
            d['duration'] = 'this turn'
        return d

    SUPERTYPES = {'creature', 'artifact', 'enchantment', 'land', 'plane',
                  'phenomenon', 'module', 'card', 'saga', 'vanguard', 'cop'}

    def i_put_zone_action(self, children):
        d = {'verb': 'put'}
        wh = self._find_one(children, 'who')
        if wh is not None and wh.data != 'card_target':
            who_value = self.interp(wh)
            if who_value:
                d['who'] = who_value
        cts = self._find(children, 'card_target')
        if cts:
            d['card'] = self.interp(cts[0])
            if len(cts) > 1:
                d['cards'] = [self.interp(c) for c in cts]
        zns = self._find(children, 'zone')
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'pile' in toks and 'card' not in d:
            # "put that pile into your hand and the other into your graveyard":
            # the objects are literal tokens, not a card_target.
            d['card'] = 'that pile'
        if zns:
            d['zone'] = self.interp(zns[0])
            # "put a card onto the battlefield and the rest into your
            # graveyard": the first destination is a bare token, while only
            # the second is a `zone` tree.
            if 'battlefield' in toks and 'rest' in toks:
                d['zone'] = 'battlefield'
            if len(zns) > 1 or ('rest' in toks and 'battlefield' in toks):
                d['rest_zone'] = self.interp(zns[-1])
        else:
            # "onto the battlefield and the rest into your graveyard" encodes
            # the destinations as bare tokens, not `zone` trees.  Keep the
            # token order (battlefield first, graveyard second) instead of the
            # ZONE_WORDS priority order.
            aliases = {}
            for z in self.ZONE_WORDS:
                aliases[z] = z
                aliases[z + 's'] = z
            aliases['libraries'] = 'library'
            found = [aliases[t] for t in toks if t in aliases]
            if found:
                d['zone'] = found[0]
                if len(found) > 1 and ('rest' in toks or len(cts) > 1
                                       or 'other' in toks):
                    d['rest_zone'] = found[-1]
            else:
                z = self._zone_from_tokens(children)
                if z is not None:
                    d['zone'] = z
        # "put the rest on the bottom … in a random order" / "on top":
        # the destination phrase is literal tokens with no card_target/zone tree.
        if 'rest' in toks and 'card' not in d:
            d['card'] = 'the rest'
        if {'under', 'your', 'control'} <= set(toks):
            d['controller'] = 'you control'
        d.update(self._placement(children))
        # Entry state: only a direct token ("onto the battlefield tapped"), not a
        # "tapped" inside the card_target's status list.
        if any(isinstance(ch, Token) and str(ch).lower() == 'tapped'
               for ch in children):
            d['tapped'] = True
        return d

    # ------------------------------------------------------------------ triggered
    def i_trig_when(self, children):
        return self._text(children)

    def i_event(self, children):
        d = {}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'event_subject':
                    d['subject'] = self.interp(ch)
                elif ch.data == 'event_object':
                    d['object'] = self.interp(ch)
                elif ch.data == 'card_target':
                    d.setdefault('object', self.interp(ch))
                elif ch.data == 'player' and 'subject' not in d:
                    d['subject'] = self.interp(ch)
                elif ch.data == 'any_text':
                    words = self._token_words(children)
                    if 'while' in words:
                        # "attacks while saddled": a state condition on the event.
                        d['condition'] = 'while ' + self._text([ch]).strip()
                    elif 'target' in words:
                        # "becomes the target of <any_text>".
                        d['of'] = self.interp(ch)
            elif isinstance(ch, Token) and ch.type == 'EVENT_VERB':
                d['verb'] = ch.value
        words = self._token_words(children)
        flat_words = [w for word in words for w in word.split()]
        event_verbs = [v for v in ('enters', 'attacks', 'blocks')
                       if v in flat_words]
        if len(event_verbs) > 1:
            d['verb'] = {'kind': 'event', 'verbs': event_verbs}
        elif isinstance(d.get('verb'), str) and ' or ' in d['verb']:
            d['verb'] = {'kind': 'event',
                         'verbs': [v.strip() for v in
                                   d['verb'].split(' or ')]}
        if 'next' in words and 'cast' in words:
            # "When you next cast a creature spell this turn": the cast is
            # the event verb; keep the one-shot window.
            d.setdefault('verb', 'cast')
            d['next'] = True
            if 'this' in words and 'turn' in words:
                d['window'] = {'kind': 'turn', 'value': 'this_turn'}
            if 'you' in words:
                d.setdefault('subject', 'you')
        if 'put' in words:
            ca = self._find_one(children, 'counter_amount')
            ck = self._find_one(children, 'counter_kind')
            if ca is not None or ck is not None:
                # "you put one or more +1/+1 counters on …" / "counters are
                # put on …": the counter event has no EVENT_VERB token.
                d.setdefault('verb', 'put')
                counter = {}
                if ca is not None:
                    counter['count'] = self._text(ca.children)
                if ck is not None:
                    counter['kind'] = self._text(ck.children)
                if counter:
                    d['counter'] = counter
                if 'you' in words and 'subject' not in d:
                    d['subject'] = 'you'
        if 'loses' in words and 'verb' not in d:
            d['verb'] = 'loses'
            if 'life' in words:
                d['object'] = 'life'
        if 'there' in words and 'are' in words and 'condition' not in d:
            d['condition'] = self._text(children)
        if 'during' in words and 'turn' in words:
            d['condition'] = 'during ' + ' '.join(
                words[words.index('during') + 1:])
        if 'discard' in words:
            d.setdefault('verb', 'discard')
            if 'subject' not in d:
                pre = ' '.join(words[:words.index('discard')]).strip()
                if pre:
                    d['subject'] = pre
        if 'becomes' in words and 'target' in words:
            # This alternative keeps "becomes the target" as literal tokens,
            # and its card_target is the subject, not the object.
            if 'object' in d and 'subject' not in d:
                d['subject'] = d.pop('object')
            d['verb'] = 'becomes the target'
        # Passive damage events ("is dealt combat damage") carry the kind as
        # direct tokens; plain "is dealt damage" must not invent one.
        words = self._token_words(children)
        if 'is' in words and 'dealt' in words:
            # Passive damage event: "is dealt [combat|noncombat] damage".
            d.setdefault('verb', 'is dealt')
        for i, w in enumerate(words):
            if w in ('combat', 'noncombat') and words[i + 1:i + 2] == ['damage']:
                d['damage'] = w
        if not d:
            # Reflexive trigger ("When you do, ..."): the clause is a pronoun plus
            # a verb, not a subject/verb/object event.  Keep it as text.
            text = self._text(children)
            if text:
                d['text'] = text
        return d

    def i_event_subject(self, children):
        cards = [self.interp(c) for c in children
                 if isinstance(c, Tree) and c.data in ('card_target', 'player')]
        if len(cards) == 1:
            return cards[0]
        return {'or': cards}

    def i_event_object(self, children):
        words = self._token_words(children)
        if 'damage' in words:
            # "deals combat damage to a player": only a sentence that states
            # the kind gets one; plain "deals damage" has no kind.
            d = {}
            if 'combat' in words:
                d['damage'] = 'combat'
            elif 'noncombat' in words:
                d['damage'] = 'noncombat'
            for ch in children:
                if isinstance(ch, Tree):
                    d['to'] = self.interp(ch)
                    break
            if 'during' in words and 'turn' in words:
                d['condition'] = 'during ' + ' '.join(
                    words[words.index('during') + 1:])
            if not d:
                # Plain "is dealt damage": keep the damage object, no kind.
                txt = self._text(children)
                return txt if txt else {}
            return d
        for ch in children:
            if isinstance(ch, Tree):
                return self.interp(ch)
        # An event with no object ("Whenever this creature attacks").  Lark's optional
        # expansion can either omit the slot or leave an empty placeholder node behind;
        # both must mean the same thing, so return the empty object rather than ''.
        return self._text(children) if children else {}

    def i_condition(self, children):
        return self.interp(children[0]) if children else None

    def i_if_clause(self, children):
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'any_text':
                return self.interp(ch)
        return self._text(children)

    def i_trailing_if(self, children):
        for ch in children:
            if isinstance(ch, Tree) and ch.data == 'any_text':
                return self.interp(ch)
        return self._text(children)

    def i_static_text(self, children):
        return self._text(children)

    def _ability_word(self, node):
        """Text of an `ability_word_prefix` without its trailing em dash."""
        return self._text(node.children).replace('\u2014', '').strip()

    def i_trigger_clause(self, children):
        d = {}
        leading = []          # ability word: "Landfall — Whenever ..."
        seen_when = False
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'trig_when':
                    seen_when = True
                    d['when'] = self.interp(ch)
                elif ch.data == 'event':
                    d['event'] = self.interp(ch)
                elif ch.data == 'static_text':
                    d['text'] = self.interp(ch)
                elif ch.data == 'any_text':
                    val = self.interp(ch)
                    if isinstance(val, dict) and val.get('lists'):
                        d['event'] = {'subject': val['lists'][0]}
                        if val.get('text'):
                            d['text'] = val['text']
                    else:
                        d['text'] = val
            elif isinstance(ch, Token):
                if ch.value == '\u2014' or ch.type == 'EMDASH':
                    continue
                if seen_when:
                    d.setdefault('keywords', []).append(ch.value)
                else:
                    leading.append(ch.value)
        if leading:
            d['ability_word'] = ' '.join(leading)
        return d

    def i_triggered_sentence(self, children):
        d = {'type': 'triggered'}
        ability_word = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'ability_word_prefix':
                    ability_word = self._ability_word(ch)
                elif ch.data == 'trigger_clause':
                    d['trigger'] = self.interp(ch)
                elif ch.data == 'if_clause':
                    d['if'] = self.interp(ch)
                elif ch.data == 'trailing_if':
                    d['trailing_if'] = self.interp(ch)
                elif ch.data in ('trailing_if', 'if_clause'):
                    val = self.interp(ch)
                    if isinstance(val, str) and val.strip().lower() == 'able':
                        d['if_able'] = True
                    else:
                        d['if'] = val
                elif ch.data == 'trailing_unless':
                    val = self.interp(ch)
                    eff = d.get('effect')
                    if isinstance(eff, dict):
                        eff['unless'] = val
                    elif isinstance(eff, list) and eff:
                        eff[-1]['unless'] = val
                    else:
                        d['unless'] = val
                elif ch.data == 'effect':
                    d['effect'] = self.interp(ch)
                elif ch.data == 'for_each_sentence':
                    d['effect'] = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    d['xdef'] = self.interp(ch)
        if ability_word and isinstance(d.get('trigger'), dict):
            d['trigger'].setdefault('ability_word', ability_word)
        elif ability_word:
            d['ability_word'] = ability_word
        return d

    # ------------------------------------------------------------------ sentence types
    def _structure_cost_item(self, item):
        if not isinstance(item, str):
            return item
        raw = item.strip()
        if not raw or raw == ',':
            return None
        low = raw.lower()
        symbols = re.findall(r'\{[^}]+\}', raw)
        if symbols and re.fullmatch(r'(?:\{[^}]+\}\s*)+', raw):
            return {'kind': 'cost', 'action': 'pay_mana', 'mana': symbols}
        mpay = re.fullmatch(r'pay ([0-9]+|x) life', low)
        if mpay:
            value = int(mpay.group(1)) if mpay.group(1).isdigit() else 'X'
            return {'kind': 'cost', 'action': 'pay_life',
                    'amount': {'kind': 'number', 'value': value,
                               'unit': 'life'}}
        if low.startswith('tap '):
            rest = raw[4:].strip()
            q = None
            status = []
            for word, qv in (('four ', 'four'), ('three ', 'three'),
                             ('two ', 'two'), ('one ', 'one')):
                if rest.lower().startswith(word):
                    q = qv
                    rest = rest[len(word):]
                    break
            if rest.lower().startswith('untapped '):
                status.append('untapped')
                rest = rest[len('untapped '):]
            if rest.lower().endswith(' you control'):
                rest = rest[:-len(' you control')]
                controller = 'you'
            else:
                controller = None
            if rest.lower().endswith('s'):
                rest = rest[:-1]
            target = {'card_type': [{'kind': 'type', 'value': rest}]}
            if q:
                target['quantifier'] = q
            if status:
                target['status'] = status
            if controller:
                target['controller'] = controller
            return {'kind': 'cost', 'action': 'tap', 'target': target}
        if low.startswith('sacrifice '):
            target = self._simple_target(raw[len('sacrifice '):])
            if target:
                return {'kind': 'cost', 'action': 'sacrifice',
                        'card': target}
        if low.startswith('discard '):
            target = self._simple_target(raw[len('discard '):])
            if target:
                return {'kind': 'cost', 'action': 'discard',
                        'card': target}
        verb = low.split(' ', 1)[0]
        rest = raw[len(verb):].strip()
        d = {'kind': 'cost', 'action': verb}
        if rest:
            target = self._simple_target(rest)
            if target:
                d['target'] = target
        return d

    def i_cost_item(self, children):
        item = self._text(children) or (self.interp(children[0]) if children else None)
        return self._structure_cost_item(item)

    def i_cost_list(self, children):
        out = [self.interp(c) for c in children]
        return [x for x in out if x not in (None, ',')]

    def i_activated_sentence(self, children):
        cost = None
        eff = None
        xdef = None
        cond = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'cost_list':
                    cost = self.interp(ch)
                elif ch.data in ('effect', 'for_each_sentence', 'until_sentence',
                                 'triggered_sentence'):
                    eff = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    xdef = self.interp(ch)
                elif ch.data in ('if_clause', 'trailing_if'):
                    cond = self.interp(ch)
        d = {'type': 'activated', 'cost': cost, 'effect': eff}
        if cond is not None:
            d['if'] = cond
        if xdef is not None:
            d['xdef'] = xdef
        return d

    def i_spree_sentence(self, children):
        """A spree mode: "+ {2}{B} — Destroy target creature".

        The "+" marker is the mode indicator; the cost is what the mode costs.
        """
        cost = None
        eff = None
        xdef = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'cost_list':
                    cost = self.interp(ch)
                elif ch.data in ('effect', 'for_each_sentence', 'triggered_sentence'):
                    eff = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    xdef = self.interp(ch)
        d = {'type': 'spree_mode', 'cost': cost, 'effect': eff}
        if xdef is not None:
            d['xdef'] = xdef
        return d

    def i_cost_dash_sentence(self, children):
        """A mana-cost line written "<cost> — <effect>" ("{P} — Draw a card",
        "Blizzard — {0} — Return …"): the mana before the dash is the price."""
        cost = None
        eff = None
        xdef = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'cost_list':
                    cost = self.interp(ch)
                elif ch.data in ('effect', 'triggered_sentence'):
                    eff = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    xdef = self.interp(ch)
        d = {'type': 'cost_dash', 'cost': cost, 'effect': eff}
        if xdef is not None:
            d['xdef'] = xdef
        return d

    def i_prefixed_static(self, children):
        """A static statement behind an ability word: "To solve — You have no cards in hand"."""
        d = {'type': 'static'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'ability_word_prefix':
                    d['ability_word'] = self._text(ch.children).replace('\u2014', '').strip()
                else:
                    val = self.interp(ch)
                    if isinstance(val, dict):
                        if 'text' in val:
                            # "To solve — You control seven or more lands":
                            # the statement is the ability's condition.
                            d['condition'] = val['text']
                        else:
                            d.update(val)
                    elif val:
                        d['condition'] = val
        return d

    def i_loyalty_sentence(self, children):
        cost = None
        eff = None
        xdef = None
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'LOY_COST':
                raw = ch.value.strip().strip('[]').replace('−', '-')
                m = re.fullmatch(r'([+-]?)([0-9]+|x)', raw.lower())
                if m:
                    sign = -1 if m.group(1) == '-' else 1
                    v = m.group(2)
                    cost = {'kind': 'cost', 'action': 'loyalty',
                            'amount': {'kind': 'number',
                                       'value': (int(v) * sign
                                                 if v.isdigit() else 'X'),
                                       'unit': 'loyalty'}}
                    if v == 'x' and sign < 0:
                        cost['amount']['sign'] = -1
                else:
                    cost = ch.value
            elif isinstance(ch, Tree) and ch.data in ('effect', 'triggered_sentence'):
                eff = self.interp(ch)
            elif isinstance(ch, Tree) and ch.data == 'xdef_clause':
                # "where X is the number of Swamps you control" defines the
                # change's X; dropping it leaves the effect under-specified.
                xdef = self.interp(ch)
        d = {'type': 'loyalty', 'cost': cost, 'effect': eff}
        if xdef is not None:
            d['xdef'] = xdef
        return d

    def i_effect_sentence(self, children):
        d = {'type': 'effect'}
        for ch in children:
            if isinstance(ch, Token) and str(ch).lower() == 'otherwise':
                d['otherwise'] = True
            if isinstance(ch, Tree):
                if ch.data == 'ability_word_prefix':
                    d['ability_word'] = self._ability_word(ch)
                elif ch.data == 'effect':
                    d['effect'] = self.interp(ch)
                    eff = d['effect']
                    if isinstance(eff, dict) and eff.pop('otherwise', None):
                        d['otherwise'] = True
                elif ch.data == 'for_each_sentence':
                    d['effect'] = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    d['xdef'] = self.interp(ch)
                elif ch.data in ('trailing_if', 'if_clause'):
                    val = self.interp(ch)
                    if isinstance(val, str) and val.strip().lower() == 'able':
                        d['if_able'] = True
                    else:
                        d['if'] = val
                elif ch.data == 'if_sentence':
                    # "Then if <condition>, <action>": hoist the if-sentence
                    # instead of returning a bare {'type':'effect'}.
                    sub = self.interp(ch)
                    if isinstance(sub, dict):
                        for key in ('condition', 'if'):
                            if sub.get(key) is not None:
                                d['condition'] = sub[key]
                        if sub.get('effect') is not None:
                            d['effect'] = sub['effect']
                        if sub.get('instead'):
                            d['instead'] = True
                        if 'effect' not in d and sub.get('text'):
                            d['text'] = sub['text']
                elif ch.data == 'trailing_unless':
                    val = self.interp(ch)
                    eff = d.get('effect')
                    if isinstance(eff, dict):
                        eff['unless'] = val
                    elif isinstance(eff, list) and eff:
                        eff[-1]['unless'] = val
                    else:
                        d['unless'] = val
        if d.get('if_able'):
            eff = d.get('effect')
            acts = eff if isinstance(eff, list) else [eff]
            for a in acts:
                if isinstance(a, dict):
                    a['if_able'] = True
        return d

    def i_trailing_unless(self, children):
        at = self._find_one(children, 'any_text')
        return self.interp(at) if at is not None else self._text(children)

    def _normalize_xdef(self, val):
        if not isinstance(val, list) or any(isinstance(x, dict) for x in val):
            if (isinstance(val, list) and len(val) >= 4
                    and [str(x).lower() for x in val[:3]]
                    == ['the', 'number', 'of']
                    and isinstance(val[-1], dict)):
                tgt = val[-1]
                unit = None
                if isinstance(tgt.get('card_type'), dict):
                    unit = tgt['card_type'].get('value')
                if unit:
                    return {'kind': 'count', 'unit': unit, 'of': tgt}
            return val
        orig = ' '.join(str(x) for x in val).strip()
        txt = orig.lower()
        if txt.startswith('the number of '):
            rest = orig[len('the number of '):]
            rl = rest.lower()
            if ' on ' in rl:
                unit, on = rest.split(' on ', 1)
                tgt = self._simple_target(on)
                if tgt:
                    return {'kind': 'count', 'unit': unit.strip(),
                            'on': tgt}
            if ' among ' in rl:
                unit, among = rest.split(' among ', 1)
                tgt = self._simple_target(among)
                if tgt:
                    return {'kind': 'count', 'unit': unit.strip(),
                            'of': tgt}
            if rl.startswith('colors of mana spent'):
                return {'kind': 'count', 'unit': 'colors',
                        'of': 'mana spent to cast this spell'}
            if ' you control' in rl or ' an opponent controls' in rl:
                tgt = self._simple_target(rest)
                if tgt:
                    unit = rest.lower().split(' you control')[0].split(' an opponent controls')[0].strip()
                    return {'kind': 'count', 'unit': unit, 'of': tgt}
        mg = re.match(r'^the greatest (power|toughness|mana value) among (.+)$',
                      txt)
        if mg:
            tgt = self._simple_target(orig[len('the greatest '):][len(mg.group(1)) + len(' among '):])
            if tgt:
                return {'kind': 'greatest', 'stat': mg.group(1), 'of': tgt}
        if txt == "the sacrificed creature's mana value":
            return {'kind': 'stat', 'stat': 'mana_value',
                    'possessor': 'sacrificed creature'}
        if txt == 'the difference between its power and toughness':
            return {'kind': 'difference', 'stat': 'power_toughness',
                    'possessor': 'its'}
        if txt == 'their total power':
            return {'kind': 'stat', 'stat': 'total_power',
                    'possessor': 'their'}
        table = {
            'your speed':
                {'kind': 'stat', 'stat': 'speed', 'possessor': 'your'},
            'your life total':
                {'kind': 'stat', 'stat': 'life_total', 'possessor': 'your'},
            'its power':
                {'kind': 'stat', 'stat': 'power', 'possessor': 'its'},
            "that spell's mana value":
                {'kind': 'stat', 'stat': 'mana_value',
                 'possessor': "that spell's"},
            'the amount of life you gained this turn':
                {'kind': 'event', 'event': 'life_gained', 'this_turn': True},
            'the number of +1/+1 counters on ~':
                {'kind': 'count', 'unit': '+1/+1 counters',
                 'on': {'card_type': {'kind': 'this_card', 'value': '~'}}},
        }
        return table.get(txt, val)

    def i_xdef_sentence(self, children):
        xd = self._find_one(children, 'xdef')
        return {'verb': 'xdef',
                'value': (self._normalize_xdef(self.interp(xd))
                          if xd is not None else None)}

    def i_xdef_clause(self, children):
        val = self.interp(children[-1]) if children else None
        return {'xdef': self._normalize_xdef(val)}

    def i_modal_sentence(self, children):
        txt = ' '.join(self._text(children).split()).rstrip('.').lower()
        txt = txt.replace(' !', '!').replace(' .', '.')
        if txt == 'choose one':
            return {'type': 'modal', 'choose': 1}
        if txt == "choose one that hasn't been chosen":
            return {'type': 'modal', 'choose': 1, 'unchosen': True}
        return {'type': 'modal', 'text': self._text(children)}

    def i_enchanted_sentence(self, children):
        target = None
        eff = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'card_kind':
                    target = self.interp(ch)
                elif ch.data == 'effect':
                    eff = self.interp(ch)
        if isinstance(target, dict):
            # The sentence-level "Enchanted" is a status on the target; the
            # action's own (empty) card_target does not carry it.
            status = target.get('status')
            status = list(status) if isinstance(status, list) else []
            if 'Enchanted' not in status:
                status.insert(0, 'Enchanted')
            target['status'] = status

        def attach(v):
            if isinstance(v, dict):
                if 'target' in v and not v['target'] and target is not None:
                    v['target'] = dict(target)
                for x in v.values():
                    attach(x)
            elif isinstance(v, list):
                for x in v:
                    attach(x)
        attach(eff)
        return {'type': 'static', 'target': target, 'effect': eff}

    def i_static_sentence(self, children):
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        txt = ' '.join(self._text(children).split()).rstrip('.').lower()
        txt = txt.replace(' !', '!').replace(' .', '.')
        fixed = {
            'this ability triggers only once each turn':
                {'kind': 'trigger_limit', 'limit': 'once_each_turn'},
            'start your engines!': {'kind': 'start_engines'},
            "this spell can't be countered":
                {'kind': 'uncounterable', 'subject': 'this spell'},
            "it's still a land":
                {'kind': 'type_retention', 'card_type': 'land'},
            "it's an enchantment":
                {'kind': 'type_retention', 'card_type': 'enchantment'},
            'do this only once each turn':
                {'kind': 'action_limit', 'limit': 'once_each_turn'},
            "damage can't be prevented":
                {'kind': 'damage_prevention_disabled'},
            "you can't lose the game and your opponents can't win the game":
                {'kind': 'loss_lock', 'you': 'cannot_lose',
                 'opponents': 'cannot_win'},
            'you may choose the same mode more than once':
                {'kind': 'mode_repeat'},
        }
        if txt in fixed:
            return {'type': 'static', **fixed[txt]}
        if txt == 'enchant creature you control':
            return {'type': 'static', 'kind': 'enchant',
                    'card_target': {'card_type': {'kind': 'type',
                                                  'value': 'creature'},
                                    'controller': 'you control'}}
        if 'activate' in toks and 'only' in toks:
            if 'sorcery' in toks:
                return {'type': 'static', 'activate_only': 'as a sorcery'}
            if 'during' in toks and 'your' in toks and 'turn' in toks:
                return {'type': 'static', 'activate_only': 'during your turn'}
            if 'once' in toks and ('each' in toks or 'per' in toks):
                return {'type': 'static', 'activate_only': 'once each turn'}
            if 'once' in toks:
                return {'type': 'static', 'activate_only': 'once'}
        if 'can' in toks and 'block' in toks and 'only' in toks:
            cts = self._find_all(children, 'card_target')
            if len(cts) >= 2:
                return {'type': 'static',
                        'effect': {'verb': 'can_block',
                                   'subject': self.interp(cts[0]),
                                   'target': self.interp(cts[1]),
                                   'only': True}}
        if 'saddles' in toks and 'crews' in toks:
            amt = self._find_one(children, 'amount')
            as_though = {'stat': 'power', 'comparison': 'greater'}
            if amt is not None:
                as_though['amount'] = self.interp(amt)
            return {'type': 'static',
                    'effect': {'verb': 'saddle_and_crew',
                               'objects': [
                                   {'kind': 'type', 'value': 'mount'},
                                   {'kind': 'type', 'value': 'vehicle'}],
                               'as_though': as_though}}
        d = {'type': 'static', 'text': self._text(children)}
        eff = self._find_one(children, 'effect')
        if eff is not None:
            d['effect'] = self.interp(eff)
            d.pop('text', None)
        if 'once' in toks and 'each' in toks and 'turns' in toks:
            d['once_each_turn'] = True
        amt = self._find_one(children, 'amount')
        if 'maximum' in toks and 'hand' in toks and amt is not None:
            d['max_hand_size'] = self.interp(amt)
            d.pop('text', None)
        if 'spend' in toks and 'mana' in toks and 'though' in toks:
            eff = {'verb': 'spend_mana', 'object': 'mana',
                   'as_though': 'mana of any color'}
            ct = self._find_one(children, 'card_target')
            if ct is not None:
                eff['to'] = self.interp(ct)
            d['effect'] = eff
            d.pop('text', None)
        elif ('cast' in toks and 'though' in toks and 'be' in toks
              and any(isinstance(c, Token) and c.type == 'KEYWORD'
                      for c in children)):
            kw = next(str(c) for c in children
                      if isinstance(c, Token) and c.type == 'KEYWORD')
            d['effect'] = {'verb': 'cast', 'object': 'spell',
                           'as_though': kw}
            d.pop('text', None)
        elif ('look' in toks and 'top' in toks and 'any' in toks
              and 'play' not in toks):
            d['effect'] = {'verb': 'look',
                           'object': 'top card of your library',
                           'any_time': True}
            d.pop('text', None)
        pref = self._find_one(children, 'ability_word_prefix')
        if pref is not None and 'text' in d:
            d['ability_word'] = self._ability_word(pref)
            d['condition'] = d.pop('text')
        return d

    def _keyword_cost(self, text):
        t = ' '.join(text.split()).strip()
        if not t or ' or ' in t or ' and ' in t:
            return None
        mana = None
        while t.startswith('{') and '}' in t:
            end = t.index('}') + 1
            mana = (mana or '') + t[:end]
            t = t[end:].lstrip(' ,')
        low = t.lower()
        if low.startswith('pay ') and low.endswith(' life'):
            d = {'kind': 'cost', 'action': 'pay_life',
                 'amount': t[4:-5].strip()}
            if mana:
                d['mana'] = mana
            return d
        if low.startswith('discard '):
            tgt = self._simple_target(t[len('discard '):])
            if tgt:
                d = {'kind': 'cost', 'action': 'discard',
                     'card_target': tgt}
                if mana:
                    d['mana'] = mana
                return d
        if low.startswith('waterbend '):
            return {'kind': 'cost', 'action': 'waterbend',
                    'amount': t[len('waterbend '):].strip()}
        if mana:
            return {'kind': 'cost', 'action': 'pay_mana', 'mana': mana}
        return None

    def i_ward_cost(self, children):
        # Children: "Ward", EMDASH, then the payload tokens/subtrees.
        mod = self._text(children[2:]).strip()
        d = {'keyword': 'Ward', 'modifier': mod}
        cost = self._keyword_cost(mod)
        if cost:
            d.pop('modifier', None)
            d['cost'] = cost
        return d

    def i_keyword_cost(self, children):
        d = {'verb': 'keyword_cost'}
        words = []
        cost = []
        after = False
        for ch in children:
            if isinstance(ch, Token):
                v = str(ch.value)
                if v in ('\u2014', '\u2013', '-'):
                    after = True
                    continue
                (cost if after else words).append(v)
            elif isinstance(ch, Tree):
                v = self.interp(ch)
                (cost if after else words).append(str(v))
        name = ' '.join(w for w in words if not w.isdigit()).strip()
        mod = ' '.join(cost).strip()
        d = {'keyword': name, 'modifier': mod}
        kc = self._keyword_cost(mod)
        if kc:
            d.pop('modifier', None)
            d['cost'] = kc
        return d

    def i_static_keyword_sentence(self, children):
        d = {'type': 'static_keyword'}
        kw = None
        prefix = self._find_one(children, 'ability_word_prefix')
        if prefix is not None:
            d['ability_word'] = self._ability_word(prefix)
            idx = children.index(prefix) + 1
            rest = list(children[idx:])
        else:
            rest = list(children)
        for ch in rest:
            if isinstance(ch, Tree) and ch.data == 'generic_kw_list':
                for gk in ch.children:
                    if not isinstance(gk, Tree) or gk.data != 'generic_kw':
                        continue
                    eff = next((c for c in gk.children
                                if isinstance(c, Tree) and c.data == 'effect'), None)
                    if eff is None:
                        continue
                    word = next((str(c.value) for c in gk.children
                                 if isinstance(c, Token) and c.value != '\u2014'), None)
                    d = {'type': 'static'}
                    if word:
                        d['ability_word'] = word
                    d['effect'] = self.interp(eff)
                    return d
        items = []
        from_list = False
        for ch in rest:
            if isinstance(ch, Tree) and ch.data in ('kw_list', 'kw_list_mod'):
                items.extend(self.interp(ch))
                from_list = True
            elif isinstance(ch, Tree) and ch.data == 'kw_with_mod':
                items.append(self.interp(ch))
        if not items and rest:
            kw = self.interp(rest[0])
            if (isinstance(kw, list) and kw
                    and isinstance(kw[0], dict)
                    and str(kw[0].get('value', '')).lower() == 'add'):
                # Bare "Add {R}" reaches the generic keyword list; it is a
                # mana action, not a keyword.
                mana = ''.join(str(x) for x in kw[1:]
                               if isinstance(x, str) and x.startswith('{'))
                if mana:
                    return {'verb': 'add_mana', 'amount': mana}
            if kw is not None:
                if isinstance(kw, list):
                    kw = [x.get('value') if isinstance(x, dict)
                          and x.get('note') == 'unresolved'
                          and str(x.get('value', '')).lower() in LIST_KEYWORDS
                          else x for x in kw]
                elif isinstance(kw, dict) and kw.get('note') == 'unresolved' \
                        and str(kw.get('value', '')).lower() in LIST_KEYWORDS:
                    kw = kw['value']
                d['keywords'] = kw
                value = kw.get('value') if isinstance(kw, dict) else kw
                if isinstance(value, str) and value.lower() == 'investigate':
                    return {'verb': 'investigate'}
            return d
        # "Lifelink, hexproof from instants" / "Trample, ward {4}": keep every
        # keyword in order, with its cost argument.
        xd = self._find_one(rest, 'xdef_clause') if rest else None
        if xd is not None:
            d['xdef'] = self.interp(xd)
        if len(items) > 1 or from_list:
            d['keywords'] = items
        else:
            d['keywords'] = items[0]
        value = (items[0].get('value') if isinstance(items[0], dict)
                 else items[0]) if len(items) == 1 else None
        # The open keyword fallback can claim a one-word keyword action.
        # Preserve its semantic class instead of emitting a fake keyword.
        if isinstance(value, str) and value.lower() == 'investigate':
            return {'verb': 'investigate'}
        return d

    def i_replacement_sentence(self, children):
        d = {'type': 'replacement'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'replacement_cond':
                    d['if'] = self.interp(ch)
                elif ch.data == 'effect':
                    d['instead'] = self.interp(ch)
                elif ch.data in ('xdef_clause', 'xdef'):
                    d['xdef'] = self.interp(ch)
        return d

    def i_replacement_cond(self, children):
        """The replaced event of "If <subject> would <event>, <action> instead"."""
        d = {}
        subj = self._find_one(children, 'event_subject')
        if subj is not None:
            d['subject'] = self.interp(subj)
        toks = [str(c).lower() for c in children if isinstance(c, Token)]
        zn = self._find_one(children, 'zone')
        if zn is not None:
            d['verb'] = 'put_into'
            d['zone'] = self.interp(zn)
        elif 'die' in toks:
            d['verb'] = 'die'
            if 'turn' in toks:
                d['this_turn'] = True
        elif 'damage' in toks:
            d['verb'] = 'deal_damage'
            if 'noncombat' in toks:
                d['kind'] = 'noncombat'
            elif 'combat' in toks:
                d['kind'] = 'combat'
            dw = self._find_one(children, 'damage_who')
            if dw is not None:
                d['to'] = self.interp(dw)
        elif 'put' in toks and 'on' in toks:
            d['verb'] = 'put_counter'
            ck = self._find_one(children, 'counter_kind')
            if ck is not None:
                d['counter'] = self._text(ck.children).strip()
            ct = self._find_one(children, 'card_target')
            if ct is not None:
                d['on'] = self.interp(ct)
        elif 'gain' in toks and 'life' in toks:
            d['verb'] = 'gain_life'
        elif 'lose' in toks and 'life' in toks:
            d['verb'] = 'lose_life'
            if 'during' in toks:
                d['during'] = 'your turn' if 'your' in toks else 'their turn'
        elif 'draw' in toks:
            d['verb'] = 'draw'
        elif 'created' in toks:
            d['verb'] = 'create_token'
            ct = self._find_one(children, 'card_target')
            if ct is not None:
                d['what'] = self.interp(ct)
            if 'your' in toks:
                d['controller'] = 'you control'
        else:
            d['text'] = self._text(children)
        return d

    def i_if_sentence(self, children):
        d = {'type': 'if'}
        texts, eff = [], None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'effect':
                    eff = self.interp(ch)
                elif ch.data == 'any_text':
                    texts.append(self.interp(ch))
                elif ch.data == 'instead_suffix':
                    d['instead'] = True
                    for sub in ch.children:
                        if isinstance(sub, Tree) and sub.data == 'any_text':
                            d['instead_of'] = self._text([sub]).strip()
                elif ch.data in ('xdef_clause', 'xdef'):
                    d['xdef'] = self.interp(ch)
        if eff is not None:
            if texts:
                d['condition'] = (self._struct_cause_trigger(texts[0])
                                  or texts[0])
            d['effect'] = eff
        elif len(texts) >= 2:
            d['condition'] = texts[0]
            d['effect'] = (self._structured_consequence(texts[1])
                           or {'verb': 'raw', 'text': texts[1]})
        else:
            d['text'] = self._text(children)
        return d

    @staticmethod
    def _struct_cause_trigger(text):
        if isinstance(text, dict):
            return text
        if not isinstance(text, str):
            return None
        low = text.strip().lower()
        if 'dying causes a triggered ability' not in low:
            return None
        return {'kind': 'causes_trigger',
                'cause': {'event': 'dies',
                          'subject': {'kind': 'creature'}},
                'triggered_abilities': [
                    {'kind': 'triggered_ability',
                     'source': {'kind': 'this', 'card_class': 'creature'}},
                    {'kind': 'triggered_ability',
                     'source': {'kind': 'emblem', 'controller': 'you'}}]}

    def _structured_consequence(self, text):
        """Give a few frequent raw if-consequences a structured verb.

        The grammar falls back to any_text for replacement effects; the text
        still states which event is replaced and by what multiplier, so keep
        that instead of a bare {'verb': 'raw'}.
        """
        if not isinstance(text, str):
            return None
        low = text.lower().strip()
        mult = 2 if 'twice' in low else 3 if 'three times' in low else None
        if mult and ('that many' in low or 'that much' in low
                     or 'as much' in low):
            if 'token' in low:
                kind = 'tokens'
            elif 'counter' in low:
                kind = 'counters'
            elif 'damage' in low:
                kind = 'damage'
            elif 'mana' in low:
                kind = 'mana'
            else:
                kind = 'permanent'
            return {'verb': 'replace_' + kind, 'multiplier': mult,
                    'instead': True}
        if 'repeat this process' in low:
            d = {'verb': 'repeat'}
            if 'once' in low:
                d['count'] = 1
            if low.startswith('draw a card and repeat'):
                d['also'] = {'verb': 'draw', 'amount': 1}
            return d
        if 'assigns combat damage as though' in low:
            return {'verb': 'assign_combat_damage',
                    'as_though': 'positive power'}
        if low.startswith('skip that draw'):
            return {'verb': 'skip', 'object': 'draw', 'instead': True}
        if 'becomes prepared' in low:
            return {'verb': 'become', 'state': 'prepared'}
        if low.startswith('amass '):
            words = text.strip().rstrip('.').split()
            if words and words[-1].lower() == 'instead':
                words = words[:-1]
            amount = words[-1] if words and words[-1].isdigit() else None
            typ = ' '.join(words[1:-1] if amount else words[1:])
            d = {'verb': 'amass'}
            if typ:
                d['type'] = typ
            if amount:
                d['amount'] = int(amount)
            return d
        if low.rstrip('.') == 'recruit':
            return {'verb': 'recruit'}
        if low.startswith('remove those counters'):
            d = {'verb': 'remove_counter', 'counter': 'those counters'}
            # "…, remove those counters and it deals 20 damage to you"
            pos = low.find(' and it deals ')
            if pos >= 0:
                tail = text[pos + len(' and it deals '):]
                words = tail.split()
                amount = None
                for w in words:
                    if w.isdigit():
                        amount = int(w)
                        break
                d['and'] = {'verb': 'deal_damage'}
                if amount is not None:
                    d['and']['amount'] = amount
                if ' to you' in tail:
                    d['and']['to'] = 'you'
            elif ' and transform it' in low:
                d['and'] = {'verb': 'transform',
                            'card': {'ref': 'anaphora', 'raw': 'it'}}
            return d
        if low.startswith('unattach it'):
            d = {'verb': 'unattach', 'object': {'ref': 'anaphora',
                                                'raw': 'it'}}
            if 'at the beginning of the next end step' in low:
                d['timing'] = 'at the beginning of the next end step'
            return d
        if low.startswith('attach it to '):
            return {'verb': 'attach',
                    'target': {'ref': 'anaphora', 'raw': 'it'},
                    'to': text[len('attach it to '):].strip()}
        return None

    def _cond_effect_sentence(self, stype, children):
        d = {'type': stype}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'any_text':
                    d['condition'] = self.interp(ch)
                elif ch.data == 'effect':
                    d['effect'] = self.interp(ch)
                elif ch.data == 'during_time':
                    d['time'] = self.interp(ch)
        if stype == 'until':
            dur = self._duration(children)
            if dur:
                d['duration'] = dur
                # "Until end of turn, this creature loses defender and gains
                # flying": the clause qualifies the inner actions too.
                self._apply_duration(d.get('effect'), dur)
        return d

    def _apply_duration(self, node, dur):
        if isinstance(node, dict):
            if (node.get('verb') in self.DURATION_VERBS
                    and 'duration' not in node):
                node['duration'] = dur
            for v in node.values():
                self._apply_duration(v, dur)
        elif isinstance(node, list):
            for v in node:
                self._apply_duration(v, dur)

    def i_spend_mana_fallback(self, children):
        return {'type': 'static', 'text': self._text(children)}

    def i_as_long_sentence(self, children):
        return self._cond_effect_sentence('as_long', children)

    def i_as_long_tail_sentence(self, children):
        d = {'type': 'effect'}
        eff = None
        cond = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'effect':
                    eff = self.interp(ch)
                elif ch.data == 'any_text':
                    cond = str(self.interp(ch))
        if cond is not None and isinstance(eff, dict):
            inner = eff.get('inner')
            if eff.get('verb') == 'gain_kw':
                # "gains hexproof for as long as …": the keyword grant is
                # time-bounded; this is its duration, not a separate if.
                eff.setdefault('duration', 'for as long as ' + cond)
            elif isinstance(inner, dict):
                # "you may cast …": the permission carries the duration.
                inner.setdefault('duration', 'for as long as ' + cond)
            else:
                eff.setdefault('condition', cond)
        d['effect'] = eff
        return d

    def i_during_sentence(self, children):
        return self._cond_effect_sentence('during', children)

    def i_until_sentence(self, children):
        return self._cond_effect_sentence('until', children)

    def i_as_cost_sentence(self, children):
        return self._cond_effect_sentence('additional_cost', children)

    def i_any_text(self, children):
        toks = [c for c in children if isinstance(c, Token) and c.type == 'LISTTOK']
        if toks:
            lists = [decode_list_token(t.value) for t in toks]
            parts = []
            for c in children:
                if isinstance(c, Token) and c.type == 'LISTTOK':
                    dec = decode_list_token(c.value)
                    parts.append(dec.get('label') or dec.get('text') or c.value)
                else:
                    parts.append(str(c))
            out = {'label': ' '.join(parts).strip(), 'lists': lists}
            if lists:
                first = lists[0]
                for k in ('items', 'connector', 'logic', 'kind'):
                    if k in first:
                        out[k] = first[k]
            return out
        return self._text(children)

    def i_raw_action(self, children):
        return {'verb': 'raw', 'text': self._text(children)}


def interpret(sentence, types=None, names=None, interp=None):
    """Convenience: interpret a raw oracle sentence string -> list of dicts."""
    from larkparser import build_parser
    if interp is None:
        interp = Interpreter(types=types, names=names)
    parser = build_parser('interp')
    from preprocess import segment
    out = []
    for it in segment(sentence, names):
        try:
            tree = parser.parse(it['text'])
            out.extend(interp.interp(tree))
        except Exception:
            out.append({'type': 'unparsed', 'reason': 'parse_error',
                        'fragment': it['text'], 'source': 'interpret'})
    return out
