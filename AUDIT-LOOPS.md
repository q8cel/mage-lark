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

## Loop 5 — seed 20261027

Cards:

`Coat of Arms`, `Awakener Druid`, `Time Reversal`, `Chandra, Heart of Fire`,
`Brought Back`, `Doublecast`, `Departed Deckhand`, `Angelic Ascension`,
`Nine Lives`, `Leafkin Avenger`, `Artificer's Hex`, `Angelic Guardian`,
`Mangara, the Diplomat`, `Kaalia, Zenith Seeker`, `Primal Clay`,
`Ajani's Sunstriker`, `Sleep Paralysis`, `Sarkhan's Catharsis` (and the remaining
sample cards).

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Primal Clay | `it becomes your choice of a 3/3 ..., a 2/2 ..., or a 1/6 ...` | added the `becomes your choice of <list>` become form |
| Departed Deckhand | `can't be blocked this turn except by Spirits` | allowed `this turn` before `except by` in the blocked form |
| Angelic Guardian | `they gain indestructible until end of turn` | allowed `they` as a card target for the existing `gain kw_list` action |
| Kaalia, Zenith Seeker | coordinated reveal `an Angel card, a Demon card, and/or a Dragon card ... put them` | added coordinated reveal targets and the put-them-into-hand tail |

### Coreference/output fixes found and fixed

- **Awakener Druid**: `It's still a land` bound to `this creature`. Added a
  `still-land-target` rule that prefers the preceding target land.
- **Departed Deckhand**: `sacrifice it` bound to the spell. Added
  `sacrifice-object`, excluding spells/players.
- **Coat of Arms**: `with it` was ambiguous with `each other creature`; added
  `for-each-other-subject`, which selects the non-`other` subject.
- **Angelic Guardian**: `they` now binds to `one or more creatures you control`
  after the parser fix.
- **Mangara, the Diplomat**: `those creatures` had no candidate because bare
  `creatures` after `attacks with` was not inventoried. Added the
  `BARE_COLLECTION` pattern; `those creatures` -> `creatures`.
- **Card-target inventory**: the new `they` target form and collection pattern
  are narrow; dev moved up rather than down.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.5% entity-aware / 84.6% exact** (was 90.4 / 84.5).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 6 — seed 20261028

Cards:

`Risen Reef`, `Primeval Titan`, `Smallpox`, `Stormtide Leviathan`, `Rancor`,
`Barrin, Tolarian Archmage`, `Quickling`, `Skyrider Patrol`, `Dub`,
`Augur of Bolas`, `Necromentia`, `Phantasmal Bear`, `Containment Priest`,
`Wild Ricochet`, `Fell Specter`, `Aether Adept`, `Mark of Mutiny`,
`Ember Hauler`, `Riddlemaster Sphinx`, `Xathrid Gorgon`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Xathrid Gorgon | `Its activated abilities can't be activated` | added plural `activated/triggered abilities` card kinds; also added the exact static form so the leading `Its` is not split into a fake keyword sentence |

### Coreference/output fixes found and fixed

- **Wild Ricochet**: `that spell` had no antecedent because the phrase
  `target instant or sorcery spell` was missing from the spell-candidate
  inventory. Added the instant/sorcery-spell pattern; `that spell` now binds to
  the target spell.
- Checked all other anaphors: Risen Reef's top card chain, Smallpox's two
  players, Stormtide Leviathan's land types, Rancor/Quickling/Skyrider
  possessives, Containment Priest's nontoken creature, and Xathrid's
  target-creature chain are all correct.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.5% entity-aware / 84.6% exact** (unchanged).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 7 — seed 20261029

Cards:

`Protean Hydra`, `Master of the Wild Hunt`, `Enthralling Hold`, `Skalla Wolf`,
`Indulgent Tormentor`, `Miscast`, `Gideon Jura`, `Djinn of Wishes`,
`Turn to Slag`, `Tezzeret's Gatebreaker`, `Militia Bugler`,
`Thorncaster Sliver`, `Magma Phoenix`, `Capture Sphere`, `Garruk's Warsteed`,
`Thran Golem`, `Frost Breath`, `Demanding Dragon`, `Lurking Predators`,
`Squad Captain`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Master of the Wild Hunt | `Each Wolf tapped this way deals damage equal to its power divided ...` | added `tapped this way` and the damage-equal-to/divided-as form |
| Enthralling Hold | `You can't choose an untapped creature as this spell's target ...` | added the static `can't choose ... as ... target` form |
| Indulgent Tormentor | `... unless target opponent sacrifices ... or pays 3 life` | allowed sacrifice-or-pay-life and a trailing `unless` in triggered/effect sentences |
| Gideon Jura | `During target opponent's next turn, ...`; `... creature that's still a planeswalker` | added owner-next-turn during phrases and `that's still a ...` become tails; added the attack-if-able action |
| Demanding Dragon | `... unless that player sacrifices a creature ...` | covered by the trailing-`unless` support |

