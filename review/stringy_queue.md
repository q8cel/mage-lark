# Stringy fix queue — Standard

Families are ranked by occurrence, biggest first; one family per commit is the intended cadence. Occurrences sum the per-path sentence weights, so a sentence that hits two paths of the same family counts twice; unique texts are deduplicated. Distinct value shapes are aggregated across the family's paths.

## 1. `amount` — 1,815 occurrences, 706 texts

paths: `[].effect.amount` (1,268), `[].effect[].amount` (345), `[].effect.inner.amount` (107), `[].keywords.cost.amount` (35), `[].instead.amount` (22), `[].trigger.event.amount` (13), `[].effect.effect.amount` (11), `[].effect.toughness_value` (6), `[].instead[].amount` (4), `[].effect[].inner.amount` (2), `[].effect.effect[].amount` (2).

| value shape | occurrences | texts |
|---|---:|---:|
| `N life` | 679 | 299 |
| `M` | 221 | 127 |
| `M or M` | 207 | 10 |
| `one mana of any color` | 123 | 16 |
| `its power` | 53 | 28 |
| `N` | 46 | 19 |
| `x life` | 43 | 22 |
| `M M` | 35 | 19 |
| `N mana of any one color` | 24 | 8 |
| `that much life` | 22 | 7 |
| `that many` | 19 | 7 |
| `its mana cost` | 19 | 4 |
| `double that` | 18 | 4 |
| `half their life , rounded up` | 17 | 6 |
| `one mana of the chosen color` | 17 | 2 |
| `M , M , or M` | 17 | 13 |
| `x mana of any one color` | 16 | 6 |
| `M for each M, 'controller': 'you control'}` | 16 | 6 |
| `that much` | 13 | 6 |
| `N mana in any combination of colors` | 12 | 4 |
| `M M M` | 12 | 3 |
| `MMM` | 10 | 3 |
| `N mana of that color` | 9 | 3 |
| `MM` | 8 | 8 |
| `the greatest power among creatures you control` | 8 | 3 |
| `the difference` | 7 | 3 |
| `the sacrificed creature 's power` | 7 | 3 |
| `M M M M` | 6 | 2 |
| `that number plus N` | 6 | 3 |
| `that card's mana cost` | 6 | 1 |
| `the number of creatures you control of the chosen type` | 5 | 1 |
| `half their library, rounded down` | 5 | 2 |
| `that much M` | 5 | 2 |
| `that creature's power` | 5 | 3 |
| `that spell's mana value` | 5 | 2 |
| `the number of creatures you control` | 5 | 4 |
| `your devotion to red` | 5 | 1 |
| `his power` | 4 | 1 |
| `half your starting life total` | 4 | 1 |
| `twice that much life` | 4 | 2 |
| `the number of spells you've cast this turn` | 4 | 1 |
| `M M M M M` | 4 | 2 |
| `the number of treasures you control` | 4 | 1 |
| `M for each M, 'modifier': 'exiled this way'}` | 3 | 1 |
| `that much life plus N` | 3 | 1 |
| `their power` | 3 | 1 |
| `the greatest power among creature cards in your graveyard` | 3 | 1 |
| `the number of equipped creatures you control` | 3 | 1 |
| `MMMMM` | 2 | 1 |
| `the number of differently named creature tokens you control` | 2 | 1 |
| `half their life` | 2 | 1 |
| `the total mana value of other permanents you control` | 2 | 1 |
| `twice its power` | 2 | 2 |
| `its loyalty` | 2 | 1 |
| `the number of colors among permanents you control` | 2 | 2 |
| `the number of artifacts you control` | 2 | 1 |
| `the number of cards in your hand` | 2 | 1 |
| `x M or x M` | 2 | 1 |
| `the sacrificed creature's power` | 2 | 1 |
| `N plus the number of lesson cards in your graveyard` | 2 | 1 |
| `the number of instant and sorcery cards in your graveyard` | 2 | 1 |
| `the number of cards discarded this way` | 1 | 1 |
| `the number of cards in target opponent's hand` | 1 | 1 |
| `M M M M M M M M M M` | 1 | 1 |
| `the greatest toughness among creatures you control` | 1 | 1 |
| `the number of swamps you control` | 1 | 1 |
| `the mana value of the exiled card used to craft it` | 1 | 1 |
| `M M M M M M` | 1 | 1 |
| `that creature's toughness` | 1 | 1 |
| `the excess damage dealt this way` | 1 | 1 |
| `life equal to the life lost this way` | 1 | 1 |
| `the number of cards shuffled into your library this way` | 1 | 1 |
| `the sacrificed creature's toughness` | 1 | 1 |
| `the number of stash counters on this enchantment` | 1 | 1 |
| `your speed` | 1 | 1 |
| `that card's power` | 1 | 1 |
| `the number of creatures you control plus the number of equipment you c` | 1 | 1 |
| `the number of lands you control` | 1 | 1 |
| `the power of the chosen creature or card` | 1 | 1 |
| `the power of the creature you chose or the card you revealed` | 1 | 1 |

examples: `1 life` (121); `{1}` (65); `2 life` (46).

## 2. `duration` — 1,783 occurrences, 877 texts

paths: `[].effect.duration` (1,196), `[].effect[].duration` (283), `[].effect.inner.duration` (177), `[].duration` (108), `[].effect[].inner.duration` (14), `[].effect.until` (4), `[].effect.effect.duration` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `until end of turn` | 1,354 | 724 |
| `this turn` | 169 | 76 |
| `until the end of your next turn` | 95 | 10 |
| `until this enchantment leaves the battlefield` | 25 | 9 |
| `until your next turn` | 24 | 10 |
| `for as long as it remains exiled` | 15 | 6 |
| `during your turn` | 12 | 1 |
| `until this artifact leaves the battlefield` | 11 | 5 |
| `until this creature leaves the battlefield` | 10 | 7 |
| `until you exile a nonland card` | 8 | 5 |
| `until this aura leaves the battlefield` | 7 | 4 |
| `until they exile a nonland card` | 7 | 2 |
| `for as long as they remain exiled` | 6 | 2 |
| `for the rest of the game` | 6 | 3 |
| `for as long as you control this creature` | 6 | 2 |
| `until your next end step` | 6 | 3 |
| `until the end of their next turn` | 4 | 2 |
| `for as long as you control this vehicle` | 4 | 1 |
| `end of turn` | 4 | 2 |
| `until they have exiled cards with total mana value N or greater this w` | 2 | 1 |
| `until you exile cards with total mana value N or greater` | 2 | 1 |
| `for as long as that card remains exiled` | 2 | 1 |
| `until you exile another card with this creature` | 2 | 1 |
| `until this equipment leaves the battlefield` | 2 | 1 |
| `until this vehicle leaves the battlefield` | 2 | 1 |
| `for as long as that aura is attached to it` | 2 | 1 |
| `for as long as you control ~` | 2 | 1 |
| `for as long as this saga remains on the battlefield` | 1 | 1 |

