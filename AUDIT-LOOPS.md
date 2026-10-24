# Out-of-dev audit loops

Each loop samples 20 anaphora-bearing cards from `classic.json`, excluding every
card already present in `coref_standard.json`, `coref_dataset.json`, or a
previous audit. Cards are parsed sentence-by-sentence and then run through the
deterministic coreference resolver. A loop is clean only when every sentence
parses and the inspected anaphora choices are semantically defensible.

## Loop 1 — seed 20261023

Cards:

`Immortal Phoenix`, `Isareth the Awakener`, `Garruk, Apex Predator`,
`Void Stalker`, `Omnath, Locus of the Roil`, `Hungering Hydra`, `Phantom Beast`,
`Anticipate`, `Rienne, Angel of Rebirth`, `Cavalier of Thorns`,
`Reduce to Ashes`, `Garruk, Unleashed`, `Marauding Raptor`, `Nissa, Worldwaker`,
`Liliana's Spoils`, `Inferno Titan`, `Oppressive Rays`, `Basri's Lieutenant`,
`Retributive Wand`, `Ancestral Blade`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Isareth the Awakener | `return ... to the battlefield with a corpse counter on it` had no generic counter-return variant | added `V_RETURN ... "with" counter_amount counter_kind "on" "it"` |
| Rienne, Angel of Rebirth | `return it to its owner's hand at the beginning of the next end step` had timing only on battlefield returns | added the timing suffix to hand returns |
| Void Stalker | coordinated `Put this creature and target creature ...`; plural `their owners' libraries`; `those players shuffle their libraries` | added coordinated put-target variant, plural owner token, plural-player subject, and `shuffle their libraries` |
| Cavalier of Thorns | `Put a land card ... onto the battlefield and the rest into your graveyard` | added the mixed onto-battlefield/rest-into-zone put variant |
| Nissa, Worldwaker | `They're still lands` only had the singular `It's still a land` form | added plural `They're still ...` |
| Oppressive Rays | `can't attack or block unless ...` was misparsed as plain `attack or block` | allowed the `unless` clause on that alternative |
| Sublime Archangel | `Other creatures you control have exalted`; `exalted` was not a keyword | added `exalted` to `KEYWORD`; existing `have kw_list` rule then parses it |

### Coreference/output fixes found and fixed

- **Oppressive Rays**: `its controller` had no `Enchanted creature` candidate.
  Status-headed NPs were missing from the regex inventory; added
  `enchanted/equipped/attacking/...` to the determiner prefixes.
- **Ancestral Blade**: `attach this Equipment to it` bound `it` to the Equipment.
  For an attachment destination (`... to it`), the pronoun is the recipient, not
  the Equipment; added an `attachment-destination` rule ahead of the existing
  attachment-object rule.
- **Garruk, Apex Predator**: `You gain life equal to its toughness` bound `its`
  to `You`. Added a narrow `life-equal-object` rule that excludes players/`You`.
- **Marauding Raptor**: `this creature deals 2 damage to it` was ambiguous with
  `this creature`; the damage object cannot be the subject. Added
  `damage-object-not-self`.
- **Return/put output**: `return` no longer includes the verb in its `to` string
  and records a counter; put actions keep both coordinated targets and distinguish
  `zone` from `rest_zone`.

### Remaining limitation

`Void Stalker`: `those players` should be the owners of the two permanents, and
`their owners' libraries` is a collection/player relationship. The inventory has
no owner-player mention, so `those players` still binds to `target creature`.
This is a known collection/owner inventory gap, not a parse failure.

### Verification

- 20/20 sampled cards now parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- Dev coreference: **90.4% entity-aware / 84.4% exact** (was 90.1 / 84.1).
- Bench coreference: **94.1% regex / 93.0% parser** (unchanged).

## Loop 2 — seed 20261024

Cards:

`Festering Newt`, `Chandra's Firemaw`, `Might Makes Right`,
`Amulet of Safekeeping`, `Furious Rise`, `Yanling's Harbinger`,
`Burning Anger`, `Chandra, the Firebrand`, `Patient Rebuilding`,
`Waker of Waves`, `Vial of Dragonfire`, `Phylactery Lich`,
`Rotfeaster Maggot`, `Verdant Haven`, `Encrust`, `Feline Sovereign`,
`Thieves' Guild Enforcer`, `Sleep`, `Transmogrify`, `Leyline of Punishment`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Festering Newt | `a creature named ~` and `-4/-4 instead if ...` | allowed `THIS_CARD` in the `named` modifier and allowed `instead if ...` as a trailing condition |
| Furious Rise | `You may play that card until you exile another card ...` | added `V_PLAY card_target "until" any_text` |
| Chandra, the Firebrand | loyalty effect beginning with a triggered clause (`[−2]: When you next cast ...`) | allowed `triggered_sentence` under `loyalty_sentence` and interpreted it as the loyalty effect |
| Patient Rebuilding | `draw a card for each land card put into their graveyard this way` | added the `put into <zone> this way` suffix to the draw-per-card rule |

### Coreference/output fixes found and fixed

- **Sleep**: `all creatures target player controls` swallowed the embedded
  `target player`. Player/opponent sub-mentions are now kept when they are the
  target of the controlling phrase; `that player` binds to `target player`.
- **Transmogrify**: `That creature's controller` was missing as a player
  mention, and `their library` bound to the card collection. Added controller
  mentions, `possessive-zone-owner`, and controller-aware player-subject rules.
  `That player` now binds to the controller.
- **Amulet of Safekeeping**: `that spell` had no antecedent because the inner
  `a spell` was buried in `target of a spell`. Added nested spell/ability
  candidates; `that spell` -> `a spell`.