### Coreference/output fixes found and fixed

- **Master of the Wild Hunt**: the first `its` bound to the previously created
  token. The possessive role for `equal to` was being read as the generic `to`
  object cue; fixed that precedence. The subject fallback also now stays in the
  anaphor's sentence. `Each Wolf tapped this way` is the antecedent.
- **Distributive singular**: `Each Wolf tapped this way` has a singular head but
  the old number heuristic marked it plural. Singular possessives may now keep
  `each/every/any <singular>` candidates.
- **Trailing unless**: moved the `unless` clause into the effect dict so
  `counter target spell unless ...` keeps its condition in output.
- **Thorncaster Sliver**: `it` inside the granted ability stays in the grant
  recipient entity (plural canonical) by design; the referent class is correct.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44 (after fixing the trailing-unless output).
- `test_coref.py`: 16/16.
- Dev coreference: **90.5% entity-aware / 84.7% exact** (was 90.5 / 84.6).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 8 — seed 20261030

Cards:

`Rupture Spire`, `Explosive Apparatus`, `Sarkhan, Dragonsoul`, `Into the Wilds`,
`Master of Predicaments`, `Barkhide Troll`, `Riddleform`, `Shared Summons`,
`Ghostly Pilferer`, `Teferi's Wavecaster`, `Goblin Kaboomist`, `Condemn`,
`Jace's Mindseeker`, `Gruesome Scourger`, `Masterful Replication`,
`Dark-Dweller Oracle`, `Totally Lost`, `Demonic Embrace`,
`Disciple of Bolas`, `Captivating Gyre`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Sarkhan, Dragonsoul | `each opponent and each creature your opponents control` | added the combined damage recipient |
| Master of Predicaments | `That player guesses whether ...` | added the guess-whether static form |
| Riddleform | `become a 3/3 Sphinx creature with flying in addition to ... until end of turn` | added the keyword + in-addition-to become tail with an optional duration |
| Goblin Kaboomist | two-word token name `Land Mine` followed by a quoted ability; `Then flip a coin` | allowed multi-word token names and added a flip-coin action |
| Masterful Replication | `becomes a copy of that artifact until end of turn` | added the become-a-copy form |
| Disciple of Bolas | `X is that creature's power` | added possessive power/toughness to xdef |

### Coreference/output fixes found and fixed

- **Masterful Replication**: `that artifact` bound to the later `Each other
  artifact`; added `copy-of-target` so the demonstrative points at the chosen
  target.
- **Jace's Mindseeker**: `them` had no milled-card candidate. Bare counts after
  mill/exile/reveal/discard/draw are now inventoried; `them` -> `cards`.
- **Demonic Embrace / Jace's Mindseeker**: `its mana cost`/`its other costs`
  bound to the wrong card. Added `its-cost-card`, preferring a spell/card and
  then the self card when present.
- **Captivating Gyre**: `their owners' hands` correctly binds to the target
  creatures; the possessive antecedent is the creatures, not a separate owner
  entity.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.7% entity-aware / 84.9% exact** (was 90.5 / 84.7).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 9 — seed 20261031

Cards:

`Inferno Hellion`, `Generator Servant`, `Mana Leak`, `Brightwood Tracker`,
`Sabertooth Mauler`, `Basri Ket`, `Faith's Fetters`, `Gloom Sower`,
`Radiating Lightning`, `Flameblast Dragon`, `Undergrowth Scavenger`,
`Diviner's Lockbox`, `Chromium, the Mutable`, `Spelltwine`, `Stone Giant`,
`Atemsis, All-Seeing`, `Harm's Way`, `Frost Titan`, `Capricious Efreet`,
`Sorin's Guide`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Undergrowth Scavenger | `enters with a number of +1/+1 counters ... equal to ...` | added the counted-counter enters form |
| Chromium, the Mutable | `base power and toughness 1/1, loses all abilities, and gains hexproof` | extended the base-power/toughness become tail |
| Spelltwine | coordinated exile targets | added coordinated exile |
| Stone Giant | `toughness less than this creature's power`; destroy at next end step | added comparative power/toughness modifiers and the destroy timing suffix |
| Harm's Way | `The next 2 damage ... is dealt ... instead` | added the static replacement-damage form |

### Coreference/output fixes found and fixed

- **Inferno Hellion**: `shuffles it` bound to `its owner`; shuffling is now an
  object verb and `owner` is typed as a player, so `it` stays the creature.
- **Gloom Sower**: `that creature` bound to `this creature` because
  `blocked by a creature` was dropped as a copula complement. The predicate
  filter now keeps relational NPs, and the relation prefix is stripped to
  `a creature`.
