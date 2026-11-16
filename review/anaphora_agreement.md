# Anaphora agreement audit — Standard

Input `compile_standard.jsonl`: 22,217 lines, 13,357 unique records, **3,241 resolved bindings**. Checks use `coref/refs.py` annotation (`head_type`, `number`, `is_self`, `is_target`) and its regex mention inventory (`refs.build(parser=False)`).

## Totals

- resolved bindings: 3,241; violation rows: 153
- bindings with at least one provable violation: 150
- **bindings passing all checks: 3,091 (95.4%)**

| violation | count | severity |
|---|---:|---|
| not_a_mention | 73 | high |
| self_binding | 42 | medium |
| cross_clause | 28 | high |
| number_mismatch | 6 | high |
| kind_mismatch | 4 | high |

Severity totals: high 111, medium 42.

## Top offending cards

| card | violations |
|---|---:|
| Terra, Magical Adept // Esper Terra | 5 |
| Ice Magic | 4 |
| Esper Origins // Summon: Esper Maduin | 3 |
| Not Dead After All | 3 |
| Presumed Dead | 3 |
| Ojer Pakpatiq, Deepest Epoch // Temple of Cyclical Time | 2 |
| Ninja Teen | 2 |
| Callous Sell-Sword // Burn Together | 2 |
| Decadent Dragon // Expensive Taste | 2 |
| Dion, Bahamut's Dominant // Bahamut, Warden of Light | 2 |
| Emeritus of Truce // Swords to Plowshares | 2 |
| Flotsam // Jetsam | 2 |
| Garland, Knight of Cornelia // Chaos, the Endless | 2 |
| Horned Loch-Whale // Lagoon Breach | 2 |
| Skycoach Conductor // All Aboard | 2 |

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
- **Gwen Stacy // Ghost-Spider** (sentence 3): "You may play that card this turn"
  `that card` -> `the top card` [cross_clause, high]: antecedent 'the top card' starts after the anaphor at 13.
- **Heaped Harvest** (sentence 0): "When this artifact enters and when you sacrifice it, you may search your library for a basic land card, put it onto the battlefield tapped, then shuffle"
  `it` -> `a basic land card` [cross_clause, high]: antecedent 'a basic land card' starts after the anaphor at 49.
- **Joshua, Phoenix's Dominant // Phoenix, Warden of Fire** (sentence 2): "Exile Phoenix, then return it to the battlefield"
  `it` -> `the battlefield` [cross_clause, high]: antecedent 'the battlefield' starts after the anaphor at 27.

