# Hoisting: alternative-resolution shifts

`core/grammar_hoist.py` moves every optional into its own helper rule, which
takes `grammar.lark` from 9,644 Lark rules to 2,803 and per-sentence parse cost
from ~5.7 s to ~0.34 s (16.8x, `classic.json`). It cannot change the *language* —
both sides of every optional survive — and it does not change the parse tree
except for the removal of Lark's empty placeholder nodes.

It does renumber rules, and the grammar is genuinely ambiguous in a few places,
so `ambiguity='resolve'` can pick a different winning alternative. Verified over
all 2,148 unique `classic.json` sentences, with the same interpreter on both
sides:

| metric | raw grammar | hoisted |
|---|---|---|
| parsed | 2,074 / 2,148 | 2,074 / 2,148 |
| content units lost (`content_check`) | 112 / 2,074 = 5.4 % | **108 / 2,074 = 5.2 %** |
| interpreted output differs | — | **29 sentences (1.4 %)** |

The 34 shapes that differed before interpreter normalisation are listed below
(29 after): five turned out to be one target parsed two ways and are now
canonicalised in `interpret.py` — a bare pronoun (`this_that` vs `card_kind`), an
event with no object (`{}` vs `""`), a token's `for each` tail (was mislabelled
`attached_to`), a wrapped `search_target` whose card target was dropped, an ability
word left in the trigger keywords, an empty `card_target` shadowing the real
search target, and a stray `who` filled with an unresolved leading word.

Of the 29 remaining, the common pattern is that hoisting prefers the analysis
that consumes *more* of the sentence, which is why content loss went down:

- `Destroy target nonbasic land` — before: type `nonbasic`, `land` **lost**;
  after: `land` kept (`nonbasic` lands in `nontoken`).
- `Whenever a nontoken creature you control enters…` — before: type
  `nontoken`, `creature` **lost**; after: both kept.
- `Counter target spell with mana value X` — before: the restriction became a
  bogus `unless`; after: proper `modifier`.
- `…token for each land you control` — before: `for each` **lost**; after:
  `for_each`.
- `Landfall — Whenever …` — before: ability word **lost**; after:
  `trigger.ability_word`.
- `This creature can block any number of creatures` — before: `any number of`
  **lost**; after: `quantifier`.

A handful move the other way and are candidates for a later narrowing pass
(`Choose one or more` loses "or more"; `zone` appears as `{prep, zone}` instead
of a bare string in a few cast/reveal sentences; one search sentence now keeps
`zone: hand` with the card target intact where the raw parse dropped the zone).
None of them drop a sentence from the parsed set.

Reproduce with the comparison harness: build the raw and hoisted grammars
(`core/grammar_hoist.py grammar/grammar.lark /tmp/g.lark`), parse a corpus with
both, and diff `Interpreter.interp` output; `MLARK_RAW_GRAMMAR=1` makes
`build_parser` use the untransformed grammar.

### {4}, {T}, Sacrifice this land: Destroy target nonbasic land

- **before** `{"type": "activated", "cost": ["{4}", ",", "{T}", ",", "Sacrifice this land"], "effect": {"verb": "destroy", "card": {"quantifier": "target", "card_type": {"kind": "type", "value": "nonbasic"}}}}`
- **after**  `{"type": "activated", "cost": ["{4}", ",", "{T}", ",", "Sacrifice this land"], "effect": {"verb": "destroy", "card": {"quantifier": "target", "nontoken": ["nonbasic"], "card_type": {"kind": "type", "value": "land"}}}}`

### Choose one or more

- **before** `{"type": "effect", "effect": {"verb": "choose", "object": "or more", "amount": 1}}`
- **after**  `{"type": "effect", "effect": {"verb": "choose", "object": {"quantifier": "one"}}}`

### This creature can block any number of creatures