- **Chandra, the Firebrand**: added `instant or sorcery spell` to the spell
  candidate pattern so `that spell` binds to the spell, not to Chandra.
- **Encrust / Oppressive Rays**: `its controller` and `its activated abilities`
  bound to the controller mention. Added `possessive-object-controller` and
  `possessive-object-attribute`, which keep the possessor as the object.
- **Status/owner inventory**: added owner-controller detection and preserved
  only the nested mentions needed for these cases, avoiding the broad
  inventory regression that initially lowered dev.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16 (test texts rebuilt into the new grammar-hash cache).
- Dev coreference: **90.4% entity-aware / 84.5% exact** (was 90.4 / 84.4).
- Bench coreference: **94.1% regex / 93.0% parser** (unchanged).

## Loop 3 — seed 20261025

Cards:

`Sphinx Ambassador`, `Roaming Ghostlight`, `Ice Cage`, `Goblin Arsonist`,
`Telepathy`, `Chandra Nalaar`, `Siege Dragon`, `Resolute Archangel`,
`Elite Arcanist`, `Drawn from Dreams`, `Borderland Ranger`, `Ponder`,
`Sylvan Ranger`, `Sarkhan's Dragonfire`, `Chandra, Flame's Catalyst`,
`Rampant Growth`, `Chaos Wand`, `Wakeroot Elemental`, `Blightbeetle`,
`Burning Earth`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Resolute Archangel | `it becomes equal to your starting life total` had no non-type become form | added `card_target "becomes" "equal" "to" any_text` |
| Elite Arcanist | `You may cast the copy ...` and standalone `X is the mana value of the exiled card` | added `cast the copy` and `X is xdef`; added `the mana value of card_target` to `xdef` |
| Chaos Wand | third-person `exiles` was not a `V_EXILE` form; `from the top of ... until ...`; `that weren't cast this way`; `that library` | made `V_EXILE` accept `exiles`, added top-of-library-until, the cast-this-way modifier, and `that` as a zone owner |

### Coreference/output fixes found and fixed

- **Telepathy**: `Your opponents` was not a player candidate, so `their` had no
  resolution. Added possessive player prefixes (`your`, `our`, `their`) and
  defending/attacking/active players to the player inventory.
- **Siege Dragon**: `that player` bound to `all Walls your opponents control`.
  The missing `defending player` candidate now wins by type and recency.
- **Chandra, Flame's Catalyst**: `that spell` had no antecedent because the
  target was an instant/sorcery **card**. Added the disjunctive instant-or-
  sorcery card pattern and allowed a spell anaphor to accept such a card.
  `it` then chains to the same card.
- **Chaos Wand**: `that card`/`its` bound to the opponent. The inner
  `an instant or sorcery card` was missing from inventory; the new card pattern
  lets `that card` and `its` bind to that card.
- **V_EXILE forms**: accepting `exiles` also made third-person exile effects
  parse instead of falling back to raw text.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.4% entity-aware / 84.5% exact** (unchanged).
- Bench coreference: **94.3% regex / 93.0% parser**; regex exact 84.3%.

## Loop 4 — seed 20261026

Cards:

`Brood Keeper`, `Sparktongue Dragon`, `Diffusion Sliver`,
`Pyromancer's Gauntlet`, `Celestial Flare`, `Storm Caller`,
`Leyline of Sanctity`, `Hellion Crucible`, `Mask of Immolation`,
`Blood Seeker`, `Act of Treason`, `Sutured Ghoul`, `Haunting Echoes`,
`Necrobite`, `Garruk, Savage Herald`, `Fraying Omnipotence`, `Frost Lynx`,
`Cultivate`, `Portal of Sanctuary`, `Oblivion Ring`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Hellion Crucible | activation cost `Remove two counters from this land and sacrifice it` | added the combined remove-counter-and-sacrifice cost item |
| Sutured Ghoul | `power ... and its toughness ...`, plus `their total toughness` | added the compound stat-definition form and the `their/its total power/toughness` xdef |
| Haunting Echoes | `card exiled this way`; `all cards with the same name as that card and exile them` | added `exiled this way`, `attached to`, `with the same name as card_target`, and search-and-exile |
| Fraying Omnipotence | `half the creatures they control` | added `half the` as a card-target quantifier |
| Portal of Sanctuary | coordinated return `target creature ... and each Aura attached to it` | added the coordinated return form and the `attached to` modifier |

### Coreference/output fixes found and fixed

- **Pyromancer's Gauntlet**: `it deals that much damage` bound to the damage
  recipient `a permanent or player`. Added a `damage-source-subject` rule for
  the `If <source> would deal damage ..., it deals ...` construction.
- **Blood Seeker**: `that player` bound to `a creature an opponent controls`.
  The embedded `an opponent` is now preserved when its container has `controls`;
  `that player` binds to the opponent.
- **Player predicate guard**: with embedded opponents back in the inventory,
  `it's a creature` must not bind to a player; added
  `it-predicate-not-player`.
- **Return output**: coordinated returns now keep both targets in `cards` and
  no longer prepend `and` to the destination phrase.
- Updated the Fiery Annihilation entity test: the new `attached to` modifier
  makes the Equipment canonical span more specific.

### Remaining limitation

`Portal of Sanctuary`: `their owners' hands` refers to the owners of the
coordinated returned permanents. There is still no combined collection mention
for `target creature ... and each Aura ...`, so `their` binds to the Aura. This
is the existing coordinated-collection/owner inventory gap, not a parse failure.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.4% entity-aware / 84.5% exact** (unchanged).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).
