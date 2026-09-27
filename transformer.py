#!/usr/bin/env python3
"""Transformer: turn the parse tree into a structured, JSON-serialisable dict.

The core principle: targets / subjects / objects are emitted as ATOMIC components
(quantifier, otherness, nontoken, status, colors, kind, modifier, controller, zone)
— never as a single flattened string like "all attacking creatures".
"""
from lark import Transformer, Token, Tree
from mtd import card_type_set, name_set


class OracleTransformer(Transformer):
    def __init__(self, types=None, names=None):
        super().__init__()
        self._card_types = types or card_type_set()
        self._card_names = names or name_set()

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _txt(children):
        """Join all token text in children (flatten simple leaf rules)."""
        out = []
        for c in children:
            if isinstance(c, Token):
                out.append(c.value)
            elif isinstance(c, Tree):
                out.append(c.meta  # placeholder, unused
                           if False else _tree_text(c))
        return ' '.join(t for t in out if t)

    def _resolve_kind(self, name):
        """Resolve a proper noun to a card type vs. a card name."""
        if name in self._card_types:
            return {'kind': 'type', 'value': name}
        if name in self._card_names:
            return {'kind': 'name', 'value': name}
        return {'kind': 'type', 'value': name, 'note': 'unresolved'}

    # -- terminals / simple leaves -----------------------------------------
    def NUMBER(self, t):
        return Token('NUMBER', t.value)

    # -- amount ------------------------------------------------------------
    def amount(self, children):
        for c in children:
            if isinstance(c, Token):
                if c.type == 'NUMBER':
                    return int(c.value)
                if c.value == 'X':
                    return 'X'
                return c.value
            if isinstance(c, Tree):
                return c
        return None

    # -- colors -------------------------------------------------------------
    def color(self, children):
        for c in children:
            if isinstance(c, Token):
                return c.value.lower()
        return None

    def colors(self, children):
        vals = []
        for c in children:
            if isinstance(c, Token):
                vals.append(c.value.lower())
            elif isinstance(c, Tree) and c.data == 'color':
                vals.append(c)
            elif isinstance(c, str):
                vals.append(c.lower())
        return vals

    # -- types --------------------------------------------------------------
    def types(self, children):
        for c in children:
            if isinstance(c, Token):
                if c.type == 'CARDNAME':
                    return self._resolve_kind(c.value)
                return {'kind': 'type', 'value': c.value.lower()}
        return None

    def GENERIC_TYPE(self, t):
        return Token('GENERIC_TYPE', t.value)

    def CARDNAME(self, t):
        return Token('CARDNAME', t.value)

    def STATUS(self, t):
        return Token('STATUS', t.value)

    # -- card_target atomic pieces -----------------------------------------
    def quantifier(self, children):
        toks = [c for c in children if isinstance(c, Token)]
        trees = [c for c in children if isinstance(c, Tree)]
        words = [t.value for t in toks]
        if 'up' in words and 'to' in words:
            n = self._first_number(children)
            return {'up_to': n}
        # a bare number as quantifier, e.g. "two creatures"
        if len(words) == 1 and words[0].isdigit():
            return int(words[0])
        if trees:
            return trees[0]
        if words:
            return words[0]
        return None

    def _first_number(self, children):
        for c in children:
            if isinstance(c, Token) and c.type == 'NUMBER':
                return int(c.value)
            if isinstance(c, Tree) and c.data == 'amount':
                return c
        return None

    def otherness(self, children):
        for c in children:
            if isinstance(c, Token):
                return c.value
        return None

    def status_list(self, children):
        out = []
        for c in children:
            if isinstance(c, Token):
                out.append(c.value)
        return out

    def THIS_CARD(self, t):
        return Token('THIS_CARD', '~')

    def card_kind(self, children):
        for c in children:
            if isinstance(c, Tree) and c.data == 'types':
                return c
            if isinstance(c, Token):
                if c.type == 'THIS_CARD':
                    return {'kind': 'this_card', 'value': '~'}
                if c.type == 'CARDNAME':
                    return self._resolve_kind(c.value)
                return {'kind': 'type', 'value': c.value.lower()}
        return None

    def with_modifier(self, children):
        return self._txt(children)

    def controller(self, children):
        return self._txt(children)

    def in_zone(self, children):
        # returns (preposition, zone)
        prep = None
        zone = None
        for c in children:
            if isinstance(c, Token):
                if c.value in ('in', 'from', 'on'):
                    prep = c.value
                else:
                    zone = c.value
            elif isinstance(c, Tree) and c.data == 'zone':
                zone = c
        return {'prep': prep, 'zone': zone}

    def this_that(self, children):
        for c in children:
            if isinstance(c, Token):
                return c.value
        return None

    def possessive(self, children):
        for c in children:
            if isinstance(c, Token):
                return c.value
        return None

    def nontoken(self, children):
        return [c.value if isinstance(c, Token) else c for c in children]

    def card_target(self, children):
        d = {}
        for c in children:
            if not isinstance(c, Tree):
                continue
            name = c.data
            if name == 'this_that':
                d['this_that'] = c
            elif name == 'possessive':
                d['possessive'] = c
            elif name == 'quantifier':
                d['quantifier'] = c
            elif name == 'otherness':
                d['otherness'] = c
            elif name == 'nontoken':
                d['nontoken'] = c
            elif name == 'status_list':
                d['status'] = c
            elif name == 'colors':
                d['colors'] = c
            elif name == 'card_kind':
                d['card_type'] = c
            elif name == 'with_modifier':
                d['modifier'] = c
            elif name == 'controller':
                d['controller'] = c
            elif name == 'in_zone':
                d['zone'] = c
            elif name == 'zone':
                d['zone'] = c
        return d

    # -- zone ---------------------------------------------------------------
    def ZONE_WORD(self, t):
        return Token('ZONE_WORD', t.value)

    def zone(self, children):
        for c in children:
            if isinstance(c, Token) and c.type == 'ZONE_WORD':
                return c.value
            if isinstance(c, Tree):
                return c
        return None

    # -- player / who --------------------------------------------------------
    def player(self, children):
        toks = [c.value for c in children if isinstance(c, Token)]
        return ' '.join(toks).strip() or (children[0] if children else None)

    def who(self, children):
        return children[0] if children else None

    # -- keyword lists -------------------------------------------------------
    def KEYWORD(self, t):
        return Token('KEYWORD', t.value)

    def kw_list(self, children):
        out = []
        for c in children:
            if isinstance(c, Token):
                out.append(c.value)
            elif isinstance(c, Tree):
                out.append(c)
        return out

    def kw_with_mod(self, children):
        key = None
        mod = None
        for c in children:
            if isinstance(c, Token):
                if key is None:
                    key = c.value
                else:
                    mod = c.value
            elif isinstance(c, Tree):
                if key is None:
                    key = c
                else:
                    mod = c
        return {'keyword': key, 'modifier': mod}

    # -- static keyword sentence -------------------------------------------
    def static_keyword_sentence(self, children):
        return {'type': 'static_keyword', 'keywords': children[0]}

    # -- modal --------------------------------------------------------------
    def modal_sentence(self, children):
        return {'type': 'modal', 'text': self._txt(children)}

    # -- loyalty -------------------------------------------------------------
    def LOY_COST(self, t):
        return Token('LOY_COST', t.value)

    def loyalty_sentence(self, children):
        cost = children[0]
        eff = children[1] if len(children) > 1 else None
        return {'type': 'loyalty', 'cost': cost, 'effect': eff}

    # -- triggered -----------------------------------------------------------
    def trig_when(self, children):
        return self._txt(children)

    def AT_WHEN(self, t):
        return Token('AT_WHEN', t.value)

    def EVENT_VERB(self, t):
        return Token('EVENT_VERB', t.value)

    def event_subject(self, children):
        return children[0] if children else None

    def event_object(self, children):
        return self._txt(children) or None

    def event(self, children):
        d = {}
        for c in children:
            if isinstance(c, Token):
                if c.type == 'EVENT_VERB':
                    d['verb'] = c.value
                else:
                    d.setdefault('text', []).append(c.value)
            elif isinstance(c, Tree):
                if c.data == 'event_subject':
                    d['subject'] = c
                elif c.data == 'event_object':
                    d['object'] = c
        if 'text' in d:
            d['text'] = ' '.join(d['text'])
        return d

    def condition(self, children):
        return children[0] if children else None

    def cond(self, children):
        return self._txt(children)

    def if_clause(self, children):
        return self._txt(children)

    def static_text(self, children):
        return self._txt(children)

    def trigger_clause(self, children):
        d = {}
        for c in children:
            if isinstance(c, Tree):
                if c.data == 'trig_when':
                    d['when'] = c
                elif c.data == 'event':
                    d['event'] = c
                elif c.data == 'condition':
                    d['condition'] = c
                elif c.data == 'static_text':
                    d['text'] = c
            elif isinstance(c, Token):
                d.setdefault('keywords', []).append(c.value)
        return d

    def triggered_sentence(self, children):
        d = {}
        for c in children:
            if isinstance(c, Tree):
                if c.data == 'trigger_clause':
                    d['trigger'] = c
                elif c.data == 'effect':
                    d.setdefault('effect', []).append(c)
                elif c.data == 'if_clause':
                    d['if'] = c
        if len(d.get('effect', [])) == 1:
            d['effect'] = d['effect'][0]
        return {'type': 'triggered', **d}

    # -- activated -----------------------------------------------------------
    def cost_item(self, children):
        return self._txt(children) or (children[0] if children else None)

    def cost_list(self, children):
        return list(children)

    def activated_sentence(self, children):
        return {'type': 'activated', 'cost': children[0], 'effect': children[1]}

    # -- effect / actions ----------------------------------------------------
    def effect(self, children):
        return list(children)

    def JOIN(self, t):
        return Token('JOIN', t.value)

    def _action_base(self, verb, children):
        d = {'verb': verb}
        for c in children:
            if isinstance(c, Tree):
                d.setdefault('args', []).append(c)
            elif isinstance(c, Token):
                d.setdefault('raw', []).append(c.value)
        if 'raw' in d and len(d['raw']) == 1:
            d['raw'] = d['raw'][0]
        return d

    def add_mana_action(self, children):
        return {'verb': 'add_mana', 'amount': children[-1] if children else None}

    def create_token_action(self, children):
        return {'verb': 'create_token', 'token': children[-1] if children else None}

    def token(self, children):
        d = {}
        for c in children:
            if isinstance(c, Tree):
                if c.data == 'card_target':
                    d['copy_of'] = c
                elif c.data == 'kw_list':
                    d.setdefault('kw', []).append(c)
                elif c.data == 'colors':
                    d['colors'] = c
                elif c.data in ('token_types', 'token_num', 'xdef'):
                    d[c.data] = c
            elif isinstance(c, Token):
                if c.type == 'POWER_T':
                    d['power_toughness'] = c.value
                elif c.type == 'CARDNAME':
                    d.setdefault('types', []).append(c.value)
        return d

    def token_num(self, children):
        return children[0] if children else None

    def token_types(self, children):
        return [c.value if isinstance(c, Token) else c for c in children]

    def token_except(self, children):
        out = []
        for c in children:
            if isinstance(c, Tree):
                if c.data == 'kw_list':
                    out.append({'except_has': c})
            elif isinstance(c, Token):
                out.append(c.value)
        return out

    def counter_kind(self, children):
        d = {}
        for c in children:
            if isinstance(c, Token):
                if c.type == 'POWER_MOD':
                    d['stat'] = c.value
                elif c.value == 'counter' or c.value == 'counters':
                    pass
            elif isinstance(c, Tree) and c.data == 'counter_name':
                d['name'] = c
        return d

    def damage_who(self, children):
        d = {}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d.setdefault('targets', []).append(c)
            elif isinstance(c, Token):
                d.setdefault('words', []).append(c.value)
        if 'words' in d:
            d['words'] = ' '.join(d['words'])
        return d

    def enters_action(self, children):
        d = {'verb': 'enters'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def enchant_action(self, children):
        return {'verb': 'enchant', 'target': children[-1] if children else None}

    def enchant_target(self, children):
        return [c.value if isinstance(c, Token) else c for c in children]

    def cant_action(self, children):
        d = {'verb': "can't"}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def no_max_hand_action(self, children):
        return {'verb': 'no_max_hand_size'}

    def can_gain_life_action(self, children):
        return {'verb': "players_can't_gain_life"}

    def attacks_each_combat_action(self, children):
        d = {'verb': 'attacks_each_combat'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def put_counter_action(self, children):
        d = {'verb': 'put_counter'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['on'] = c
            elif isinstance(c, Tree) and c.data == 'counter_amount':
                d['counters'] = c
        return d

    def remove_counter_action(self, children):
        d = {'verb': 'remove_counter'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['from'] = c
            elif isinstance(c, Tree) and c.data == 'counter_amount':
                d['counters'] = c
        return d

    def counter_amount(self, children):
        return self._txt(children) or (children[0] if children else None)

    def counter_name(self, children):
        return self._txt(children)

    def search_action(self, children):
        return self._action_base('search', children)

    def draw_action(self, children):
        d = {'verb': 'draw'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['cards'] = c
            elif isinstance(c, Tree) and c.data == 'amount':
                d['amount'] = c
        return d

    def life_amount(self, children):
        return self._txt(children) or (children[0] if children else None)

    def gain_life_action(self, children):
        d = {'verb': 'gain_life'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'who':
                d['who'] = c
            elif isinstance(c, Tree) and c.data == 'life_amount':
                d['amount'] = c
        return d

    def lose_life_action(self, children):
        d = {'verb': 'lose_life'}
        for c in children:
            if isinstance(c, Tree) and c.data in ('who', 'player'):
                d['who'] = c
            elif isinstance(c, Tree) and c.data == 'life_amount':
                d['amount'] = c
        return d

    def damage_amount(self, children):
        return self._txt(children) or (children[0] if children else None)

    def damage_target(self, children):
        return self._txt(children) or (children[0] if children else None)

    def deal_damage_action(self, children):
        d = {'verb': 'deal_damage'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d.setdefault('source_or_target', c)
            elif isinstance(c, Tree) and c.data in ('damage_amount', 'damage_target'):
                d[c.data] = c
        return d

    def counter_spell_action(self, children):
        d = {'verb': 'counter'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['spell'] = c
        return d

    def return_action(self, children):
        d = {'verb': 'return'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        d['to'] = self._txt([c for c in children if not (isinstance(c, Tree) and c.data == 'card_target')])
        return d

    def put_zone_action(self, children):
        d = {'verb': 'put', 'args': [c for c in children if isinstance(c, Tree)]}
        d['rest'] = self._txt([c for c in children if isinstance(c, Token)])
        return d

    def exile_action(self, children):
        d = {'verb': 'exile'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def destroy_action(self, children):
        d = {'verb': 'destroy'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def tap_action(self, children):
        d = {'verb': 'tap'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def untap_action(self, children):
        d = {'verb': 'untap'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def sacrifice_action(self, children):
        d = {'verb': 'sacrifice'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def gain_control_action(self, children):
        d = {'verb': 'gain_control'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def scry_action(self, children):
        return {'verb': 'scry', 'amount': children[-1] if children else None}

    def surveil_action(self, children):
        return {'verb': 'surveil', 'amount': children[-1] if children else None}

    def mill_action(self, children):
        d = {'verb': 'mill'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'amount':
                d['amount'] = c
            elif isinstance(c, Tree) and c.data == 'player':
                d['who'] = c
        return d

    def fight_action(self, children):
        d = {'verb': 'fight'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['target'] = c
        return d

    def attach_action(self, children):
        d = {'verb': 'attach'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['to'] = c
        return d

    def POWER_MOD(self, t):
        return Token('POWER_MOD', t.value)

    def stat_change(self, children):
        return self._txt(children) or [c for c in children if isinstance(c, Tree)]

    def stat_action(self, children):
        d = {'verb': 'stat_change'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['target'] = c
            elif isinstance(c, Tree) and c.data == 'stat_change':
                d['change'] = c
        return d

    def gain_kw_action(self, children):
        d = {'verb': 'gain_kw'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['target'] = c
            elif isinstance(c, Tree) and c.data == 'kw_list':
                d['keywords'] = c
        return d

    def prevent_action(self, children):
        d = {'verb': 'prevent_damage'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def look_action(self, children):
        return self._action_base('look', children)

    def reveal_action(self, children):
        d = {'verb': 'reveal'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def discard_action(self, children):
        d = {'verb': 'discard'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def shuffle_action(self, children):
        return {'verb': 'shuffle'}

    def cast_action(self, children):
        d = {'verb': 'cast'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def play_action(self, children):
        d = {'verb': 'play'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def xdef_clause(self, children):
        return {'xdef': children[-1] if children else None}

    def xdef(self, children):
        return self._txt(children) or (children[0] if children else None)

    def effect_sentence(self, children):
        d = {'type': 'effect'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'effect':
                d['effect'] = c
            elif isinstance(c, Tree) and c.data == 'xdef_clause':
                d['xdef'] = c
        return d

    # -- new sentence / action types ----------------------------------------
    def if_sentence(self, children):
        return {'type': 'if', 'text': self._txt(children)}

    def static_sentence(self, children):
        return {'type': 'static', 'text': self._txt(children)}

    def may_action(self, children):
        inner = None
        for c in children:
            if isinstance(c, Tree) and c.data not in ('V_YOU', 'V_MAY'):
                inner = c
        return {'verb': 'may', 'inner': inner}

    def cost_mod_action(self, children):
        d = {'verb': 'cost_mod'}
        for c in children:
            if isinstance(c, Tree) and c.data == 'card_target':
                d['card'] = c
        return d

    def emblem_action(self, children):
        d = {'verb': 'emblem'}
        for c in children:
            if isinstance(c, Token) and c.type == 'QUOTE':
                d['quote'] = c.value
        return d

    def kw_item(self, children):
        return self._txt(children)

    def kw_list_mod(self, children):
        return [c for c in children if c is not None]

    # -- raw / fallback ------------------------------------------------------
    def any_text(self, children):
        return self._txt(children)

    def raw_action(self, children):
        return {'verb': 'raw', 'text': self._txt(children)}

    # -- top -----------------------------------------------------------------
    def sentence(self, children):
        return children[0] if children else None

    def start(self, children):
        return [c for c in children if c is not None]


def _tree_text(tree):
    parts = []
    def walk(n):
        if isinstance(n, Token):
            parts.append(n.value)
        elif isinstance(n, Tree):
            for ch in n.children:
                walk(ch)
    walk(tree)
    return ' '.join(parts)
