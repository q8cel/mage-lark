# Certain defects — content loss in long sentences

Snapshot `Standard_1e032c36fb62eaea_056f23fd05529720.json`.

- sentences >=12 words checked: 4005
- sentences with >=1 missing content unit: 792 (19.8%)
- rows with missing units or defect evidence: 1866; top 100 written

Function-word allowlist: a after again all already also am an and another any are aren't as at back be been before being but by can can't cannot could delirium did didn't do does doesn't doing don't done down during each every few for from further had has have having he her here hers him his i if in into is isn't it it's its just least less little long many may me might mine more most much must my no none nor not of on once one only onto or other our ours out over own same shall she should so some such than that that's the their theirs them then there these they they're this those to under up us very was wasn't we we're were weren't when whenever where which who whom whose will with within without won't would wouldn't yet you you're your yours

Calibration (25 stratified samples): 15 true_loss, 5 structured_repr, 2 allowlist_gap, 3 scan_bug (signed-number tokenization). The scan now normalises signed numbers, carries a representation map for number/equal/greater/less/among/turn/target/cast/counter/additional/base/attacking/amount/resolved, and allowlists already/delirium/long. The rate below is the calibrated upper bound.

## Top missing units

| cast | 119 |
| equal | 73 |
| spell | 61 |
| card | 56 |
| creature | 54 |
| cards | 44 |
| until | 34 |
| among | 30 |
| end | 28 |
| artifact | 24 |
| land | 24 |
| mana | 20 |
| turn | 17 |
| cost | 17 |
| time | 16 |
| power | 16 |
| activate | 15 |
| choice | 15 |
| exhaust | 13 |
| owner | 13 |
| spent | 12 |
| control | 12 |
| renew | 12 |
| opponent | 11 |
| twice | 11 |
| battlefield | 11 |
| library | 11 |
| enchantment | 9 |
| enters | 9 |
| counters | 9 |

## Top 100 by length x missing content

### `1edbdcd6de43` — 32 words, score 256

Sentence: When you do, you may cast target instant or sorcery card with mana value equal to the number of coin counters on this artifact from your graveyard without paying its mana cost

Missing: mana, equal, coin, counters, artifact, graveyard, paying, cost

Evidence: stringy:1

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": [{"kind": "type", "value": "instant"}, {"kind": "type", "value": "sorcery"}], "modifier": "with", "quantifier": "target"}, "verb": "cast"}, "verb": "may"}, "trigger": {"event": {"actor": "you", "kind": "event_ref", "polarity": "positive"}, "when": "When"}, "type": "triggered"}]`

### `984269b68e5b` — 28 words, score 224

Sentence: If you do, discard a card unless a permanent entered the battlefield face down under your control this turn or you turned a permanent face up this turn

Missing: unless, permanent, entered, battlefield, face, control, turn, turned

Output (truncated): `[{"condition": {"actor": "you", "kind": "event_ref", "polarity": "positive"}, "effect": {"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "verb": "discard"}, "type": "if"}]`

### `a3058542f02d` — 31 words, score 186

Sentence: When ~ enters, it deals X damage divided as you choose among any number of target creatures and/or planeswalkers your opponents control, where X is the number of lands you control

Missing: divided, choose, target, creatures, planeswalkers, opponents

Output (truncated): `[{"effect": {"amount": {"kind": "x"}, "source": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "deal_damage"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "enters"}, "when": "When"}, "type": "triggered", "xdef": {"xdef": {"kind": "count", "of": {"card_type": {"kind": "type", "value": "lands"}, "controller": "you control"}, "unit": "lands"}}}]`

### `2bad88ef9f68` — 29 words, score 145

Sentence: When this creature enters, distribute three +1/+1 counters among one, two, or three target creatures, then you gain life equal to the greatest toughness among creatures you control

Missing: 3, counters, 2, target, equal

Output (truncated): `[{"effect": [{"verb": "distribute"}, {"amount": {"kind": "superlative", "set": {"card_type": [{"kind": "type", "value": "creature"}], "controller": "you"}, "stat": "toughness", "which": "greatest"}, "verb": "gain_life", "who": "you"}], "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}]`

### `92230a20b5ef` — 31 words, score 124

Sentence: {2}, {T}, Sacrifice this creature: Search your library for up to two basic land cards, reveal them, put one onto the battlefield tapped and the other into your hand, then shuffle

Missing: creature, library, put, battlefield

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}, {"action": "sacrifice", "card": {"card_type": {"kind": "this_card", "value": "~"}}, "kind": "cost"}], "effect": {"card": {"card_type": {"kind": "type", "value": "basic land"}, "quantifier": {"up_to": 2}}, "reveal": true, "then_shuffle": true, "verb": "search", "zone": "hand"}, "type": "activated"}]`

### `d9fa679bc166` — 20 words, score 120

Sentence: {X}: Destroy each nonland permanent with mana value X whose controller was dealt combat damage by this creature this turn

Missing: controller, dealt, combat, damage, creature, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{X}"]}], "effect": {"card": {"card_type": {"kind": "type", "value": "permanent"}, "modifier": {"kind": "stat_filter", "op": "=", "stat": "mana value", "value": "X"}, "nontoken": ["nonland"], "quantifier": "each"}, "verb": "destroy"}, "type": "activated"}]`

### `a9afab0bd06e` — 23 words, score 115

Sentence: Delirium — This spell costs {2} less to cast as long as there are four or more card types among cards in your graveyard

Missing: cast, 4, types, among, graveyard

Output (truncated): `[{"ability_word": "Delirium", "effect": {"amount": {"kind": "mana", "symbols": ["{2}"]}, "direction": "less", "target": {"card_type": {"kind": "type", "value": "spell"}, "this_that": "This"}, "verb": "cost_mod"}, "type": "static"}]`

### `d18384878aa5` — 22 words, score 110

Sentence: Until your next end step, you may play those cards, and mana of any type can be spent to cast those spells

Missing: until, next, end, step, spent

Output (truncated): `[{"effect": [{"inner": {"card": {"card_type": {"kind": "type", "value": "cards"}, "this_that": "those"}, "verb": "play"}, "verb": "may"}, {"mana": "any type", "target": {"card_type": {"kind": "type", "value": "spells"}, "this_that": "those"}, "verb": "spend_mana_only_to_cast"}], "type": "effect"}]`

### `b8ea2be3fd29` — 18 words, score 108

Sentence: When this artifact enters, distribute three +1/+1 counters among one, two, or three target creatures you control

Missing: 3, counters, among, 2, target, creatures

Evidence: unparsed

Output (truncated): `[{"effect": {"verb": "distribute"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "artifact"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}, {"fragment": "you control", "reason": "static_text", "source": "i_static_sentence", "type": "unparsed"}]`

