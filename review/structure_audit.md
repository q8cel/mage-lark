# Structural audit — Standard

Snapshot `Standard_1e032c36fb62eaea_a281987190b5d430.json` (grammar `1e032c36fb62eaea`, interp `a281987190b5d430`), read at the snapshot hash (the live `core/interpret.py` is being edited; this audit does not use it). Policy `review/stringy_policy.json`; stringy flags use the list-string fix.

Minimal required content: effect->verb; triggered->event; event->verb; target->card_type/quantifier or other semantic content; condition->kind; cost item->action (not prose); amount->value/kind or computed content; zone destination->zone. Allow-listed as legitimately minimal: unparsed trigger fragments; bare phase triggers (`when` is a phase dict); `event.kind == event_ref`; cost items that are brace-only mana, punctuation or a single keyword atom; keyword-only statics; verbs such as investigate that need no target/amount.

## Totals

- parsed texts: 7,265 / 20,882 occurrences
- honest: 6,331 / 19,164
- stringy (corrected list-string walk; v7 missed strings inside lists, so its 1,725 occurrences were optimistic): 1,844 / 3,715
- >=1 empty required slot: 496 texts / 924 occurrences, 504 sites
- **structural completeness: 4,562 / 7,265 texts (62.8%), 15,595 / 20,882 occurrences (74.7%)**
- structural completeness of corpus: 15,595 / 22,217 = 70.2%

## Per-shape

| shape | missing slot | texts | occurrences |
|---|---|---:|---:|
| cost | action | 479 | 912 |
| event | verb | 15 | 22 |
| target | type | 2 | 5 |

## Top 20 empty-slot families

| # | shape | missing | path | texts | occurrences | example |
|---:|---|---|---|---:|---:|---|
| 1 | cost | action | `[].cost[]` | 459 | 864 | {T}, Sacrifice this land: Search your library for a bas |
| 2 | event | verb | `[].trigger.event` | 15 | 22 | Whenever you sacrifice this artifact or another artifac |
| 3 | cost | action | `[].effect.quote.sentence[].cost[]` | 13 | 16 | Planeswalkers you control have "[+2]: This planeswalker |
| 4 | cost | action | `[].effect[].quote.sentence[].cost[]` | 5 | 13 | Equipped creature gets +3/+3 and has vigilance and "{T} |
| 5 | cost | action | `[].effect.token.quote.sentence[].cost[]` | 2 | 6 | Whenever you gain life, create a colorless artifact tok |
| 6 | target | type | `[].effect.target` | 2 | 3 | The copy gains haste and "At the beginning of the end s |

## Examples

- cost/action at `[].cost[2]` (13 occurrences): {T}, Sacrifice this land: Search your library for a basic land card, put it onto the battl
- cost/action at `[].cost[4]` (10 occurrences): {4}, {T}, Sacrifice this land: Draw a card
- cost/action at `[].cost[4]` (9 occurrences): {2}, {T}, Sacrifice this artifact: You gain 3 life
- cost/action at `[].cost[2]` (9 occurrences): {1}, Sacrifice ~: Creatures you control gain hexproof and indestructible until end of turn
- cost/action at `[].cost[2]` (8 occurrences): {1}, Sacrifice this creature: Destroy target artifact or enchantment

