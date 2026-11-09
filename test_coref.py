#!/usr/bin/env python3
"""Golden tests for the deterministic coreference engine (regression guard).

Style follows `test_output.py`: plain functions, no framework, hand-written
against the behaviour we intend to keep. Two kinds of case:

  * intended behaviour — must stay true,
  * documented limitation — asserts the *current wrong* answer on purpose, so
    that a future fix breaks the test loudly and forces the doc to be updated.

No parsing: cases whose card text is not already in the parse cache are SKIPPED
rather than silently spending 30 s each.

Usage:
    python test_coref.py            # all
    python test_coref.py -v         # show skip reasons
"""
import sys

BASE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, BASE)

import ptree
import refs
import rulecoref
from anaphora import find_anaphors
from setdata import card_text

VERBOSE = "-v" in sys.argv
RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append(("PASS", name, ""))
    except Skip as e:
        RESULTS.append(("SKIP", name, str(e)))
    except AssertionError as e:
        RESULTS.append(("FAIL", name, str(e)))


class Skip(Exception):
    pass


def resolve_card(name, path=None):
    text = card_text(name, path)
    assert text, f"card not found: {name}"
    if not (ptree.has_structure(text) or ptree.key(text) in ptree._load_legacy()):
        raise Skip("card text not in parse cache")
    res = rulecoref.resolve(text, refs.build(text), find_anaphors(text))
    return text, res


def anas(res):
    return [(a["surface"], a["status"], a["canonical"]) for a in res["anaphors"]]


# --------------------------------------------------------------- the exemplar
def t_fiery_all_three_resolve_to_the_creature():
    _, res = resolve_card("Fiery Annihilation")
    assert len(res["anaphors"]) == 3, anas(res)
    assert {a["entity"] for a in res["anaphors"]} == {1}, anas(res)
    assert {a["canonical"] for a in res["anaphors"]} == {"target creature"}, anas(res)


def t_fiery_entities():
    _, res = resolve_card("Fiery Annihilation")
    canon = sorted(e["canonical"] for e in res["entities"])
    assert canon == ["target creature", "up to one target Equipment attached to that creature", "~"], canon


def t_fiery_chain_through_an_anaphor():
    # the 2nd "that creature" must bind through the 1st anaphor, not to a string
    _, res = resolve_card("Fiery Annihilation")
    second = res["anaphors"][1]
    assert second["antecedent"]["surface"] == "that creature", second["antecedent"]
    assert second["entity"] == res["anaphors"][0]["entity"]


def t_fiery_rewrite_round_trips():
    text, res = resolve_card("Fiery Annihilation")
    rw = res["rewritten_text"]
    assert rw == ("~ deals 5 damage to target creature. Exile up to one target "
                  "Equipment attached to target creature. If target creature "
                  "would die this turn, exile target creature instead."), rw
    assert find_anaphors(rw) == [], [a["surface"] for a in find_anaphors(rw)]


# ------------------------------------------------------------ other behaviour
def t_plural_pronoun_agrees():
    _, res = resolve_card("Run Away Together")
    plural = [a for a in res["anaphors"] if a["surface"].lower() == "their"]
    assert plural, anas(res)
    assert plural[0]["status"] == "resolved", plural[0]
    assert plural[0]["canonical"].startswith("target creatures"), plural[0]["canonical"]


def t_ambiguous_is_reported_not_guessed():
    # Two same-type candidates in the anaphor's own sentence: the engine must say
    # it is unsure (this is where a model fallback would run) instead of guessing.
    text = ("Target creature deals damage to target creature, then it gains flying")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    assert res["anaphors"][0]["status"] == "ambiguous", res["anaphors"][0]


def t_granted_ability_binds_to_recipient():
    # `target creature gets +2/+0 and gains "When this creature dies, return it ..."`
    # Everything inside the quote refers to the RECIPIENT, not to the card - so
    # "this creature" inside a quote must not be treated as a self-reference.
    _, res = resolve_card("Fake Your Own Death")
    assert res["anaphors"], "no anaphors"
    for a in res["anaphors"]:
        assert a["canonical"] == "target creature", (a["surface"], a["canonical"])


def t_no_candidate_abstains():
    text = "It gains flying"
    res = rulecoref.resolve(text, [], find_anaphors(text))
    assert res["anaphors"][0]["status"] == "no-resolution", res["anaphors"][0]["status"]
    assert res["anaphors"][0]["antecedent"] is None


def t_possessive_binds_to_the_clause_subject():
    # "Each player sacrifices thirteen creatures of their choice": the possessive
    # follows "of", which points at the clause SUBJECT. Needed two fixes - the
    # distributive determiner must count as plural for agreement, and the
    # possessive must use the role derived from the introducing phrase.
    _, res = resolve_card("Blasphemous Edict")
    got = [a["canonical"] for a in res["anaphors"] if a["surface"].lower() == "their"]
    assert got == ["Each player"], got