### `420032220dc4` — 26 words, score 104

Sentence: Search your library for up to two basic Forest cards, reveal them, put one onto the battlefield tapped and the other into your hand, then shuffle

Missing: library, put, battlefield, tapped

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "type", "value": "basic forest"}, "quantifier": {"up_to": 2}}, "reveal": true, "then_shuffle": true, "verb": "search", "zone": "hand"}, "type": "effect"}]`

### `a22499eee5a1` — 24 words, score 96

Sentence: Whenever this creature or another Detective you control enters and whenever a Detective you control is turned face up, you may draw a card

Missing: creature, detective, control, enters

Output (truncated): `[{"effect": {"inner": {"amount": 1, "verb": "draw", "who": "You"}, "verb": "may"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `c7c08a932515` — 19 words, score 95

Sentence: {1}{U}, {T}: Shuffle this creature and target creature with a stun counter on it into their owners' libraries

Missing: creature, stun, counter, owners', libraries

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{1}", "{U}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}], "effect": {"verb": "shuffle"}, "type": "activated"}]`

### `2ee641685950` — 18 words, score 90

Sentence: When this creature enters, distribute three +1/+1 counters among one, two, or three target creatures you control

Missing: 3, counters, among, 2, target

Evidence: unparsed

Output (truncated): `[{"effect": {"verb": "distribute"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}, {"fragment": "you control", "reason": "static_text", "source": "i_static_sentence", "type": "unparsed"}]`

### `1fa843f8ed81` — 15 words, score 90

Sentence: You may collect evidence 10 rather than pay the mana cost for spells you cast

Missing: rather, pay, mana, cost, spells, cast

Output (truncated): `[{"effect": {"inner": {"amount": 10, "verb": "collect_evidence"}, "verb": "may"}, "type": "effect"}]`

### `a9a54473cd60` — 29 words, score 87

Sentence: Whenever a face-down permanent you control enters and whenever this creature or another permanent you control is turned face up, put a +1/+1 counter on this creature

Missing: permanent, control, enters

Output (truncated): `[{"effect": {"count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "put_counter"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `78339424f0da` — 28 words, score 84

Sentence: Survival — At the beginning of your second main phase, if this creature is tapped, reveal cards from the top of your library until you reveal a land card

Missing: creature, until, land

Output (truncated): `[{"effect": {"amount": 1, "card": {"card_type": {"kind": "type", "value": "cards"}}, "top": true, "verb": "reveal", "zone": "library"}, "if": {"kind": "state", "state": {"status": "tapped"}, "subject": {"card_type": {"kind": "this_card", "value": "~"}}}, "trigger": {"ability_word": "Survival", "when": {"phase": "main_phase", "player": "you", "position": "beginning", "which": "second"}}, "type": "triggered"}]`

### `072b5c260b3a` — 14 words, score 84

Sentence: Distribute three +1/+1 counters among one, two, or three target creatures you control

Missing: 3, counters, among, 2, target, creatures

Evidence: unparsed

Output (truncated): `[{"effect": {"verb": "distribute"}, "type": "effect"}, {"fragment": "you control", "reason": "static_text", "source": "i_static_sentence", "type": "unparsed"}]`

### `68534a12072e` — 14 words, score 84

Sentence: Target player shuffles up to four target cards from their graveyard into their library

Missing: target, player, 4, cards, graveyard, library

Output (truncated): `[{"effect": {"verb": "shuffle"}, "type": "effect"}]`

### `1fb4a4a8d5a3` — 16 words, score 80

Sentence: When ~ enters, he deals 3 damage divided as you choose among one, two, or three targets

Missing: divided, choose, among, 2, targets

Output (truncated): `[{"effect": {"amount": 3, "source": {"card_type": {"raw": "he", "ref": "anaphora"}}, "verb": "deal_damage"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "enters"}, "when": "When"}, "type": "triggered"}]`

### `6399cc6ceb8d` — 16 words, score 80

Sentence: When you do, it deals 7 damage divided as you choose among one or two targets

Missing: divided, choose, among, 2, targets

Output (truncated): `[{"effect": {"amount": 7, "source": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "deal_damage"}, "trigger": {"event": {"actor": "you", "kind": "event_ref", "polarity": "positive"}, "when": "When"}, "type": "triggered"}]`

### `a90fbed5cd8d` — 16 words, score 80

Sentence: This creature enters with a number of stun counters on it equal to three minus X

Missing: stun, counters, equal, 3, minus

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "This"}, "verb": "enters"}, "type": "effect"}]`

### `5a6a024a553a` — 25 words, score 75

Sentence: Whenever another Detective you control enters and whenever a Detective you control is turned face up, this creature gets +1/+1 until end of turn

Missing: detective, control, enters

Output (truncated): `[{"effect": {"change": {"power": 1, "toughness": 1}, "duration": {"event": "end_of_turn", "kind": "until"}, "target": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "stat_change"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `7fb2c6ec9a48` — 25 words, score 75

Sentence: You may cast this card from your graveyard by paying 2 life and sacrificing an artifact or creature in addition to paying its other costs

Missing: sacrificing, artifact, creature

Output (truncated): `[{"effect": {"inner": {"by": {"actions": [{"action": "pay_life", "amount": 2}], "addition_to_other_costs": true, "kind": "cost_phrase"}, "card": {"card_type": {"kind": "type", "value": "card"}, "this_that": "this", "zone": {"possessor": "your", "prep": "from", "zone": "graveyard"}}, "verb": "cast"}, "verb": "may"}, "type": "effect"}]`

### `fa7cad918d07` — 25 words, score 75

Sentence: When that mana is spent to cast a red instant or sorcery spell, copy that spell and you may choose new targets for the copy

Missing: mana, spent, cast

Evidence: stringy:2, empty:1

Output (truncated): `[{"effect": [{"target": {"this_that": "that"}, "verb": "copy"}, {"for": {"kind": "copy"}, "modal": "may", "verb": "choose_new_targets"}], "trigger": {"event": {"object": {"connector": "or", "items": ["a red instant", "sorcery spell"], "kind": "set", "label": {"card_class": "spell", "card_type": [{"kind": "type", "value": "red instant"}, {"kind": "type", "value": "sorcery"}], "quantifier": "a"}, "logic": "union"}}, "when": "When"}, "type": "triggered"}]`

### `efe15d5f2ace` — 15 words, score 75

Sentence: Target player adds three mana of the chosen color for each artifact sacrificed this way

Missing: chosen, color, artifact, sacrificed, way

Output (truncated): `[{"effect": {"amount": 3, "verb": "add_mana", "who": "Target player"}, "type": "effect"}]`

### `59c31eda89ae` — 24 words, score 72

Sentence: {1}, {T}: Target artifact you control becomes a copy of a second target artifact you control until end of turn, except it isn't legendary

Missing: second, until, end

Evidence: stringy:1

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{1}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}], "effect": {"copy_of": {"card_type": {"kind": "type", "value": "artifact"}, "controller": "you control", "quantifier": "a"}, "except": ", except it isn't legendary", "target": {"card_type": {"kind": "type", "value": "artifact"}, "controller": "you control", "quantifier": "target"}, "verb": "become"}, "type": "activated"}]`

### `2f6eb601733e` — 35 words, score 70

Sentence: At the beginning of each combat, if you've cast two or more spells this turn, this enchantment becomes a 3/3 Monk creature with haste in addition to its other types until end of turn

Missing: until, end

Output (truncated): `[{"effect": {"in_addition": true, "keywords": ["haste"], "pt": {"power": 3, "toughness": 3}, "target": {"card_type": {"kind": "type", "value": "enchantment"}, "this_that": "this"}, "types": ["Monk", "creature"], "verb": "become"}, "if": {"event": {"object": {"card_type": {"kind": "type", "value": "spells"}, "quantifier": {"at_least": 2}}, "subject": "you", "verb": "cast"}, "kind": "event", "this_turn": true}, "trigger": {"when": {"phase": "combat", "player": "each", "position": "beginning"}}, "type": "triggered"}]`

### `3c642dadcb3d` — 14 words, score 70

Sentence: You may shuffle up to four target cards from your graveyard into your library

Missing: 4, target, cards, graveyard, library

Output (truncated): `[{"effect": {"inner": {"verb": "shuffle"}, "verb": "may"}, "type": "effect"}]`

### `6ae50147e2a1` — 23 words, score 69

Sentence: As long as equipped creature's toughness is greater than its power, it assigns combat damage equal to its toughness rather than its power

Missing: damage, equal, rather

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "equipped creature's toughness is greater than its power", "reason": "condition_text", "source": "i_as_long", "unparsed": true}, "effect": {"basis": "toughness", "card": {"card_type": {"raw": "it", "ref": "anaphora"}}, "instead_of": "power", "verb": "assign_combat"}, "type": "as_long"}]`