examples: `until end of turn` (546); `until end of turn` (322); `this turn` (54).

## 3. `counter` — 1,471 occurrences, 711 texts

paths: `[].effect.counter` (1,045), `[].effect.with.counter` (221), `[].effect[].counter` (125), `[].effect.inner.counter` (21), `[].effect.and[].counter` (16), `[].condition.of.counter` (12), `[].if.counter` (8), `[].instead.counter` (8), `[].effect[].with.counter` (4), `[].instead[].counter` (3), `[].effect.with.and[].counter` (2), `[][].with.counter` (2), `[].effect[].counters` (2), `[].trigger.event.condition.of.counter` (1), `[].effect.effect.counter` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `+N/+N counter` | 786 | 373 |
| `+N/+N counter s` | 218 | 125 |
| `+N/+N counters` | 59 | 25 |
| `stun counter` | 47 | 30 |
| `finality counter` | 45 | 20 |
| `stun counter s` | 24 | 13 |
| `-N/-N counters` | 20 | 5 |
| `-N/-N counter` | 19 | 8 |
| `loyalty counter` | 18 | 7 |
| `flying counter` | 13 | 7 |
| `charge counter` | 13 | 5 |
| `+N/+N` | 11 | 7 |
| `quest counter` | 11 | 5 |
| `plan counter` | 9 | 7 |
| `each kind of counter` | 9 | 2 |
| `lifelink counter` | 8 | 4 |
| `indestructible counter` | 8 | 4 |
| `those counters` | 7 | 3 |
| `counter s` | 7 | 3 |
| `lore counter` | 6 | 3 |
| `-N/-N counter s` | 5 | 4 |
| `time counter` | 5 | 2 |
| `deathtouch counter` | 5 | 2 |
| `time counters` | 5 | 2 |
| `hone counter` | 5 | 2 |
| `blight counter` | 5 | 2 |
| `trample counter` | 4 | 2 |
| `fellowship counter` | 4 | 1 |
| `revival counters` | 4 | 1 |
| `revival counter` | 4 | 1 |
| `time counter s` | 4 | 2 |
| `incubation counter s` | 4 | 1 |
| `shield counter` | 4 | 1 |
| `double strike counter` | 3 | 2 |
| `nest counter` | 3 | 1 |
| `film counters` | 3 | 1 |
| `fire counters` | 3 | 1 |
| `ingenuity counter` | 3 | 1 |
| `bird creature card from your hand or graveyard onto the battlefield wi` | 3 | 1 |
| `growth counters` | 2 | 1 |
| `bore counter` | 2 | 1 |
| `charge counter s` | 2 | 2 |
| `haste counter` | 2 | 1 |
| `chorus counters` | 2 | 1 |
| `a first strike counter` | 2 | 1 |
| `landmark counter` | 2 | 1 |
| `unlock counter` | 2 | 1 |
| `decayed counter` | 2 | 1 |
| `hexproof counter and an indestructible counter` | 2 | 1 |
| `bore counters` | 2 | 1 |
| `landmark counters` | 2 | 1 |
| `net counters` | 2 | 1 |
| `stun counters` | 2 | 1 |
| `this creature's` | 2 | 1 |
| `impostor counter` | 2 | 1 |
| `bloodstain counter` | 2 | 1 |
| `rev counter` | 2 | 1 |
| `skewer counter` | 2 | 1 |
| `growth counter` | 2 | 1 |
| `chorus counter` | 2 | 1 |
| `flood counter` | 2 | 1 |
| `conqueror counter` | 2 | 1 |
| `coin counter` | 2 | 1 |
| `hexproof counter` | 2 | 1 |
| `possession counter` | 1 | 1 |
| `plus one of each of those kinds of counter s` | 1 | 1 |
| `dread counter` | 1 | 1 |
| `reach counter` | 1 | 1 |
| `dread counters` | 1 | 1 |
| `wish counters` | 1 | 1 |
| `page counters` | 1 | 1 |
| `stash counter` | 1 | 1 |
| `bait counter` | 1 | 1 |
| `page counter` | 1 | 1 |
| `loot counter` | 1 | 1 |
| `supply counter` | 1 | 1 |
| `soul counter` | 1 | 1 |
| `fire counter` | 1 | 1 |
| `point counter` | 1 | 1 |
| `divinity counter` | 1 | 1 |

examples: `+1/+1 counter` (298); `+1/+1 counter s` (106); `+1/+1 counter` (41).

## 4. `pt-change` — 1,155 occurrences, 670 texts

paths: `[].effect.change` (745), `[].effect[].change` (401), `[][].change` (5), `[].effect.inner.change` (2), `[][][].change` (2).

| value shape | occurrences | texts |
|---|---:|---:|
| `+N/+N` | 924 | 541 |
| `-N/-N` | 114 | 65 |
| `+x/+x` | 47 | 26 |
| `+x/+N` | 33 | 17 |
| `-x/-x` | 23 | 11 |
| `an additional +N/+N` | 6 | 2 |
| `+N/-N` | 6 | 6 |
| `-N/-x` | 3 | 2 |
| `-x/-N` | 2 | 2 |
| `an additional -N/-N` | 2 | 2 |

examples: `+1/+1` (87); `+1/+0` (72); `+1/+1` (63).

## 5. `timing` — 1,141 occurrences, 362 texts

paths: `[].trigger.when` (608), `[].activate_only` (359), `[].effect.timing` (95), `[].trigger.event.window` (62), `[].effect.trigger.event.window` (6), `[].trigger.event.condition` (5), `[].trigger.event.object.condition` (4), `[].if.during` (2).

