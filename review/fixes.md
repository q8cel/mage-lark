# Deferred defect classes

Not fixed in this pass; representative sids from `review/*/verdicts/`.
Counts are verdict rows matching the note shape when last measured.

| class | sids | why deferred |
|---|---|---|
| "would … instead" replacement effects (token doubling/tripling, extra tokens, counter doubling) | 3463c1add138 ed961aa155dc 94a49a70a885 aa7cea1f2677 a9142ff0befe 6e498839a208 2b9549e74eb0 | These sentences describe a replacement of a *would-be* event; the grammar has no replacement-effect action, so they collapse to raw text. Needs a new sentence/action shape, not a handler readback. |
| coordinated multi-object actions: second conjunct / destination dropped ("put a +1/+1 and a plan counter", "that pile … and the other", "hand and/or library", "… and the rest") | 0b2233483bc7 b47a39f2f185 f715d22cd4d9 93635c37f3ef 415de49557fb 1fd2ff116ec2 526fa612ccdd | Each grammar alternative keeps only the first object/destination. Needs a coordinated-action representation shared by put/counter/search actions. |
| copy source and `become a copy of …` target | 50acc43ad19c 6e08aa7bfbdb ec19275a 94802e05716b | `become`/`copy` handlers read only the copying permanent; the copy source is a sibling `card_target`. Needs a result-type + copy-source decomposition. |
| X definitions not attached in every action ("where X is …" on cost mods, damage, mill) | cf436b946804 88004a9eda6d 1e3ceaf0307e 9faafcbb6bcd c3d50abc6f5d | The `xdef_clause` reaches most sentence types now; some nested actions (cost mods, for-each, trigger xdef) still truncate or drop it. |
| mana actions that dispatch to the generic keyword list ("Add {R}" → static_keyword) | d41a3f5db042 | Sentence-level disambiguation between `add_mana` and `generic_kw_list`; needs a grammar alternative/priority rather than a handler fix. |
| token counters ("with a hexproof counter and an indestructible counter") and long granted abilities with quoted rules | 0f84ee3b9431 82831477d85c 324b9ceff19b | `token_tail` has no counter-list form; granted QUOTE is now kept, but multi-tail counters need a grammar alternative. |
| "Then if …" consequence that is not a recognized action (transform, skips, delayed setup) | 007848ea7828 bffffb6b6a04 1aee81b1b363 | Condition is now preserved, but the consequence still interprets to `{'verb':'raw'…}` because no action rule matches it. Each verb (transform, skip, plotted) needs its own action. |
| coordinated subject/object across or-lists ("Dwarf or Equipment you control") | 067ecdbea18a 345dd0914093 2f86de40c83a | The or-list rebuild drops per-item qualifiers; needs a subject decomposition, not a token readback. |
| `one or more N` quantifier reported as `1` (no "one or more" marker) | 5c77f39978ed 4d5fae31d75d | Reviewer marked these unsure; the quantifier `amount V_TARGET` path reports the count without the "or more" bound. Needs a quantifier representation decision. |

## Unparsed-tail deferrals

| class | texts | why deferred |
|---|---|---|
| "with counters on them" modifier (Creatures you control with counters on them …) | ~4 Standard | Adding the alternative to `with_modifier` doubles 15-word parse time (0.42 s -> 0.77 s) because `with_modifier` is reachable from every `card_target`. Needs a non-`with_modifier` home. |
| Keyword cost with em dash (`Impending 4—{2}{W}{W}`, `Blitz—{…}`) | ~10 Standard | Needs a closed keyword-argument rule; not yet attempted. |
| Double-dash ability line (`Name — {cost} — effect`, `{P}{P} — effect`) | ~15 Standard | Sentence-level dispatch alternative needed. |
| "until your next turn" on stat/keyword changes | ~8 Standard | Needs additive alternatives in several actions; would duplicate long rules. |

## Cycle-12 deferrals (grammar queue)

| class | sids | why deferred |
|---|---|---|
| alternative cast cost: "in addition to paying its other costs" as a structured field | e4e9c2d2d824 | The clause parses and is currently kept inside the `by` string; representing it as a separate cost component needs a cost-by decomposition shared by cast/activated cost lists, not a readback. |
| shuffle object "the rest" not referenced | cf482a72c5b3 | `shuffle_action` emits `from: []`; expressing "the rest of the chosen cards" needs an anaphoric set reference in the action model, which is a structural change. |

## Cycle-14 cost-boundary scan

| class | sids | why deferred / measured result |
|---|---|---|
| silent activated cost-boundary mismatch | none (probe "{4}, {T}: Two target creatures … can't be blocked") | Snapshot scan of interpreted outputs (Standard_cycle14 7,184; classic 2,076; FDN 761): `has_prefix_no_cost` = 5 / 0 / 1, all keyword-cost statics (Equip/Flashback/Ward/Warp) whose cost is still in `keywords.modifier`; `activated_no_prefix` = 0 / 0 / 0 after normalizing ability words ("Power-up —", "Exhaust —", "Waterbend {N}"); `activated_empty_cost` = 0. The probe sentence is a parse failure, not a silent success, so no cost_list/effect rewrite was made. Scenario counts are flap-prone if the prefix regex ignores ability words (raw first pass: 38/0/0 activated_no_prefix and 119 including parsefails). |