### `69409c4359ec` — 22 words, score 66

Sentence: Once during each of your turns, you may cast an instant or sorcery spell from your hand without paying its mana cost

Missing: spell, mana, cost

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": [{"kind": "type", "value": "instant"}, {"kind": "type", "value": "sorcery"}], "quantifier": "an", "zone": {"possessor": "your", "prep": "from", "zone": "hand"}}, "verb": "cast", "without_paying": true}, "verb": "may"}, "once_each_turn": true, "type": "static"}]`

### `753737f89df7` — 22 words, score 66

Sentence: Find New Host — {2}{U/B}, Exile this card from your graveyard: Put a +1/+1 counter on target creature you control

Missing: find, new, host

Evidence: stringy:1

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{U/B}"]}, {"action": "exile", "kind": "cost", "target": {"card_type": {"kind": "type", "value": "this card from your graveyard"}}}], "effect": {"count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"kind": "type", "value": "creature"}, "controller": "you control", "quantifier": "target"}, "verb": "put_counter"}, "type": "activated"}]`

### `e22199ec8f4a` — 13 words, score 65

Sentence: Double all damage that sources you control of the chosen type would deal

Missing: damage, sources, control, chosen, deal

Output (truncated): `[{"effect": {"multiplier": 2, "verb": "double"}, "type": "effect"}]`

### `743d7e093856` — 21 words, score 63

Sentence: You may pay {B} rather than pay this spell's mana cost if there are thirteen or more creatures on the battlefield

Missing: rather, spell, cost

Evidence: unparsed

Output (truncated): `[{"effect": {"inner": {"amount": {"kind": "mana", "symbols": ["{B}"]}, "verb": "pay"}, "verb": "may"}, "if": {"fragment": "there are thirteen or more creatures on the battlefield", "reason": "condition_text", "source": "i_effect", "unparsed": true}, "type": "effect"}]`

### `c920649b7424` — 21 words, score 63

Sentence: Flare Star — If a Wizard you control would deal damage to a permanent or player, it deals double that damage instead

Missing: flare, star, double

Output (truncated): `[{"if": {"subject": {"card_type": {"kind": "type", "value": "Wizard"}, "controller": "you control", "quantifier": "a"}, "to": {"or": [{"card_type": {"kind": "type", "value": "permanent"}, "quantifier": "a"}, {"card_type": {"kind": "type", "value": "player"}}]}, "verb": "deal_damage"}, "instead": {"amount": {"kind": "relative", "multiplier": 2, "of": {"kind": "that_much"}}, "source": {"ref": "anaphora"}, "verb": "deal_damage"}, "type": "replacement"}]`

### `efd3e1c44b83` — 21 words, score 63

Sentence: If a creature card was exiled this way, you may have ~ become a copy of that card until end of turn

Missing: until, end, turn

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "a creature card was exiled this way", "reason": "condition_text", "source": "i_if", "unparsed": true}, "effect": {"inner": {"effect": {"copy_of": {"card_type": {"kind": "type", "value": "card"}, "this_that": "that"}, "target": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "become"}, "verb": "have"}, "verb": "may"}, "type": "if"}]`

### `4281547c68f4` — 31 words, score 62

Sentence: Search your library and/or graveyard for an artifact creature card with mana value X or less and put it onto the battlefield with X additional +1/+1 counters on it

Missing: additional, counters

Output (truncated): `[{"effect": [{"card": {"card_type": {"kind": "type", "value": "artifact creature"}, "modifier": {"kind": "stat_filter", "op": "<=", "stat": "mana value", "value": "X"}, "quantifier": "an"}, "verb": "search", "zone": "library", "zones": ["library", "graveyard"]}, {"card": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "put", "zone": "battlefield"}], "type": "effect"}]`

### `e66e6e249bc0` — 31 words, score 62

Sentence: Disappear — At the beginning of your end step, if a permanent left the battlefield under your control this turn, you may cast a card exiled with ~ without paying its mana cost

Missing: mana, cost

Evidence: unparsed

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "card"}, "modifier": {"event": "exiled", "kind": "event_filter", "with": {"kind": "this_card", "value": "~"}}, "quantifier": "a"}, "verb": "cast", "without_paying": true}, "verb": "may"}, "if": {"fragment": "a permanent left the battlefield under your control this turn", "reason": "condition_text", "source": "i_triggered", "unparsed": true}, "trigger": {"ability_word": "Disappear", "when": {"phase": "end_step", "player": "you", "position": "beginning"}}, "type": "triggered"}]`

### `2b9549e74eb0` — 30 words, score 60

Sentence: If you would put one or more counters on a permanent or player, put twice that many of each of those kinds of counters on that permanent or player instead

Missing: twice, kinds

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "you would put one or more counters on a permanent or player", "reason": "condition_text", "source": "i_if", "unparsed": true}, "effect": {"instead": true, "multiplier": 2, "verb": "replace_counters"}, "type": "if"}]`

