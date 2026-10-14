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
from lark import Token, Tree
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

    ANAPHORA = {'it', 'them', 'its', "it's", 'they', 'their'}
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
    def i_start(self, children):
        out = []
        for ch in children:
            v = self.interp(ch)
            if v is not None:
                out.append(v)
        return out

    def i_sentence(self, children):
        for ch in children:
            if isinstance(ch, Tree):
                return self.interp(ch)
        return None

    # ------------------------------------------------------------------ card target
    def i_card_target(self, children):
        d = {}
        # Fields are grouped under lead/core/zone_mod; search the whole subtree
        # so the grouping is transparent.  Order of the mapping is the precedence
        # when a key can be produced by more than one rule name.
        mapping = [
            ('this_that', 'this_that'), ('possessive', 'possessive'),
            ('quantifier', 'quantifier'), ('otherness', 'otherness'),
            ('nontoken', 'nontoken'), ('status_list', 'status'),
            ('colors', 'colors'), ('card_kind', 'card_type'),
            ('with_modifier', 'modifier'), ('controller', 'controller'),
            ('in_zone', 'zone'),
        ]
        for name, key in mapping:
            found = self._find_all(children, name)
            if found:
                d[key] = self.interp(found[0])
        return d

    def i_card_kind(self, children):
        toks = [c for c in children if isinstance(c, Token)]
        trees = [c for c in children if isinstance(c, Tree)]
        if trees:
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
        return {'kind': 'type', 'value': toks[0].value.lower()}

    def i_types(self, children):
        for ch in children:
            if isinstance(ch, Token):
                if ch.type == 'CARDNAME':
                    return self._resolve_kind(ch.value)
                return {'kind': 'type', 'value': ch.value.lower()}
        return None

    def i_quantifier(self, children):
        toks = [c for c in children if isinstance(c, Token)]
        trees = [c for c in children if isinstance(c, Tree)]
        words = [t.value for t in toks]
        if 'up' in words and 'to' in words:
            return {'up_to': self._first_number(children)}
        if len(words) == 1 and words[0].isdigit():
            return int(words[0])
        if trees:
            return self.interp(trees[0])
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
        return self._text(children)

    def i_this_that(self, children):
        return self._text(children)

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
                zone = self.interp(ch)
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
            low = [c.value.lower() for c in n.children if isinstance(c, Token)]
            if 'protection' in low:
                out.append(self._text(n.children))
                return
            for c in n.children:
                walk(c)
        for ch in children:
            walk(ch)
        return out

    # kw_list_mod / kw_item are parallel keyword-list rules -> same extraction.
    i_kw_list_mod = i_kw_list
    def i_kw_item(self, children):
        v = self.i_kw_list(children)
        return v[0] if v else None

    def i_kw_with_mod(self, children):
        key = None
        mod = None
        for ch in children:
            v = self.interp(ch)
            if key is None:
                key = v
            else:
                mod = v
        return {'keyword': key, 'modifier': mod}

    def i_player(self, children):
        return self._text(children)

    def i_who(self, children):
        if not children:
            return None
        toks = [ch.value for ch in children if isinstance(ch, Token)]
        if 'controller' in toks:
            return 'its controller'
        first = children[0]
        return self.interp(first) if isinstance(first, Tree) else first

    # ------------------------------------------------------------------ effect / actions
    def i_effect(self, children):
        out = []
        for ch in children:
            if isinstance(ch, Tree):
                out.append(self.interp(ch))
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
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d[key] = self.interp(ct)
        amt = self._find_one(children, 'amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        zn = self._find_one(children, 'zone') or self._find_one(children, 'in_zone')
        if zn is not None:
            d['zone'] = self.interp(zn)
        else:
            z = self._zone_from_tokens(children)
            if z is not None:
                d['zone'] = z
        wm = self._find_one(children, 'with_modifier')
        if wm is not None:
            d['modifier'] = self.interp(wm)
        return d

    def i_cast_action(self, children):
        return self._card_action('cast', children)

    def i_play_action(self, children):
        return self._card_action('play', children)

    def i_draw_action(self, children):
        d = {'verb': 'draw'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['cards'] = self.interp(ct)
        amt = self._find_one(children, 'draw_amount')
        if amt is not None:
            d['amount'] = self.interp(amt)
        return d

    def i_discard_action(self, children):
        return self._card_action('discard', children)

    def i_exile_action(self, children):
        return self._card_action('exile', children)

    def i_destroy_action(self, children):
        return self._card_action('destroy', children)

    def i_tap_action(self, children):
        return self._card_action('tap', children)

    def i_untap_action(self, children):
        return self._card_action('untap', children)

    def i_sacrifice_action(self, children):
        return self._card_action('sacrifice', children)

    def i_return_action(self, children):
        d = {'verb': 'return'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        d['to'] = self._text([c for c in children
                              if not (isinstance(c, Tree) and c.data == 'card_target')])
        return d

    def i_gain_control_action(self, children):
        return self._card_action('gain_control', children)

    def i_extra_turns_action(self, children):
        d = {'verb': 'extra_turns'}
        who = self._find_one(children, 'who')
        if who is not None:
            d['actor'] = self.interp(who)
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
        return d

    def i_phase_action(self, children):
        d = {'verb': 'phase'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        toks = [str(ch).lower() for ch in children if isinstance(ch, Token)]
        d['direction'] = 'in' if 'in' in toks else 'out'
        return d

    def i_enchant_action(self, children):
        d = {'verb': 'enchant'}
        et = self._find_one(children, 'enchant_target')
        if et is not None:
            d['targets'] = [c.value for c in et.children
                            if isinstance(c, Token) and c.type == 'GENERIC_TYPE']
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
        return d

    def i_reveal_action(self, children):
        return self._card_action('reveal', children)

    def i_attach_action(self, children):
        d = {'verb': 'attach'}
        cts = self._find(children, 'card_target')
        token = any(isinstance(c, Token) and str(c).lower() == 'token' for c in children)
        if len(cts) >= 2:
            d['object'] = self.interp(cts[0])
            d['to'] = self.interp(cts[1])
        elif cts:
            d['object'] = self.interp(cts[0])
            if token:
                d['to'] = {'card_type': {'kind': 'type', 'value': 'token'}}
        return d

    def i_fight_action(self, children):
        return self._card_action('fight', children, key='target')

    def i_cant_action(self, children):
        d = {'verb': "can't"}
        cts = self._find(children, 'card_target')
        if cts:
            d['card'] = self.interp(cts[0])
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

    def i_gain_kw_action(self, children):
        d = {'verb': 'gain_kw'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        kw = self._find_one(children, 'kw_list')
        if kw is not None:
            d['keywords'] = self.interp(kw)
        return d

    def i_base_pt_action(self, children):
        d = {'verb': 'set_base_pt'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
        pt = [c for c in children if isinstance(c, Token) and c.type == 'POWER_T']
        if pt:
            d['base_pt'] = pt[0].value
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
        if any(isinstance(c, Token) and c.value == 'addition' for c in children):
            d['in_addition'] = True
        pt = [c for c in children if isinstance(c, Token) and c.type in ('POWER_T', 'POWER_MOD')]
        if not pt:
            pcm = self._find_one(children, 'pt_color_mod')
            if pcm is not None:
                pt = [c for c in pcm.children if isinstance(c, Token) and c.type in ('POWER_T', 'POWER_MOD')]
        if pt:
            d['pt'] = pt[0].value
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
            d['who'] = self.interp(who)
        la = self._find_one(children, 'life_amount')
        if la is not None:
            d['amount'] = self.interp(la)
        return d

    def i_lose_life_action(self, children):
        d = {'verb': 'lose_life'}
        who = self._find_one(children, 'who') or self._find_one(children, 'player')
        if who is not None:
            d['who'] = self.interp(who)
        la = self._find_one(children, 'life_amount')
        if la is not None:
            d['amount'] = self.interp(la)
        return d

    def i_life_amount(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_dmg_amount(self, children):
        # a bare number/word keeps its structured (int) value; relative forms -> text
        if len(children) == 1 and isinstance(children[0], Tree) and children[0].data == 'amount':
            return self.interp(children[0])
        return self._text(children)

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
                d['who'] = self.interp(ch)
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
            d['for'] = self.interp(at)
        return d

    def i_gain_poison_action(self, children):
        d = {'verb': 'gain_poison'}
        who = self._find_one(children, 'who')
        if who is not None:
            d['who'] = self.interp(who)
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
        return d

    def i_damage_amount(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_damage_target(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

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
            d['actor'] = self.interp(who)
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
            elif isinstance(ch, Token):
                if ch.type == 'POWER_T':
                    d['power_toughness'] = ch.value
                elif ch.type == 'COLOR':
                    d.setdefault('colors', ch.value)
                elif ch.type == 'CARDNAME':
                    types.append(ch.value)
                elif ch.value.lower() in self.SUPERTYPES:
                    types.append(ch.value.lower())
        if types:
            d['types'] = types
        return d

    def _token_tail(self, ch, d):
        """Extract 'with <kw>' / 'named X' / 'tapped' / zone from a token_tail."""
        for sub in ch.children:
            if isinstance(sub, Tree):
                if sub.data == 'kw_list':
                    d.setdefault('kw', []).append(self.interp(sub))
                elif sub.data == 'in_zone':
                    d['zone'] = self.interp(sub)
            elif isinstance(sub, Token):
                if sub.value.lower() == 'tapped':
                    d['tapped'] = True
                if sub.type == 'CARDNAME':
                    d.setdefault('named', []).append(sub.value)

    def i_token_num(self, children):
        return self.interp(children[0]) if children else None

    def i_token_types(self, children):
        return [ch.value if isinstance(ch, Token) else self.interp(ch)
                for ch in children]

    def i_add_mana_action(self, children):
        d = {'verb': 'add_mana'}
        if children:
            d['amount'] = self.interp(children[-1])
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
        pl = self._find_one(children, 'player')
        if pl is not None:
            d['who'] = self.interp(pl)
        return d

    def i_search_action(self, children):
        d = {'verb': 'search'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'card_target':
                    d['card'] = self.interp(ch)
                elif ch.data == 'amount':
                    d['amount'] = self.interp(ch)
                elif ch.data in ('zone', 'in_zone'):
                    d['zone'] = self.interp(ch)
        if 'zone' not in d:
            z = self._zone_from_tokens(children)
            if z is not None:
                d['zone'] = z
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
        return d

    def i_shuffle_action(self, children):
        return {'verb': 'shuffle'}

    def i_no_max_hand_action(self, children):
        return {'verb': 'no_max_hand_size'}

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
        return d

    def i_choose_obj(self, children):
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            return self.interp(ct)
        return self._text(children)

    def i_may_action(self, children):
        inner = None
        for ch in children:
            if isinstance(ch, Tree) and ch.data not in ('V_YOU', 'V_MAY'):
                inner = self.interp(ch)
        return {'verb': 'may', 'inner': inner}

    def i_cost_mod_action(self, children):
        d = {'verb': 'cost_mod'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
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
        elif any(isinstance(ch, Token) and ch.value == 'additional' for ch in children):
            d['direction'] = 'additional'
        return d

    def i_gain_quote_action(self, children):
        d = {'verb': 'gain_quote'}
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['target'] = self.interp(ct)
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
        return d

    def i_pay_action(self, children):
        d = {'verb': 'pay'}
        mana = [ch.value for ch in children
                if isinstance(ch, Token) and ch.type == 'MANA']
        if mana:
            d['amount'] = ''.join(mana)
        return d

    def i_stat_define_action(self, children):
        d = {'verb': 'stat_define', 'stat': 'power_and_toughness', 'relation': 'each_equal_to'}
        xd = self._find_one(children, 'xdef')
        if xd is not None:
            d['value'] = self.interp(xd)
        return d

    def i_emblem_action(self, children):
        d = {'verb': 'emblem'}
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'QUOTE':
                d['quote'] = ch.value
        return d

    def i_prevent_action(self, children):
        return self._card_action('prevent_damage', children)

    SUPERTYPES = {'creature', 'artifact', 'enchantment', 'land', 'plane',
                  'phenomenon', 'module', 'card', 'saga', 'vanguard', 'cop'}

    def i_put_zone_action(self, children):
        d = {'verb': 'put'}
        wh = self._find_one(children, 'who')
        if wh is not None and wh.data != 'card_target':
            d['who'] = self.interp(wh)
        ct = self._find_one(children, 'card_target')
        if ct is not None:
            d['card'] = self.interp(ct)
        zn = self._find_one(children, 'zone')
        if zn is not None:
            d['zone'] = self.interp(zn)
        else:
            z = self._zone_from_tokens(children)
            if z is not None:
                d['zone'] = z
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
            elif isinstance(ch, Token) and ch.type == 'EVENT_VERB':
                d['verb'] = ch.value
        return d

    def i_event_subject(self, children):
        cards = [self.interp(c) for c in children
                 if isinstance(c, Tree) and c.data in ('card_target', 'player')]
        if len(cards) == 1:
            return cards[0]
        return {'or': cards}

    def i_event_object(self, children):
        for ch in children:
            if isinstance(ch, Tree):
                return self.interp(ch)
        return self._text(children)

    def i_condition(self, children):
        return self.interp(children[0]) if children else None

    def i_if_clause(self, children):
        return self._text(children)

    def i_trailing_if(self, children):
        return self._text(children)

    def i_static_text(self, children):
        return self._text(children)

    def i_trigger_clause(self, children):
        d = {}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'trig_when':
                    d['when'] = self.interp(ch)
                elif ch.data == 'event':
                    d['event'] = self.interp(ch)
                elif ch.data == 'condition':
                    d['condition'] = self.interp(ch)
                elif ch.data == 'static_text':
                    d['text'] = self.interp(ch)
            elif isinstance(ch, Token):
                d.setdefault('keywords', []).append(ch.value)
        return d

    def i_triggered_sentence(self, children):
        d = {'type': 'triggered'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'trigger_clause':
                    d['trigger'] = self.interp(ch)
                elif ch.data == 'if_clause':
                    d['if'] = self.interp(ch)
                elif ch.data == 'trailing_if':
                    d['trailing_if'] = self.interp(ch)
                elif ch.data == 'effect':
                    d['effect'] = self.interp(ch)
        return d

    # ------------------------------------------------------------------ sentence types
    def i_cost_item(self, children):
        return self._text(children) or (self.interp(children[0]) if children else None)

    def i_cost_list(self, children):
        return [self.interp(c) for c in children]

    def i_activated_sentence(self, children):
        cost = None
        eff = None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'cost_list':
                    cost = self.interp(ch)
                elif ch.data == 'effect':
                    eff = self.interp(ch)
        return {'type': 'activated', 'cost': cost, 'effect': eff}

    def i_loyalty_sentence(self, children):
        cost = None
        eff = None
        for ch in children:
            if isinstance(ch, Token) and ch.type == 'LOY_COST':
                cost = ch.value
            elif isinstance(ch, Tree) and ch.data == 'effect':
                eff = self.interp(ch)
        return {'type': 'loyalty', 'cost': cost, 'effect': eff}

    def i_effect_sentence(self, children):
        d = {'type': 'effect'}
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'effect':
                    d['effect'] = self.interp(ch)
                elif ch.data == 'xdef_clause':
                    d['xdef'] = self.interp(ch)
        return d

    def i_xdef_clause(self, children):
        return {'xdef': self.interp(children[-1]) if children else None}

    def i_modal_sentence(self, children):
        return {'type': 'modal', 'text': self._text(children)}

    def i_static_sentence(self, children):
        return {'type': 'static', 'text': self._text(children)}

    def i_static_keyword_sentence(self, children):
        d = {'type': 'static_keyword'}
        if children:
            d['keywords'] = self.interp(children[0])
        return d

    def i_if_sentence(self, children):
        d = {'type': 'if'}
        texts, eff = [], None
        for ch in children:
            if isinstance(ch, Tree):
                if ch.data == 'effect':
                    eff = self.interp(ch)
                elif ch.data == 'any_text':
                    texts.append(self._text([ch]).strip())
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
            d['effect'] = {'verb': 'raw', 'text': texts[1]}
        else:
            d['text'] = self._text(children)
        return d

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
        return d

    def i_as_long_sentence(self, children):
        return self._cond_effect_sentence('as_long', children)

    def i_during_sentence(self, children):
        return self._cond_effect_sentence('during', children)

    def i_until_sentence(self, children):
        return self._cond_effect_sentence('until', children)

    def i_as_cost_sentence(self, children):
        return self._cond_effect_sentence('additional_cost', children)

    def i_any_text(self, children):
        return self._text(children)

    def i_raw_action(self, children):
        return {'verb': 'raw', 'text': self._text(children)}


def interpret(sentence, types=None, names=None, interp=None):
    """Convenience: interpret a raw oracle sentence string -> list of dicts."""
    from lark import Lark
    import os
    if interp is None:
        interp = Interpreter(types=types, names=names)
    base = os.path.dirname(os.path.abspath(__file__))
    parser = Lark.open(os.path.join(base, 'grammar.lark'), parser='earley',
                       start='start', ambiguity='resolve', keep_all_tokens=False)
    from preprocess import segment
    out = []
    for it in segment(sentence):
        try:
            tree = parser.parse(it['text'])
            out.extend(interp.interp(tree))
        except Exception:
            out.append({'type': 'unparsed', 'text': it['text']})
    return out