- **before** `{"type": "effect", "effect": {"verb": "can_block", "blocker": {"this_that": "This", "card_type": {"kind": "type", "value": "creature"}}, "attacker": {"card_type": {"kind": "type", "value": "creatures"}}}}`
- **after**  `{"type": "effect", "effect": {"verb": "can_block", "blocker": {"this_that": "This", "card_type": {"kind": "type", "value": "creature"}}, "attacker": {"quantifier": "any number of", "card_type": {"kind": "type", "value": "creatures"}}}}`

### [−3]: You may cast Zombie spells from your graveyard this turn

- **before** `{"type": "loyalty", "cost": "[\u22123]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"card_type": {"kind": "type", "value": "Zombie spells"}}, "zone": "graveyard"}}}`
- **after**  `{"type": "loyalty", "cost": "[\u22123]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"card_type": {"kind": "type", "value": "Zombie spells"}, "zone": {"prep": "from", "zone": "graveyard"}}}}}`

### You may reveal a creature card of the chosen type from among them and put it into your hand

- **before** `{"type": "effect", "effect": [{"verb": "may", "inner": {"verb": "reveal", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "creature"}, "modifier": "of the chosen type"}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "it"}}, "zone": "hand"}]}`
- **after**  `{"type": "effect", "effect": [{"verb": "may", "inner": {"verb": "reveal", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "creature"}, "modifier": "of the chosen type", "zone": {"prep": "from", "zone": "them"}}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "it"}}, "zone": "hand"}]}`