### `0be31874ed1c` — 20 words, score 60

Sentence: Max speed — {1}{B}, Sacrifice this enchantment: Search your library for a card, put it into your hand, then shuffle

Missing: max, speed, enchantment

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{1}", "{B}"]}, {"action": "sacrifice", "card": {"card_type": {"kind": "this_card", "value": "~"}}, "kind": "cost"}], "effect": [{"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "verb": "search", "zone": "library"}, {"card": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "put", "zone": "hand"}, {"verb": "shuffle"}], "type": "activated"}]`

### `3400c4450d2b` — 20 words, score 60

Sentence: Whenever you cast your first instant or sorcery spell each turn, this creature gets +2/+0 until end of turn

Missing: cast, first, spell

Evidence: empty:1

Output (truncated): `[{"effect": {"change": {"power": 2, "toughness": 0}, "duration": {"event": "end_of_turn", "kind": "until"}, "target": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "stat_change"}, "trigger": {"event": {"object": {"card_type": [{"kind": "type", "value": "instant"}, {"kind": "type", "value": "sorcery"}]}}, "when": "Whenever"}, "type": "triggered"}]`

### `55fc47f105ce` — 20 words, score 60

Sentence: ~ enters with a number of +1/+1 counters on it equal to the amount of mana spent to cast it

Missing: mana, spent, cast

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "enters", "with": {"counter": {"count": 1, "kind": "+1/+1"}}}, "type": "effect"}]`

### `6da928a37087` — 20 words, score 60

Sentence: Whenever an opponent casts a white or blue instant or sorcery spell, this creature deals 2 damage to that player

Missing: instant, sorcery, spell

Output (truncated): `[{"effect": {"amount": 2, "source": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "to": {"card_type": {"kind": "type", "value": "player"}, "this_that": "that"}, "verb": "deal_damage"}, "trigger": {"event": {"object": ["white", "blue"], "subject": {"card_type": {"kind": "type", "value": "opponent"}, "quantifier": "an"}, "verb": "casts"}, "when": "Whenever"}, "type": "triggered"}]`

### `084acb14c3d2` — 15 words, score 60

Sentence: {5}, {T}, Exile this artifact: Shuffle all nonland cards from your graveyard into your library

Missing: artifact, nonland, graveyard, library

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{5}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}, {"action": "exile", "kind": "cost", "target": {"card_type": {"kind": "this_card", "value": "~"}}}], "effect": {"verb": "shuffle"}, "type": "activated"}]`

### `1893bbd0313f` — 15 words, score 60

Sentence: If this spell was kicked, the creature you control deals twice that much damage instead

Missing: creature, control, deals, twice

Output (truncated): `[{"condition": {"kind": "spell_state", "state": "kicked"}, "effect": {"instead": true, "multiplier": 2, "verb": "replace_damage"}, "type": "if"}]`

### `313f3fe92e17` — 29 words, score 58

Sentence: When this creature enters, put target creature card with mana value 4 or less from a graveyard onto the battlefield under your control with a finality counter on it

Missing: finality, counter

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "type", "value": "creature"}, "modifier": {"kind": "stat_filter", "op": "<=", "stat": "mana value", "value": 4}, "quantifier": "target", "zone": {"possessor": "a", "prep": "from", "zone": "graveyard"}}, "controller": "you control", "verb": "put", "zone": "battlefield"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}]`

### `9175d67f1878` — 19 words, score 57

Sentence: Whenever a creature dealt damage by this creature this turn dies, put a +1/+1 counter on this creature

Missing: dealt, damage, dies

Evidence: empty:1

Output (truncated): `[{"effect": {"count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "put_counter"}, "trigger": {"event": {"object": {"card_type": {"kind": "type", "value": "creature"}, "quantifier": "a"}}, "when": "Whenever"}, "type": "triggered"}]`

### `e98362ff5155` — 19 words, score 57

Sentence: Exile an artifact or creature card from your graveyard: This Vehicle becomes an artifact creature until end of turn

Missing: until, end, turn

Evidence: stringy:1

Output (truncated): `[{"cost": [{"action": "exile", "kind": "cost", "target": {"card_type": [{"kind": "type", "value": "artifact"}, {"kind": "type", "value": "creature card from your graveyard"}], "quantifier": "an"}}], "effect": {"target": {"card_type": {"kind": "type", "value": "Vehicle"}, "this_that": "This"}, "types": ["artifact", "creature"], "verb": "become"}, "type": "activated"}]`

### `3f8cbfa38921` — 28 words, score 56

Sentence: Whenever you cast a permanent spell using mana produced by ~, up to one other target permanent you control becomes a copy of that spell until end of turn

Missing: until, end

Output (truncated): `[{"effect": {"copy_of": {"card_type": {"kind": "type", "value": "spell"}, "this_that": "that"}, "target": {"card_type": {"kind": "type", "value": "permanent"}, "controller": "you control", "otherness": "other", "quantifier": {"up_to": 1}}, "verb": "become"}, "trigger": {"event": {"object": {"card_type": {"kind": "type", "value": "permanent spell using mana produced by ~"}}, "subject": "you", "verb": "cast"}, "when": "Whenever"}, "type": "triggered"}]`

### `d706eb791f2f` — 28 words, score 56

Sentence: Whenever you cast a spell, each opponent reveals cards from the top of their library until they reveal a land card, then puts those cards into their graveyard

Missing: until, land

Output (truncated): `[{"effect": [{"amount": 1, "card": {"card_type": {"kind": "type", "value": "cards"}}, "top": true, "verb": "reveal", "who": "each opponent", "zone": "library"}, {"card": {"card_type": {"kind": "type", "value": "cards"}, "this_that": "those"}, "verb": "put", "zone": "graveyard"}], "trigger": {"event": {"object": {"kind": "spell", "quantifier": "a"}, "subject": "you", "verb": "cast"}, "when": "Whenever"}, "type": "triggered"}]`

### `e7df53999db9` — 28 words, score 56

Sentence: Void — If a nonland permanent left the battlefield this turn or a spell was warped this turn, instead you draw two cards and each opponent loses 2 life