## Clause phase: deferred structural shapes (measured)

| class | measured size | why deferred |
|---|---|---|
| replacement-event clauses | 49 Standard clause sites; top sub-shape "would die this turn" only 5, then "would be created under your control" 4, "would be put into a graveyard" 3 | the class is genuinely varied (would die/created/put/deal/enter/leave, each 1-5 sites), so a closed grammar alternative would cover only a small slice at a chart-cost; leave triage |
| while / as-long-as nesting | 38 Standard clause sites, all beginning "while" | nesting (while + control/count/state) needs recursive condition construction; the simple inner states are already structured by the readback handlers, but the wrapper is a grammar/structural change |

## Interpret-gap phase (readback families)

| family | size (texts / occurrences) | built | left |
|---|---|---|---|
| static_text / i_static_sentence | 95 / 497 | fixed enum: trigger/action once-each-turn, start engines, uncounterable, type retention, damage-prevention disabled, loss lock, mode repeat, enchant creature you control, plus split enchant+`you control` join: 329 occurrences closed | 168 occurrences (arbitrary "Activate only if …", free-form statics) |
| xdef_text / i_xdef* | 73 / 134 | six highest-frequency raw expressions normalized (your speed, your life total, its power, that spell's mana value, life gained this turn, +1/+1 counters on ~): 51 occurrences closed | 83 occurrences, varied (number-of/among/color-pair forms) |
| trigger_text / i_trigger_clause | 379 / 634 | one-or-more [other] X you control die (83), a creature you control attacks alone (44), ~ enters (13): 140 occurrences closed | ~494 occurrences: cast/activate/unlock/commit-crime/expend and compound enter-or-turn-face-up events |

## Parse-gap batches (parse-fail ledger, Standard)

Queue: `review/gap_ledger.tsv`, class `parse_fail` (781 unique / 1,463 occurrences
against 20,754/22,217 parse), grouped by `head`; top-10 heads cover 12.71% and the
rest is a long tail. Sampling shows the heads are tail problems (the trigger prefix
parses; the effect/clause after the comma fails), so causes were picked by tail
shape across heads, not head by head.

### batch: Level-N frame marker

| field | value |
|---|---|
| gap | `{W}: Level 2` — the activated/level-up effect is the marker `Level N`; no action matched it, so the line died after the colon |
| change | `level_action: "Level" number` in the action list; `i_level_action` -> `{verb: level, level: N}` |
| texts fixed | 21 unique / 28 occurrences (all `Level 2`/`Level 3` lines) |
| rule count | 3,338 -> 3,340 (+2) |
| timing | ABBA 15-word parse 1.113 s -> 1.127 s (1.013x, noise) |
| corpus delta | Standard seeded parse 20,754 -> 20,782; failures 1,463 -> 1,435 occ / 781 -> 760 uniq. FDN honest unchanged 1,494/1,653 (90.4%) |
| left | `Level N` lines with a non-cost prefix (e.g. "Level up" costs) not present upstream |

### batch: Craft-with keyword line

| field | value |
|---|---|
| gap | `Craft with <arg> {cost}` — a keyword ability line whose argument is a card kind / list / quantifier and whose trailing mana is the craft cost; the sentence dispatcher had no rule for it (CHAR at the `{`) |
| change | `craft_sentence: "Craft" "with" craft_arg MANA+`; `craft_arg` = `one or more [target]` / `amount or more target` / `target ("," target)* (","? "and" target)?`; `i_craft_sentence` returns `type: craft`, `with`, `cost` |
| texts fixed | 18 unique / 22 occurrences (`Craft with artifact/creature/Cave/Island/Dinosaurs`, list and "two creatures" forms) |
| rule count | 3,340 -> 3,351 (+11) |
| timing | ABBA 15-word parse 0.433 s -> 0.436 s (1.007x) |
| corpus delta | Standard seeded parse 20,782 -> 20,804; failures 1,435 -> 1,413 occ / 760 -> 742 uniq. FDN honest unchanged 1,494/1,653 (90.4%) |
| left | `Craft with four or more nonlands with activated abilities {8}{U}` (card_target lacks the relative "with activated abilities" modifier) |

### batch: double/triple power and toughness

| field | value |
|---|---|
| gap | `Double the power and toughness of X`, `Double target creature's power and toughness`, `Double the power of X`, `Double its power and toughness and it gains trample`, `Double all damage … would deal`, `Triple target creature's power and toughness` — double_action only knew "double the number of X" and "double X's power" |
| change | double_action gains the power-and-toughness forms, the all-damage form, "the power of X", the anaphoric "its power and toughness and it gains kw", and V_TRIPLE forms; i_double_action reports verb triple when the V_TRIPLE token is present |
| texts fixed | 8 unique / 16 occurrences measured for the drafted set; seeded Standard delta is +18 occurrences / +9 unique (one extra text resolved through the new alternatives) |
| rule count | 3,351 -> 3,371 (+20) |
| timing | ABBA 15-word parse 0.684 s -> 0.666 s (noise, no regression) |
| honest | parse-only gain: the pipeline tags verb `double` as `raw_action` by design (`_unparsed_tag`), so these sentences add parse coverage but not honest coverage. FDN honest stays 1,494/1,653 (the single FDN "Double …" line becomes parse-only, not honest) |
| left | relative-clause targets ("Double all damage that sources you control of the chosen type would deal" card-target tails) are now covered, but "double strike" texts are unrelated; making double honest needs an interpret-schema decision (out of this grammar phase) |

| condition shared cluster | i_if 513 / i_triggered 393 / i_effect 182 occ | gift-promised/not (27), you-control N or more/fewer (99), it was/is a <type> (51), x is N or more/less (11), player life threshold (10), five-or-more-mana-spent (13): ~211 occ closed across all condition sources; trailing-if reuses the same builder | remaining ledger heads: would-replacement 155, triggered-ability 42, there-are 37, you-put 23, opponent-comparison 19, plus other residual |

### shared tails: may-copy, empower X, keyword effect tails, compound become

Queue re-measured on master 7d706d9 (781 ledger texts re-parsed: 733 still failing;
the ledger is keyed to the older grammar). Tails were taken in occurrence order,
skipping anything under ~8 occurrences.

| tail | texts / occ | change | rules | ABBA | seeded Standard parse delta |
|---|---|---:|---|---|---|
| may-copy | 3 / 8 | copy_action added to may_action | +1 | 0.478 -> 0.482 s | 20,822 -> 20,831 |
| empower X | 4 / 8 measured (+12/+7 seeded) | case-insensitive V_EMPOWER + X as the amount | +1 | 1.043 -> 0.926 s | 20,831 -> 20,843 |
| keyword effect tails | 17 of 20 / 29 | endure_action + V_ENDURE; collect evidence as cost_item/effect with V_COLLECT; harmonize/persist/rebound in KEYWORD; as_cost xdef_clause | +12 | 0.528 -> 0.541 s (1.025x) | 20,843 -> 20,874 |
| compound become + gains | 2 still failing / 6 (third text unblocked by the cost fix) | become_tail his/her addition + and-gains, with-base-P/T + and-gains; "the color of your choice and gains …"; kw_list_item "KEYWORD from that color" | +25 | 0.499 -> 0.502 s | 20,874 -> 20,880 |

Cumulative after the four tails: Standard 20,880/22,217 = 94.0 % parse,
parse_fail 1,337 occ / 702 unique (from 1,395 / 733). Left: harmonize/persist/
rebound keyword words are now accepted but their _action_ forms (e.g. a
harmonize verb) are not; collect-evidence lines blocked on unrelated effects;
the long tail below.

| trigger_text event-kind groups | cast 103, unlock 45, commit-crime 27, activate 20, expend 14, face-up/transform 35 | 763f4c9 (cast), 1945a40 (commit/expend/unlock/activate), c96fe36 (face-up/transform): {kind:event, event:{subject,verb,object,window/ordinal/amount}} | trigger_text residual ~270 occ, mostly compound enter-or-turn-face-up and free-form one-offs |
| Standard honest after condition+trigger readbacks | parse 20,822/22,217 (93.7%), honest 18,662/22,217 (84.0%), unique 6,072; interpret_unparsed 2,160 occ / 1,161 unique | approximate marker split from ledger closures: condition ~1,317, trigger ~270, static 168, no_handler 125, raw_action 109, xdef 83, object 64, modifier 24 | remaining condition heads: would-replacement 155, triggered-ability 42, there-are 37, you-put 23, opponent-comparison 19 |

### family: would-replacement clauses

Measured on the ledger's `interpret_unparsed` rows: 51 texts / 158 occurrences
contain a "would" replacement (the named family size is 49 / 155; the wider
regex catches two more). Distribution by the event after "would": would be put
38, would die 32, would deal 32, would be created 17, would draw 7, would
create 6, would gain 5, would lose 5, would put 5, would be dealt 4, then
one-offs (connive/pay/mill/explore).

Built `replacement_sentence.2` with a closed `replacement_cond`
(would die; would be put into a zone (+from anywhere); would put counters on;
would deal damage; would be dealt damage; damage would be dealt; would gain/
lose life; would draw a card; would be created) and a new output type
`{type: replacement, if: <event>, instead: <action>}` reusing the event and
action builders. The rule has priority 2 so it wins over the generic
`any_text` if-sentence parse.

| field | value |
|---|---|
| structured | 22 texts / 89 of 158 occurrences (56%); prior shape was raw condition text |
| rule count | 3,410 -> 3,452 (+42) |
| timing | ABBA 15-word parse 0.530 -> 0.542 s (1.023x) |
| left | the remaining 67 occurrences need passive replacement actions ("twice that many of those tokens are created", "it deals twice that much damage") and conditions outside the closed set ("would lose unspent mana", "would connive/explore", "while …" tails). The passive multiplication side is a second structure, not a condition variant. |
| tests | if-instead / if-relative-life updated to assert the replacement shape (the deliberate contract change) |