- **Spelltwine**: `those cards`/`their` had only one conjunct. Added
  `merge_coordinated`, which keeps the individual mentions and adds one
  coordinated collection span; the collection can now be the antecedent.
- **Harm's Way**: `that a source` was a false demonstrative from the relative
  clause. The demonstrative regex now rejects an article immediately after
  `that/this/those/these`.
- **Owner type**: `its owner` / `their owners` now count as player mentions.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.6% entity-aware / 84.8% exact** (owner typing and
  coordinated spans changed a few dev candidate choices).
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 10 — seed 20261101

Cards:

`Chord of Calling`, `Cruel Sadist`, `Ogre Battledriver`, `Bramble Creeper`,
`Blastfire Bolt`, `Bogbrew Witch`, `Glimpse the Future`,
`Infernal Reckoning`, `Liliana's Shade`, `Diabolic Revelation`, `Dissipate`,
`Repeated Reverberation`, `The Chain Veil`, `Scapeshift`,
`Dismiss into Dream`, `Wild Evocation`, `Abnormal Endurance`, `Merfolk Spy`,
`Arachnus Web`, `Scheming Symmetry`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Repeated Reverberation | coordinated `cast an instant spell, cast a sorcery spell, or activate a loyalty ability`; `copy that spell or ability twice` | added the coordinated trigger and copy-spell-or-ability form; `instant spell`/`sorcery spell` card kinds |
| The Chain Veil | activated ability whose effect is `For each planeswalker ...`; `activate one of its loyalty abilities` | allowed `for_each_sentence` under activated abilities and added the one-of-its-loyalty-abilities activate form |
| Wild Evocation | `the player casts it ... if able` | added player-subject cast and the `if able` tail |
| Scheming Symmetry | third-person `searches`; `then shuffles and puts that card on top` | made `V_SEARCH` accept `searches`, added the third-person shuffle/put tail and the `Each of them` actor |

### Coreference/output fixes found and fixed

- **Wild Evocation**: `the player casts it` bound `it` to the player. `cast` is
  now an object verb, so `it` binds to `a card`.
- **The Chain Veil**: `one of its loyalty abilities` bound `its` to `you`.
  Added `its-quantified-object`, which prefers the quantified non-player object.
- **Repeated Reverberation**: `that spell or ability` remains ambiguous among
  the instant/sorcery/ability alternatives; the canonical shown is one of the
  valid spell branches.
- **Scheming Symmetry**: the search/put chain and `that card` are correct.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.6% entity-aware / 84.8% exact**.
- Bench coreference: **94.3% regex / 93.0% parser** (unchanged).

## Loop 11 — seed 20261102

Cards:

`Voracious Hydra`, `Cavalier of Gales`, `Pentavus`, `Embodiment of Agonies`,
`Disperse`, `Ring of Evos Isle`, `Boonweaver Giant`, `Goblin Rabblemaster`,
`Pursued Whale`, `Tenacious Dead`, `Secure the Scene`, `Garruk's Harbinger`,
`Flood of Tears`, `Vivien's Invocation`, `Quicken`, `Void Snare`, `Sage Owl`,
`Yawning Fissure`, `Megrim`, `Goblin Bangchuckers`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Cavalier of Gales | `put two cards ... on top of your library in any order` | added the order modifier to the on-top put form |
| Boonweaver Giant | search graveyard/hand/library for an Aura and put it onto the battlefield attached to this creature | allowed plural `zones` in the put-attached search form and attached-put output |
| Goblin Rabblemaster | `Other Goblin creatures you control attack each combat if able` | added plural attack-each-combat/this-turn if able |
| Pursued Whale | `Spells your opponents cast that target this creature cost ...` | added the opponents-cast-that-target cost subject |
| Garruk's Harbinger | `a creature card or Garruk planeswalker card` | allowed `or` in reveal lists and CARDNAME + planeswalker card |
| Quicken | `The next sorcery spell you cast this turn can be cast as though it had flash` | added the next-spell flash static form |

### Coreference/output fixes found and fixed

- **Pursued Whale**: `that target this creature` was a false demonstrative from
  a relative clause. The anaphor detector now rejects two determiners
  (`target this/that/...`).
- **Tragic Banshee / Fiery-style chains**: `that creature` now prefers a target
  mention over a later indefinite creature, but keeps an earlier same-surface
  anaphor so existing chains stay intact.
- **Garruk's Harbinger**: the reveal alternatives and `them`/`the rest` map to
  the coordinated card collection; singular `it` remains one legal alternative.
- **Boonweaver Giant**: `it` binds to the searched Aura card.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.7% entity-aware / 84.8% exact**.
- Bench coreference: **94.3% regex / 93.0% parser**.