### Whenever a Swamp you control enters, choose one

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "Swamp"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "choose", "object": {}, "amount": 1}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "Swamp"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "choose", "object": "one"}}`

### Counter target spell with mana value X

- **before** `{"type": "effect", "effect": {"verb": "counter", "spell": {"quantifier": "target"}, "unless": "mana value X"}}`
- **after**  `{"type": "effect", "effect": {"verb": "counter", "spell": {"quantifier": "target", "card_type": {"kind": "type", "value": "spell"}, "modifier": "with mana value X"}}}`

### When this creature enters, choose one

- **before** `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "choose", "object": {}, "amount": 1}}`
- **after**  `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "choose", "object": "one"}}`

### [−6]: Create a 6/6 green Wurm creature token for each land you control

- **before** `{"type": "loyalty", "cost": "[\u22126]", "effect": {"verb": "create_token", "token": {"power_toughness": "6/6", "colors": "green", "types": ["Wurm", "creature"]}}}`
- **after**  `{"type": "loyalty", "cost": "[\u22126]", "effect": {"verb": "create_token", "token": {"power_toughness": "6/6", "colors": "green", "for_each": {"card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "types": ["Wurm", "creature"]}}}`

### Whenever a nontoken creature you control enters, you may pay {W}

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "nontoken"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "may", "inner": {"verb": "pay", "amount": "{W}"}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "nontoken": ["nontoken"], "card_type": {"kind": "type", "value": "creature"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "may", "inner": {"verb": "pay", "amount": "{W}"}}}`

### Whenever a player taps a nonbasic land for mana, this enchantment deals 1 damage to that player

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "player"}}, "object": {"quantifier": "a", "card_type": {"kind": "type", "value": "nonbasic"}}}}, "effect": {"verb": "deal_damage", "amount": 1, "source": {"this_that": "this", "card_type": {"kind": "type", "value": "enchantment"}}, "to": {"this_that": "that", "card_type": {"kind": "type", "value": "player"}}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "player"}}, "object": {"quantifier": "a", "nontoken": ["nonbasic"], "card_type": {"kind": "type", "value": "land"}}}}, "effect": {"verb": "deal_damage", "amount": 1, "source": {"this_that": "this", "card_type": {"kind": "type", "value": "enchantment"}}, "to": {"this_that": "that", "card_type": {"kind": "type", "value": "player"}}}}`

### Landfall — Whenever a land you control enters, create a 1/1 green Saproling creature token

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "1/1", "colors": "green", "types": ["Saproling", "creature"]}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}, "ability_word": "Landfall"}, "effect": {"verb": "create_token", "token": {"power_toughness": "1/1", "colors": "green", "types": ["Saproling", "creature"]}}}`

### All creatures able to block enchanted creature do so

- **before** `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"card_type": {"kind": "type", "value": "creatures"}}, "block": {"status": ["enchanted"], "card_type": {"kind": "type", "value": "creature"}}}}`
- **after**  `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"quantifier": "all", "card_type": {"kind": "type", "value": "creatures"}}, "block": {"status": ["enchanted"], "card_type": {"kind": "type", "value": "creature"}}}}`

### Create a 2/2 green Wolf creature token for each Forest you control

- **before** `{"type": "effect", "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "green", "types": ["Wolf", "creature"]}}}`
- **after**  `{"type": "effect", "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "green", "for_each": {"card_type": {"kind": "type", "value": "Forest"}, "controller": "you control"}, "types": ["Wolf", "creature"]}}}`

### Landfall — Whenever a land you control enters, you gain 3 life

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "gain_life", "who": "you", "amount": "3 life"}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}, "ability_word": "Landfall"}, "effect": {"verb": "gain_life", "who": "you", "amount": "3 life"}}`

### [−2]: You may cast target instant or sorcery card with mana value 3 or less from your graveyard

- **before** `{"type": "loyalty", "cost": "[\u22122]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"quantifier": "target", "card_type": {"kind": "type", "value": "instant or sorcery"}, "modifier": "with mana value 3 or less"}, "zone": "graveyard"}}}`
- **after**  `{"type": "loyalty", "cost": "[\u22122]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"quantifier": "target", "card_type": {"kind": "type", "value": "instant or sorcery"}, "modifier": "with mana value 3 or less", "zone": {"prep": "from", "zone": "graveyard"}}}}}`

### This creature can't be blocked as long as you've drawn two or more cards this turn

- **before** `{"type": "effect", "effect": {"verb": "can't", "card": {"this_that": "This", "card_type": {"kind": "type", "value": "creature"}}, "predicate": "be blocked", "condition": "you've drawn two or more cards"}}`
- **after**  `{"type": "effect", "effect": {"verb": "can't", "card": {"this_that": "This", "card_type": {"kind": "type", "value": "creature"}}, "predicate": "be blocked", "condition": "you've drawn two or more cards this turn"}}`

### You may reveal a creature card with power 2 or less from among them and put it into your hand

- **before** `{"type": "effect", "effect": [{"verb": "may", "inner": {"verb": "reveal", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "creature"}, "modifier": "with power 2 or less"}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "it"}}, "zone": "hand"}]}`
- **after**  `{"type": "effect", "effect": [{"verb": "may", "inner": {"verb": "reveal", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "creature"}, "modifier": "with power 2 or less", "zone": {"prep": "from", "zone": "them"}}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "it"}}, "zone": "hand"}]}`

### [−2]: You may cast target red instant or sorcery card from your graveyard

- **before** `{"type": "loyalty", "cost": "[\u22122]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"quantifier": "target", "colors": ["red"], "card_type": {"kind": "type", "value": "instant or sorcery"}}, "zone": "graveyard"}}}`
- **after**  `{"type": "loyalty", "cost": "[\u22122]", "effect": {"verb": "may", "inner": {"verb": "cast", "card": {"quantifier": "target", "colors": ["red"], "card_type": {"kind": "type", "value": "instant or sorcery"}, "zone": {"prep": "from", "zone": "graveyard"}}}}}`

### Choose two target players

- **before** `{"type": "effect", "effect": {"verb": "choose", "object": {"quantifier": "target", "card_type": {"kind": "type", "value": "players"}}, "amount": 2}}`
- **after**  `{"type": "effect", "effect": {"verb": "choose", "object": {"quantifier": 2, "card_type": {"kind": "type", "value": "players"}}}}`

### Landfall — Whenever a land you control enters, put a +1/+1 counter on target Elemental you control

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}}, "effect": {"verb": "put_counter", "on": {"quantifier": "target", "card_type": {"kind": "type", "value": "Elemental"}, "controller": "you control"}, "count": "a", "counter": "+1/+1 counter"}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "land"}, "controller": "you control"}, "verb": "enters", "object": {}}, "ability_word": "Landfall"}, "effect": {"verb": "put_counter", "on": {"quantifier": "target", "card_type": {"kind": "type", "value": "Elemental"}, "controller": "you control"}, "count": "a", "counter": "+1/+1 counter"}}`

### {G}: Choose one

- **before** `{"type": "activated", "cost": ["{G}"], "effect": {"verb": "choose", "object": {}, "amount": 1}}`
- **after**  `{"type": "activated", "cost": ["{G}"], "effect": {"verb": "choose", "object": "one"}}`

### All creatures able to block it this turn do so

- **before** `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"card_type": {"kind": "type", "value": "creatures"}}, "block": {"card_type": {"ref": "anaphora", "raw": "it"}}, "this_turn": true}}`
- **after**  `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"quantifier": "all", "card_type": {"kind": "type", "value": "creatures"}}, "block": {"card_type": {"ref": "anaphora", "raw": "it"}}, "this_turn": true}}`

### When this creature enters, you may search your library for a card named ~ and/or a card named ~, reveal them, put them into your hand, then shuffle

- **before** `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": [{"verb": "may", "inner": {"verb": "search", "zone": "library", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "card"}, "modifier": "named ~"}}}, {"verb": "reveal", "card": {"card_type": {"ref": "anaphora", "raw": "them"}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "them"}}, "zone": "hand"}, {"verb": "shuffle"}]}`
- **after**  `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": [{"verb": "may", "inner": {"verb": "search", "zone": "library", "card": {"quantifier": "a", "card_type": {"kind": "type", "value": "card"}}}}, {"verb": "reveal", "card": {"card_type": {"ref": "anaphora", "raw": "them"}}}, {"verb": "put", "card": {"card_type": {"ref": "anaphora", "raw": "them"}}, "zone": "hand"}, {"verb": "shuffle"}]}`