Missing: void, cards

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "a nonland permanent left the battlefield this turn or a spell was warped this turn", "reason": "condition_text", "source": "i_if", "unparsed": true}, "effect": [{"amount": 2, "instead": true, "verb": "draw", "who": "you"}, {"amount": {"kind": "number", "unit": "life", "value": 2}, "instead": true, "verb": "lose_life", "who": "each opponent"}], "type": "if"}]`

### `10552c3be5cb` — 14 words, score 56

Sentence: This creature saddles Mounts and crews Vehicles using its toughness rather than its power

Missing: creature, using, toughness, rather

Output (truncated): `[{"effect": {"as_though": {"comparison": "greater", "stat": "power"}, "objects": [{"kind": "type", "value": "mount"}, {"kind": "type", "value": "vehicle"}], "verb": "saddle_and_crew"}, "type": "static"}]`

### `4e232de51d5b` — 27 words, score 54

Sentence: Equipped creature has "If a creature dying causes a triggered ability of this creature or an emblem you own to trigger, that ability triggers an additional time."

Missing: dying, time

Output (truncated): `[{"effect": {"quote": {"kind": "quoted_ability", "sentence": [{"condition": {"cause": {"event": "dies", "subject": {"kind": "creature"}}, "kind": "causes_trigger", "triggered_abilities": [{"kind": "triggered_ability", "source": {"card_class": "creature", "kind": "this"}}, {"kind": "triggered_ability", "source": {"controller": "you", "kind": "emblem"}}]}, "effect": {"target": {"kind": "target_ref", "ref": "that_ability"}, "verb": "trigger_extra"}, "type": "if"}]}, "target": {"card_type": {"kind": "type", "value": "creature"}, "status": ["Equipped"]}, "verb": "gain_quote"}, "type": "effect"}]`

### `59e14f9e15fc` — 27 words, score 54

Sentence: Sensational Save — If ~ was cast using web-slinging, he enters with X +1/+1 counters on him, where X is the mana value of the returned creature

Missing: sensational, save

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "~ was cast using web-slinging", "reason": "condition_text", "source": "i_if", "unparsed": true}, "effect": {"card": {"card_type": {"raw": "he", "ref": "anaphora"}}, "verb": "enters", "with": {"count": "X", "counter": {"count": "X", "kind": "+1/+1"}}}, "type": "if", "xdef": {"xdef": ["the", "mana", "value", "of", {"card_type": {"kind": "type", "value": "creature"}, "status": ["returned"], "this_that": "the"}]}}]`

### `7f01c80e540e` — 27 words, score 54

Sentence: You may have this land enter tapped as a copy of any land card in a graveyard, except it's a Cave in addition to its other types

Missing: enter, tapped

Evidence: stringy:1

Output (truncated): `[{"effect": {"inner": {"effect": {"except": "except it's a Cave in addition to its other types", "of": {"card_type": {"kind": "type", "value": "land"}, "zone": {"possessor": "a", "prep": "in", "zone": "graveyard"}}, "verb": "copy"}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "this"}, "verb": "have"}, "verb": "may"}, "type": "effect"}]`

### `fc90d1c5827a` — 27 words, score 54

Sentence: Whenever ~ attacks, exile the top card of each player's library, then you may cast any number of spells from among those cards without paying their mana costs

Missing: mana, costs

Output (truncated): `[{"effect": [{"possessor": "each player", "top": true, "verb": "exile", "zone": "library"}, {"inner": {"card": {"card_type": {"kind": "type", "value": "spells"}, "quantifier": "any number of"}, "from_among": {"card_type": {"kind": "type", "value": "cards"}, "this_that": "those"}, "verb": "cast", "without_paying": true}, "verb": "may"}], "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "attacks"}, "when": "Whenever"}, "type": "triggered"}]`

### `061c3dd191ca` — 18 words, score 54

Sentence: [−4]: Chandra deals 8 damage divided as you choose among any number of target creatures and/or planeswalkers

Missing: divided, choose, among

Output (truncated): `[{"cost": {"action": "loyalty", "amount": {"kind": "number", "unit": "loyalty", "value": -4}, "kind": "cost"}, "effect": {"amount": 8, "source": {"card_type": {"kind": "type", "value": "Chandra"}}, "to": {"or": [{"card_type": {"kind": "type", "value": "creatures"}, "quantifier": "target"}, {"card_type": {"kind": "type", "value": "planeswalkers"}}]}, "verb": "deal_damage"}, "type": "loyalty"}]`

### `1649e9485a37` — 18 words, score 54

Sentence: {1}{R}{W}: This land becomes a 2/2 red and white Ox creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{1}", "{R}", "{W}"]}], "effect": {"colors": ["red", "white"], "pt": {"power": 2, "toughness": 2}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "types": ["Ox", "creature"], "verb": "become"}, "type": "activated"}]`

### `3c5dfe2b2e03` — 18 words, score 54

Sentence: {2}{G}{W}: This land becomes a 3/3 green and white Llama creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{G}", "{W}"]}], "effect": {"colors": ["green", "white"], "pt": {"power": 3, "toughness": 3}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "types": ["Llama", "creature"], "verb": "become"}, "type": "activated"}]`

### `42d12380c41b` — 18 words, score 54

Sentence: {2}{W}{B}: This land becomes a 1/4 white and black Nightmare creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{W}", "{B}"]}], "effect": {"colors": ["white", "black"], "pt": {"power": 1, "toughness": 4}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "types": ["Nightmare", "creature"], "verb": "become"}, "type": "activated"}]`

### `5d57a835361c` — 18 words, score 54

Sentence: {2}{R}{G}: This land becomes a 3/4 red and green Dinosaur creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{R}", "{G}"]}], "effect": {"colors": ["red", "green"], "pt": {"power": 3, "toughness": 4}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "types": ["Dinosaur", "creature"], "verb": "become"}, "type": "activated"}]`

### `dd783eb79a2f` — 18 words, score 54

Sentence: {2}{B}{G}: This land becomes a 4/4 black and green Horror creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{B}", "{G}"]}], "effect": {"colors": ["black", "green"], "pt": {"power": 4, "toughness": 4}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "types": ["Horror", "creature"], "verb": "become"}, "type": "activated"}]`

### `e3bc08f81b30` — 18 words, score 54

Sentence: Whenever a Detective you control enters or is turned face up, put a +1/+1 counter on it

Missing: detective, control, enters