| value shape | occurrences | texts |
|---|---:|---:|
| `as a sorcery` | 316 | 1 |
| `at the beginning of your end step` | 236 | 114 |
| `at the beginning of combat on your turn` | 138 | 74 |
| `at the beginning of your upkeep` | 99 | 42 |
| `at the beginning of the next end step` | 78 | 21 |
| `at the beginning of your first main phase` | 59 | 18 |
| `each turn` | 32 | 22 |
| `once each turn` | 30 | 1 |
| `this turn` | 28 | 12 |
| `during your turn` | 22 | 3 |
| `at the beginning of your second main phase` | 21 | 15 |
| `at the beginning of each end step` | 20 | 11 |
| `at the beginning of your next end step` | 15 | 3 |
| `at the beginning of each combat` | 5 | 3 |
| `at the beginning of each opponent's draw step` | 5 | 1 |
| `at the beginning of each opponent's upkeep` | 5 | 3 |
| `at the beginning of the end step` | 5 | 2 |
| `an opponent's turn` | 5 | 5 |
| `at the beginning of each upkeep` | 4 | 2 |
| `at the beginning of your next upkeep` | 4 | 1 |
| `at the beginning of each player's draw step` | 3 | 2 |
| `at the beginning of each player's first main phase` | 3 | 1 |
| `your turn` | 3 | 2 |
| `at end of combat` | 2 | 1 |
| `your turn other than your first spell that turn` | 2 | 1 |
| `at the beginning of the upkeep of enchanted creature 's controller` | 1 | 1 |

examples: `At the beginning of your end step` (114); `At the beginning of combat on your turn` (74); `At the beginning of your upkeep` (42).

## 6. `destination` — 1,076 occurrences, 469 texts

paths: `[].effect.to` (718), `[].trigger.event.object.to` (199), `[].effect[].to` (113), `[].effect.inner.to` (23), `[].effect.destination` (21), `[].effect[].inner.to` (2).

| value shape | occurrences | texts |
|---|---:|---:|
| `a player` | 192 | 80 |
| `to the battlefield` | 171 | 70 |
| `to your hand` | 156 | 89 |
| `to its owner's hand` | 135 | 61 |
| `any target` | 125 | 52 |
| `to the battlefield under its owner's control` | 63 | 15 |
| `to the battlefield tapped` | 33 | 19 |
| `to the battlefield with a finality counter on it` | 27 | 14 |
| `to the battlefield transformed under its owner's control` | 25 | 7 |
| `to their owners' hands` | 24 | 9 |
| `their choice of the top or bottom of their library` | 18 | 9 |
| `to the battlefield transformed under your control` | 10 | 1 |
| `to the battlefield tapped and transformed under its owner's control` | 8 | 1 |
| `to the battlefield under its owner's control with a +N/+N counter on i` | 7 | 4 |
| `an opponent` | 7 | 3 |
| `to the battlefield under your control` | 6 | 3 |
| `defending player` | 6 | 2 |
| `from your graveyard to the battlefield attached to` | 5 | 3 |
| `to the battlefield under their owners' control` | 5 | 2 |
| `to their owner's hand` | 4 | 4 |
| `to the battlefield tapped under your control` | 4 | 2 |
| `with mana value less than or equal to ~ 's power from your graveyard t` | 4 | 1 |
| `to the battlefield tapped under its owner's control` | 4 | 3 |
| `to the battlefield with one fewer revival counter on it` | 4 | 1 |
| `from your graveyard to the battlefield with an additional +N/+N counte` | 3 | 2 |
| `from your graveyard to the battlefield with two additional +N/+N count` | 3 | 2 |
| `their library second from the top or on the bottom` | 3 | 3 |
| `to the battlefield tapped under its owner's control with two stun coun` | 3 | 1 |
| `with mana value less than or equal to this creature 's power from your` | 3 | 2 |
| `to the battlefield transformed under her owner's control` | 3 | 1 |
| `to the battlefield under its owner's control with a flying counter on ` | 2 | 1 |
| `to the battlefield with a hexproof counter and an indestructible count` | 2 | 1 |
| `to the battlefield tapped and transformed under its owner's control wi` | 2 | 1 |
| `to the battlefield under its owner's control with a finality counter o` | 2 | 1 |
| `each of up to two other target s` | 2 | 1 |
| `to the battlefield transformed` | 2 | 1 |
| `to the battlefield with a finality counter on him` | 2 | 1 |
| `to the battlefield with an indestructible counter on it` | 2 | 1 |
| `to the battlefield tapped and attacking` | 1 | 1 |
| `to the battlefield under its owner's control with two +N/+N counter s ` | 1 | 1 |
| `to the battlefield under her owner's control with a +N/+N counter on h` | 1 | 1 |

examples: `a player` (80); `to your hand` (76); `to the battlefield` (65).

## 7. `pt` — 901 occurrences, 514 texts

paths: `[].effect.token.power_toughness` (717), `[].effect[].token.power_toughness` (53), `[].effect.pt` (51), `[].effect.base_pt` (35), `[].effect[].base_pt` (31), `[].effect.inner.token.power_toughness` (6), `[].effect[].pt` (4), `[].effect.effect.token.power_toughness` (3), `[].effect.inner.effect.pt` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `PT` | 890 | 506 |
| `x/x` | 11 | 8 |

examples: `1/1` (225); `2/2` (85); `3/3` (23).

## 8. `modifier` — 890 occurrences, 438 texts