def t_set_anaphora_is_set_valued():
    # "the rest" denotes a collection minus a subset, so the output must be
    # flagged and must bind to a plural collection NP, not the last mention.
    text = ("Look at the top five cards of your library. Put one into your hand "
            "and the rest on the bottom of your library.")
    anas = [a for a in find_anaphors(text)]
    rest = [a for a in anas if a["kind"] == "phrase"]
    assert rest, [a["surface"] for a in anas]
    res = rulecoref.resolve(text, refs.build(text, parser=False), anas)
    got = [a for a in res["anaphors"] if a["kind"] == "phrase"][0]
    assert got["set_valued"] is True, got
    assert got["op"] == "minus", got
    assert refs.number(got["canonical"]) == "pl", got["canonical"]


# ----------------------------------------------------------------- unit rules
def t_clean_is_maximal_and_junk_free():
    text = "Exile up to one target Equipment attached to that creature"
    raw = [{"surface": "up to one target Equipment", "start": 6, "end": 32},
           {"surface": "target Equipment", "start": 17, "end": 32},
           {"surface": "target", "start": 17, "end": 23},
           {"surface": "that creature", "start": 45, "end": 58}]
    kept = [m["surface"] for m in refs.clean(raw)]
    assert kept == ["up to one target Equipment", "that creature"], kept


def t_number_and_type():
    assert refs.number("that creature") == "sg"
    assert refs.number("target creatures") == "pl"
    assert refs.number("those cards") == "pl"
    assert refs.number("their") == "pl"
    assert refs.head_type("an instant or sorcery card") == "card"
    assert refs.head_type("a nontoken, non-Angel creature") == "creature"
    assert refs.head_type("~") is None


def t_type_lattice():
    assert refs.type_compatible("creature", "card")          # a creature is a card
    assert not refs.type_compatible("creature", "spell")
    assert refs.type_expected("card", "creature")            # verb "exile" takes a card
    assert not refs.type_expected("spell", "creature")


def t_rewrite_skips_possessives():
    anas = [{"surface": "its", "start": 10, "end": 13, "kind": "pronoun",
             "status": "resolved", "number": "sg",
             "antecedent": {"surface": "target creature", "start": 0, "end": 15},
             "canonical": "target creature"}]
    assert rulecoref.rewrite_text("Return it to its hand", anas) == "Return it to its hand"


def t_structure_never_parses():
    # a text that cannot be in any cache: must return [] instead of parsing
    assert ptree.structure("Zzz qqq wubble florb") == []


def t_kitesail_hand_and_chosen_card():
    text = ("When this creature enters, target opponent reveals their hand. "
            "You choose a noncreature, nonland card from it. Exile that card "
            "until this creature leaves the battlefield.")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    got = [(a["surface"], a["canonical"]) for a in res["anaphors"]]
    assert ("it", "their hand") in got, got
    assert ("that card", "a noncreature, nonland card") in got, got


def t_owner_and_control_pronouns():
    text = ("For each attacking creature, its owner puts it on their choice of "
            "the top or bottom of their library.")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    got = [(a["surface"], a["canonical"]) for a in res["anaphors"]]
    assert ("their", "its owner") in got, got
    text2 = ("Each opponent and each creature and planeswalker they control "
             "is dealt 1 damage.")
    res2 = rulecoref.resolve(text2, refs.build(text2, parser=False), find_anaphors(text2))
    got2 = [(a["surface"], a["canonical"]) for a in res2["anaphors"]]
    assert ("they", "Each opponent") in got2, got2


def t_possessive_attribute_across_sentences():
    # "its mana value" describes the previously revealed top card, not the
    # player who is losing life in the following sentence.
    text = ("Reveal the top card of your library and put that card into your "
            "hand. You lose life equal to its mana value.")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    got = [(a["surface"], a["canonical"]) for a in res["anaphors"]]
    assert ("its", "the top card") in got, got


def t_set_element_does_not_capture_later_possessives():
    # "one of them" refers only to its own instruction; it must not make the
    # later possessive "its owner" or "their hand" bind to that card collection.
    text = ("[+1]: Look at the top two cards of your library. Put one of them "
            "into your graveyard. [\u22123]: Return another target nonland "
            "permanent to its owner's hand. [\u22128]: Each player shuffles "
            "their hand and graveyard into their library.")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    got = [(a["surface"], a["canonical"]) for a in res["anaphors"]]
    assert ("its", "another target nonland permanent") in got, got
    assert got.count(("their", "Each player")) == 2, got


def t_set_rest_prefers_source_collection():
    text = ("Reveal the top four cards of your library. Put all Goblin cards "
            "revealed this way into your hand and the rest on the bottom of "
            "your library in any order.")
    res = rulecoref.resolve(text, refs.build(text, parser=False), find_anaphors(text))
    got = [a["canonical"] for a in res["anaphors"] if a["surface"].lower() == "the rest"]
    assert got == ["the top four cards"], got


def t_entity_ids_not_indices():
    # two spans of the same object must collapse to one entity id
    text = "~ deals 3 damage to target creature. ~ gains flying."
    res = rulecoref.resolve(text, refs.build(text, parser=False), [])
    ids = [e["id"] for e in res["entities"] if e["canonical"] == "~"]
    assert len(ids) == 1, [e["canonical"] for e in res["entities"]]