Output (truncated): `[{"effect": {"count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "put_counter"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `f2774cdfa29a` — 18 words, score 54

Sentence: If ~ would be put into a graveyard from anywhere, reveal ~ and shuffle it into its owner's library instead

Missing: anywhere, owner, library

Output (truncated): `[{"if": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "put_into", "zone": "graveyard"}, "instead": [{"card": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "reveal"}, {"verb": "shuffle"}], "type": "replacement"}]`

### `b47a39f2f185` — 26 words, score 52

Sentence: Whenever a face-down permanent you control is turned face up, put a +1/+1 counter on it and a +1/+1 counter on this creature

Missing: permanent, control

Output (truncated): `[{"effect": {"and": [{"count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}}], "count": 1, "counter": {"count": 1, "kind": "+1/+1"}, "on": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "put_counter"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `e07cd84d8777` — 26 words, score 52

Sentence: Whenever this creature attacks, you may cast a spell from among cards you own in exile with dream counters on them without paying its mana cost

Missing: mana, cost

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "spell"}, "quantifier": "a"}, "from_among": {"card_type": {"kind": "type", "value": "cards"}, "controller": "you own", "modifier": {"counter": {"kind": "dream"}, "kind": "counter", "on": "them"}, "zone": {"prep": "in", "zone": "exile"}}, "verb": "cast", "without_paying": true}, "verb": "may"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "attacks"}, "when": "Whenever"}, "type": "triggered"}]`

### `0e13d0df93b6` — 13 words, score 52

Sentence: {4}{U}{U}: Shuffle enchanted creature into its owner's library, then manifest dread

Missing: enchanted, creature, owner, library

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{4}", "{U}", "{U}"]}], "effect": [{"verb": "shuffle"}, {"verb": "manifest_dread"}], "type": "activated"}]`

### `31f19673efdd` — 17 words, score 51

Sentence: Spend this mana only to cast an Ally spell or activate an ability of an Ally source

Missing: activate, ability, source

Output (truncated): `[{"effect": {"target": {"card_type": {"kind": "type", "value": "Ally spell"}, "quantifier": "an"}, "verb": "spend_mana_only_to_cast"}, "type": "effect"}]`

### `4db2d3e1284e` — 17 words, score 51

Sentence: Tap two other untapped artifacts you control: This Vehicle becomes an artifact creature until end of turn

Missing: until, end, turn

Evidence: stringy:1

Output (truncated): `[{"cost": [{"action": "tap", "kind": "cost", "target": {"card_type": [{"kind": "type", "value": "other untapped artifact"}], "controller": "you", "quantifier": "two"}}], "effect": {"target": {"card_type": {"kind": "type", "value": "Vehicle"}, "this_that": "This"}, "types": ["artifact", "creature"], "verb": "become"}, "type": "activated"}]`

### `59d3a2d364e1` — 17 words, score 51

Sentence: Then you may have it become a copy of another creature you control until end of turn

Missing: until, end, turn

Output (truncated): `[{"effect": {"inner": {"effect": {"copy_of": {"card_type": {"kind": "type", "value": "creature"}, "controller": "you control", "otherness": "another"}, "target": {"card_type": {"raw": "it", "ref": "anaphora"}}, "verb": "become"}, "verb": "have"}, "verb": "may"}, "type": "effect"}]`

### `6c8790a96e59` — 17 words, score 51

Sentence: Spend this mana only to cast an artifact spell or activate an ability of an artifact source

Missing: activate, ability, source

Output (truncated): `[{"effect": {"target": {"card_type": {"kind": "type", "value": "artifact spell"}, "quantifier": "an"}, "verb": "spend_mana_only_to_cast"}, "type": "effect"}]`

### `1879673ffaf4` — 25 words, score 50

Sentence: Undying Vengeance — Whenever you play a land or cast a spell from anywhere other than your hand, this enchantment deals 1 damage to each opponent

Missing: play, land

Output (truncated): `[{"effect": {"amount": 1, "source": {"card_type": {"kind": "type", "value": "enchantment"}, "this_that": "this"}, "to": {"card_type": {"kind": "type", "value": "opponent"}, "quantifier": "each"}, "verb": "deal_damage"}, "trigger": {"ability_word": "Undying Vengeance", "event": {"object": {"card_type": {"kind": "type", "value": "spell from anywhere other than your hand"}}, "subject": "you", "verb": "cast"}, "when": "Whenever"}, "type": "triggered"}]`

### `66f3bcd99844` — 25 words, score 50

Sentence: {6}, {T}, Sacrifice this artifact: Put each creature card exiled with this artifact onto the battlefield under your control with a flying counter on it

Missing: flying, counter

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{6}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}, {"action": "sacrifice", "card": {"card_type": {"kind": "this_card", "value": "~"}}, "kind": "cost"}], "effect": {"card": {"card_type": {"kind": "type", "value": "creature"}, "modifier": {"event": "exiled", "kind": "event_filter", "with": {"card_class": "artifact", "kind": "this"}}, "quantifier": "each", "this_that": "this"}, "controller": "you control", "verb": "put", "zone": "battlefield"}, "type": "activated"}]`

### `23f42e128de8` — 24 words, score 48

Sentence: When this creature enters, create a number of 1/1 white Rabbit creature tokens equal to the number of other creatures you control named ~

Missing: equal, named

Output (truncated): `[{"effect": {"token": {"colors": "white", "power_toughness": {"power": 1, "toughness": 1}, "types": ["Rabbit", "creature"], "xdef": ["the", "number", "of", {"card_type": {"kind": "type", "value": "creatures"}, "controller": "you control", "modifier": {"kind": "name", "name": "chosen"}, "otherness": "other"}]}, "verb": "create_token"}, "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}]`

### `4d69ce7d2ba5` — 24 words, score 48

Sentence: Whenever you cast a noncreature spell, if at least four mana was spent to cast it, ~ becomes an artifact creature until end of turn

Missing: until, end

Evidence: unparsed

Output (truncated): `[{"effect": {"target": {"card_type": {"kind": "this_card", "value": "~"}}, "types": ["artifact", "creature"], "verb": "become"}, "if": {"fragment": "at least four mana was spent to cast it", "reason": "condition_text", "source": "i_triggered", "unparsed": true}, "trigger": {"event": {"object": {"card_type": {"kind": "type", "value": "spell"}, "kind": "spell", "noncreature": true, "quantifier": "a"}, "subject": "you", "verb": "cast"}, "when": "Whenever"}, "type": "triggered"}]`

### `4dfa6b6ea030` — 24 words, score 48

Sentence: When this Class becomes level 3, search your library for a card, put it into your hand, shuffle, then discard a card at random

Missing: library, put

Evidence: unparsed

Output (truncated): `[{"effect": [{"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "verb": "search", "zone": "hand"}, {"verb": "shuffle"}, {"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "random": true, "verb": "discard"}], "trigger": {"fragment": "this Class becomes level 3", "reason": "trigger_text", "source": "i_trigger_clause", "unparsed": true, "when": "When"}, "type": "triggered"}]`

### `af43420c4e47` — 24 words, score 48

Sentence: You may cast a spell from among the exiled cards without paying its mana cost if you exiled four or more cards this way

Missing: mana, cost

Evidence: unparsed

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "spell"}, "quantifier": "a"}, "from_among": {"card_type": {"kind": "type", "value": "cards"}, "status": ["exiled"], "this_that": "the"}, "verb": "cast", "without_paying": true}, "verb": "may"}, "if": {"fragment": "you exiled four or more cards this way", "reason": "condition_text", "source": "i_effect", "unparsed": true}, "type": "effect"}]`

### `28ca6b0fbf66` — 16 words, score 48

Sentence: When this creature enters or is turned face up, target creature blocks this turn if able

Missing: enters, blocks, able

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "type", "value": "creature"}, "quantifier": "target"}, "verb": "attacks_each_combat"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "When"}, "type": "triggered"}]`