paths: `[].effect.card.modifier` (249), `[].trigger.event.object.modifier` (93), `[].effect.target.modifier` (64), `[].trigger.event.subject.modifier` (54), `[].effect.inner.card.modifier` (45), `[].effect.token.except` (40), `[].effect[].card.modifier` (40), `[].keywords.modifier` (37), `[].effect.for_each.modifier` (31), `[].effect[].inner.card.modifier` (29), `[].if.card_target.modifier` (19), `[].effect.blocked_by.modifier` (19), `[].effect.cards.modifier` (17), `[].effect[].target.modifier` (16), `[].xdef.xdef.of.modifier` (14), `[].effect.except` (9), `[].condition.card_target.modifier` (8), `[].effect.inner.from_among.modifier` (8), `[].effect.cards[].modifier` (8), `[].effect.inner.effect.except` (8), `[].effect.on.modifier` (7), `[].effect.object.modifier` (5), `[].effect[].cards[].modifier` (5), `[].xdef.xdef[].modifier` (5), `[].trigger.event.subject.or[].modifier` (5), `[].effect.token.for_each.modifier` (4), `[].on.modifier` (4), `[].condition.event.object.modifier` (4), `[].effect.except_by.modifier` (4), `[].effect.inner.effect.copy_of.modifier` (4), `[].effect.to.modifier` (4), `[].condition.of.modifier` (3), `[].condition.action.card_target.modifier` (2), `[].effect[].blocked_by.modifier` (2), `[].effect.modifier` (2), `[].effect.except.modifier` (2), `[].effect.unless.card_target.modifier` (2), `[].effect.inner.cards[].modifier` (2), `[].trailing_if.card_target.modifier` (2), `[].effect[].inner.cards[].modifier` (2), `[].if.event.object.modifier` (2), `[].effect.who.modifier` (2), `[].effect.inner.effect.of.modifier` (2), `[].effect[].token.except` (2), `[].effect.spell.modifier` (1), `[].effect.token.copy_of.modifier` (1), `[].effect.token.xdef[].modifier` (1), `[].effect.trigger.event.object.modifier` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `with mana value N or less` | 130 | 67 |
| `with power N or less` | 69 | 38 |
| `with power N or greater` | 59 | 35 |
| `with mana value N or greater` | 50 | 28 |
| `of the chosen type` | 41 | 17 |
| `with flying` | 40 | 19 |
| `for M}` | 29 | 13 |
| `with mana value x or less` | 27 | 12 |
| `with a +N/+N counter on it` | 19 | 14 |
| `of that type` | 19 | 4 |
| `discarded this way` | 17 | 4 |
| `that targets a creature` | 16 | 12 |
| `exiled this way` | 13 | 6 |
| `exiled with ~` | 12 | 5 |
| `, except it isn't legendary` | 11 | 7 |
| `destroyed this way` | 11 | 3 |
| `with total mana value N or less` | 10 | 5 |
| `with the chosen name` | 10 | 3 |
| `with different names` | 10 | 5 |
| `with mana value x` | 10 | 5 |
| `with three or more creatures` | 9 | 5 |
| `, except it has haste and "at the beginning of the end step, sacrifice` | 8 | 2 |
| `other than ~` | 8 | 1 |
| `with mana value less than or equal to the number of lands you control` | 8 | 2 |
| `with a counter on it` | 7 | 6 |
| `with +N/+N counter s on them` | 7 | 4 |
| `milled this way` | 7 | 4 |
| `exiled with it` | 7 | 3 |
| `named ~` | 6 | 5 |
| `with haste` | 6 | 3 |
| `not legendary` | 6 | 2 |
| `, except it's a PT black demon` | 5 | 1 |
| `with that name` | 5 | 2 |
| `with seven or more cards in it` | 5 | 2 |
| `that crewed it this turn` | 5 | 3 |
| `other than this creature` | 4 | 3 |
| `, except it's a nightmare in addition to its other types` | 4 | 1 |
| `with toughness N or greater` | 4 | 2 |
| `exiled with this creature` | 4 | 2 |
| `with stash counter s on them` | 4 | 1 |
| `with mana value less than or equal to the amount of life you gained` | 4 | 1 |
| `revealed this way` | 4 | 2 |
| `exiled with this land` | 4 | 2 |
| `other than enchanted creature` | 4 | 3 |
| `, except it has "this equipment's equip abilities cost M less to activ` | 4 | 1 |
| `with five or more creatures` | 4 | 1 |
| `with a stash counter on it` | 4 | 1 |
| `with a single target` | 4 | 1 |
| `with mana value less than or equal to the number of creatures you cont` | 4 | 1 |
| `exiled with this artifact` | 4 | 2 |
| `with mana value N` | 3 | 3 |
| `of the chosen color` | 3 | 2 |
| `of each permanent type` | 3 | 1 |
| `attached to it` | 3 | 1 |
| `attached to ~` | 3 | 1 |
| `from everything` | 3 | 1 |
| `with different powers` | 3 | 1 |
| `collect evidence N` | 3 | 1 |
| `, except the tokens aren't legendary` | 3 | 1 |
| `with deathtouch` | 3 | 2 |
| `with menace` | 3 | 1 |
| `with mana value of the chosen quality` | 3 | 1 |
| `with two or more spiders` | 3 | 1 |
| `with mana value equal to ~'s power` | 3 | 1 |
| `with one or more blue mana symbols in its mana cost` | 3 | 1 |
| `with M in its mana cost` | 3 | 2 |
| `attached to him` | 3 | 2 |
| `that type` | 2 | 1 |
| `exiled with this saga` | 2 | 2 |
| `with toughness x or less` | 2 | 1 |
| `with the greatest power or tied for the greatest power` | 2 | 1 |
| `with four time counter s on it` | 2 | 1 |
| `, except it has haste and "at the beginning of the end step, if you do` | 2 | 1 |
| `with flash` | 2 | 1 |
| `with defender` | 2 | 1 |
| `with the greatest mana value among creatures and planeswalkers they co` | 2 | 2 |
| `chosen this way` | 2 | 1 |
| `, except it's PT` | 2 | 1 |
| `, except it has flying` | 2 | 1 |
| `with toughness N or less` | 2 | 1 |
| `with total mana value x or less` | 2 | 1 |
| `, except it's not legendary` | 2 | 1 |
| `other than that creature` | 2 | 1 |
| `with an impostor counter on it` | 2 | 1 |
| `with one or more counter s on it` | 2 | 1 |
| `with dream counter s on them` | 2 | 1 |
| `that isn't a mana ability` | 2 | 1 |
| `with one or more creatures` | 2 | 2 |
| `with one or more faeries` | 2 | 1 |
| `with one or more lizards` | 2 | 1 |
| `with one or more non-gnome creatures` | 2 | 1 |
| `that targets an artifact or land` | 2 | 1 |
| `that targets only a single creature` | 2 | 1 |
| `except it's a bird in addition to its other types` | 2 | 1 |
| `with mana value less than or equal to the amount of mana spent to cast` | 2 | 1 |
| `except it's a cave in addition to its other types` | 2 | 1 |
| `except his name is ~` | 2 | 1 |
| `, except it's a PT red balloon creature in addition to its other color` | 2 | 1 |
| `exiled with this enchantment` | 2 | 1 |
| `with no counter s on it` | 1 | 1 |
| `attached to that creature` | 1 | 1 |
| `from ['black']` | 1 | 1 |
| `from ['white']` | 1 | 1 |
| `with greater mana value than that creature` | 1 | 1 |
| `tapped this way` | 1 | 1 |
| `with one or more rats` | 1 | 1 |
| `with creatures` | 1 | 1 |
| `that targets a creature or player` | 1 | 1 |
| `that targets an opponent or a creature` | 1 | 1 |
| `except it's a shapeshifter rogue in addition to its other types` | 1 | 1 |
| `except it has changeling` | 1 | 1 |
| `with mana value less than or equal to ~'s power` | 1 | 1 |

examples: `with mana value 3 or less` (28); `with mana value 2 or less` (14); `that targets a creature` (12).

## 9. `object-phrase` — 527 occurrences, 187 texts

paths: `[].effect.object` (270), `[].trigger.event.object` (234), `[].effect[].object` (14), `[].effect.trigger.event.object` (5), `[].if.object` (4).

