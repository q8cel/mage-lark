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