### `610727056a5d` — 16 words, score 48

Sentence: Reveal cards from the top of your library until you reveal a creature or planeswalker card

Missing: until, creature, planeswalker

Output (truncated): `[{"effect": {"amount": 1, "card": {"card_type": {"kind": "type", "value": "cards"}}, "top": true, "verb": "reveal", "zone": "library"}, "type": "effect"}]`

### `729200ac3158` — 16 words, score 48

Sentence: Tap two untapped tokens you control: This Vehicle becomes an artifact creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "tap", "kind": "cost", "target": {"card_type": [{"kind": "type", "value": "token"}], "controller": "you", "quantifier": "two", "status": ["untapped"]}}], "effect": {"target": {"card_type": {"kind": "type", "value": "Vehicle"}, "this_that": "This"}, "types": ["artifact", "creature"], "verb": "become"}, "type": "activated"}]`

### `dd22519ddb95` — 16 words, score 48

Sentence: During your turn, your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments

Missing: artifacts, creatures, enchantments

Evidence: stringy:2

Output (truncated): `[{"effect": {"card": {"card_type": {"kind": "type", "value": "opponents"}, "possessive": "your"}, "predicate": {"kind": "predicate", "verbs": ["cast spells", "activate abilities"]}, "verb": "can't"}, "time": ["your", "turn"], "type": "during"}]`

### `038e1f9ad822` — 12 words, score 48

Sentence: Max speed — If you would draw a card, draw two cards instead

Missing: max, speed, card, cards

Output (truncated): `[{"if": {"verb": "draw"}, "instead": {"amount": 2, "verb": "draw"}, "type": "replacement"}]`

### `e0778dc00bd0` — 12 words, score 48

Sentence: ~ deals 2 damage divided as you choose among one or two targets

Missing: divided, choose, among, targets

Output (truncated): `[{"effect": {"amount": 2, "source": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "deal_damage"}, "type": "effect"}]`

### `e1f149d88022` — 46 words, score 46

Sentence: You may have this creature enter as a copy of any creature on the battlefield with mana value less than or equal to the amount of mana spent to cast this creature, except it's a Bird in addition to its other types and it has flying

Missing: enter

Evidence: stringy:2

Output (truncated): `[{"effect": {"inner": {"effect": {"except": "except it's a Bird in addition to its other types", "except_keywords": ["flying"], "of": {"card_type": {"kind": "type", "value": "creature"}, "modifier": "with mana value less than or equal to the amount of mana spent to cast this creature", "this_that": "this", "zone": {"possessor": "the", "prep": "on", "zone": "battlefield"}}, "verb": "copy"}, "target": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "have"}, "verb": "may"}, "type": "effect"}]`

### `09a190b3a2c9` — 23 words, score 46

Sentence: Whenever this creature or another creature you control is turned face up, that creature deals damage equal to its power to each opponent

Missing: control, equal

Output (truncated): `[{"effect": {"amount": {"kind": "relative", "of": {"kind": "possessive", "possessor": {"anaphor": true, "kind": "anaphora", "possessive": "its"}, "stat": "power"}}, "source": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "that"}, "to": {"card_type": {"kind": "type", "value": "opponent"}, "quantifier": "each"}, "verb": "deal_damage"}, "trigger": {"event": {"subject": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "turn_face_up"}, "when": "Whenever"}, "type": "triggered"}]`

### `80e5cb9a2fc8` — 23 words, score 46

Sentence: At the beginning of your second main phase, if an opponent lost life this turn, exile the top two cards of your library

Missing: lost, cards

Output (truncated): `[{"effect": {"amount": 2, "top": true, "verb": "exile", "zone": "library"}, "if": {"event": {"object": "life", "subject": "an opponent", "verb": "lose"}, "kind": "event", "this_turn": true}, "trigger": {"when": {"phase": "main_phase", "player": "you", "position": "beginning", "which": "second"}}, "type": "triggered"}]`

### `0d24c90725cb` — 15 words, score 45

Sentence: Each other creature you control becomes a copy of that creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"effect": {"copy_of": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "that"}, "target": {"card_type": {"kind": "type", "value": "creature"}, "controller": "you control", "otherness": "other", "quantifier": "each"}, "verb": "become"}, "type": "effect"}]`

### `e7a647a0ac7c` — 15 words, score 45

Sentence: Then you may have it become a 0/0 Elemental creature until end of turn

Missing: until, end, turn

Output (truncated): `[{"effect": {"inner": {"effect": {"pt": {"power": 0, "toughness": 0}, "target": {"card_type": {"raw": "it", "ref": "anaphora"}}, "types": ["Elemental", "creature"], "verb": "become"}, "verb": "have"}, "verb": "may"}, "type": "effect"}]`

### `e855a61fff67` — 15 words, score 45

Sentence: {5}: This land becomes a copy of target creature you control until end of turn

Missing: until, end, turn

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{5}"]}], "effect": {"copy_of": {"card_type": {"kind": "type", "value": "creature"}, "controller": "you control", "quantifier": "target"}, "target": {"card_type": {"kind": "type", "value": "land"}, "this_that": "This"}, "verb": "become"}, "type": "activated"}]`

### `02b1cce72e7d` — 22 words, score 44

Sentence: Exhaust — {2}{U}{U}, {T}: Any number of target players each mill cards equal to the number of cards in their graveyard

Missing: exhaust, equal