def t_planeswalker_demonstrative_not_player():
    _, res = resolve_card("Hooded Blightfang", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "that planeswalker"]
    assert len(got) == 1 and got[0]["canonical"] == "a planeswalker", anas(res)


def t_search_put_pronoun_prefers_search_card():
    _, res = resolve_card("Pattern Matcher", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "it"]
    assert len(got) == 2, anas(res)
    assert all(a["canonical"].lower().startswith("a card") for a in got), anas(res)


def t_conditional_it_continues_with_object():
    _, res = resolve_card("Conundrum Sphinx", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "it"]
    assert len(got) == 3, anas(res)
    assert all(a["canonical"] == "the card a player" for a in got), anas(res)


def t_as_though_refers_to_sentence_subject():
    _, res = resolve_card("Savage Summoning", "classic.json")
    got = [(a["surface"].lower(), a["canonical"]) for a in res["anaphors"]]
    assert ("it", "The next creature spell") in got, got
    assert ("that spell", "The next creature spell") in got, got


def t_color_choice_demonstrative_prefers_chosen_card():
    _, res = resolve_card("Lifebane Zombie", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "that card"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "a green or white creature card", anas(res)


def t_copy_except_pronouns_bind_new_copy():
    _, res = resolve_card("Phantasmal Image", "classic.json")
    got = [a for a in res["anaphors"]
           if a["surface"].lower() in ("it's", "its", "it")]
    assert len(got) == 4, anas(res)
    assert all(a["canonical"] == "this creature" for a in got), anas(res)


def t_reveal_object_is_the_card():
    _, res = resolve_card("Dryad Greenseeker", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "it"]
    assert len(got) == 2, anas(res)
    assert all(a["canonical"] == "the top card" for a in got), anas(res)


def t_search_plural_binds_search_target():
    _, res = resolve_card("Boundless Realms", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "them"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "up to X basic land cards", anas(res)


def t_owner_possessive_keeps_card_collection():
    _, res = resolve_card("Open the Vaults", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "their"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "all artifact and enchantment cards", anas(res)


def t_among_cards_binds_container():
    _, res = resolve_card("Mindclaw Shaman", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "those cards"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "their hand", anas(res)


def t_bare_zone_binds_container_pronoun():
    _, res = resolve_card("Visions of Beyond", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "it"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "a graveyard", anas(res)


def t_event_list_does_not_capture_demonstrative():
    _, res = resolve_card("Inferno Elemental", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "that creature"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "a creature", anas(res)


def t_mention_does_not_cross_newline():
    _, res = resolve_card("Entangling Vines", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "its"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "Enchanted creature", anas(res)


def t_those_cards_after_search_bind_card():
    _, res = resolve_card("Doubling Chant", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "those cards"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == (
        "a creature card with the same name as that creature"), anas(res)


def t_possessive_owner_prefers_object():
    _, res = resolve_card("Serra Avatar", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "its"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "~", anas(res)


def t_counter_modifier_binds_container():
    _, res = resolve_card("Emil, Vastlands Roamer", "Standard.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "them"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == (
        "Creatures you control with +1/+1 counters on them"), anas(res)


def t_triggered_ability_is_a_candidate():
    _, res = resolve_card("Twinflame Travelers", "Standard.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "it"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "a triggered ability", anas(res)


def t_player_demonstrative_skips_zone_container():
    _, res = resolve_card("Stain the Mind", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "that player"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "target player", anas(res)


def t_rest_after_one_of_binds_source_collection():
    _, res = resolve_card("See the Truth", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "the rest"]
    assert len(got) == 1, anas(res)
    assert got[0]["canonical"] == "the top three cards", anas(res)
    assert got[0]["status"] == "resolved", anas(res)


def t_rest_without_collection_abstains():
    # Documented limitation: Monomania's "the rest" has no explicit collection
    # mention (only the singled-out card and the hand zone).  Keep the honest
    # abstention instead of binding it to the chosen card.
    _, res = resolve_card("Monomania", "classic.json")
    got = [a for a in res["anaphors"] if a["surface"].lower() == "the rest"]
    assert len(got) == 1 and got[0]["status"] == "no-resolution", anas(res)


CASES = [(k[2:], v) for k, v in sorted(globals().items()) if k.startswith("t_")]

if __name__ == "__main__":
    for name, fn in CASES:
        check(name, fn)
    for status, name, msg in RESULTS:
        if status == "FAIL" or (status == "SKIP" and VERBOSE):
            print(f"  {status}  {name}" + (f"   -- {msg}" if msg else ""))
    n = len(RESULTS)
    p = sum(1 for s, _, _ in RESULTS if s == "PASS")
    f = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    k = sum(1 for s, _, _ in RESULTS if s == "SKIP")
    print(f"\ncoref tests: {p}/{n} passed, {f} failed, {k} skipped")
    sys.exit(1 if f else 0)
