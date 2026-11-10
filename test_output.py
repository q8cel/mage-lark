#!/usr/bin/env python3
"""Golden output tests: lock in the interpreter fixes (regression guard).

Each case is (name, sentence, predicate); predicate(output) is True iff the
interpreted output has the expected structure. Hand-written for the known
silent-bug classes, so a regressing fix fails loudly here.

Usage:  python test_output.py [data.json]      # default classic.json
"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
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
add("anaphora-not-type", "It gains haste until end of turn",
    lambda o: has(o, lambda d: d.get('ref') == 'anaphora'))
add("draw-amount-int", "Draw two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('amount') == 2))
add("draw-amount-article", "Draw a card",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('amount') == 1))
add("draw-who", "You draw two cards",
    lambda o: has(o, lambda d: d.get('verb') == 'draw' and d.get('who')))
add("deal-damage", "this enchantment deals 2 damage to that player",
    lambda o: has(o, lambda d: d.get('verb') == 'deal_damage' and d.get('amount') == 2 and d.get('to')))
add("enters-counters", "This creature enters with three wish counters on it",
    lambda o: has(o, lambda d: d.get('verb') == 'enters' and d.get('with', {}).get('count') == 3))
add("put-zone", "put it into your hand",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'hand'))
add("token-color-type", "Create a white Avatar creature token",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('colors') == 'white'
                  and 'creature' in d.get('token', {}).get('types', [])))
add("stat-for-each", "This creature gets +1/+1 for each other creature on the battlefield",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change'
                  and 'battlefield' in str(d.get('for_each', ''))))
add("cant-except", "This creature can't be blocked except by black creatures",
    lambda o: has(o, lambda d: d.get('verb') == "can't" and d.get('predicate') == 'be blocked'
                  and d.get('except_by')))
add("search-zone", "Search your library for a card named Test Card",
    lambda o: has(o, lambda d: d.get('verb') == 'search' and d.get('zone') == 'library'))
add("put-counter", "put a -1/-1 counter on it",
    lambda o: has(o, lambda d: d.get('verb') == 'put_counter'
                  and '-1/-1' in str(d.get('counter', ''))))
add("token-pt-kw", "Create a 1/1 colorless Thopter artifact creature token with flying",
    lambda o: has(o, lambda d: d.get('verb') == 'create_token'
                  and d.get('token', {}).get('power_toughness') == '1/1'
                  and 'flying' in str(d.get('token', {}).get('kw', []))))
add("counter-unless", "Counter target spell unless its controller pays {1}",
    lambda o: has(o, lambda d: d.get('verb') == 'counter' and '{1}' in str(d.get('unless', ''))))
add("become-pt", "Target land you control becomes a 4/4 Elemental creature with trample",
    lambda o: has(o, lambda d: d.get('verb') == 'become' and d.get('pt') == '4/4'))
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
                  and 'rounded up' in str(d.get('amount', ''))))
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
                  and d.get('to') == 'to the battlefield'))
add("cost-less-to-activate-this",
    "This ability costs {1} less to activate for each Island you control",
    lambda o: has(o, lambda d: d.get('verb') == 'cost_mod'
                  and d.get('amount') == '{1}'
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
    lambda o: has(o, lambda d: d.get('type') == 'if' and d.get('instead') is True
                  and d.get('effect', {}).get('verb') == 'exile'))
add("if-relative-life", "If you would gain life, you gain twice that much life instead",
    lambda o: has(o, lambda d: d.get('effect', {}).get('verb') == 'gain_life'
                  and 'twice' in str(d.get('effect', {}).get('amount', ''))))
add("put-with-subject", "that player puts it into their hand",
    lambda o: has(o, lambda d: d.get('verb') == 'put' and d.get('zone') == 'hand'
                  and d.get('who') == 'that player'))
add("stat-loses-kw", "Equipped creature gets +10/+10 and loses flying",
    lambda o: has(o, lambda d: d.get('verb') == 'stat_change' and d.get('change') == '+10/+10'
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
    lambda o: has(o, lambda d: 'Start your engines' in str(d.get('text', ''))))
add("ability-word-activated", "Max speed — {3}, Exile this card from your graveyard: Draw a card",
    lambda o: has(o, lambda d: d.get('type') == 'activated'))
add("ability-word-if", "Flare Star — If a Wizard you control would deal damage to a permanent or player, it deals double that damage instead",
    lambda o: has(o, lambda d: d.get('type') == 'if'))
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