## Loop 12 — seed 20261103

Cards:

`Conspicuous Snoop`, `Elvish Clancaller`, `Fauna Shaman`, `Growth Cycle`,
`Elderscale Wurm`, `Call to the Grave`, `Wall of Frost`, `Leyline of Abundance`,
`Underworld Dreams`, `Distress`, `Gauntlets of Light`, `Soul Sear`,
`Grasping Scoundrel`, `Nexus of Fate`, `Traumatize`,
`Mu Yanling, Celestial Wind`, `Necrotic Plague`, `Soul of Shandalar`,
`Obstinate Baloth` (and the repeated sample card).

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Conspicuous Snoop | `has all activated abilities of that card` | added the has-all-activated-abilities action |
| Elderscale Wurm | `your life total becomes 7`; `damage ... reduces it to 7 instead` | added life-total and damage-reduction actions |
| Leyline of Abundance | `add an additional {G}` | allowed additional symbol mana |
| Gauntlets of Light | `assigns combat damage equal to its toughness ...` | added the assign-combat-damage action |
| Necrotic Plague | controller chooses `target creature one of their opponents controls`; return from a graveyard attached | added the choose-object form and the from-zone attached return |
| Soul of Shandalar | `up to one target creature that player or that planeswalker's controller controls` | added the damage recipient |

### Coreference/output fixes found and fixed

- **Necrotic Plague**: `its owner's graveyard` bound to `its controller` because
  the generic `from ...` container rule ran on a possessive. Container-player
  binding now skips possessives; the antecedent is `this card`.
- **Distress**: `that card` binds to the chosen nonland card; `it`/`that player`
  stay on the target player/hand proxy.
- **Soul of Shandalar**: `It` binds to `this card` (the card exiled from the
  graveyard), with the zone kept in the mention surface.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.7% entity-aware / 84.9% exact**.
- Bench: **95.7% regex / 93.0% parser**.

## Loop 13 — seed 20261104

Cards:

`Index`, `Peer into the Abyss`, `Rise from the Grave`, `Yeva, Nature's Herald`,
`Apex of Power`, `Kurkesh, Onakke Ancient`, `Satyr Wayfinder`,
`Ajani Goldmane`, `Chromatic Orrery`, `Tidebinder Mage`, `Roaring Primadox`,
`Awaken the Ancient`, `Tezzeret, Cruel Machinist`, `Forge Devil`,
`Urborg, Tomb of Yawgmoth`, `Leyline of Combustion`, `Druid of Horns`,
`Mistcaller`, `Mutavault`, `Into the Void`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Tezzeret, Cruel Machinist | `put any number of cards ... onto the battlefield face down` | allowed face-down puts |
| Tezzeret / token text | `They're 5/5 artifact creatures` | added the plural static token form |
| Mistcaller | activated ability whose effect is `Until end of turn, if ...` | **not fixed**: the broad until/if form caused a parser blow-up and was reverted; documented as a limitation |
| Mutavault | `creature with all creature types until end of turn` | allowed the duration on the all-creature-types become tail |

### Coreference/output fixes found and fixed

- **Mistcaller**: the `if a nontoken creature would enter and it wasn't
  cast ...` condition needed `it` inside `any_text`; `it` now remains the
  entering nontoken creature (ambiguous but correct class).
- **Awaken the Ancient**: `Enchanted Mountain` was missing from inventory.
  Added status+card-name mentions; `It's still a land` binds to the Mountain.
- **Druid of Horns / Pursued Whale**: `that targets this creature` is a
  relative clause, not a demonstrative; the detector now skips surfaces with
  `target(s)`.
- **Peer into the Abyss / Index / Ajani**: collection and token anaphors checked
  and correct.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- `test_output.py FDN.json`: 44/44.
- `test_coref.py`: 16/16.
- Dev coreference: **90.7% entity-aware / 84.9% exact**.
- Bench: **95.7% regex / 93.0% parser**.

## Loop 14 — seed 20261105 (halted)

The sample began cleanly, but `Sanctum of All`'s second ability

```text
If a triggered ability of another Shrine you control triggers while you
control six or more Shrines, that ability triggers an additional time.
```

made the Earley parser spend over a minute on one sentence even after adding a
targeted rule; the ambiguity came from the existing permissive `if_sentence` /
`any_text` alternatives, not from the card-specific phrase.  A previous attempt
to solve this by allowing `it`/`they` in `any_text` and `if_sentence` under
`until_sentence` had already been reverted in `df02271` because it made simple
parses globally slow.

Loop 14 is therefore halted rather than committed with a workaround that would
hide a parser-ambiguity/performance problem.  The next useful work is to
refactor the permissive condition fallbacks (or add a deterministic fast path
for fixed-form condition sentences), not to add another broad `any_text` rule.

