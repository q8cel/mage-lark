# Out-of-dev coreference audit

Sample: 20 anaphora-bearing cards from `classic.json`, excluding every card in
`coref_standard.json` and `coref_dataset.json` (random seed `20261022`). Each
card was run through `rulecoref` sequentially and the text, mentions, anaphors,
antecedents, and entities were inspected by hand.

## Results

| # | card | result |
|---|---|---|
| 1 | Chandra, Awakened Inferno | anaphora OK; fixed own-name normalization |
| 2 | Grim Return | PASS |
| 3 | Vaevictis Asmadi, the Dire | PASS (6/6) |
| 4 | Mindclaw Shaman | mitigated: `those cards` -> player fallback; proper anchor is the revealed hand collection |
| 5 | Chandra's Incinerator | PASS |
| 6 | Belltower Sphinx | `that many` separated as a quantity anaphor, not an entity anaphor |
| 7 | Soul Bleed | limitation: no `enchanted creature's controller` candidate |
| 8 | Sublime Epiphany | PASS |
| 9 | Odric, Master Tactician | limitation: free-relative blocking creatures not in inventory |
| 10 | Crumbling Colossus | PASS |
| 11 | Scepter of Empires | limitation: subject continuation `It deals 3` still binds to the object |
| 12 | Excommunicate | PASS |
| 13 | Loaming Shaman | PASS |
| 14 | Unsubstantiate | PASS |
| 15 | Dismissive Pyromancer | PASS |
| 16 | Chandra's Outrage | PASS |
| 17 | Inferno Elemental | PASS |
| 18 | Sorin Markov | PASS |
| 19 | Monomania | limitation: `the rest` = remaining cards in hand; no hand collection candidate, so it now abstains |
| 20 | Gem of Becoming | limitation: coordinated search set is only the last conjunct |

## Bugs fixed

- Scalar anaphors such as `that many` / `that much` are now exposed by
  `find_quantity_anaphors` and kept out of the entity inventory; they are real
  anaphors, just not entity anaphors.
- `from among those cards` after a player reveals a hand falls back to the
  player/opponent when no card NP exists, instead of an unrelated creature.
  This is a mitigation, not the full collection resolution.
- `the rest` abstains when no plural collection candidate exists, instead of
  binding to the singled-out card. The correct resolution still needs a
  hand/collection mention.
- `setdata.card_text()` normalizes the card's own short name even when that name
  collides with a type/subtype word (e.g. `Chandra`).

## Known limitations exposed by the audit

- Status-headed NPs (`enchanted creature`, `equipped creature`) and their
  controllers are not in the regex candidate inventory.
- Free relatives (`which creatures block`) introduce referents with no mention.
- Cross-sentence subject continuation needs structural role information; a
  broad earliest-subject rule regressed the dev set and was not kept.
- Coordinated search targets need a collection mention (`an Island card, a Swamp
  card, and a Mountain card`), not only the last conjunct.
- Collection anaphors (`those cards`, `the rest`) need zone/collection mentions
  such as `their hand` / `the top N cards`; resolving them to a player is only a
  fallback, not the semantic antecedent.

Dev metrics were unchanged by these audit fixes: 90.1% entity-aware / 84.2%
exact; bench 94.1% regex / 93.0% parser.