| value shape | occurrences | texts |
|---|---:|---:|
| `a noncreature spell` | 74 | 40 |
| `a creature type` | 61 | 10 |
| `the battlefield` | 51 | 20 |
| `top card of your library` | 34 | 2 |
| `a color` | 33 | 9 |
| `your second card each turn` | 32 | 17 |
| `a card` | 29 | 13 |
| `a spell` | 28 | 13 |
| `one or both` | 26 | 2 |
| `a nonland card from it` | 17 | 3 |
| `an instant or sorcery spell` | 16 | 5 |
| `odd or even` | 10 | 2 |
| `up to five M worth of modes` | 10 | 1 |
| `one that hasn't been chosen` | 9 | 5 |
| `one that hasn't been chosen this turn` | 8 | 4 |
| `of those piles` | 6 | 1 |
| `a card name` | 6 | 1 |
| `a number between N and N` | 5 | 2 |
| `of those cards` | 4 | 2 |
| `a nonland card name` | 4 | 1 |
| `cards in hand` | 4 | 2 |
| `a basic land type` | 3 | 1 |
| `a card type other than creature` | 3 | 1 |
| `a card at random exiled with this enchantment` | 3 | 1 |
| `or more instead` | 3 | 2 |
| `a player` | 3 | 2 |
| `a nonland permanent card from it` | 3 | 1 |
| `an artifact or creature card from it` | 3 | 1 |
| `a permanent they control of each permanent type and sacrifices the res` | 3 | 1 |
| `of the piles` | 2 | 1 |
| `any card name` | 2 | 1 |
| `exactly two creatures you control` | 2 | 1 |
| `target creature you control and target equipment` | 2 | 1 |
| `target creature you control and target creature you don't control` | 2 | 1 |
| `a land card name` | 2 | 1 |
| `target opponent and up to one target creature they control` | 2 | 1 |
| `a noncreature or dragon spell` | 2 | 1 |
| `life for the first time each turn` | 2 | 2 |
| `up to that many target creatures you control` | 2 | 1 |
| `a nonlegendary creature that saddled it this turn and create a tapped ` | 2 | 1 |
| `an instant or sorcery card from it` | 2 | 1 |
| `target enchantment you control that doesn't have the same name as anot` | 2 | 1 |
| `a creature you control or a warped creature card you own in exile` | 1 | 1 |
| `a creature you control or reveal a creature card from your hand` | 1 | 1 |
| `target creature you control and target creature an opponent controls` | 1 | 1 |
| `target nontoken creature you control that doesn't have the same name a` | 1 | 1 |
| `target creatures controlled by the same opponent` | 1 | 1 |
| `any number of creatures they control with total power N or less` | 1 | 1 |
| `of those creatures` | 1 | 1 |
| `target permanent card in your graveyard that was put there from anywhe` | 1 | 1 |
| `a noncreature or otter spell` | 1 | 1 |
| `life for the first time during each of your turns` | 1 | 1 |

examples: `a noncreature spell` (40); `the battlefield` (20); `your second card each turn` (17).

## 10. `quoted-ability` — 325 occurrences, 182 texts