Evidence: stringy:1

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{2}", "{U}", "{U}"]}, {"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}], "effect": {"amount": ["the", "number", "of", {"card_type": {"kind": "type", "value": "cards"}, "zone": {"possessor": {"anaphor": true, "kind": "anaphora", "possessive": "their"}, "prep": "in", "zone": "graveyard"}}], "verb": "mill", "who": "any number of target players"}, "type": "activated"}]`

### `2bdc4d205269` — 22 words, score 44

Sentence: Then if you control three or more creatures with different powers, you may play the exiled card without paying its mana cost

Missing: mana, cost

Output (truncated): `[{"condition": {"card_target": {"card_type": {"kind": "type", "value": "creatures"}, "controller": "you control", "modifier": {"kind": "comparison", "mode": "different", "property": "power"}}, "kind": "control", "quantity": {"at_least": 3}}, "effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "card"}, "status": ["exiled"], "this_that": "the"}, "verb": "play", "without_paying": true}, "verb": "may"}, "type": "effect"}]`

### `2f3ced0e097d` — 22 words, score 44

Sentence: You may cast this spell as though it had flash if you behold a Dragon as an additional cost to cast it

Missing: though, flash

Evidence: unparsed

Output (truncated): `[{"effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "spell"}, "this_that": "this"}, "verb": "cast"}, "verb": "may"}, "if": {"fragment": "you behold a Dragon as an additional cost to cast it", "reason": "condition_text", "source": "i_effect", "unparsed": true}, "type": "effect"}]`

### `53c62f83150f` — 22 words, score 44

Sentence: As an additional cost to cast this spell, choose a creature you control or a warped creature card you own in exile

Missing: cast, spell

Evidence: stringy:1

Output (truncated): `[{"effect": {"object": "a creature you control or a warped creature card you own in exile", "verb": "choose"}, "type": "additional_cost"}]`

### `5ae45898aa39` — 22 words, score 44

Sentence: Whenever you sacrifice a Clue, you may have ~ become a copy of a creature card exiled with it until end of turn

Missing: until, end

Output (truncated): `[{"effect": {"inner": {"effect": {"copy_of": {"card_type": {"kind": "type", "value": "creature"}, "modifier": {"event": "exiled", "kind": "event_filter", "with": {"anaphor": true, "kind": "anaphora", "possessive": "it"}}, "quantifier": "a"}, "target": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "become"}, "verb": "have"}, "verb": "may"}, "trigger": {"event": {"object": {"card_type": {"kind": "type", "value": "Clue"}, "quantifier": "a"}, "subject": "you", "verb": "sacrifice"}, "when": "Whenever"}, "type": "triggered"}]`

### `6a8239716e05` — 22 words, score 44

Sentence: Cosmic Awareness — As long as an opponent has cast a spell this turn, you may cast spells as though they had flash

Missing: though, flash

Evidence: unparsed

Output (truncated): `[{"ability_word": "Cosmic Awareness", "condition": {"fragment": "an opponent has cast a spell this turn", "reason": "condition_text", "source": "i_as_long", "unparsed": true}, "effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "spells"}}, "verb": "cast"}, "verb": "may"}, "type": "as_long"}]`

### `a0e2e2c1ea6f` — 22 words, score 44

Sentence: Mardu — If a creature attacking causes a triggered ability of a permanent you control to trigger, that ability triggers an additional time

Missing: mardu, time

Evidence: unparsed

Output (truncated): `[{"condition": {"fragment": "a creature attacking causes a triggered ability of a permanent you control to trigger", "reason": "condition_text", "source": "i_if", "unparsed": true}, "effect": {"target": {"kind": "target_ref", "ref": "that_ability"}, "verb": "trigger_extra"}, "type": "if"}]`

### `c2af1b5714c8` — 22 words, score 44

Sentence: {T}: Until end of turn, you may cast creature spells from your graveyard by foraging in addition to paying their other costs

Missing: until, end

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{T}"]}], "effect": {"inner": {"by": {"actions": [{"action": "forage"}], "addition_to_other_costs": true, "kind": "cost_phrase"}, "card": {"card_type": {"kind": "type", "value": "creature spells"}, "zone": {"possessor": "your", "prep": "from", "zone": "graveyard"}}, "verb": "cast"}, "verb": "may"}, "type": "activated"}]`

### `c7b49e940692` — 22 words, score 44

Sentence: When this creature enters, search your library for a card, put it into your hand, shuffle, then discard a card at random

Missing: library, put

Output (truncated): `[{"effect": [{"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "verb": "search", "zone": "hand"}, {"verb": "shuffle"}, {"card": {"card_type": {"kind": "type", "value": "card"}, "quantifier": "a"}, "random": true, "verb": "discard"}], "trigger": {"event": {"object": {}, "subject": {"card_type": {"kind": "type", "value": "creature"}, "this_that": "this"}, "verb": "enters"}, "when": "When"}, "type": "triggered"}]`

### `04469b33f284` — 43 words, score 43

Sentence: At the beginning of each end step, create X 1/1 black Rat creature tokens with "This token gets +1/+1 for each other Rat you control," where X is the number of creatures that were exiled under your opponents' control this turn

Missing: gets

Evidence: unparsed, stringy:2

Output (truncated): `[{"effect": {"token": {"colors": "black", "count": "X", "power_toughness": {"power": 1, "toughness": 1}, "quote": "\"This token gets +1/+1 for each other Rat you control,\"", "types": ["Rat", "creature"]}, "verb": "create_token"}, "trigger": {"when": {"phase": "end_step", "player": "each", "position": "beginning"}}, "type": "triggered", "xdef": {"xdef": {"fragment": ["the", "number", "of", "creatures that were exiled under your opponents' control this turn"], "reason": "xdef_text", "source": "i_sentence", "unparsed": true}}}]`

### `30818ad52072` — 21 words, score 42

Sentence: Tyrannosaurus Rex — {6}: Until end of turn, ~ becomes a Dinosaur Hero with base power and toughness 6/6 and gains trample

Missing: tyrannosaurus, rex

Output (truncated): `[{"cost": [{"action": "pay_mana", "kind": "cost", "mana": ["{6}"]}], "effect": [{"base_pt": {"power": 6, "toughness": 6}, "duration": {"event": "end_of_turn", "kind": "until"}, "target": {"card_type": {"kind": "this_card", "value": "~"}}, "types": ["Dinosaur", "Hero"], "verb": "become"}, {"duration": {"event": "end_of_turn", "kind": "until"}, "keywords": ["trample"], "target": {"card_type": {"kind": "this_card", "value": "~"}}, "verb": "gain_kw"}], "type": "activated"}]`

### `88a1dba28d16` — 21 words, score 42

Sentence: If there are three or more Lesson cards in your graveyard, you may cast this spell as though it had flash

Missing: though, flash

Output (truncated): `[{"condition": {"kind": "count", "of": {"card_target": {"card_type": {"kind": "type", "value": "Lesson cards"}}, "zone": {"possessor": "you", "prep": "in", "zone": "graveyard"}}, "quantity": {"at_least": 3}}, "effect": {"inner": {"card": {"card_type": {"kind": "type", "value": "spell"}, "this_that": "this"}, "verb": "cast"}, "verb": "may"}, "type": "if"}]`

