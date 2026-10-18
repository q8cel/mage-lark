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


def resolve_card(name):
    text = card_text(name)
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
    assert canon == ["target creature", "up to one target Equipment", "~"], canon


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
    # Fake Your Own Death: "it" is genuinely undecidable without role info.
    # We want the engine to SAY so (this is where a model fallback would run).
    _, res = resolve_card("Fake Your Own Death")
    assert any(a["status"] == "ambiguous" for a in res["anaphors"]), anas(res)


def t_no_candidate_abstains():
    text = "It gains flying"
    res = rulecoref.resolve(text, [], find_anaphors(text))
    assert res["anaphors"][0]["status"] == "no-resolution", res["anaphors"][0]["status"]
    assert res["anaphors"][0]["antecedent"] is None


def t_known_limitation_blasphemous_edict():
    # KNOWN WRONG (asserted on purpose): "their" belongs to the clause SUBJECT
    # ("Each player sacrifices thirteen creatures of their choice"), but the
    # possessive rule falls back to recency and picks the nearest plural. Fixing
    # it needs subject binding; update DETERMINISTIC-COREF.md when it lands.
    # NB: a cap-degraded parse cache once made this look fixed ("Each player") -
    # it was the degraded mention inventory, not the rule.
    _, res = resolve_card("Blasphemous Edict")
    got = [a["canonical"] for a in res["anaphors"] if a["surface"].lower() == "their"]
    assert got == ["thirteen creatures"], got


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


def t_entity_ids_not_indices():
    # two spans of the same object must collapse to one entity id
    text = "~ deals 3 damage to target creature. ~ gains flying."
    res = rulecoref.resolve(text, refs.build(text, parser=False), [])
    ids = [e["id"] for e in res["entities"] if e["canonical"] == "~"]
    assert len(ids) == 1, [e["canonical"] for e in res["entities"]]


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