No card-fix commit was made for this loop.

## Loop 15 — seed 20261106

Cards:

`Setessan Training`, `Archfiend's Vessel`, `Bonescythe Sliver`,
`Charging Griffin`, `Elixir of Immortality`, `Acidic Slime`, `Scorch Spitter`,
`Yarok's Wavecrasher`, `Goremand`, `Kitesail Freebooter`, `Flesh to Dust`,
`Slumbering Dragon`, `Aegis Angel`, `Ajani's Influence`,
`Cavalry Drillmaster`, `Drudge Skeletons`, `Fiery Emancipation`,
`Chief Engineer`, `Crumbling Colossus`, `Goblin Motivator`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Scorch Spitter | `damage to the player or planeswalker it's attacking` | allowed the relative `it's/they're attacking` suffix on `damage_who`; interpreter now emits `{or: [...], attacking: true}` |
| Chief Engineer | `Artifact spells you cast have convoke` | added `convoke` to the keyword terminal |
| Setessan Training | `Enchanted creature gets +1/+0 and has trample` | added `i_enchanted_sentence`; applies the enchanted subject to both coordinated actions |
| Cavalry Drillmaster | `target creature gets +2/+0 and gains first strike` | coordinated effect actions now inherit a shared target when the later tree target is empty |
| Kitesail Freebooter | `choose a noncreature, nonland card from it` | cut the trailing source PP out of the list span and exposed the chosen card as a structured list object |

### Coreference/output fixes found and fixed

- **Kitesail Freebooter**: `it` in `choose ... from it` now binds to `their hand`,
  not `target opponent`. Added possessive zone mentions and a container filter
  for hand/graveyard/library/exile. `that card` now binds to
  `a noncreature, nonland card` via a choose-context list mention.
- **Archfiend's Vessel**: the new zone mentions initially stole `it` after
  `cast`/`exile`; object/sacrifice filters now exclude zone containers. All
  three `it` occurrences bind to `this creature`.
- **Scorch Spitter**: `it's attacking` is represented as the damage recipient
  relation, not loose tokens.
- **Setessan Training / Cavalry Drillmaster**: coordinated stat/keyword actions
  retain their shared target.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible.
- `test_output.py FDN.json`: 48/48.
- `test_coref.py`: 17/17 after cache rebuild.
- Dev coreference: **90.7% entity-aware / 84.9% exact**.
- Bench: **95.8% regex / 91.5% parser** entity-aware.
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 16 — seed 20261107

Cards:

`Pridemalkin`, `Sigiled Contender`, `Indestructibility`, `Liliana's Caress`,
`Vial of Poison`, `Alpine Moon`, `Colossal Whale`, `Tempered Veteran`,
`Sanctified Charge`, `Goblin Ringleader`, `Enlarge`, `Druidic Satchel`,
`Spined Megalodon`, `Benalish Veteran`, `Poison-Tip Archer`, `Battle Mastery`,
`Conclave Mentor`, `Drowsing Tyrannodon`, `Kinetic Augur`, `Blood Ogre`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Alpine Moon | `Lands ... lose all land types and abilities, and they gain "{T}: ..."` | added the static land-type-loss/gain form |
| Sanctified Charge | `White creatures you control also gain first strike` | allowed `also` before `gain` in `gain_kw_action` |
| Drowsing Tyrannodon | `this creature can attack as though it didn't have defender` | added `can_attack_as_though_action` and structured the missing keyword |
| Conclave Mentor | `that many plus one +1/+1 counters are put on that creature instead` | added `replace_counter_action` |

### Coreference/output fixes found and fixed

- **Pridemalkin / Tempered Veteran**: a pronoun inside a modifier
  (`... with a +1/+1 counter on it`) now binds to the containing creature NP.
- **Alpine Moon**: `they` binds to `Lands your opponents control with the
  chosen name`, not the embedded `your opponents` NP, via the
  collection-subject rule.
- **Druidic Satchel**: after `Reveal the top card ... If it's A ... If it's B`,
  later `it's` conditions chain to the original top card instead of the token
  created by the intervening effect.
- **Drowsing Tyrannodon**: `as though it didn't have defender` binds to the
  clause subject.
- **Conclave Mentor**: the replacement effect is structured, with the quantity
  anaphor kept separate from entity coreference.
- **Goblin Ringleader**: `the rest` binds to `the top four cards`, the source
  collection, not to the `all Goblin cards` subset just moved to hand.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible.
- `test_output.py FDN.json`: 51/51.
- `test_coref.py`: 18/18 after cache rebuild.
- Dev coreference: **91.2% entity-aware / 85.2% exact** (was 90.7 / 84.9).
- Bench: **95.8% regex / 91.5% parser** entity-aware.
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 17 — seed 20261108

