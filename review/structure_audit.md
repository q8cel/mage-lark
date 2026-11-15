# Structural audit — Standard

Snapshot `Standard_1e032c36fb62eaea_056f23fd05529720.json` (grammar `1e032c36fb62eaea`, interp `056f23fd05529720`), read at the snapshot hash (the live `core/interpret.py` is being edited; this audit does not use it). Policy `review/stringy_policy.json`; stringy flags use the list-string fix.

Minimal required content: effect->verb; triggered->event; event->verb; target->card_type/quantifier or other semantic content; condition->kind; cost item->action (not prose); amount->value/kind or computed content; zone destination->zone. Allow-listed as legitimately minimal: unparsed trigger fragments; bare phase triggers (`when` is a phase dict); `event.kind == event_ref`; cost items that are brace-only mana, punctuation or a single keyword atom; keyword-only statics; verbs such as investigate that need no target/amount.

## Totals

- parsed texts: 7,265 / 20,882 occurrences
- honest: 6,331 / 19,164
- stringy (corrected list-string walk; v7 missed strings inside lists, so its 1,725 occurrences were optimistic): 839 / 1,788
- >=1 empty required slot: 14 texts / 19 occurrences, 15 sites
- **structural completeness: 5,544 / 7,265 texts (76.3%), 17,476 / 20,882 occurrences (83.7%)**
- structural completeness of corpus: 17,476 / 22,217 = 78.7%

## Per-shape

| shape | missing slot | texts | occurrences |
|---|---|---:|---:|
| event | verb | 12 | 16 |
| target | type | 2 | 5 |

## Top 20 empty-slot families

| # | shape | missing | path | texts | occurrences | example |
|---:|---|---|---|---:|---:|---|
| 1 | event | verb | `[].trigger.event` | 12 | 16 | Whenever you sacrifice this artifact or another artifac |
| 2 | target | type | `[].effect.target` | 2 | 3 | The copy gains haste and "At the beginning of the end s |

## Examples

- event/verb at `[].trigger.event` (3 occurrences): Whenever you sacrifice this artifact or another artifact, you may pay {2}
- event/verb at `[].trigger.event` (2 occurrences): Whenever one or more other Rabbits, Bats, Birds, and/or Mice you control enter, scry 1
- target/type at `[].effect.target` (2 occurrences): The copy gains haste and "At the beginning of the end step, sacrifice this token."
- target/type at `[].effect.target` (2 occurrences): The copy gains haste and "At the beginning of the end step, sacrifice this token."
- event/verb at `[].trigger.event` (2 occurrences): Whenever another artifact or creature is put into a graveyard from the battlefield, put a 