paths: `[].effect.token.quote` (142), `[].effect.quote` (123), `[].effect[].quote` (59), `[].effect[].token.quote` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `"this token can't block."` | 21 | 15 |
| `"M: target creature you control gets +N/+N until end of turn. activate` | 16 | 11 |
| `"whenever you cast a noncreature spell, this token deals N damage to e` | 16 | 4 |
| `"this token saddles mounts and crews vehicles as though its power were` | 13 | 9 |
| `"M: add one mana of any color."` | 12 | 5 |
| `"this token can block only creatures with flying."` | 7 | 5 |
| `"whenever a land you control enters, this token gets +N/+N until end o` | 7 | 4 |
| `"equipped creature gets +N/+N"` | 7 | 4 |
| `"whenever this token attacks, you gain N life."` | 6 | 5 |
| `"M: add M."` | 6 | 3 |
| `"ward—pay N life."` | 5 | 2 |
| `"whenever a creature dies, target opponent loses N life and you gain N` | 5 | 1 |
| `"this token can't block or be blocked by non-spirit creatures."` | 5 | 3 |
| `"whenever a player casts a spell, you create a PT blue ninja creature ` | 5 | 1 |
| `"M, M, sacrifice this artifact: you gain N life."` | 4 | 2 |
| `"this token can't block,"` | 4 | 2 |
| `"M, exile ~: you control target opponent during their next turn. this ` | 4 | 1 |
| `"M, sacrifice this creature: add three mana of any one color."` | 4 | 1 |
| `"this token's power and toughness are each equal to the number of arti` | 4 | 2 |
| `"M, sacrifice this token: add three mana of any one color."` | 4 | 1 |
| `"ninjas you control get +N/+N."` | 4 | 1 |
| `"whenever an artifact you control enters, this emblem deals N damage t` | 4 | 1 |
| `"whenever ~ deals combat damage to a player, exile the top card of you` | 4 | 1 |
| `"M, M: target creature gets +N/+N until end of turn for each creature ` | 3 | 1 |
| `"whenever this creature deals combat damage to a player, draw a card f` | 3 | 1 |
| `"MMM: turn this creature face up. if you can't, exile it, then you may` | 3 | 1 |
| `"M: add M or M. spend this mana only to cast a creature spell."` | 3 | 1 |
| `"creatures you control have 'M: add M, M, or M.'"` | 3 | 1 |
| `"whenever this creature is dealt damage, put that many +N/+N counters ` | 3 | 1 |
| `"equipped creature gets +N/+N and has vigilance, trample, and haste"` | 3 | 1 |
| `"this token gets +N/+N for each artifact you control."` | 3 | 1 |
| `"instant and sorcery spells you cast have storm."` | 3 | 1 |
| `"creatures you control get +N/+N and have vigilance, trample, and inde` | 3 | 1 |
| `"whenever this creature deals combat damage to a player, draw cards eq` | 3 | 1 |
| `"M, sacrifice this artifact: it deals damage to any target equal to N ` | 2 | 1 |
| `"M: add M. spend this mana only to cast a spell from anywhere other th` | 2 | 1 |
| `"this token attacks each combat if able."` | 2 | 1 |
| `"this token gets +N/+N for each other rat you control,"` | 2 | 1 |
| `"whenever galactus attacks, destroy target land."` | 2 | 1 |
| `"when this token dies, it deals N damage to each opponent."` | 2 | 1 |
| `"whenever this creature attacks, you gain N life."` | 2 | 2 |
| `"whenever this creature attacks, untap target attacking creature,"` | 2 | 1 |
| `"whenever this creature attacks, tap target creature an opponent contr` | 2 | 1 |
| `"whenever this creature attacks, you may sacrifice an artifact other t` | 2 | 1 |
| `"if a creature dying causes a triggered ability of this creature or an` | 2 | 1 |
| `"whenever you cast a noncreature spell and whenever you draw your thir` | 2 | 1 |
| `"whenever this token attacks, you may mill a card."` | 2 | 1 |
| `"M: add two mana of any one color. spend this mana only to cast instan` | 2 | 1 |
| `"M: create a token that's a copy of target token you control that ente` | 2 | 1 |
| `"M, M, sacrifice this permanent: you gain N life."` | 2 | 1 |
| `"[+N]: this planeswalker deals N damage to each opponent and you gain ` | 2 | 1 |
| `"[−N]: put a +N/+N counter on target creature for each land you contro` | 2 | 1 |
| `"at the beginning of the end step, sacrifice this token."` | 2 | 1 |
| `"when this creature dies, return it to the battlefield tapped under it` | 2 | 2 |
| `"when this creature dies, return it to the battlefield tapped under it` | 2 | 1 |
| `"~'s base power is equal to the number of cards in your hand."` | 2 | 1 |
| `"beau's power and toughness are each equal to the number of lands you ` | 2 | 1 |
| `"this token can't attack or block alone."` | 2 | 1 |
| `"the void attacks each combat if able."` | 2 | 1 |
| `"when this token leaves the battlefield, it deals N damage to any targ` | 2 | 1 |
| `"M, sacrifice this token: add one mana of any color."` | 2 | 1 |
| `"when this token enters, it deals N damage to any target"` | 2 | 1 |
| `"creatures you control of the chosen type get +N/+N and have vigilance` | 2 | 1 |
| `"whenever this creature deals combat damage to a player, that player l` | 2 | 1 |
| `"creatures you control get +N/+N."` | 2 | 1 |
| `"at the beginning of combat on your turn, if a card was put into exile` | 2 | 1 |
| `"whenever you cast a spell, draw a card."` | 2 | 1 |
| `"whenever you gain life, target opponent loses that much life."` | 2 | 1 |
| `"at the beginning of combat on your turn, put three +N/+N counters on ` | 2 | 1 |
| `"whenever you cast a spell, this emblem deals N damage to any target."` | 2 | 1 |
| `"whenever you cast an instant or sorcery spell, this creature gets +N/` | 2 | 1 |
| `"whenever this creature is dealt damage, you draw that many cards and ` | 2 | 1 |
| `"whenever this creature deals combat damage to a player, draw a card."` | 2 | 1 |
| `"during your turn, this creature has first strike."` | 2 | 1 |
| `"whenever this creature deals combat damage to a player, draw two card` | 1 | 1 |
| `"whenever redwing attacks, surveil N."` | 1 | 1 |
| `"whenever this creature deals combat damage to a player, investigate."` | 1 | 1 |
| `"M: untap this creature."` | 1 | 1 |
| `"M: add two mana of any one color."` | 1 | 1 |
| `"M, M, sacrifice this artifact: you gain N life"` | 1 | 1 |
| `"M: add M"` | 1 | 1 |
| `"whenever this creature attacks, you may sacrifice ~. when you do, thi` | 1 | 1 |
| `"whenever you cast a noncreature spell, this creature deals N damage t` | 1 | 1 |
| `"whenever this creature attacks, create a treasure token."` | 1 | 1 |
| `"whenever this creature attacks, draw a card, then discard a card."` | 1 | 1 |
| `"whenever this creature attacks, surveil N."` | 1 | 1 |
| `"whenever this creature deals combat damage, untap it and you gain N l` | 1 | 1 |
| `"M, M, sacrifice ~: destroy target artifact or enchantment."` | 1 | 1 |
| `"M, M: tap target creature."` | 1 | 1 |
| `"whenever this creature attacks, you gain N life,"` | 1 | 1 |
| `"whenever this creature deals combat damage to a player, draw a card,"` | 1 | 1 |
| `"whenever this creature deals combat damage to a player, draw a card, ` | 1 | 1 |
| `"whenever this creature attacks, it gains your choice of trample or de` | 1 | 1 |
| `"whenever you cast a noncreature spell, this creature gets +N/+N until` | 1 | 1 |
| `"M, M, tap ~: put a bait counter on ~."` | 1 | 1 |
| `"M, M: tap target creature. return ~ to its owner's hand."` | 1 | 1 |
| `"whenever this creature attacks, you may put a creature card from your` | 1 | 1 |
| `"M, pay N life: add one mana of any color."` | 1 | 1 |
| `"no more than one creature can attack this planeswalker each combat."` | 1 | 1 |
| `"[+N]: add M."` | 1 | 1 |
| `"[−N]: create a PT colorless wizard soldier creature token named cadet` | 1 | 1 |
| `"[−N]: you may sacrifice a creature. if you do, create a PT green beas` | 1 | 1 |
| `"[−N]: when you next cast an instant or sorcery spell this turn, copy ` | 1 | 1 |
| `"[−N]: create a PT green beast creature token with trample."` | 1 | 1 |
| `"[−N]: this planeswalker deals N damage to up to one target creature o` | 1 | 1 |
| `"[−N]: create an PT blue leviathan creature token with hexproof."` | 1 | 1 |
| `"the tiger god can't be blocked by more than one creature."` | 1 | 1 |
| `"landfall — whenever a land you control enters, create a PT green elf ` | 1 | 1 |
| `"when this creature dies, draw a card."` | 1 | 1 |
| `"this creature can't be blocked by more than one creature."` | 1 | 1 |
| `"whenever this creature deals combat damage to a player, destroy targe` | 1 | 1 |
| `"when this creature dies, return it to the battlefield tapped under it` | 1 | 1 |
| `"when this creature dies, put a number of +N/+N counters equal to its ` | 1 | 1 |
| `"when this creature dies, return it to the battlefield under its owner` | 1 | 1 |
| `"when this creature dies, return it to the battlefield tapped under it` | 1 | 1 |
| `"landfall — whenever a land you control enters, put a +N/+N counter on` | 1 | 1 |
| `"this creature can't block."` | 1 | 1 |
| `"this creature's power and toughness are each equal to the number of l` | 1 | 1 |
| `"when this creature deals combat damage, sacrifice it."` | 1 | 1 |

examples: `"This token can't block."` (15); `"{T}: Target creature you control gets +1/+0 until end of turn. Activa` (11); `"This token saddles Mounts and crews Vehicles as though its power were` (8).

## 11. `target-label` — 267 occurrences, 115 texts