Cards:

`Idol of Endurance`, `Ob Nixilis, Unshackled`, `Feat of Resistance`,
`Heroic Reinforcements`, `Liliana of the Dark Realms`, `Scepter of Empires`,
`Aetherspouts`, `Sarkhan's Unsealing`, `Will-Forged Golem`,
`Tezzeret's Strider`, `Miner's Bane`, `Brink of Disaster`, `Triskelion`,
`Chandra, Awakened Inferno`, `Academy Raider`, `Lifelink`, `Terra Stomper`,
`Lurking Crocodile`, `Overcome`, `Burst of Speed`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Idol of Endurance | `cast a creature spell from among cards exiled with this artifact` | added `from among` to `cast_action` and `exiled with` to `with_modifier` |
| Scepter of Empires | `It deals 3 damage instead if ...` | allowed capital `It`/`They` damage subjects and preserved the trailing `if` condition |
| Aetherspouts | `For each attacking creature, its owner puts it on their choice ...` | allowed `its/their owner` as `owner_subject` |
| Sarkhan's Unsealing | `creature spell with power 4, 5, or 6`; damage to `each opponent and each creature and planeswalker they control` | added the comma power list and the full damage-recipient phrase |

### Coreference/output fixes found and fixed

- **Scepter of Empires**: `It deals 3 damage instead` now binds to `This artifact`,
  the damage source, not the target player/planeswalker.
- **Aetherspouts**: `their` in `its owner puts it on their choice ... their
  library` binds to `its owner`; owner NPs are now part of the mention inventory.
- **Sarkhan's Unsealing**: `they control` binds to `each opponent`, not the
  controlled creature/planeswalker collection.
- `i_effect_sentence` now retains a trailing `if` condition on effects.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible.
- `test_output.py FDN.json`: 54/54.
- `test_coref.py`: 19/19 after cache rebuild.
- Dev coreference: **91.2% entity-aware / 85.2% exact**.
- Bench: **95.8% regex / 91.5% parser** entity-aware.
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 18 — seed 20261109

Cards:

`Elvish Rejuvenator`, `Blood Reckoning`, `Polymorph`, `Icon of Ancestry`,
`Stabbing Pain`, `Dark Tutelage`, `Mystifying Maze`, `Liliana, Waker of the Dead`,
`Elvish Reclaimer`, `Ajani's Chosen`, `Peel from Reality`, `Chandra's Outrage`,
`Excommunicate`, `Primordial Hydra`, `Farseek`, `Double Vision`,
`Jace, the Living Guildpact`, `Thought Distortion`, `Invasive Species`,
`Liliana, Death Mage`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Thought Distortion | `Exile ... cards from that player's hand and graveyard` | allowed a coordinated `zones` source and emitted `zones: [hand, graveyard]` |
| Liliana, Death Mage | `Target opponent loses 2 life for each creature card in their graveyard` | added `V_LOSE life_amount for each card_target` and a structured `for_each` field |

### Coreference/output fixes found and fixed

- **Full-card resolution**: the audit now resolves the normalized card text as a
  whole (preserving oracle newlines), so cross-sentence pronouns in `Polymorph`,
  `Stabbing Pain`, and `Mystifying Maze` are exercised. They now bind to the
  creature established in the previous sentence.
- **Jace, the Living Guildpact**: a preceding `one of them` no longer captures
  later possessives. `its owner` binds to `another target nonland permanent`, and
  both `their hand` / `their library` bind to `Each player`.
- **Dark Tutelage**: `its mana value` binds across the sentence boundary to
  `the top card`, not to the player losing life.
- **Ajani's Chosen**: `attach it to the token` binds `it` to the enchantment
  being attached, not to the destination token.
- **Liliana, Death Mage**: `Its controller` chains to the target creature from
  the preceding destruction clause; `their graveyard` binds to the opponent.

### Remaining limitation

`Peel from Reality`: `their` in `their owners' hands` still binds to the
coordinated creature collection, not to a separately invented owner-player
mention. This is the known owner/collection inventory limitation first recorded
in Loop 1.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible
  (apart from the documented owner-collection limitation).
- `test_output.py FDN.json`: 56/56.
- `test_coref.py`: 21/21 after cache rebuild.
- Dev coreference: **91.2% entity-aware / 85.3% exact**.
- Bench: **95.8% regex / 91.5% parser** entity-aware.
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 19 — seed 20261110

Cards:

