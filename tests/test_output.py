#!/usr/bin/env python3
"""Golden output tests: lock in the interpreter fixes (regression guard).

Each case is (name, sentence, predicate); predicate(output) is True iff the
interpreted output has the expected structure. Hand-written for the known
silent-bug classes, so a regressing fix fails loudly here.

Usage:  python test_output.py [data.json]      # default classic.json
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys, os
BASE = _paths.ROOT
sys.path.insert(0, BASE)
from larkparser import build_parser
from setdata import load
from preprocess import segment
from interpret import Interpreter

def has(obj, pred):
    """Recursively: does any node satisfy pred?"""
    if isinstance(obj, dict):
        try:
            if pred(obj):
                return True
        except Exception:
            pass
        return any(has(v, pred) for v in obj.values())
    if isinstance(obj, list):
        return any(has(v, pred) for v in obj)
    try:
        return bool(pred(obj))
    except Exception:
        return False

T = []
def add(name, sent, pred):
    T.append((name, sent, pred))

add("keywords-list", "Flying, first strike, and deathtouch",
    lambda o: has(o, lambda d: isinstance(d.get('keywords'), list)
                  and {'Flying', 'first strike', 'deathtouch'} <= set(d['keywords'])))
add("attach-target-controller",
    "When this Equipment enters, attach it to target creature you control",
    lambda o: has(o, lambda d: d.get('verb') == 'attach'
                  and d.get('to', {}).get('controller') == 'you control'))
add("exile-each-opponent-graveyard",
    "{T}, Sacrifice this artifact: Exile each opponent's graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'
                  and d.get('possessor') == 'each opponent'))
add("exile-top-each-player",
    "Whenever this creature attacks, exile the top card of each player's library",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'
                  and d.get('top') is True and d.get('possessor') == 'each player'))
add("each-of-up-to",
    "When this creature enters, put a +1/+1 counter on each of up to two other target creatures you control",
    lambda o: has(o, lambda d: d.get('on', {}).get('quantifier') == {'up_to': 2}
                  and d.get('on', {}).get('otherness') == 'other'))
add("coordinated-stat-targets",
    "Skeletons you control and other Zombies you control get +1/+1 and have deathtouch",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and len(d.get('cards', [])) == 2))
add("as-long-as-condition",
    "This creature has flying as long as it's attacking",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and isinstance(d.get('condition'), dict)
                  and d['condition'].get('kind') == 'state'
                  and d['condition'].get('state', {}).get('status') == 'attacking'))
add("if-able-on-action",
    "Each creature you control gets +3/+3 until end of turn and must be blocked this turn if able",
    lambda o: has(o, lambda d: d.get('verb') == 'must_block'
                  and d.get('if_able') is True)
                  and not has(o, lambda d: d.get('type') == 'effect' and d.get('if')))
add("page-counter-condition",
    "When there are four or more page counters on this artifact, exile it",
    lambda o: has(o, lambda d: isinstance(d.get('condition'), dict)
                  and d['condition'].get('kind') == 'count'
                  and d['condition'].get('quantity') == {'at_least': 4}
                  and 'page counters' in str(d['condition'].get('of', {}))))
add("during-turn-event",
    "Whenever a creature you control deals combat damage during your turn, put that many +1/+1 counters on it",
    lambda o: has(o, lambda d: d.get('condition') == 'during your turn'))
add("event-during-subject-verb",
    "Whenever an opponent loses life during your turn, you draw that many cards",
    lambda o: has(o, lambda d: d.get('verb') == 'loses'
                  and d.get('subject') == 'an opponent'
                  and d.get('condition') == 'during your turn'))
add("enchanted-for-each-no-empty-card",
    "Enchanted creature gets +1/+1 for each Forest you control",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and all(c for c in d.get('cards', []))))
add("coordinated-condition",
    "Delirium — This creature gets +1/+1 and has trample as long as there are four or more card types among cards in your graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and d.get('condition'))
                  and has(o, lambda d: isinstance(d.get('effect'), list)
                          and all(a.get('condition') for a in d['effect']
                                  if isinstance(a, dict))))
add("coordinated-cards-controller",
    "Skeletons you control and other Zombies you control get +1/+1 and have deathtouch",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and len(d.get('cards', [])) == 2))
add("shuffle-two-sources",
    "Each player may shuffle their hand and graveyard into their library",
    lambda o: has(o, lambda d: d.get('verb') == 'shuffle'
                  and d.get('from') == ['hand', 'graveyard']))
add("prevent-by-only",
    "Prevent all combat damage that would be dealt by nongreen creatures this turn",
    lambda o: has(o, lambda d: d.get('verb') == 'prevent_damage'
                  and d.get('by') and 'to' not in d))
add("zone-possessor",
    "Whenever this creature deals combat damage to a player, you may cast target nonland permanent card from that player's graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'cast'
                  and d.get('card', {}).get('zone', {}).get('possessor') == "that player's"))
add("delirium-static-effect",
    "Delirium — This creature gets +1/+1 and has trample as long as there are four or more card types among cards in your graveyard",
    lambda o: has(o, lambda d: d.get('type') == 'static'
                  and d.get('ability_word') == 'Delirium'
                  and isinstance(d.get('effect'), list)))
add("shuffle-zones",
    "{T}, Exile this artifact: Shuffle your graveyard into your library",
    lambda o: has(o, lambda d: d.get('verb') == 'shuffle'
                  and d.get('from') == 'graveyard' and d.get('to') == 'library'))
add("prevent-to-and-by",
    "Prevent all combat damage that would be dealt to and dealt by this creature",
    lambda o: has(o, lambda d: d.get('verb') == 'prevent_damage'
                  and d.get('to') and d.get('by')))
add("second-damage-source",
    "Whenever this creature attacks, it deals 4 damage to any target and 3 damage to each of up to two other targets",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage'
                  and d.get('amount') == 3 and d.get('source')))
add("pay-life-amount", "Whenever a Vampire you control dies, you may pay 2 life",
    lambda o: has(o, lambda d: d.get('verb') == 'pay'
                  and d.get('amount') == {'kind': 'number', 'value': 2,
                                          'unit': 'life'}))
add("for-each-colors",
    "Whenever you cast a spell, put a +1/+1 counter on this creature for each of that spell's colors",
    lambda o: has(o, lambda d: d.get('for_each', {}).get('colors') is True))
add("spend-mana-any-type",
    "You can spend mana of any type to cast creature spells",
    lambda o: has(o, lambda d: d.get('verb') == 'spend_mana_only_to_cast'
                  and d.get('mana') == 'any type'))
add("add-mana-bare", "Add {R}",
    lambda o: has(o, lambda d: d.get('verb') == 'add_mana'
                  and d.get('amount') == {'kind': 'mana',
                                          'symbols': ['{R}']}))
add("waterbend-not-keyword",
    "Waterbend {4}: Target creature can't be blocked this turn",
    lambda o: has(o, lambda d: d.get('type') == 'activated'
                  and d.get('ability_word') == 'Waterbend')
                  and not has(o, lambda d: d.get('type') == 'static_keyword'))
add("activated-prefix-not-keyword",
    "Activated abilities of artifacts you control cost {1} less to activate",
    lambda o: has(o, lambda d: d.get('type') == 'effect')
                  and has(o, lambda d: d.get('verb') == 'cost_mod')
                  and not has(o, lambda d: d.get('type') == 'static_keyword'))
add("activated-if-condition",
    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature",
    lambda o: has(o, lambda d: d.get('type') == 'activated'
                  and "isn't a creature" in str(d.get('if', ''))))
add("cost-mod-shared-cast",
    "Instant and sorcery spells you cast with mana value 4 or greater cost {X} less to cast",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and all(c.get('cast_by') == 'you' for c in d.get('cards', []))))
add("extra-turns-no-empty-actor",
    "Time Compression — When this creature transforms into this creature, take an extra turn after this one",
    lambda o: has(o, lambda d: d.get('verb') == 'extra_turns'
                  and 'actor' not in d))
add("ward-full-cost", "Ward—Pay 2 life",
    lambda o: has(o, lambda d: d.get('keyword') == 'Ward'
                  and d.get('cost', {}).get('action') == 'pay_life'
                  and d.get('cost', {}).get('amount') == 2))
add("flashback-full-cost", "Flashback {2}{B}{B}",
    lambda o: has(o, lambda d: d.get('cost', {}).get('action') == 'pay_mana'
                  and d.get('cost', {}).get('mana') == '{2}{B}{B}'))
add("multiple-keywords-with-mod",
    "Lifelink, hexproof from instants",
    lambda o: has(o, lambda d: isinstance(d.get('keywords'), list)
                  and len(d['keywords']) == 2))
add("become-tail-keywords",
    "{4}: This land becomes a 3/3 creature with vigilance and all creature types",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('keywords') == ['vigilance']
                  and d.get('all_creature_types') is True))
add("become-named",
    "Enchanted creature loses all abilities and is a green and white Citizen creature with base power and toughness 1/1 named Legitimate Businessperson",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('named') == 'Legitimate Businessperson'))
add("become-lose-types-no-all-creature",
    "Enchanted permanent is a colorless land with \"{T}: Add {C}\" and loses all other card types and abilities",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and 'all_creature_types' not in d
                  and d.get('quote') == '"{T}: Add {C}"'
                  and d.get('loses_all_other_card_types_and_abilities') is True))
add("lose-keywords-otherness",
    "Lizard Formula — When this creature enters, up to one other target creature loses all abilities and becomes a green Lizard creature with base power and toughness 4/4",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_keywords'
                  and d.get('target', {}).get('otherness') == 'other'))
add("cost-mod-filter-shared",
    "Instant and sorcery spells you cast with mana value 4 or greater cost {X} less to cast",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and all(c.get('modifier') for c in d.get('cards', []))))
add("cost-mod-subject",
    "Dragon spells you cast cost {1} less to cast",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and 'Dragon' in str(d.get('target', ''))))
add("cost-mod-opponents",
    "Noncreature spells your opponents cast cost {1} more to cast",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and d.get('target', {}).get('cast_by') == 'your opponents'))
add("cost-mod-conjunction",
    "Kithkin spells and Soldier spells you cast cost {1} less to cast",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and len(d.get('cards', [])) == 2))
add("stat-define-singular-power",
    "~'s power is equal to the number of artifacts you control",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_define'
                  and d.get('stat') == 'power' and d.get('subject') == '~'))
add("stat-define-toughness-split",
    "~'s power is equal to the number of card types among cards in all graveyards and its toughness is equal to that number plus 1",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_define'
                  and d.get('toughness_value') == 'that number plus 1'))
add("hexproof-from-color", "Reach, hexproof from blue",
    lambda o: has(o, lambda d: 'hexproof from blue' in str(d.get('keywords', ''))))
add("cost-direction-more",
    "This spell costs {2} more to cast if it targets a Dragon",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and d.get('direction') == 'more'))
add("cost-name-equal",
    "The embalm cost is equal to its mana cost",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and d.get('cost_name') == 'embalm'))
add("become-duration",
    "Until end of turn, this creature becomes a Plant with base power and toughness 0/8",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}))
add("anaphora-not-type", "It gains haste until end of turn",
    lambda o: has(o, lambda d: d.get('ref') == 'anaphora'))
add("gain-kw-duration", "It gains haste until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}))
add("stat-duration", "Target creature gets +2/+0 until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}))
add("coordinated-duration",
    "Target creature gets +1/+0 and gains first strike until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}))
add("until-in-activated-duration",
    "{3}: Until end of turn, this creature loses defender and gains flying",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_keywords'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}))
add("become-base-pt",
    "Until end of turn, this creature becomes a Plant with base power and toughness 0/8",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('base_pt') == {'power': 0, 'toughness': 8}))
add("become-generic-types",
    "If it's a Vehicle, it becomes an artifact creature",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and {'artifact', 'creature'} <= set(d.get('types', []))))
add("become-in-addition",
    "It becomes a 0/0 Bird creature with flying in addition to its other types",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('in_addition') is True))
add("without-flying-target",
    "Creatures without flying can't block this turn",
    lambda o: has(o, lambda d: d.get('without_keywords') == ['flying']))
add("choice-of-keywords",
    "Target creature gets +1/+1 and gains your choice of deathtouch or lifelink until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and d.get('your_choice') is True))
add("put-under-your-control",
    "Put up to two creature cards from graveyards onto the battlefield under your control",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and d.get('controller') == 'you control'))
add("activated-xdef",
    "{4}{R}{G}: ~ gets +X/+X until end of turn, where X is the number of lands you control",
    lambda o: has(o, lambda d: d.get('type') == 'activated' and d.get('xdef')))
add("search-named-qualifier",
    "When this creature enters, you may search your library for up to three cards named ~, reveal them, put them into your hand, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'search'
                  and d.get('named') == '~'))
add("sacrifice-delayed-timing",
    "Sacrifice it at the beginning of your next end step",
    lambda o: has(o, lambda d: d.get('verb') == 'sacrifice'
                  and d.get('timing') == {'position': 'beginning', 'player': 'you', 'which': 'next', 'phase': 'end_step'}))
add("play-permission-duration", "You may play those cards this turn",
    lambda o: has(o, lambda d: d.get('verb') == 'play'
                  and d.get('duration') == {'kind': 'for', 'event': 'this_turn'}))
add("cast-without-paying",
    "You may cast that card without paying its mana cost",
    lambda o: has(o, lambda d: d.get('verb') == 'cast'
                  and d.get('without_paying') is True))
add("cast-from-among",
    "You may cast any number of spells from among them without paying their mana costs",
    lambda o: has(o, lambda d: d.get('verb') == 'cast'
                  and d.get('from_among', {}).get('card_type', {}).get('raw') == 'them'))
add("may-actor",
    "Its controller may search their library for a basic land card, put it onto the battlefield tapped, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'may'
                  and d.get('who') == 'Its controller'))
add("coordinated-who",
    "Target player draws three cards and loses 3 life",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_life'
                  and d.get('who') == 'Target player'))
add("mill-actor", "Target player mills four cards",
    lambda o: has(o, lambda d: d.get('verb') == 'mill'
                  and d.get('who') == 'Target player'))
add("mill-no-actor-no-empty-who", "Mill four cards",
    lambda o: has(o, lambda d: d.get('verb') == 'mill'
                  and 'who' not in d))
add("mill-singular-amount", "Mill a card",
    lambda o: has(o, lambda d: d.get('verb') == 'mill'
                  and d.get('amount') == 1))
add("gain-life-no-empty-who",
    "Whenever you put one or more +1/+1 counters on a creature, you may gain that much life",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_life'
                  and d.get('who') != {})
                  and not has(o, lambda d: d.get('who') == {}))
add("look-possessor", "As this creature enters, look at an opponent's hand",
    lambda o: has(o, lambda d: d.get('verb') == 'look'
                  and d.get('possessor') == "an opponent's"))
add("cant-block-duration", "Target creature can't block this turn",
    lambda o: has(o, lambda d: d.get('verb') == "can't"
                  and d.get('duration') == {'kind': 'for', 'event': 'this_turn'}))
add("prevent-damage-object-duration",
    "Until your next turn, prevent all damage that would be dealt to you",
    lambda o: has(o, lambda d: d.get('verb') == 'prevent_damage'
                  and d.get('object') == 'damage'
                  and d.get('to') == 'you'
                  and d.get('duration') == {'kind': 'until', 'event': 'next_turn', 'player': 'you'}))
add("prevent-combat-kind-this-turn",
    "Prevent all combat damage that would be dealt this turn",
    lambda o: has(o, lambda d: d.get('verb') == 'prevent_damage'
                  and d.get('damage') == 'combat'
                  and d.get('duration') == {'kind': 'for', 'event': 'this_turn'}))
add("damage-cant-be-prevented",
    "The damage can't be prevented",
    lambda o: has(o, lambda d: d.get('verb') == "can't"
                  and d.get('predicate') == 'be prevented'))
add("may-gain-life-actor",
    "You may gain 4 life",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_life'
                  and d.get('who') == 'You'))
add("cast-permission-as-long",
    "You may cast this card for as long as it remains exiled",
    lambda o: has(o, lambda d: d.get('verb') == 'cast'
                  and d.get('duration') == 'for as long as it remains exiled'))
add("no-max-hand-duration",
    "You have no maximum hand size for the rest of the game",
    lambda o: has(o, lambda d: d.get('verb') == 'no_max_hand_size'
                  and d.get('duration') == {'kind': 'for', 'event': 'rest_of_game'}))
add("until-sentence-duration",
    "Until the end of your next turn, you may play those cards",
    lambda o: has(o, lambda d: d.get('type') == 'until'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn', 'which': 'next', 'player': 'you'}))
add("effect-timing-delayed",
    "At the beginning of the next end step, return those creatures to their owner's hand",
    lambda o: has(o, lambda d: d.get('verb') == 'return'
                  and d.get('timing') == {'position': 'beginning', 'which': 'next', 'phase': 'end_step'}))
add("gain-quote-duration-keywords",
    '{T}: Until end of turn, target creature you control gains trample and "Whenever this creature deals combat damage to a player, draw a card."',
    lambda o: has(o, lambda d: d.get('verb') == 'gain_quote'
                  and d.get('duration') == {'kind': 'until', 'event': 'end_of_turn'}
                  and d.get('keywords') == ['trample']))
add("passive-damage-object",
    "Whenever this creature is dealt damage, destroy it",
    lambda o: has(o, lambda d: d.get('verb') == 'is dealt'
                  and d.get('object') == 'damage'
                  and 'damage' not in d))
add("draw-amount-int", "Draw two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('amount') == 2))
add("up-to-quantifier", "Discard up to two cards",
    lambda o: has(o, lambda d: d.get('card', {}).get('quantifier') == {'up_to': 2}))
add("other-target",
    "When this creature enters, destroy up to one other target creature",
    lambda o: has(o, lambda d: d.get('card', {}).get('otherness') == 'other'
                  and d.get('card', {}).get('quantifier') == {'up_to': 1}))
add("one-or-more-quantifier",
    "Whenever one or more creatures you control attack, you gain life equal to the number of attacking creatures",
    lambda o: has(o, lambda d: d.get('quantifier') == {'one_or_more': 1}))
add("for-each-gain-life",
    "When this creature enters, you gain 2 life for each Gate you control",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_life'
                  and d.get('for_each', {}).get('card_type', {}).get('value') == 'Gate'))
add("for-each-cost-mod",
    "This spell costs {1} less to cast for each instant and sorcery card in your graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and 'instant' in str(d.get('for_each', ''))))
add("for-each-put-counter",
    "Whenever you cast a spell, put a +1/+1 counter on this creature for each of that spell's colors",
    lambda o: has(o, lambda d: d.get('verb') == 'put_counter'
                  and d.get('for_each')))
add("fight-second-target",
    "Target creature you control fights target creature an opponent controls",
    lambda o: has(o, lambda d: d.get('verb') == 'fight'
                  and d.get('fights', {}).get('controller') == 'an opponent controls'))
add("life-total-equal", "your life total becomes equal to X",
    lambda o: has(o, lambda d: d.get('verb') == 'life_total'
                  and d.get('amount') == {'kind': 'x'}))
add("xdef-your-speed",
    "Noncreature spells you cast cost {X} less to cast, where X is your speed",
    lambda o: has(o, lambda d: 'speed' in str(d.get('xdef', ''))))
add("become-prepared", "Target creature becomes prepared",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('state') == 'prepared'))
add("become-copy-source",
    "This creature becomes a copy of another target creature you control",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('copy_of', {}).get('otherness') == 'another'))
add("quantified-become-target",
    "Until end of turn, target creature loses all abilities and becomes a blue Frog with base power and toughness 1/1",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('target', {}).get('quantifier') == 'target'))
add("two-exile-targets",
    "Exile up to one target artifact and up to one target enchantment",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'
                  and len(d.get('cards', [])) == 2))
add("second-put-counter",
    "When this creature enters, put a +1/+1 counter on it and a +1/+1 counter on this creature",
    lambda o: has(o, lambda d: d.get('verb') == 'put_counter' and d.get('and')))
add("that-pile-other-destination",
    "Put that pile into your hand and the other into your graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and d.get('card') == 'that pile'
                  and d.get('rest_zone') == 'graveyard'))
add("or-pay-cost",
    "As an additional cost to cast this spell, sacrifice a creature or pay {3}{B}",
    lambda o: has(o, lambda d: d.get('verb') == 'sacrifice'
                  and d.get('or_pay') == '{3} {B}'))
add("instead-replacement-marker",
    "If this spell was kicked, instead choose any number of target creatures you own",
    lambda o: has(o, lambda d: d.get('verb') == 'choose' and d.get('instead') is True))
add("otherwise-else-branch", "Otherwise, you lose 2 life",
    lambda o: has(o, lambda d: d.get('type') == 'effect'
                  and d.get('otherwise') is True))
add("replace-token-doubling",
    "If one or more tokens would be created under your control, twice that many of those tokens are created instead",
    lambda o: has(o, lambda d: d.get('verb') == 'replace_tokens'
                  and d.get('multiplier') == 2 and d.get('instead') is True))
add("replace-damage-doubling",
    "If a creature you control that entered this turn would deal damage, it deals twice that much damage instead",
    lambda o: has(o, lambda d: d.get('verb') == 'replace_damage'
                  and d.get('multiplier') == 2))
add("skip-that-draw",
    "If you would draw a card while your library has no cards in it, skip that draw instead",
    lambda o: has(o, lambda d: d.get('verb') == 'skip'
                  and d.get('object') == 'draw'))
add("life-total-equal", "your life total becomes equal to X",
    lambda o: has(o, lambda d: d.get('verb') == 'life_total'
                  and d.get('amount') == {'kind': 'x'}))
add("xdef-your-speed",
    "Noncreature spells you cast cost {X} less to cast, where X is your speed",
    lambda o: has(o, lambda d: 'speed' in str(d.get('xdef', ''))))
add("become-prepared",
    "Then if an opponent controls more creatures than you, this creature becomes prepared",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('state') == 'prepared'))
add("amass-consequence",
    "If this spell was cast from a graveyard, amass Goblins 3 instead",
    lambda o: has(o, lambda d: d.get('verb') == 'amass'
                  and d.get('type') == 'Goblins' and d.get('amount') == 3))
add("recruit-consequence",
    "If that spell's mana value was 2 or less, recruit",
    lambda o: has(o, lambda d: d.get('verb') == 'recruit'))
add("repeat-process",
    "If two cards that share a card type were milled this way, draw a card and repeat this process",
    lambda o: has(o, lambda d: d.get('verb') == 'repeat'
                  and d.get('also', {}).get('verb') == 'draw'))
add("assign-damage-as-though-positive",
    "If this creature's power is negative, he assigns combat damage as though his power were positive",
    lambda o: has(o, lambda d: d.get('verb') == 'assign_combat_damage'
                  and d.get('as_though') == 'positive power'))
add("remove-counter-and-damage",
    "Then if there are seven or more time counters on it, remove those counters and it deals 20 damage to you",
    lambda o: has(o, lambda d: d.get('verb') == 'remove_counter'
                  and d.get('and', {}).get('amount') == 20))
add("remove-counter-and-transform",
    "Then if there are three or more bore counters on it, remove those counters and transform it",
    lambda o: has(o, lambda d: d.get('verb') == 'remove_counter'
                  and d.get('and', {}).get('verb') == 'transform'))
add("unattach-timing",
    "If you do, unattach it at the beginning of the next end step",
    lambda o: has(o, lambda d: d.get('verb') == 'unattach'
                  and d.get('timing') == {'position': 'beginning', 'which': 'next', 'phase': 'end_step'}))
add("then-if-not-empty",
    "Then if it has three or more +1/+1 counters on it, transform it",
    lambda o: has(o, lambda d: d.get('type') == 'effect'
                  and 'three or more' in str(d.get('condition', ''))
                  and d.get('effect')))
add("transform-action",
    "Then if it has three or more +1/+1 counters on it, transform it",
    lambda o: has(o, lambda d: d.get('verb') == 'transform'))
add("untap-and-transform",
    "Then if your life total is less than or equal to half your starting life total, untap this creature and transform this creature",
    lambda o: has(o, lambda d: d.get('verb') == 'transform'))
add("draw-amount-article", "Draw a card",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('amount') == 1))
add("draw-who", "You draw two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('who')))
add("deal-damage", "this enchantment deals 2 damage to that player",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage' and d.get('amount') == 2 and d.get('to')))
add("damage-equal-to-power",
    "It deals damage equal to its power to target creature an opponent controls",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage'
                  and d.get('amount') == 'its power'))
add("life-loss-equal-to-count",
    "Target opponent loses life equal to the number of creatures they control",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_life'
                  and 'number' in str(d.get('amount', ''))))
add("enters-counters", "This creature enters with three wish counters on it",
    lambda o: has(o, lambda d: d.get('verb') == 'enters' and d.get('with', {}).get('count') == 3))
add("put-zone", "put it into your hand",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'hand'))
add("exile-top-card", "Exile the top card of your library",
    lambda o: has(o, lambda d: d.get('verb') == 'exile' and d.get('top') is True))
add("look-top-card-amount", "Look at the top card of your library",
    lambda o: has(o, lambda d: d.get('verb') == 'look' and d.get('top') is True
                  and d.get('amount') == 1))
add("put-bottom", "Put target card from a graveyard on the bottom of your library",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and d.get('placement') == 'bottom'))
add("put-rest-random-order", "Put the rest on the bottom in a random order",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and d.get('card') == 'the rest'
                  and d.get('placement') == 'bottom'
                  and d.get('order') == 'random'))
add("token-color-type", "Create a white Avatar creature token",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('colors') == 'white'
                  and 'creature' in d.get('token', {}).get('types', [])))
add("token-tapped",
    "Whenever you commit a crime, create a tapped Treasure token",
    lambda o: has(o, lambda d: d.get('token', {}).get('tapped') is True))
add("token-granted-ability",
    'Create a 0/1 black Wizard creature token with "Whenever you cast a noncreature spell, this token deals 1 damage to each opponent."',
    lambda o: has(o, lambda d: 'noncreature spell' in str(d.get('token', {}).get('quote', ''))))
add("token-crew",
    "When this creature enters, create a 3/2 colorless Vehicle artifact token with crew 1",
    lambda o: has(o, lambda d: {'keyword': 'crew', 'modifier': 1} in d.get('token', {}).get('kw', [])))
add("token-tapped-and-attacking",
    "{2}{W}, {T}: Whenever you attack this turn, create two 1/1 red Warrior creature tokens that are tapped and attacking",
    lambda o: has(o, lambda d: d.get('token', {}).get('tapped') is True
                  and d.get('token', {}).get('attacking') is True))
add("token-except-clause",
    "Create a token that's a copy of target creature you control, except it has haste",
    lambda o: has(o, lambda d: 'except' in str(d.get('token', {})).lower()
                  and 'haste' in str(d.get('token', {}))))
add("token-that-many",
    "Whenever one or more Dinosaurs you control attack, create that many Treasure tokens",
    lambda o: has(o, lambda d: d.get('token', {}).get('count') == 'that many'))
add("token-two-quotes",
    'Whenever ~ enters or attacks, create a tapped colorless artifact token named Test Relic with "When this token enters, it deals 2 damage to any target" and "{T}: Add one mana of any color."',
    lambda o: has(o, lambda d: len(d.get('token', {}).get('quotes', [])) == 2))
add("stat-for-each", "This creature gets +1/+1 for each other creature on the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and 'battlefield' in str(d.get('for_each', ''))))
add("cant-except", "This creature can't be blocked except by black creatures",
    lambda o: has(o, lambda d: d.get('verb') == "can't" and d.get('predicate') == 'be blocked'
                  and d.get('except_by')))
add("search-zone", "Search your library for a card named Test Card",
    lambda o: has(o, lambda d: d.get('verb') == 'search' and d.get('zone') == 'library'))
add("search-reveal-step",
    "Search your library for a Demon card, reveal it, put it into your hand, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'search' and d.get('reveal') is True))
add("basic-land-type", "Search your library for a basic land card",
    lambda o: has(o, lambda d: d.get('verb') == 'search'
                  and d.get('card', {}).get('card_type', {}).get('value') == 'basic land'))
add("put-counter", "put a -1/-1 counter on it",
    lambda o: has(o, lambda d: d.get('verb') == 'put_counter'
                  and '-1/-1' in str(d.get('counter', ''))))
add("token-pt-kw", "Create a 1/1 colorless Thopter artifact creature token with flying",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('power_toughness') == {'power': 1, 'toughness': 1}
                  and 'flying' in str(d.get('token', {}).get('kw', []))))
add("counter-unless", "Counter target spell unless its controller pays {1}",
    lambda o: has(o, lambda d: d.get('verb') == 'counter' and '{1}' in str(d.get('unless', ''))))
add("become-pt", "Target land you control becomes a 4/4 Elemental creature with trample",
    lambda o: has(o, lambda d: d.get('verb') == 'become' and d.get('pt') == {'power': 4, 'toughness': 4}))
add("stat-condition", "This creature gets +4/+4 as long as an opponent has ten or more cards in their graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and 'graveyard' in str(d.get('condition', ''))))
add("skip-combat-phase",
    "When this creature enters, target opponent skips their next combat phase",
    lambda o: has(o, lambda d: d.get('verb') == 'skip'
                  and d.get('phase') == 'combat'
                  and 'opponent' in str(d.get('who', ''))))
add("hexproof-targeting",
    "Until end of turn, your opponents and creatures your opponents control with hexproof can be the targets of spells and abilities you control as though they didn't have hexproof",
    lambda o: has(o, lambda d: d.get('verb') == 'can_be_target'
                  and d.get('as_though_without') == 'hexproof'
                  and len(d.get('targets', [])) == 2))
add("choose-per-player",
    "Whenever ~ attacks, for each player, choose target permanent that player controls",
    lambda o: has(o, lambda d: d.get('verb') == 'choose'
                  and d.get('per_player') is True
                  and d.get('object', {}).get('quantifier') == 'target'))
add("reveal-sacrificed-this-way",
    "Each player who sacrificed a permanent this way reveals the top card of their library, then puts it onto the battlefield if it's a permanent card",
    lambda o: has(o, lambda d: d.get('verb') == 'reveal'
                  and 'each player' in str(d.get('who', '')).lower())
                  and has(o, lambda d: d.get('verb') == 'put'
                          and d.get('zone') == 'battlefield'))
add("gain-control-chosen",
    "Then each player gains control of each permanent for which they were chosen",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_control'
                  and d.get('for_which_chosen') is True))
add("put-library-choice",
    "Its owner puts it on their choice of the top or bottom of their library",
    lambda o: has(o, lambda d: d.get('verb') == 'put_library'
                  and 'Its owner' == d.get('owner')
                  and 'bottom' in str(d.get('destination', ''))))
add("reveal-until-that-many",
    "Exile all creatures you control, then reveal cards from the top of your library until you reveal that many creature cards",
    lambda o: has(o, lambda d: d.get('verb') == 'reveal'
                  and d.get('until', {}).get('card_type', {}).get('kind') == 'type'))
add("shuffle-revealed-rest",
    "Put all creature cards revealed this way onto the battlefield, then shuffle the rest of the revealed cards into your library",
    lambda o: has(o, lambda d: d.get('verb') == 'shuffle'))
add("bloodthirst-number",
    "Whenever you cast a Vampire creature spell, it gains bloodthirst 3",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and 'bloodthirst 3' in str(d.get('keywords', [])).lower()))
add("copy-with-exception",
    "You may have this creature enter as a copy of any creature on the battlefield, except it's an Illusion in addition to its other types and it has \"When this creature becomes the target of a spell or ability, sacrifice it.\"",
    lambda o: has(o, lambda d: d.get('verb') == 'have'
                  and d.get('effect', {}).get('verb') == 'copy')
                  and has(o, lambda d: d.get('verb') == 'gain_quote'))
add("damage-player-and-creatures",
    "~ deals 2 damage to target player and each creature that player controls",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage'
                  and 'each creature that player controls' in str(d.get('to', ''))))
add("opponent-life-total",
    "Target opponent's life total becomes 10",
    lambda o: has(o, lambda d: d.get('verb') == 'life_total'
                  and d.get('amount') == 10
                  and d.get('who') == 'Target opponent'))
add("control-player-turn",
    "You control target player during that player's next turn",
    lambda o: has(o, lambda d: d.get('verb') == 'control_player'
                  and d.get('player') == 'target player'
                  and d.get('during_next_turn') is True))
add("additional-land-their-turns",
    "Each player may play an additional land on each of their turns",
    lambda o: has(o, lambda d: d.get('verb') == 'play'
                  and d.get('additional_land') is True))
add("those-tokens-instead-if",
    "Create five of those tokens instead if you control artifacts named ~ and ~",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('count') == 5
                  and d.get('of_those_tokens') is True
                  and d.get('instead') is True))
add("search-keyword-choice",
    "When this creature enters, search your library for a creature card with deathtouch, hexproof, reach, or trample and reveal it",
    lambda o: has(o, lambda d: d.get('verb') == 'search')
                  and has(o, lambda d: d.get('verb') == 'reveal'))
add("block-all-this-turn",
    "All creatures able to block it this turn do so",
    lambda o: has(o, lambda d: d.get('verb') == 'block_do_so'
                  and d.get('this_turn') is True
                  and d.get('subject', {}).get('card_type', {}).get('value') == 'creatures'))
add("warp-same-action",
    "Each player puts all artifact, creature, and land cards revealed this way onto the battlefield, then does the same for enchantment cards",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'battlefield')
                  and has(o, lambda d: d.get('verb') == 'same'
                          and d.get('card', {}).get('card_type', {}).get('value') == 'enchantment'))
add("return-tapped-next-upkeep",
    "When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of their next upkeep",
    lambda o: has(o, lambda d: d.get('verb') == 'return'))
add("return-all-multi-types",
    "Return all artifact and enchantment cards from all graveyards to the battlefield under their owners' control",
    lambda o: has(o, lambda d: d.get('verb') == 'return'))
add("reveal-then-exile-name",
    "Then that player reveals their hand and exiles all cards with that name from their hand and graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'reveal')
                  and has(o, lambda d: d.get('verb') == 'exile'))
add("search-xdef-then-put",
    "Search your library for up to X basic land cards, where X is the number of lands you control, put them onto the battlefield tapped, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'search'))
add("cast-copies-plural-cost",
    "You may cast the copies without paying their mana costs",
    lambda o: has(o, lambda d: d.get('verb') == 'cast'))
add("play-without-paying-plural",
    "You may play them this turn without paying their mana costs",
    lambda o: has(o, lambda d: d.get('verb') == 'play'))
add("search-mana-value-xdef",
    "Search your library for a creature card with mana value equal to the number of verse counters on ~, put it onto the battlefield, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'search'))
add("phase-out-controlled-creatures",
    "Each creature target opponent controls phases out",
    lambda o: has(o, lambda d: d.get('verb') == 'phase'
                  and d.get('direction') == 'out'))
add("cant-phase-in",
    "Until the end of your next turn, they can't phase in",
    lambda o: has(o, lambda d: d.get('verb') == "can't"
                  and d.get('predicate') == 'phase in'))
add("return-tapped-attacking",
    "Return that card to the battlefield tapped and attacking",
    lambda o: has(o, lambda d: d.get('verb') == 'return'))
add("search-card-list",
    "Search your library for an Island card, a Swamp card, and a Mountain card",
    lambda o: has(o, lambda d: d.get('verb') == 'search'))
add("stat-gain-kw-and-type",
    "Equipped creature gets +2/+0, has vigilance, and is a Knight in addition to its other types",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'))
add("token-thats-attacking",
    "Whenever equipped creature attacks, create a 2/2 white Knight creature token with vigilance that's attacking",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'))
add("copy-with-player-subject",
    "Whenever a player casts an instant or sorcery spell, each other player copies that spell",
    lambda o: has(o, lambda d: d.get('verb') == 'copy'))
add("choose-new-targets-player",
    "Each of those players may choose new targets for their copy",
    lambda o: has(o, lambda d: d.get('verb') == 'choose_new_targets'))
add("compound-player-discard-sacrifice",
    "That player or that planeswalker's controller discards seven cards, then sacrifices seven permanents of their choice",
    lambda o: has(o, lambda d: d.get('verb') == 'discard')
                  and has(o, lambda d: d.get('verb') == 'sacrifice'))
add("become-base-pt-in-addition",
    "Enchanted artifact is a creature with base power and toughness 5/5 in addition to its other types",
    lambda o: has(o, lambda d: d.get('verb') == 'become'))
add("xdef-life-youve-gained",
    "This creature enters with X +1/+1 counters on it, where X is the amount of life you've gained this turn",
    lambda o: has(o, lambda d: d.get('verb') == 'enters'))
add("earthbend",
    "At the beginning of your end step, earthbend 2",
    lambda o: has(o, lambda d: d.get('verb') == 'earthbend'
                  and d.get('amount') == 2))
add("may-mill-two",
    "Whenever this Vehicle attacks, you may mill two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'may'
                  and d.get('inner', {}).get('verb') == 'mill'
                  and d.get('inner', {}).get('amount') == 2))
add("gain-kw-lose-all-other",
    "It has defender and loses all other abilities",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and d.get('keywords') == ['defender']
                  and d.get('loses_all_other_abilities') is True))
add("activated-triggered-effect",
    "{2}, {T}: When you next activate an exhaust ability that isn't a mana ability this turn, copy it",
    lambda o: has(o, lambda d: d.get('verb') == 'copy') or has(o, lambda d: d.get('type') == 'triggered'))
add("once-each-turn-static",
    "Once during each of your turns, you may cast an instant or sorcery spell from your hand without paying its mana cost",
    lambda o: has(o, lambda d: d.get('once_each_turn') is True
                  and d.get('effect', {}).get('verb') == 'may'))
add("ability-word-equip",
    "Lightbringer and Hero's Shield \u2014 Equip {4}",
    lambda o: has(o, lambda d: d.get('type') == 'static_keyword'
                  and str(d.get('ability_word', '')).startswith('Lightbringer')
                  and d.get('keywords', {}).get('keyword') == 'Equip'))
add("enchant-player",
    "Enchant player",
    lambda o: has(o, lambda d: d.get('verb') == 'enchant'
                  and d.get('targets') == ['player']))
add("cant-gain-life",
    "Enchanted player can't gain life",
    lambda o: has(o, lambda d: d.get('verb') == "can't"
                  and d.get('predicate') == 'gain life'))
add("half-life-rounded",
    "Whenever enchanted player is dealt damage, they lose half their life, rounded up",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_life'
                  and d.get('amount', {}).get('kind') == 'half'
                  and d.get('amount', {}).get('rounding') == 'up'))
add("add-mana-equal-x",
    "{T}: Add an amount of {G} equal to this creature's power",
    lambda o: has(o, lambda d: d.get('verb') == 'add_mana'
                  and d.get('amount', {}).get('symbol') == '{G}'
                  and 'equal_to' in d.get('amount', {})))
add("becomes-saddled",
    "Target Mount you control becomes saddled until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'become'
                  and d.get('state') == 'saddled'))
add("role-token-attached",
    "When this creature dies, create a Young Hero Role token attached to up to one target creature you control",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and 'attached_to' in d.get('token', {})))
add("counter-all-spells-abilities",
    "Counter all spells your opponents control and all abilities your opponents control",
    lambda o: has(o, lambda d: d.get('verb') == 'counter'
                  and d.get('spells') is True and d.get('abilities') is True))
add("max-hand-size",
    "Your maximum hand size is ten",
    lambda o: has(o, lambda d: d.get('max_hand_size') == 10))
add("draw-the-difference",
    "At the beginning of your end step, if you have fewer than ten cards in hand, draw cards equal to the difference",
    lambda o: has(o, lambda d: d.get('verb') == 'draw'
                  and d.get('amount') == 'the difference'))
add("type-disjunction",
    "Destroy target artifact or creature",
    lambda o: has(o, lambda d: (d.get('kind') == 'set'
                                and 'creature' in str(d.get('items')))
                  or d.get('card_type', {}).get('value')
                  == 'artifact or creature'))
add("for-each-color",
    "For each color among permanents you control, add one mana of that color",
    lambda o: has(o, lambda d: d.get('verb') == 'for_each'
                  and d.get('effect', {}).get('verb') == 'add_mana'))
add("lose-all-creature-types",
    "Target creature gets +3/-3 and loses all creature types until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_keywords'
                  and d.get('all_types') == 'creature'))
add("owner-manifests-dread",
    "When this Vehicle leaves the battlefield, the exiled card's owner manifests dread",
    lambda o: has(o, lambda d: d.get('verb') == 'manifest_dread'
                  and 'owner' in str(d.get('who', ''))))
add("put-and-or-tokens",
    "You may put a creature card and/or a land card from your hand onto the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and d.get('zone') == 'battlefield'
                  and len(d.get('cards', [])) == 2))
add("return-to-battlefield-mv",
    "Return to the battlefield target nonland permanent card in your graveyard with mana value less than or equal to the number of permanent cards in your graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'return'
                  and 'mana_value' in d
                  and d.get('to') == {'zone': 'battlefield'}))
add("cost-less-to-activate-this",
    "This ability costs {1} less to activate for each Island you control",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and d.get('amount') == {'kind': 'mana',
                                          'symbols': ['{1}']}
                  and d.get('direction') == 'less'))
add("ability-word-effect",
    "Fathomless descent \u2014 Return to the battlefield target nonland permanent card in your graveyard with mana value less than or equal to the number of permanent cards in your graveyard",
    lambda o: has(o, lambda d: d.get('type') == 'effect'
                  and str(d.get('ability_word', '')).startswith('Fathomless')
                  and d.get('effect', {}).get('verb') == 'return'))
add("if-decomposed", "If you control three or more creatures, draw a card",
    lambda o: has(o, lambda d: d.get('type') == 'if' and 'condition' in d
                  and isinstance(d.get('effect'), dict)
                  and d['effect'].get('verb') == 'draw'))
add("if-instead", "If a card would be put into an opponent's graveyard from anywhere, exile it instead",
    lambda o: has(o, lambda d: d.get('type') == 'replacement'
                  and d.get('if', {}).get('verb') == 'put_into'
                  and d.get('instead', {}).get('verb') == 'exile'))
add("if-relative-life", "If you would gain life, you gain twice that much life instead",
    lambda o: has(o, lambda d: d.get('type') == 'replacement'
                  and d.get('if', {}).get('verb') == 'gain_life'
                  and d.get('instead', {}).get('verb') == 'gain_life'
                  and 'twice' in str(d.get('instead', {}).get('amount', ''))))
add("put-with-subject", "that player puts it into their hand",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'hand'
                  and d.get('who') == 'that player'))
add("stat-loses-kw", "Equipped creature gets +10/+10 and loses flying",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and d.get('change') == {'power': 10, 'toughness': 10}
                  and 'flying' in d.get('loses', [])))
add("prevent-that-damage", "If a source would deal damage to you, prevent that damage",
    lambda o: has(o, lambda d: d.get('verb') == 'prevent_damage'))
add("deal-damage-plus", "it deals that much damage plus 2 to that creature",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage'
                  and 'plus 2' in str(d.get('amount', ''))))
add("lose-game", "that player loses the game",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_game' and d.get('who') == 'that player'))
add("regenerate-target", "Regenerate target creature",
    lambda o: has(o, lambda d: d.get('verb') == 'regenerate'))
add("suspect-target", "Suspect target creature",
    lambda o: has(o, lambda d: d.get('verb') == 'suspect'))
add("can-block-any", "Target creature can block any number of creatures",
    lambda o: has(o, lambda d: d.get('verb') == 'can_block' and d.get('blocker')))
add("investigate", "Investigate",
    lambda o: has(o, lambda d: d.get('verb') == 'investigate'))
add("exile-all-graveyards", "Exile all graveyards",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'))
add("cant-cast-or-activate", "Your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments",
    lambda o: has(o, lambda d: d.get('verb') == "can't" and 'activate' in str(d.get('predicate'))))
add("additional-phase", "After this phase, there is an additional combat phase",
    lambda o: has(o, lambda d: d.get('verb') == 'additional_phase'))
add("must-block", "Creatures you control must be blocked this turn if able",
    lambda o: has(o, lambda d: d.get('verb') == 'must_block'))
add("gift", "Gift a card",
    lambda o: has(o, lambda d: d.get('verb') == 'gift'))
add("manifest-dread", "Manifest dread",
    lambda o: has(o, lambda d: d.get('verb') == 'manifest_dread'))
add("start-engines", "Start your engines!",
    lambda o: has(o, lambda d: d.get('type') == 'static'
                  and d.get('kind') == 'start_engines'))
add("ability-word-activated", "Max speed — {3}, Exile this card from your graveyard: Draw a card",
    lambda o: has(o, lambda d: d.get('type') == 'activated'))
add("ability-word-if", "Flare Star — If a Wizard you control would deal damage to a permanent or player, it deals double that damage instead",
    lambda o: has(o, lambda d: d.get('type') == 'replacement'
                  and d.get('if', {}).get('verb') == 'deal_damage'
                  and d.get('instead', {}).get('verb') == 'deal_damage'))
add("empower", "When ~ enters, empower Jace 5",
    lambda o: has(o, lambda d: d.get('verb') == 'empower'))
add("collect-evidence", "As an additional cost to cast this spell, you may collect evidence 6",
    lambda o: has(o, lambda d: d.get('verb') == 'collect_evidence'))
add("cloak", "Cloak a card from your hand",
    lambda o: has(o, lambda d: d.get('verb') == 'cloak'))
add("enter-untapped", "Lands you control enter untapped",
    lambda o: has(o, lambda d: d.get('verb') == 'enters'))
add("gain-control-as-long", "When this Vehicle enters, gain control of target creature an opponent controls for as long as you control this Vehicle",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_control'))
add("spend-mana-chosen-type", "Spend this mana only to cast a creature spell of the chosen type or activate an ability of a creature source of the chosen type",
    lambda o: has(o, lambda d: d.get('verb') == 'spend_mana_only_to_cast'))

add("scorch-relative-damage",
    "Whenever this creature attacks, it deals 1 damage to the player or planeswalker it's attacking",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage'
                  and isinstance(d.get('to'), dict)
                  and d['to'].get('attacking') is True
                  and len(d['to'].get('or', [])) == 2))
add("convoke-keyword", "Artifact spells you cast have convoke",
    lambda o: has(o, lambda d: d.get('keywords') == ['convoke']))
add("enchanted-target", "Enchanted creature gets +1/+0 and has trample",
    lambda o: has(o, lambda d: d.get('type') == 'static'
                  and d.get('target', {}).get('value') == 'creature'
                  and all(a.get('target') for a in d.get('effect', [])
                          if isinstance(a, dict))))
add("enchanted-status",
    "Enchanted creature gets +1/+1 and has menace and trample",
    lambda o: has(o, lambda d: d.get('type') == 'static'
                  and 'Enchanted' in d.get('target', {}).get('status', [])
                  and all('Enchanted' in a.get('target', {}).get('status', [])
                          for a in d.get('effect', []) if isinstance(a, dict))))
add("unless-clause",
    "Whenever an opponent casts a spell, that player loses 5 life unless they discard a card",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_life'
                  and 'discard a card' in str(d.get('unless', ''))))
add("stat-define-subject",
    "~'s power and toughness are each equal to the number of creatures you control",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_define'
                  and d.get('subject') == '~'))
add("destroy-attached-relation",
    "Destroy up to one Equipment attached to that creature",
    lambda o: has(o, lambda d: d.get('verb') == 'destroy'
                  and d.get('attached_to', {}).get('this_that') == 'that'))
add("exile-two-shared-zone",
    "When ~ enters, exile up to one target nonland permanent and up to one target nonland permanent card from a graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'
                  and len(d.get('cards', [])) == 2
                  and all(c.get('zone') == 'graveyard' for c in d['cards'])))
add("coordinated-card-target",
    "Equipped creature can't be blocked and has shroud",
    lambda o: has(o, lambda d: d.get('verb') == 'gain_kw'
                  and 'Equipped' in d.get('target', {}).get('status', []))
                  or has(o, lambda d: d.get('verb') == 'gain_kw'
                  and 'Equipped' in d.get('card', {}).get('status', [])))
add("coordinated-target", "When this creature enters, target creature gets +2/+0 and gains first strike until end of turn",
    lambda o: has(o, lambda d: isinstance(d.get('effect'), list)
                  and all(a.get('target') for a in d['effect']
                          if isinstance(a, dict))))

add("also-gain-kw", "White creatures you control also gain first strike until end of turn",
    lambda o: has(o, lambda d: d.get('keywords') == ['first strike']))
add("can-attack-as-though",
    "As long as you control a creature with power 4 or greater, this creature can attack as though it didn't have defender",
    lambda o: has(o, lambda d: d.get('verb') == 'can_attack_as_though'
                  and d.get('without_keywords') == ['defender']))
add("replace-counter",
    "If one or more +1/+1 counters would be put on a creature you control, that many plus one +1/+1 counters are put on that creature instead",
    lambda o: has(o, lambda d: d.get('verb') == 'replace_counter'
                  and d.get('extra') == 1
                  and d.get('on', {}).get('card_type', {}).get('value') == 'creature'))

add("aetherspouts-owner-choice",
    "For each attacking creature, its owner puts it on their choice of the top or bottom of their library",
    lambda o: has(o, lambda d: d.get('verb') == 'put_library'))
add("sarkhan-power-list",
    "Whenever you cast a creature spell with power 4, 5, or 6, this enchantment deals 4 damage to any target",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage' and d.get('amount') == 4))
add("scepter-instead-if",
    "It deals 3 damage instead if you control artifacts named Crown of Empires and Throne of Empires",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage')
                  and has(o, lambda d: d.get('if')))
add("exile-coordinated-zones",
    "Exile all noncreature, nonland cards from that player's hand and graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'exile'
                  and d.get('zones') == ['hand', 'graveyard']))
add("lose-life-per-card",
    "Target opponent loses 2 life for each creature card in their graveyard",
    lambda o: has(o, lambda d: d.get('verb') == 'lose_life'
                  and d.get('for_each', {}).get('card_type', {}).get('value') == 'creature'))
add("cant-counter-duration",
    "It can't have counters put on it for as long as this creature remains on the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == "can't"
                  and 'remains on the battlefield' in str(d.get('condition', ''))))
add("sacrifice-choice-modifier",
    "Target opponent sacrifices a creature of their choice with flying",
    lambda o: has(o, lambda d: d.get('verb') == 'sacrifice'
                  and 'flying' in str(d.get('modifier', ''))))
add("optional-sacrifice-is-not-regenerate", "You may sacrifice a creature",
    lambda o: has(o, lambda d: d.get('verb') == 'may'
                  and d.get('inner', {}).get('verb') == 'sacrifice')
                  and not has(o, lambda d: d.get('verb') == 'regenerate'))
add("any-opponent-may-sacrifice",
    "At the beginning of each combat, any opponent may sacrifice a creature of their choice",
    lambda o: has(o, lambda d: d.get('verb') == 'may'
                  and d.get('inner', {}).get('verb') == 'sacrifice'))
add("upkeep-of-controller",
    "At the beginning of the upkeep of enchanted creature's controller, that player loses 2 life",
    lambda o: has(o, lambda d: d.get('type') == 'triggered'
                  and "enchanted creature" in str(d.get('trigger', {}))
                  and d.get('effect', {}).get('verb') == 'lose_life'))
add("begin-game",
    "If this card is in your opening hand, you may begin the game with it on the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'may'
                  and d.get('inner', {}).get('verb') == 'begin_game'))
add("draw-greatest-discarded",
    "Each player discards their hand, then draws cards equal to the greatest number of cards a player discarded this way",
    lambda o: has(o, lambda d: d.get('verb') == 'draw'
                  and 'greatest' in str(d.get('amount', ''))))
add("reveal-top-their",
    "Then each player reveals the top card of their library",
    lambda o: has(o, lambda d: d.get('verb') == 'reveal'
                  and d.get('zone') == 'library'))
add("spend-mana-cast-or-activate",
    "Spend this mana only to cast artifact spells or activate abilities of artifacts",
    lambda o: has(o, lambda d: d.get('verb') == 'spend_mana_only_to_cast'))

# --- shapes that Lark's optional expansion used to hide (grammar hoisting) ---
# Each of these was produced two different ways depending on which alternative
# the parser resolved; the interpreter now reports one canonical shape.
add("pronoun-is-anaphora",
    "It gains haste until end of turn",
    lambda o: has(o, lambda d: d.get('ref') == 'anaphora' and d.get('raw')))
add("pronoun-subject-anaphora", "He gains menace until end of turn",
    lambda o: has(o, lambda d: d.get('ref') == 'anaphora'
                  and d.get('raw') == 'He'))
add("event-without-object",
    "Whenever this creature attacks, it gets +1/+1 until end of turn",
    lambda o: has(o, lambda d: d.get('verb') == 'attacks' and d.get('object') == {}))
add("event-combat-damage",
    "Whenever this creature deals combat damage to a player, draw a card",
    lambda o: has(o, lambda d: d.get('verb') == 'deals'
                  and d.get('object', {}).get('damage') == 'combat'
                  and d.get('object', {}).get('to') == {'kind': 'player', 'quantifier': 'a'}))
add("event-plain-damage-no-kind",
    "Whenever this creature deals damage to an opponent, you may draw a card",
    lambda o: has(o, lambda d: d.get('verb') == 'deals'
                  and d.get('object', {}).get('to') == {'kind': 'opponent', 'quantifier': 'an'}
                  and 'damage' not in d.get('object', {})))
add("event-passive-combat-damage",
    "Whenever this creature is dealt combat damage, you gain that much life",
    lambda o: has(o, lambda d: d.get('verb') == 'is dealt'
                  and d.get('damage') == 'combat'))
add("event-passive-damage-no-kind",
    "Whenever equipped creature is dealt damage, destroy it",
    lambda o: has(o, lambda d: d.get('verb') == 'is dealt'
                  and 'damage' not in d))
add("event-sacrifice-verb",
    "Whenever you sacrifice an artifact, put a +1/+1 counter on this creature",
    lambda o: has(o, lambda d: d.get('verb') == 'sacrifice' and d.get('subject') == 'you'))
add("event-while-saddled",
    "Whenever this creature attacks while saddled, put a +1/+1 counter on it",
    lambda o: has(o, lambda d: d.get('verb') == 'attacks'
                  and isinstance(d.get('condition'), dict)
                  and d['condition'].get('reason') == 'condition_text'
                  and d['condition'].get('fragment') == 'while saddled'))
add("event-becomes-the-target",
    "Whenever this creature becomes the target of a spell or ability you control for the first time each turn, put a +1/+1 counter on it",
    lambda o: has(o, lambda d: d.get('verb') == 'becomes the target'
                  and 'spell or ability' in str(d.get('of', ''))))
add("event-counter-put",
    "Whenever you put one or more +1/+1 counters on this creature, draw a card",
    lambda o: has(o, lambda d: d.get('verb') == 'put'
                  and 'one or more' in str(d.get('counter', {}))))
add("token-for-each",
    "Create a 2/2 green Wolf creature token for each Forest you control",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and isinstance(d.get('token'), dict)
                  and d['token'].get('for_each', {}).get('card_type', {})
                       .get('value') == 'Forest'))
add("trigger-ability-word",
    "Landfall \u2014 Whenever a land you control enters, create a 1/1 green Saproling creature token",
    lambda o: has(o, lambda d: d.get('ability_word') == 'Landfall'
                  and d.get('when') == 'Whenever'))
add("search-named-target",
    "{2}, {T}: Search your library for a card named ~ or ~, put it onto the battlefield tapped, then shuffle",
    lambda o: has(o, lambda d: d.get('verb') == 'search' and d.get('card')))
add("counter-with-modifier",
    "Counter target spell with mana value X",
    lambda o: has(o, lambda d: d.get('verb') == 'counter'
                  and isinstance(d.get('spell'), dict)
                  and 'mana value X' in str(d['spell'].get('modifier'))))

add("unparsed-static-fallback",
    "Activate only if you control a Sliver",
    lambda o: has(o, lambda d: d.get('type') == 'unparsed'
                  and d.get('reason') == 'static_text'
                  and 'Sliver' in str(d.get('fragment', ''))))
add("unparsed-raw-fallback",
    "If X is 6 or more, return a creature card put into a graveyard this way to the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'raw'
                  and d.get('unparsed') is True
                  and d.get('reason') == 'raw_action'))
add("no-text-key-in-fallback",
    "Activate only if you control a Sliver",
    lambda o: not has(o, lambda d: isinstance(d, dict) and 'text' in d))

def main():
    data = sys.argv[1] if len(sys.argv) > 1 else 'classic.json'
    items, types, card_names, sets = load(data)
    names = sorted(card_names, key=len, reverse=True)
    parser = build_parser('interp')
    interp = Interpreter(types=types, names=card_names)
    passed = failed = 0
    for name, sent, pred in T:
        try:
            sents = [d['text'] for d in segment(sent, names)
                     if d['text'] and not d['modal']]
            if not sents:
                raise ValueError('no sentence produced')
            out = interp.interp(parser.parse(sents[0]))
        except Exception as e:
            print(f"  FAIL {name:20s} (parse) {e}")
            failed += 1
            continue
        if pred(out):
            print(f"  PASS {name}")
            passed += 1
        else:
            print(f"  FAIL {name:20s}  {sent}")
            print(f"       {json.dumps(out)[:200]}")
            failed += 1
    print(f"\n{passed}/{passed+failed} golden tests passed")
    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    import json
    main()