paths: `[].effect.card.label` (87), `[].trigger.event.object.label` (54), `[].trigger.event.subject.label` (23), `[].effect.target.label` (20), `[].if.subject.label` (10), `[].effect.unless.label` (10), `[].effect.unless.lists[].label` (10), `[].condition.label` (8), `[].condition.lists[].label` (8), `[].effect[].target.label` (7), `[].effect.spell.label` (7), `[].effect.inner.card.label` (6), `[].effect.object.label` (6), `[].if.label` (3), `[].if.lists[].label` (3), `[].effect.inner.card.card_type.label` (3), `[].effect[].card.label` (1), `[].effect.card.card_type.label` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `an instant or sorcery spell` | 51 | 27 |
| `target creature or planeswalker` | 21 | 2 |
| `target artifact or enchantment` | 16 | 3 |
| `target creature or enchantment` | 9 | 2 |
| `a card or token` | 9 | 2 |
| `target artifact or creature` | 7 | 3 |
| `another creature or planeswalker you control` | 6 | 4 |
| `all creatures and vehicles` | 5 | 1 |
| `up to one target artifact or creature` | 5 | 1 |
| `target creature or vehicle` | 4 | 3 |
| `instant and sorcery spells you control` | 4 | 2 |
| `a nontoken, non-angel creature you control` | 4 | 1 |
| `target creature, planeswalker, or vehicle` | 3 | 1 |
| `target attacking or blocking creature` | 3 | 1 |
| `an instant or sorcery card` | 3 | 2 |
| `target artifact or creature you control` | 3 | 1 |
| `another creature or artifact` | 3 | 2 |
| `target equipment, instant, or sorcery card` | 3 | 1 |
| `another creature or artifact you control` | 3 | 2 |
| `it's the first instant spell, the first sorcery spell, or the first ot` | 3 | 1 |
| `the first instant spell, the first sorcery spell, or the first otter s` | 3 | 1 |
| `an artifact, instant, or sorcery spell` | 3 | 1 |
| `an artifact, enchantment, or token` | 2 | 1 |
| `target artifact or enchantment spell` | 2 | 1 |
| `target white or black spell` | 2 | 1 |
| `target creature or spacecraft` | 2 | 2 |
| `target creature, enchantment, or planeswalker` | 2 | 1 |
| `target noncreature, nonland permanent with mana value N or less` | 2 | 1 |
| `target skeleton, spirit, or zombie` | 2 | 1 |
| `a lizard, mouse, otter, or raccoon you control would deal damage to a ` | 2 | 1 |
| `a lizard, mouse, otter, or raccoon you control` | 2 | 1 |
| `an instant or sorcery card is exiled this way` | 2 | 1 |
| `other rabbits, bats, birds, and mice you control` | 2 | 1 |
| `skeletons and zombies you control` | 2 | 1 |
| `a dragon spell or an omen spell` | 2 | 1 |
| `that creature is a mutant, ninja, or turtle` | 2 | 1 |
| `a mutant, ninja, or turtle` | 2 | 1 |
| `you control a forest or a plains` | 2 | 1 |
| `a forest or a plains` | 2 | 1 |
| `you control a mountain or a forest` | 2 | 1 |
| `a mountain or a forest` | 2 | 1 |
| `you control a plains or an island` | 2 | 1 |
| `a plains or an island` | 2 | 1 |
| `you control a swamp or a mountain` | 2 | 1 |
| `a swamp or a mountain` | 2 | 1 |
| `you control an island or a swamp` | 2 | 1 |
| `an island or a swamp` | 2 | 1 |
| `another frog, rabbit, raccoon, or squirrel you control` | 2 | 1 |
| `another goblin, orc, or army you control` | 2 | 1 |
| `another artifact or creature` | 2 | 1 |
| `one or more other rabbits, bats, birds, and/or mice you control` | 2 | 1 |
| `up to one target artifact, creature, or planeswalker an opponent contr` | 2 | 1 |
| `a noncreature spell or a dragon spell` | 2 | 1 |
| `an artifact or lesson spell` | 2 | 1 |
| `an artifact or creature` | 2 | 1 |
| `MM: goblins and orcs you control` | 2 | 1 |
| `an artifact or creature you control` | 2 | 1 |
| `target artifact or creature spell` | 1 | 1 |
| `target creature or enchantment spell` | 1 | 1 |
| `target red or green spell` | 1 | 1 |
| `target artifact or land an opponent controls` | 1 | 1 |
| `target artifact or tapped creature` | 1 | 1 |
| `target creature or enchantment an opponent controls` | 1 | 1 |
| `target green or white creature` | 1 | 1 |
| `target land creature or nonbasic land` | 1 | 1 |
| `target noncreature, nonland permanent` | 1 | 1 |
| `exhaust — MMM: creatures and vehicles you control` | 1 | 1 |
| `target artifact, creature, or enchantment` | 1 | 1 |
| `target creature, vehicle, or nonbasic land` | 1 | 1 |
| `up to one noncreature, nonland card` | 1 | 1 |
| `up to one target creature or land you control` | 1 | 1 |
| `it's an artifact or creature card` | 1 | 1 |
| `an artifact or creature card` | 1 | 1 |
| `that creature is a bird, frog, otter, or rat` | 1 | 1 |
| `a bird, frog, otter, or rat` | 1 | 1 |
| `max speed — sacrifice this enchantment: creatures and vehicles you con` | 1 | 1 |
| `a red instant or sorcery spell` | 1 | 1 |
| `target noncreature, nonland permanent card` | 1 | 1 |
| `target noncreature, nonland card` | 1 | 1 |
| `another squirrel or food you control` | 1 | 1 |
| `one or more noncreature, nonland permanents you control` | 1 | 1 |
| `an artifact or creature spell` | 1 | 1 |
| `a noncreature, nonland card` | 1 | 1 |

examples: `an instant or sorcery spell` (26); `another creature or planeswalker you control` (4); `target artifact or enchantment` (3).

## 12. `predicate` — 222 occurrences, 104 texts

paths: `[].effect.predicate` (188), `[].effect[].predicate` (33), `[][].predicate` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `be blocked` | 134 | 78 |
| `attack or block` | 30 | 11 |
| `be countered` | 15 | 4 |
| `cast spells` | 14 | 2 |
| `activate abilities` | 13 | 5 |
| `lose mana` | 6 | 1 |
| `cast spells or activate abilities` | 3 | 1 |
| `gain life` | 3 | 1 |
| `play cards` | 3 | 1 |
| `be prevented` | 2 | 1 |

examples: `be blocked` (63); `be blocked` (14); `attack or block` (10).

## 13. `colour-list` — 127 occurrences, 77 texts

paths: `[].effect.token.colors` (115), `[].effect[].token.colors` (12).