`Leyline of Vitality`, `Warstorm Surge`, `Ethereal Elk`, `Suncleanser`,
`Run Afoul`, `Yarok's Fenlurker`, `Niambi, Esteemed Speaker`, `Liliana's Scorn`,
`Fire Servant`, `Sublime Epiphany`, `Lofty Denial`, `Hooded Blightfang`,
`Sparkmage Apprentice`, `Stab Wound`, `Pattern Matcher`, `Diabolic Tutor`,
`Mitotic Slime`, `Track Down`, `Ring of Kalonia`, `Palladia-Mors, the Ruiner`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Leyline of Vitality | `you may begin the game with it on the battlefield` | added `begin_game_action` inside effects and may-actions, with an interpreter handler |
| Suncleanser | `can't have counters put on it for as long as ...` | added the duration form of `cant_action` |
| Run Afoul | `sacrifices a creature of their choice with flying` | allowed `with_modifier` on `sacrifice_action` |
| Stab Wound | `At the beginning of the upkeep of enchanted creature's controller` | added the controller-upkeep form of `trig_when` |

### Coreference/output fixes found and fixed

- **Pattern Matcher**: both `it` occurrences now bind to the searched card, not
  the nested `another creature you control`; the search context prefers the
  matching card mention.
- **Suncleanser**: `It` / `it` bind to `target creature`, and `That player` binds
  to `Target opponent`.
- **Hooded Blightfang**: `that planeswalker` binds to `a planeswalker`; the
  typed demonstrative is locked with a regression test.
- **Stab Wound**: `that player` binds to `enchanted creature's controller`.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible.
- `test_output.py FDN.json`: 60/60.
- `test_coref.py`: 23/23 after cache rebuild.
- Dev coreference: **91.2% entity-aware / 85.3% exact** (3083/3380, 2883/3380).
- Bench: **95.8% regex / 91.5% parser** entity-aware.
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 20 — seed 20261111

Cards:

`Renowned Weaponsmith`, `Jace's Archivist`, `Meteorite`, `Dwindle`,
`Ring of Valkas`, `Liliana's Reaver`, `Waterknot`, `Thundermaw Hellkite`,
`Conundrum Sphinx`, `Fire Servant`, `Cavalier of Flame`, `Belltower Sphinx`,
`Salvager of Ruin`, `Savage Summoning`, `Hypnotic Specter`,
`Dismissive Pyromancer`, `Lay of the Land`, `Monomania`, `Convolute`,
`Unsubstantiate`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Renowned Weaponsmith | `Spend this mana only to cast artifact spells or activate abilities of artifacts` | added the plural coordinated cast/activate form of `spend_mana_action` |
| Jace's Archivist | `cards equal to the greatest number of cards a player discarded this way` | added the matching `xdef` alternative |
| Conundrum Sphinx | `each player reveals the top card of their library` | allowed a non-`your` possessor in the top-card `reveal_action` |

### Coreference/output fixes found and fixed

- **Savage Summoning**: `as though it` now prefers a same-sentence non-self
  subject over the card itself. `it` and `That spell` bind to
  `The next creature spell`.
- **Savage Summoning**: spell-typed anaphors may bind to a candidate whose
  surface contains `spell`, so `That spell` can select
  `The next creature spell`.
- **Conundrum Sphinx**: `If it doesn't ...` continues with the object from the
  preceding clause (`the card a player`) instead of the destination `their hand`.
- **Monomania**: `the rest` intentionally abstains. The text has no explicit
  collection mention for the unchosen cards, and binding it to the chosen card
  or the hand would be semantically wrong.

### Remaining limitations

- **Monomania**: `the rest` stays `no-resolution` (`set-rest-no-collection`),
  as documented above.
- **Jace's Archivist**: the draw effect omits its `who` field because the
  optional `who` can match an empty `card_target`. This is pre-existing and
  left as an accepted output limitation; the discard subject and the draw
  amount are correct.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible,
  apart from the documented abstentions.
- `test_output.py FDN.json`: 63/63.
- `test_coref.py`: 26/26 after cache rebuild.
- Dev coreference: **91.3% entity-aware / 85.4% exact** (3086/3380, 2886/3380;
  was 91.2 / 85.3).
- Bench: **95.8% regex / 91.5% parser** entity-aware (unchanged from baseline).
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 21 — seed 20261112

Cards:

`Hunter's Insight`, `Wit's End`, `Hunter's Edge`, `Seasoned Hallowblade`,
`Lifebane Zombie`, `Destructive Force`, `Leyline of Anticipation`, `Stuffy Doll`,
`Ring of Three Wishes`, `Guardian of the Ages`,
`Vaevictis Asmadi, the Dire`, `Kalonian Hydra`, `Vivien, Nature's Avenger`,
`Stonehorn Dignitary`, `Bag of Holding`, `Novice Knight`, `Chronostutter`,
`Detection Tower`, `Pulse of Murasa`, `Arachnus Spinner`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Vaevictis Asmadi, the Dire | `for each player, choose target permanent that player controls` | added the per-player prefix to `choose_action`; the handler reports `per_player` |
| Vaevictis Asmadi, the Dire | `Each player who sacrificed a permanent this way reveals ...` | allowed the `who sacrificed ... this way` relative clause in `who` |
| Stonehorn Dignitary | `target opponent skips their next combat phase` | added `skip_action` and the `skips` verb |
| Detection Tower | `... can be the targets of spells ... as though they didn't have hexproof` | added `can_target_action` and the negative auxiliary form `didn't` |