### When this creature enters, create a 2/2 black Zombie creature token for each card named ~ in your graveyard

- **before** `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "black", "types": ["Zombie", "creature"]}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "black", "for_each": {"card_type": {"kind": "type", "value": "card"}, "modifier": "named ~", "zone": {"prep": "in", "zone": "graveyard"}}, "types": ["Zombie", "creature"]}}}`

### When ~ enters, create a 1/1 white Soldier creature token for each nontoken creature you control

- **before** `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "1/1", "colors": "white", "types": ["Soldier", "creature"]}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "When", "event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "enters", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "1/1", "colors": "white", "for_each": {"card_type": {"kind": "type", "value": "nontoken"}, "controller": "you control"}, "types": ["Soldier", "creature"]}}}`

### Whenever this creature attacks or blocks, choose one

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}}}, "effect": {"verb": "choose", "object": {}, "amount": 1}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}}}, "effect": {"verb": "choose", "object": "one"}}`

### Whenever a nontoken creature you control dies, create a 2/2 black Zombie creature token

- **before** `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "card_type": {"kind": "type", "value": "nontoken"}, "controller": "you control"}, "verb": "dies", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "black", "types": ["Zombie", "creature"]}}}`
- **after**  `{"type": "triggered", "trigger": {"when": "Whenever", "event": {"subject": {"quantifier": "a", "nontoken": ["nontoken"], "card_type": {"kind": "type", "value": "creature"}, "controller": "you control"}, "verb": "dies", "object": {}}}, "effect": {"verb": "create_token", "token": {"power_toughness": "2/2", "colors": "black", "types": ["Zombie", "creature"]}}}`

### All creatures able to block this creature do so

- **before** `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"card_type": {"kind": "type", "value": "creatures"}}, "block": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}}}`
- **after**  `{"type": "effect", "effect": {"verb": "block_do_so", "subject": {"quantifier": "all", "card_type": {"kind": "type", "value": "creatures"}}, "block": {"this_that": "this", "card_type": {"kind": "type", "value": "creature"}}}}`