| value shape | occurrences | texts |
|---|---:|---:|
| `green and white` | 29 | 15 |
| `black and green` | 19 | 14 |
| `white and black` | 19 | 11 |
| `white and blue` | 17 | 11 |
| `green and blue` | 12 | 9 |
| `blue and black` | 11 | 6 |
| `red and white` | 9 | 5 |
| `blue and red` | 8 | 4 |
| `black and red` | 3 | 2 |

examples: `green and white` (15); `black and green` (14); `white and black` (11).

## 14. `for-each` — 98 occurrences, 39 texts

paths: `[].effect.for_each` (72), `[].effect.with.for_each` (26).

| value shape | occurrences | texts |
|---|---:|---:|
| `artificer you control and each artificer card in your graveyard` | 16 | 1 |
| `opponent who lost life this turn` | 6 | 2 |
| `color of mana spent to cast it` | 5 | 1 |
| `creature card exiled this way` | 5 | 1 |
| `fellowship counter on this artifact` | 4 | 1 |
| `creature you control with power N or greater` | 4 | 2 |
| `equipment you control` | 4 | 1 |
| `creature you control of the chosen type` | 4 | 1 |
| `instant and sorcery card in your graveyard` | 4 | 1 |
| `angel you already control` | 3 | 1 |
| `dog and/or wolf you control` | 3 | 1 |
| `land that entered the battlefield under your control this turn` | 2 | 1 |
| `charge counter on ~` | 2 | 1 |
| `land you control with a flood counter on it` | 2 | 1 |
| `color of the creature it targets` | 2 | 1 |
| `other town you control` | 2 | 1 |
| `basic island you control` | 2 | 1 |
| `color among allies you control` | 2 | 1 |
| `attacking creature` | 2 | 1 |
| `creature that attacked this turn` | 2 | 1 |
| `permanent card in your graveyard` | 2 | 1 |
| `permanent sacrificed this way` | 2 | 1 |
| `target beyond the first` | 2 | 1 |
| `color among permanents you control` | 2 | 1 |
| `color of mana spent to cast that spell` | 2 | 1 |
| `+N/+N counter on the creature it targets` | 1 | 1 |
| `island you control` | 1 | 1 |
| `town you control` | 1 | 1 |
| `page counter on this artifact` | 1 | 1 |
| `creature that died under your control this turn` | 1 | 1 |
| `other creature and/or artifact you control` | 1 | 1 |
| `creature you control and each creature card in your graveyard` | 1 | 1 |
| `cave you control and each cave card in your graveyard` | 1 | 1 |
| `artifact and/or creature card in your graveyard` | 1 | 1 |
| `creature card in your graveyard` | 1 | 1 |
| `creature card you own in exile and in your graveyard` | 1 | 1 |
| `other instant and sorcery spell you've cast before it this turn` | 1 | 1 |

examples: `creature you control with power 4 or greater` (2); `Artificer you control and each Artificer card in your graveyard` (1); `opponent who lost life this turn` (1).

## 15. `phrase` — 60 occurrences, 38 texts

paths: `[].effect.card.relative` (14), `[].trigger.event.of` (10), `[].xdef.xdef.of` (8), `[].instead_of` (8), `[].effect.of` (5), `[].effect.as_though` (5), `[].effect.inner.card.relative` (3), `[].trigger.event.into` (2), `[].xdef.xdef[].relative` (2), `[].effect.to.relative` (1), `[].effect.on.relative` (1), `[].effect.target.relative` (1).

| value shape | occurrences | texts |
|---|---:|---:|
| `a spell or ability you control for the first time each turn` | 10 | 8 |
| `mana spent to cast this spell` | 8 | 6 |
| `that was dealt damage this turn` | 7 | 5 |
| `target spell or ability with a single target` | 5 | 2 |
| `that attacked this turn` | 4 | 2 |
| `putting it into its owner's graveyard` | 4 | 2 |
| `that don't share a creature type with the chosen creature they control` | 4 | 1 |
| `that saddled it this turn` | 4 | 3 |
| `mana of any color` | 4 | 2 |
| `putting it into your hand` | 3 | 2 |
| `~ and at the beginning of your first main phase` | 2 | 1 |
| `that have a creature type in common` | 2 | 1 |
| `putting it into your graveyard` | 1 | 1 |
| `positive power` | 1 | 1 |
| `that share a creature type` | 1 | 1 |

examples: `a spell or ability you control for the first time each turn` (8); `mana spent to cast this spell` (6); `that was dealt damage this turn` (4).

## 16. `count` — 59 occurrences, 26 texts

paths: `[].effect.count` (20), `[].trigger.event.counter.count` (19), `[].effect.token.count` (14), `[].instead[].count` (3), `[].effect[].token.count` (3).

| value shape | occurrences | texts |
|---|---:|---:|
| `that many` | 37 | 14 |
| `one or more` | 19 | 10 |
| `any number of` | 2 | 1 |
| `twice x` | 1 | 1 |

examples: `one or more` (10); `that many` (7); `that many` (5).

## 17. `target` — 58 occurrences, 25 texts

paths: `[].effect.target` (58).

| value shape | occurrences | texts |
|---|---:|---:|
| `that ability` | 38 | 12 |
| `this ability` | 18 | 12 |
| `unlock cost s you pay` | 2 | 1 |

examples: `that ability` (12); `This ability` (12); `Unlock cost s you pay` (1).

## 18. `cost-phrase` — 19 occurrences, 8 texts

paths: `[].effect.inner.by` (19).

| value shape | occurrences | texts |
|---|---:|---:|
| `paying N life in addition to paying their other costs` | 4 | 1 |
| `removing six counters from among creatures you control in addition to ` | 4 | 1 |
| `removing three counters from among creatures you control in addition t` | 2 | 1 |
| `paying N life in addition to their other costs` | 2 | 1 |
| `discarding a card rather than paying its mana cost` | 2 | 1 |
| `discarding a card in addition to paying its other costs` | 2 | 1 |
| `foraging in addition to paying their other costs` | 2 | 1 |
| `paying N life and sacrificing an artifact or creature in addition to p` | 1 | 1 |

examples: `removing three counters from among creatures you control in addition t` (1); `paying 1 life in addition to their other costs` (1); `paying 3 life in addition to paying their other costs` (1).

## 19. `condition` — 5 occurrences, 3 texts

paths: `[].effect.unless` (3), `[].effect.mana_value` (2).

| value shape | occurrences | texts |
|---|---:|---:|
| `mana value N or less` | 2 | 1 |
| `less than or equal to the number of permanent cards in your graveyard` | 2 | 1 |
| `mana value N or greater` | 1 | 1 |

examples: `mana value 2 or less` (1); `mana value 4 or greater` (1); `less than or equal to the number of permanent cards in your graveyard` (1).

