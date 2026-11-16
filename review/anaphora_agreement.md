# Anaphora agreement audit — Standard

Input `compile_standard.jsonl`: 22,217 lines, 13,357 unique records, **3,241 resolved bindings**. Checks use `coref/refs.py` annotation (`head_type`, `number`, `is_self`, `is_target`) and its regex mention inventory (`refs.build(parser=False)`). The earlier report keyed card context by card name (first printing); keying each record to its own printing via sentence containment cut not_a_mention from 83 to 3 - those were audit-side, not resolver errors.

## Totals

- resolved bindings: 3,241; violation rows: 78
- bindings with at least one provable violation: 75
- **bindings passing all checks: 3,166 (97.7%)**

| violation | count | severity |
|---|---:|---|
| self_binding | 42 | medium |
| cross_clause | 23 | high |
| number_mismatch | 6 | high |
| kind_mismatch | 4 | high |
| not_a_mention | 3 | high |

Severity totals: high 36, medium 42.

## Top offending cards

| card | violations |
|---|---:|
| Ice Magic | 4 |
| Not Dead After All | 3 |
| Presumed Dead | 3 |
| Ninja Teen | 2 |
| Does Machines | 2 |
| Fake Your Own Death | 2 |
| Host of the Hereafter | 2 |
| Pain 101 | 2 |
| Perigee Beckoner | 2 |
| Undying Malice | 2 |
| Vincent's Limit Break | 2 |
| Break Out | 1 |
| Carnage, Crimson Chaos | 1 |
| Dragonbroods' Relic | 1 |
| Eriette, the Beguiler | 1 |

## Examples

- **Break Out** (sentence 2): "If that card has mana value 2 or less, you may put it onto the battlefield and it gains haste until end of turn"
  `it` -> `the battlefield` [cross_clause, high]: antecedent 'the battlefield' starts after the anaphor at 142.
- **Carnage, Crimson Chaos** (sentence 2): "It gains "This creature attacks each combat if able" and "When this creature deals combat damage to a player, sacrifice it.""
  `it` -> `this creature` [cross_clause, high]: antecedent 'this creature' starts after the anaphor at 117.
- **Dragonbroods' Relic** (sentence 2): "It has flying, lifelink, and "When this token enters, it deals 3 damage to any target.""
  `it` -> `this token` [cross_clause, high]: antecedent 'this token' starts after the anaphor at 192.
- **Eriette, the Beguiler** (sentence 1): "Whenever an Aura you control becomes attached to a nonland permanent an opponent controls with mana value less than or equal to that Aura's mana value, gain control of th"
  `that Aura` -> `that permanent` [cross_clause, high]: antecedent 'that permanent' starts after the anaphor at 137.
- **Esper Origins // Summon: Esper Maduin** (sentence 2): "If this spell was cast from a graveyard, exile it, then put it onto the battlefield transformed under its owner's control with a finality counter on it"
  `it` -> `the battlefield` [cross_clause, high]: antecedent 'the battlefield' starts after the anaphor at 75.
- **Fortune, Loyal Steed** (sentence 1): "Whenever ~ attacks while saddled, at end of combat, exile it and up to one creature that saddled it this turn, then return those cards to the battlefield under their owne"
  `it` -> `up to one creature` [cross_clause, high]: antecedent 'up to one creature' starts after the anaphor at 81.
- **Goliath Daydreamer** (sentence 0): "Whenever you cast an instant or sorcery spell from your hand, exile that card with a dream counter on it instead of putting it into your graveyard as it resolves"
  `it` -> `your graveyard` [cross_clause, high]: antecedent 'your graveyard' starts after the anaphor at 102.
- **Heaped Harvest** (sentence 0): "When this artifact enters and when you sacrifice it, you may search your library for a basic land card, put it onto the battlefield tapped, then shuffle"
  `it` -> `a basic land card` [cross_clause, high]: antecedent 'a basic land card' starts after the anaphor at 49.
- **Lilah, Undefeated Slickshot** (sentence 1): "Whenever you cast a multicolored instant or sorcery spell from your hand, exile that spell instead of putting it into your graveyard as it resolves"
  `it` -> `your graveyard` [cross_clause, high]: antecedent 'your graveyard' starts after the anaphor at 118.
- **Not Dead After All** (sentence 0): "Until end of turn, target creature you control gains "When this creature dies, return it to the battlefield tapped under its owner's control, then create a Wicked Role to"
  `it` -> `a Wicked Role token` [cross_clause, high]: antecedent 'a Wicked Role token' starts after the anaphor at 86.

