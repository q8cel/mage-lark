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

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
from lark import Token, Tree

from lists import decode as decode_list_token
from mtd import card_type_set, name_set


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
        return cleaned

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
            ('in_zone', 'zone'),
        ]
        for name, key in mapping:
            found = self._find_all(children, name)
            if found:
                d[key] = self.interp(found[0])
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
                    return {'kind': 'type', 'value': ' or '.join(vals)}
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
        return {'keyword': key, 'modifier': modifier}

    def i_player(self, children):
        return self._text(children)

    def i_who(self, children):
        if not children:
            return None
        toks = [ch.value for ch in children if isinstance(ch, Token)]
        if 'controller' in toks:
            return 'its controller'
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
        return d

    def i_play_action(self, children):
        d = self._card_action('play', children)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'additional' in toks and 'land' in toks:
            d['additional_land'] = True
        if 'this' in toks and 'turn' in toks:
            d.setdefault('duration', 'this turn')
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
            val = self.interp(xd)
            d['amount'] = (' '.join(str(v) for v in val)
                           if isinstance(val, list) else val)
        ref = self._find_one(children, 'draw_ref')
        if ref is not None:
            d['amount'] = self.i_draw_ref(ref.children)
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
        return self._card_action('discard', children)

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
        return d

    def i_destroy_action(self, children):
        return self._card_action('destroy', children)

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
        d['to'] = to
        ca = self._find_one(children, 'counter_amount')
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            w = {'counter': self._text(ck.children)}
            if ca is not None:
                w['count'] = self.interp(ca)
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

    def i_keyword_action(self, children):
        """Keyword actions with an optional parameter: blight N, waterbend {N},
        discover N, amass <type> N, connives, recruit, forage, airbend <target>,
        devour land N."""
        toks = [str(c).lower() for c in children if isinstance(c, Token)]
        verb = next((v for v in self.KW_ACTION_VERBS if v in toks), 'keyword_action')
        d = {'verb': verb}
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        mana = ''.join(str(c) for c in children
                       if isinstance(c, Token) and c.type == 'MANA')
        if mana:
            d['mana'] = mana
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
        return self._card_action('suspect', children)

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
            d['text'] = self._text(children)
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
        elif 'copy' in toks:
            d['effect'] = {'verb': 'copy'}
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
                w['counter'] = self._text(ck.children) if isinstance(ck, Tree) else str(ck)
            if pm:
                w['counter'] = pm[0].value + ' counter'
            d['with'] = w
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        if 'tapped' in toks:
            d['tapped'] = True
        if 'prepared' in toks:
            d['prepared'] = True
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
                    d['named'] = ' '.join(names)
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
            d['text'] = self.interp(at)
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
                d['for'] = {'kind': 'copy', 'text': val.strip()}
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
        return d

    def i_remove_counter_action(self, children):
        d = {'verb': 'remove_counter'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['from'] = self.interp(ct)
        ca = self._find_one(children, 'counter_amount')
        if ca is not None:
            d['count'] = self.interp(ca)
        ck = self._find_one(children, 'counter_kind')
        if ck is not None:
            d['counter'] = self._text(ck.children)
        return d

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
        for name in ('mana_amount', 'xdef', 'amount'):
            node = self._find_one(children, name)
            if node is not None:
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
        if amt is not None:
            d['amount'] = self.interp(amt)
        else:
            words = self._token_words(children)
            if 'that' in words and 'many' in words:
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
        inner = None
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
                inner = self.interp(ch)
            elif ch.data in ('controller_subject', 'owner_subject'):
                actor_tree = self._text([ch]).strip()
            elif ch.data in ('player', 'card_target'):
                actor_tree = self.interp(ch)
            else:
                actor_words.append(self._text([ch]))
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
        d = {'verb': 'double'}
        d['text'] = self._text(children)
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
                elif ch.data == 'xdef_clause':
                    d['xdef'] = self.interp(ch)
        if ability_word and isinstance(d.get('trigger'), dict):
            d['trigger'].setdefault('ability_word', ability_word)
        elif ability_word:
            d['ability_word'] = ability_word
        return d

    # ------------------------------------------------------------------ sentence types
    def i_cost_item(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_cost_list(self, children):
        return [self.interp(c) for c in children]

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
                        d.update(val)
                    else:
                        d['text'] = val
        return d

    def i_loyalty_sentence(self, children):
        cost = None
        eff = None
        xdef = None
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'LOY_COST':
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

    def i_xdef_sentence(self, children):
        xd = self._find_one(children, 'xdef')
        return {'verb': 'xdef', 'value': self.interp(xd) if xd is not None else None}

    def i_xdef_clause(self, children):
        return {'xdef': self.interp(children[-1]) if children else None}

    def i_modal_sentence(self, children):
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
        d = {'type': 'static', 'text': self._text(children)}
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
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
        return {'keyword': name, 'modifier': ' '.join(cost).strip()}

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
        if eff is not None:
            if texts:
                d['condition'] = texts[0]
            d['effect'] = eff
        elif len(texts) >= 2:
            d['condition'] = texts[0]
            d['effect'] = (self._structured_consequence(texts[1])
                           or {'verb': 'raw', 'text': texts[1]})
        else:
            d['text'] = self._text(children)
        return d

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
                    'instead': True, 'text': text}
        if 'repeat this process' in low:
            d = {'verb': 'repeat'}
            if 'once' in low:
                d['count'] = 1
            if low.startswith('draw a card and repeat'):
                d['also'] = {'verb': 'draw', 'amount': 1}
            d['text'] = text
            return d
        if 'assigns combat damage as though' in low:
            return {'verb': 'assign_combat_damage',
                    'as_though': 'positive power', 'text': text}
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
            d = {'verb': 'remove_counter', 'counter': 'those counters',
                 'text': text}
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
                                                'raw': 'it'}, 'text': text}
            if 'at the beginning of the next end step' in low:
                d['timing'] = 'at the beginning of the next end step'
            return d
        if low.startswith('attach it to '):
            return {'verb': 'attach',
                    'target': {'ref': 'anaphora', 'raw': 'it'},
                    'to': text[len('attach it to '):].strip(), 'text': text}
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

    def i_as_long_sentence(self, children):
        return self._cond_effect_sentence('as_long', children)

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
                    parts.append(decode_list_token(c.value).get('text', c.value))
                else:
                    parts.append(str(c))
            return {'text': ' '.join(parts).strip(), 'lists': lists}
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
            out.append({'type': 'unparsed', 'text': it['text']})
    return out
