# Anaphora agreement audit — Standard

Input `compile_standard.jsonl`: 22,217 lines, 13,357 unique records, **4,504 resolved bindings**. Checks use `coref/refs.py` annotation (`head_type`, `number`, `is_self`, `is_target`) and its regex mention inventory (`refs.build(parser=False)`).

Rules: a violation is reported only when provable from the card text plus the resolver's own annotations (`refs.head_type/number/is_self/is_target`). The owner-of case (Horned Loch-Whale `their`) is a fixture and passes clean; fixtures 8/8.

## Totals

- resolved bindings: 4,504; violation rows: 488
- bindings with at least one provable violation: 439
- **bindings passing all checks: 4,065 (90.3%)**

| violation | count | severity |
|---|---:|---|
| cross_clause | 150 | high |
| number_mismatch | 106 | high |
| not_a_mention | 97 | high |
| kind_mismatch | 70 | high |
| self_binding | 61 | medium |
| owner_confusion | 4 | medium |

Severity totals: high 423, medium 65.

## Top offending cards

| card | violations |
|---|---:|
| Terra, Magical Adept // Esper Terra | 14 |
| Parker Luck | 7 |
| Ojer Pakpatiq, Deepest Epoch // Temple of Cyclical Time | 6 |
| Archdruid's Charm | 5 |
| Avatar Destiny | 5 |
| Vito, Fanatic of Aclazotz | 5 |
| Push // Pull | 5 |
| Esper Origins // Summon: Esper Maduin | 4 |
| Presumed Dead | 4 |
| Thunderbolts Conspiracy | 4 |
| Ice Magic | 4 |
| Baron Helmut Zemo | 3 |
| Cracked Skull | 3 |
| Deceit | 3 |
| Demonic Counsel | 3 |

## Examples

- **Additive Evolution** (sentence 1): "Put three +1/+1 counters on it"
  `It` -> `target creature` [cross_clause, high]: antecedent 'target creature' starts after the anaphor at 110.
- **Alien Symbiosis** (sentence 1): "Enchanted creature gets +1/+1, has menace, and is a Symbiote in addition to its other types"
  `its` -> `this card` [cross_clause, high]: antecedent 'this card' starts after the anaphor at 93.
- **Angelic Destiny** (sentence 1): "Enchanted creature gets +4/+4, has flying and first strike, and is an Angel in addition to its other types"
  `its` -> `this card` [cross_clause, high]: antecedent 'this card' starts after the anaphor at 108.
- **Archangel of Tithes** (sentence 1): "As long as this creature is untapped, creatures can't attack you or planeswalkers you control unless their controller pays {1} for each of those creatures"
  `their` -> `those creatures` [cross_clause, high]: antecedent 'those creatures' starts after the anaphor at 108.
- **Archdruid's Charm** (sentence 0): "Search your library for a creature or land card and reveal it"
  `it` -> `the battlefield` [cross_clause, high]: antecedent 'the battlefield' starts after the anaphor at 74.
- **Archdruid's Charm** (sentence 0): "Search your library for a creature or land card and reveal it"
  `It` -> `target creature` [cross_clause, high]: antecedent 'target creature' starts after the anaphor at 74.
- **Archdruid's Charm** (sentence 1): "Put it onto the battlefield tapped if it's a land card"
  `it` -> `the battlefield` [cross_clause, high]: antecedent 'the battlefield' starts after the anaphor at 82.
- **Archdruid's Charm** (sentence 1): "Put it onto the battlefield tapped if it's a land card"
  `It` -> `target creature` [cross_clause, high]: antecedent 'target creature' starts after the anaphor at 82.
- **Archdruid's Charm** (sentence 2): "Otherwise, put it into your hand"
  `It` -> `target creature` [cross_clause, high]: antecedent 'target creature' starts after the anaphor at 149.
- **Avatar Destiny** (sentence 1): "Enchanted creature gets +1/+1 for each creature card in your graveyard and is an Avatar in addition to its other types"
  `its` -> `this card` [cross_clause, high]: antecedent 'this card' starts after the anaphor at 132.