### Coreference/output fixes found and fixed

- **Lifebane Zombie**: color-qualified card phrases such as
  `a green or white creature card` are now candidate mentions. `that card`
  binds to that phrase instead of falling back to `this creature`.
- **Vaevictis Asmadi, the Dire**: `those permanents` retains the full
  `target permanent that player controls` antecedent; `it's` binds to
  `the top card`.
- Added output regressions for skipping a combat phase, hexproof-targeting
  exceptions, per-player choices, and the sacrificed-this-way reveal.
- Added a coreference regression for Lifebane Zombie's color-qualified card.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible.
- `test_output.py classic.json`: 67/67.
- `test_coref.py`: 27/27 after cache rebuild.
- Dev coreference: the Lifebane candidate fix is retained with no other
  observed regressions (the combined loop-22 figures are below).
- Bench: **95.8% regex / 91.5% parser** entity-aware (unchanged).
- `test_normalize_map.py`: 6/6; dataset span validation passes.

## Loop 22 — seed 20261113

Cards:

`Claustrophobia`, `Ajani, Inspiring Leader`, `Vivien of the Arkbow`,
`Chandra's Fury`, `Illusionary Servant`, `Scrambleverse`, `Aether Gust`,
`Mass Polymorph`, `Bloodlord of Vaasgoth`, `Nissa's Expedition`,
`Brash Taunter`, `Basri, Devoted Paladin`, `Jalira, Master Polymorphist`,
`Phantasmal Image`, `Cavalier of Dawn`, `Read the Tides`, `Grim Tutor`,
`Alpine Houndmaster`, `Grim Return`, `Nefarox, Overlord of Grixis`.

### Parse failures found and fixed

| card | sentence / cause | fix |
|---|---|---|
| Scrambleverse | `gains control of each permanent for which they were chosen` | added the trailing `for which ... chosen` modifier; the handler emits `for_which_chosen` |
| Aether Gust | `Its owner puts it on their choice of the top or bottom of their library` | allowed capitalized `Its` as an owner subject; `put_library` keeps owner and destination as text |
| Mass Polymorph | `reveal ... until you reveal that many creature cards` and `shuffle the rest of the revealed cards into your library` | allowed a `that many` reveal condition and the full revealed-rest shuffle phrase |
| Bloodlord of Vaasgoth | `it gains bloodthirst 3` | added `bloodthirst` and an optional number to keyword-list items |
| Phantasmal Image | `enter as a copy ... except it's ... and it has "..."` | allowed `token_except` and the quoted granted ability in `have_action` |

### Coreference/output fixes found and fixed

- **Phantasmal Image**: all four anaphors (`it's`, `its`, `it`, and the
  quoted `it`) bind to `this creature`, the new copy. The copy-with-exception
  rule is restricted to `enter as a copy` contexts so token-copy mentions
  elsewhere are not rewritten.
- **Mass Polymorph**: the reveal action records its `that many` condition,
  and the revealed-rest shuffle parses as a `shuffle` action.
- **Scrambleverse**: the gain-control action records that the permanents
  were chosen for each player.
- **Aether Gust**: owner and destination are plain text, and `it` / `their`
  bind to the spell-or-permanent and its owner respectively.
- Added output regressions for chosen-control, owner-choice library
  placement, reveal-until, revealed-rest shuffle, numbered bloodthirst, and
  copy-with-exception; added the four-pronoun Phantasmal Image coref test.

### Remaining limitations

- **Phantasmal Image**: the `except ...` clause is emitted as a separate
  `gain_quote` action rather than being folded into the `copy` effect.
- **Alpine Houndmaster**: both `them` occurrences stay `ambiguous` because the
  candidate pool contains two identical `a card named ~` mentions.

### Verification

- 20/20 sampled cards parse every non-modal sentence.
- All inspected anaphora choices are resolved and semantically defensible,
  apart from the documented ambiguity.
- `test_output.py classic.json`: 73/73.
- `test_coref.py`: 28/28 after cache rebuild.
- Dev coreference: **91.4% entity-aware / 85.5% exact** (3089/3380, 2889/3380;
  was 91.3 / 85.4).
- Bench: **95.8% regex / 91.5% parser** entity-aware (unchanged from baseline).
- `test_normalize_map.py`: 6/6; dataset span validation passes.
