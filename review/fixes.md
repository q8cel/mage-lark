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

| trigger residual / no_handler / raw_action | trigger residual ~270; no_handler 125; raw_action 109 | 2750395 condition residual cluster (triggered-ability, there-are-among, you-put, opponent comparison); 9d978de no_handler event refs (When you/they do, cast-during-window); 6924944 double/triple structured | final Standard honest 18,983/22,217 = 85.4% occurrences (unique 6,253/7,966; interpret_unparsed 1,897 occ / 1,011 unique). Approx reason split: condition ~1,197, trigger ~270, static 168, xdef 83, object 64, modifier 24, raw_action ~91, no_handler ~0 |

### residual: passive replacement actions (closed, not built)

The would-replacement family structures 89 of 158 occurrences. The remaining 69
occurrences, enumerated by the replacement clause after the comma:

| shape | occurrences | example |
|---|---:|---|
| multiplication ("twice/three times that many … created/put") | 28 | "…, twice that many of those tokens are created instead" |
| other instead-clause (state flips, life/mana) | 18 | "… would lose unspent mana, that mana becomes red instead" |
| exile (condition-tail variants) | 11 | "If a card you didn't control would be put into an opponent's graveyard from anywhere, exile it instead" |
| double damage | 8 | "… it deals twice that much damage instead" |
| draw replacement | 3 | "If you would draw a card except the first one …, draw two cards instead" |
| other | 1 | "Prevent all damage that would be dealt by up to one target creature …" |

The largest closed form is the multiplication shape at 28 occurrences, below
the 30-occurrence build threshold, and the rest are distinct passivisations.
Adding a passive replacement action would cost a broad action shape for <30
occurrences, so the family is closed here; the 69 occurrences stay in the
ledger for a future phase.

| xdef closed forms | 83 occ residual; generic number-of/among/greatest + sacrificed/difference/total power | 78b1128: closed ~50; left ~33 (the number of times, rev/skewer/charge/cave counters, free-form) |
| object_text / modifier_text | object 64, modifier 24 | aa5e3dc: put-library owner choice (14) and distribute counts (13) structured; remaining object text is for_each one-offs; modifier_text is free-form "you've cast/discarded this turn" qualifiers and compound keyword costs — left |
| raw_action residual | ~91 non-double after 6924944 | top shapes pay-life-equal (9), it becomes plotted (8), additional-combat/end-step (5), cast-exiled-until (4); all below the 50-occ closed threshold — left |
| static_text residual | 168 | arbitrary "Activate only if …" + free-form statics; no closed sub-family ≥20 in head grouping — left |
| freeze point | Standard honest 19,158/22,217 = 86.2% (unique 6,328/7,966; interpret_unparsed 1,722 occ / 936 unique); FDN 1,572/1,653 = 95.1% (unparsed 81/45), parse 94.0% Standard | approximate remaining split: condition ~1,099 (would/free-form), trigger ~270 (compound), static 168, raw ~91, object ~37, xdef ~33, modifier 24, no_handler ~0 |

## Stringy families structured (Standard snapshot 69cae293)

Queue: `review/stringy_queue.md`. Acceptance: the family value is no longer a
prose string at its structured path, so an engine consumes it without splitting
text. Occurrences below are queue totals for the family; "covered" is the part
now emitted as an object (the rest are one-off shapes listed under left).

| family | total occ | covered | new object | left / notes |
|---|---:|---:|---|---|
| amount | 1,815 | ~1,480 | `{kind: number, value, unit: life}`; `{kind: mana, symbols}`; `{kind: mana_choice, options}`; `{kind: mana, count, of}`; `{kind: half/quarter, of, rounding}` | relative counts ("that much", "its power", "the number of ...") and a few joined mana lists; commit cd6cbec |
| duration | 1,783 | ~1,660 | `{kind: until/for, event: end_of_turn/this_turn/next_turn/next_end_step/rest_of_game/leaves_battlefield, which, player}` | "for as long as ..." exile/control conditions; commit d575f7c |
| counter | 1,471 | ~1,440 | `{kind: "+1/+1"/"stun"/..., count}` (count from sibling, words normalized) | "each kind of counter", "those counters", possessives; 42f20cf |
| pt-change | 1,155 | ~1,140 | `{power, toughness}` signed integers, X preserved, `additional` flag | none of the measured shapes; 6292a0b |
| timing | 1,141 | ~1,060 | `activate_only` -> `{timing: sorcery}` / `{frequency: once_each_turn/each_turn}`; `when` -> `{position: beginning, phase, which?, player?}`; `timing`/`window` same | "during" / "as though" tails and opponent-turn windows; abfb029 |
| destination | 1,076 | ~900 | `{zone, controller?, owner?, tapped?, transformed?, library_position?, counter?}`; player recipients typed | long "with mana value ..." tails appended to destination text; 0e3932b |
| pt | 901 | 901 | `{power, toughness}` (ints, `X`, `*`) | none; 851535a |
| modifier | 890 | ~620 | `{kind: stat_filter, stat, op, value}`, keyword, chosen-type, event filter, target predicate, name, counter-on, pay-life | ", except ..." / compound stat expressions / free-form qualifiers; e4688d4 |
| object-phrase | 527 | ~350 | typed spell/card/type/colour/zone/position/choice objects | long target lists and "one that hasn't been chosen" variants; ca17dab |
| colours | 127 compound | 127 | `{kind: all/any/and_or, values: [atoms]}`; single colours remain atoms | none; cbdfe91 |

Invariant: the detector's frozen pre-change snapshot reported `bad_amount` 64,
`bare_modifier` 16, `raw_action` 50. Amount, timing and modifier values are now
objects, so `bad_amount`/`bare_modifier` no longer see prose; the remaining
flags are unchanged classes (conditions/xdef), not stringified family values.
`fragment` remains restricted to unparsed nodes (bare_fragment 0).

FDN after every commit: parse 1,653/1,653; honest 1,572/1,653 (81 unparsed, 45
unique). Tests 277/277. Standard gate on the final tree: parse 20,880/22,217 (94.0%); honest
19,158/22,217 (86.2%, unique 6,328/7,966) — unchanged from the pre-change
baseline.

## Stringy round two (same Standard corpus, current snapshot)

Detector: `swarm/scripts/stringy_audit.py --measure`, snapshot
`Standard_69cae293a709a048_d6d6ad94bfcd62d0.json`, report
`review/stringy_report_4.tsv` / `review/stringiness_4.md`.

| family | v2 residual | v4 residual | closed | new object |
|---|---:|---:|---:|---|
| predicate | 223 | 6 | 217 | `{kind: predicate, verbs: [...], voice?, object?}` |
| target-label (+ *.label) | 269 | 3 | 266 | `{quantifier?, card_type: [{kind,value},...], card_class?, controller?}` |
| relative amount + phrase | 328 + 84 | 117 + 53 | 242 | `{kind: relative, of: {kind/possessor/stat,...}}`; phrase refs (`relative`, `xdef.of`) as event/mana-spent objects |
| window | 32 | 0 | 32 | `{kind: frequency|turn, value/player}` |
| for-each | 98 | 0 | 98 | `{kind: set|counter_set|event_set, items/counter/object}` |
| count | 79 | 23 | 56 | `{kind: count, at_least}` / `{kind: relative, of: {kind: that_many}}` / ints / X |
| cost-phrase | 19 | 4 | 15 | `{kind: cost_phrase, actions: [...], addition_to_other_costs: true}` |
| quoted-ability | 325 | 118 | 207 | `{kind: quoted_ability, sentence: [structured sentence]}`; depth 1, unparsed/fragment quotes stay strings |

Detector totals: structured coverage **17,943 -> 18,138 / 20,880 occurrences**
(85.9 -> **86.9%**; unique 78.7 -> **80.0%**), stringy sentences **1,323 ->
1,124**. Quoted-text parse probe: 87/123 unique quoted abilities parse; the
rest stay strings and are counted above.

Invariant audit on the same snapshot: `bad_amount` **62 -> 5 occurrences**
(remaining: compound computed refs such as "2 plus the number of Lesson cards
in your graveyard", "the power of the chosen creature or card"); `bare_modifier`
**16 -> 0**. `fragment` violations 0; no new string field introduced (structured
objects only).

## Stringy round three (computed refs only)

Detector after commit 77447b2, snapshot
`Standard_69cae293a709a048_c88263d60e922022.json`:

- structured: **18,244/20,880 parsed occurrences = 87.4%**
  (unique 5,865/7,264 = 80.7%); of the full corpus 18,244/22,217 = 82.1%
  (unique 5,865/7,966 = 73.6%)
- stringy: **986 occurrences / 498 texts** (was 1,124 / 560)
- `bad_amount` **5 -> 0**; `bare_modifier` **0**; fragment violations 0

| family | prior residual | now | closed | object |
|---|---:|---:|---:|---|
| amount | 117 | 32 | 85 | `{kind: computed, base, op: plus, of: {kind: count_of, set}}`; `count_of`, `superlative`, `fraction`, `mana_per`, `relative` with structured refs |
| phrase | 53 | 40 | 13 | relative event refs (`that attacked/saddled it/was dealt damage this turn`), `of` choice refs with `single_target` |
| count | 23 | 4 | 19 | late-created `{kind: count, at_least}` / relative `that_many` |
| target | 58 | 2 | 56 | `{kind: target_ref, ref: 'that_ability'|'this_ability'|'that_spell'|'this_spell'}` |

Remaining under the 50-occurrence ledger threshold: amount 32 (compound
manifold/mana-value refs), phrase 40 (free-form relative clauses such as
"that don't share a creature type with the chosen creature they control"),
count 4, target 2. `quoted-ability` residual 118 is untouched: 36 unique
quoted texts fail to parse and are grammar work.

## Quoted-ability interpret gaps (grammar branch fix2b merged)

The grammar worker's `fix2b` commits are merged as `9256d36` (period-separated
quoted abilities, quoted static surfaces). The detector numbers in this section
are the pre-merge master tree; the merged-tree probe is in the grammar section
below.

- `_quoted_ability` now accepts single-quoted hosts, unescapes `\'`, and
  recurses nested quote fields with a depth-2 guard (outer + one nested).
  On fix2b the `Creatures you control have '{T}: Add …'` host parses; on this
  tree that host still falls to grammar `UnexpectedCharacters`, so the detector
  still counts those quotes as strings. Standalone inner single-quoted
  abilities and nested quotes inside double-quoted hosts structure correctly.
- Interpret handlers now close the three probe texts without grammar changes:
  - `can block only <target>` -> `{type: static, effect: {verb: can_block,
    subject, target, only: true}}`
  - `saddles … and crews … as though its power were N greater` ->
    `{verb: saddle_and_crew, objects: [mount, vehicle], as_though: {stat:
    power, comparison: greater, amount: N}}`
  - `a creature dying causes a triggered ability of … to trigger` ->
    `{kind: causes_trigger, cause: {event: dies, subject: {kind: creature}},
    triggered_abilities: [{kind: triggered_ability, source: …}, …]}`

Detector after these changes on the master grammar: structured
**18,268/20,874 parsed = 87.5%** (unique 5,881/7,260 = 81.0%); of corpus
18,268/22,217 = 82.2% (unique 5,881/7,966 = 73.8%); stringy **958 occ / 479
texts**; quoted-ability residual **96**. `bad_amount` and `bare_modifier`
remain 0; fragment violations 0.

Final Standard gate on this tree: parse 20,880/22,217 (94.0%); honest
19,156/22,217 (86.2%, unique 6,326/7,966). FDN unchanged at 1,572/1,653.
Tests 277/277.

## Quoted abilities: sentence periods and static surfaces (grammar branch fix2b)

Merged as `9256d36` on top of the quoted-ability interpret gaps. Probe set: the
unique string-residual quotes in snapshot
`Standard_69cae293a709a048_d6d6ad94bfcd62d0` (68 instances / 42 unique; the
current snapshot reports 36 unique, the split of causes is the same).

Causes fixed (rebased commits `ec150fd`, `9256d36`; branch history `1fee187`, `46fb87d`):

- **Period-separated quoted abilities.** Quoted text keeps its internal
  sentence periods (`segment()` only strips the corpus-level final period), so
  `start: sentence+` rejected every multi-sentence quote (`{T}: Add {U}. Spend
  this mana only to cast a spell…`, `{1}, {T}: Tap target creature. Return ~ to
  its owner's hand`, …). `start: sentence+ (DOT sentence+)*` with `DOT: "."`
  (corpus sentences never carry a period) structured 11 of the 42 and all
  period-split quotes that were previously parse failures at the period.
  Nested check: `Frogs you control have "{T}: Add {G} or {U}. Spend this mana
  only to cast a creature spell."` emits
  `{kind: quoted_ability, sentence: [...]}` instead of a string.
- **Quoted static surfaces.** `storm` was missing from `KEYWORD`; there was no
  possessive `card_target "'s" power and toughness are each equal to …` /
  `base power is equal to …`; and no `can't block or be blocked by`. Additive
  alternatives structured 5 more.

Cost: rules 3,452 -> 3,460 (+8); ABBA 15-word parse 0.613 -> 0.636 s (1.038x,
repeat run no regression) and 0.927 -> 0.930 s (1.003x). Gate: PASS on
`fix2b` (tests 277/277, review, grammar, check_interp, FDN 1,653/1,653,
classic 4,217/4,280, Standard unique delta 0, parser-cost ratio 1.02).

Merged-tree quoted probe: **19/42 unique, 44/68 residual instances structured**
(branch-only, before the interpret gaps merged: 16/42, 29/68). The interpret
gap commit `adb4349` closed three of the probe texts on its own (`can block
only`, `saddles…`, `dying causes a triggered ability`).

Deferred (still strings):

- Trailing-comma fragments, 6 unique (`Whenever this creature attacks, you
  gain 1 life,`): quote capture ends at the comma, so the payload is not a
  sentence — upstream capture/segmentation, not grammar.
- `Creatures you control have '{T}: Add {R}, {G}, or {W}.'`: single-quoted
  hosts are accepted, but a sentence with a quoted ability as its *payload*
  (`have '<ability>'`) has no grammar form — grammar gap, needs a quoted-
  ability sentence alternative rather than the interpret recursion.
- Other remaining 16 unique: trigger/effect tails that parse but interpret
  leaves unparsed (`untap it and you gain 2 life`, `this emblem deals 5 damage
  to any target`, `sacrifice it`), computed/compound refs (`1 plus the number
  of permanents named ~`, `copy of target token you control that entered this
  turn`, `spend this mana only to cast a spell from anywhere other than your
  hand`), and static shapes (`No more than one creature can attack this
  planeswalker each combat`, `becomes a 0/0 Robot artifact creature`) —
  interpret/grammar follow-ups, not closed by this branch.
- Reverted as not paying for itself: `in_zone` `from anywhere other than your
  hand/their hand` (+2 hoisted rules for 1 unique quote); the `that entered
  this turn` modifier parses but its interpret output keeps an unparsed note,
  so it yields no quoted-ability object.

Merged-tree suites: test_output 277/277, test_review PASS, test_grammar_hoist
5/5, test_normalize_map 6/6, test_invariant_check 4/4; test_lists fails with
`AttributeError: 'dict' object has no attribute 'strip'` in
`_struct_cause_trigger` — reproduced identically at base `6667be3`, so
pre-existing master breakage (interpret `i_if_sentence`), not from this merge.

## Human review v3 sheet_01 interpret fixes (W001–W050)

Corpus/segmentation defect: W034 sid `5a1e39044d70` — source sentence is
truncated before its modes ("When this creature enters, choose one"); recorded
here, no interpreter change. W045 X context is upstream ambiguity; no change.

Interpret changes: activated/spree/cost-dash cost items are structured
(pay_mana as a symbol array, tap/target/status, pay_life, sacrifice/discard,
generic action), `to` destination for W005 already carried zone/controller/
transformed, computed stat filters (`value: {kind: computed, of: count_of}`),
compound event verbs (`{kind: event, verbs: [...]}`), card-type disjunctions as
typed arrays, `color_of` for-each mana-spent refs with anaphora, possessive
amount kinds, Plot in the keyword vocabulary, and `states: ["prepared"]`.
Verification: no raw string remains in an activated/spree/cost_dash `cost`;
W005/W025/W040 were already green on the current tree.

Detector after these fixes and the merged grammar, using the calibrated
policy (`review/stringiness_8.md`): structured 17,744/20,882 = 85.0%
(unique 5,630/7,265 = 77.5%); of corpus 17,744/22,217 = 79.9%; stringy
1,515 occ / 746 texts. Raw activated/spree/cost_dash cost strings: 0;
weighted fragment fields (unparsed raw sentences): 1,812.

## Calibrated compound/cost/modifier/anaphora families

Sampled 20 distinct `compound_atom` sites before fixing: 15 are real
alternatives (`artifacts and creatures`, `creature and planeswalker`,
`Mounts and Vehicles`, `instant and/or sorcery cards`, `another untapped
Mount or Vehicle`, etc.); 5 are malformed/capture flags rather than atom
alternatives: `creature type and behold two creatures of`, `creature you
control with power 4 or greater` (stat modifier inside a card_type string),
`noncreature spell and whenever you draw your third card` (clause
concatenation), `both a creature spell and a noncreature spell` (leading
`both a` is not a type), and `spell from exile and whenever a permanent you
control enters from exile` (clause concatenation). The real type lists are
split; the malformed captures remain in the ledger rather than being forced
into a wrong atom split.

Fixes and same-policy deltas (current calibrated policy, snapshot before ->
after):

| family | before | after | change |
|---|---:|---:|---:|
| compound_atom | 126 occ / 55 texts | 0 | -126 |
| raw_cost | 238 occ / 90 texts | 0 | -238 |
| modifier_prose | 150 occ / 83 texts | 0 | -150 |
| anaphora | 142 occ / 68 texts | 59 occ / 30 texts | -83 |

Structured coverage under the current calibrated policy: 17,025/20,882
(81.5%) -> 17,488/20,882 (**83.7%**); unique 5,348/7,265 (73.6%) ->
5,553/7,265 (**76.4%**). Of corpus: 17,488/22,217 = 78.7% (unique
5,553/7,966 = 69.7%). Stringy: 2,272 -> 1,788 occurrences. Note the headline
moved from the earlier 85.0% because the concurrent calibrated policy change
made many pre-existing list paths explicit; the before/after above uses the
same current policy on both snapshots.

## Card-aware interpretation (opt-in `--resolve`) 

Flag: `tools/run.py --resolve [--mentions regex|parser]` and
`tools/snapshot.py build --resolve [--mentions ...]`. Default is unchanged.

Contract: the plan is keyed by the original segmented sentence and resolves the
whole card with `rulecoref`; a rewritten sentence is interpreted only when it
parses and its interpretation has no unparsed marker, otherwise the original
sentence is used (so honest coverage never drops). Snapshot records keep the
original key and add `resolved_text` + `anaphora:[{surface,antecedent,status}]`
under `sentences[sid]`. Fallback rejected rewrites are counted in
`meta.resolve` (`applied`/`reverted`, mentions source, plan cache state).

FDN (260 anaphora cards, 474 anaphor occurrences):
- anaphora markers in output (weighted occurrences): 144 -> **76 (regex)** /
  **74 (parser)**; changed output sentences 76 / 79; honest 1,572/1,653
  unchanged; parse 1,653/1,653.
- rewrite decisions: regex 202 applied / 125 reverted; parser 200 / 94 (parser
  mentions also skip 52 embedded slots vs 0 regex).
- plan runtime: regex cache miss **192.6 s** -> cache hit **0.0 s**; parser plan
  394 s (separate mentions key). Snapshot build with regex cache: 222.5 s cold,
  **4.5 s warm**.
- structured detector on FDN: base 84.2%, regex 83.6%, parser 83.8% (resolution
  replaces some prose targets with concrete NPs; the detector's generic paths
  see the new concrete text, so this small drop is not a lost structure).

Standard sample (162 cards, 520 anaphora-bearing sentences, 329 unique parsed):
- anaphora markers 83 -> 26; 72 rewritten-sentence outputs changed, 33 rewrites
  fell back to the original; parse 487/520 and unparsed 74/520 unchanged.
- structured coverage 256/329 = 77.8% on the sample.
- sample plan 139.8 s (0.86 s/card); full sample parse+interpret both sides
  756 s.

Blast radius (current Standard corpus): **3,870 context-dependent sentences**
(anaphor present and not the first segment) across 3,017 cards; current outputs
carry `ref: anaphora` on **818 sentences / 873 markers / 1,988 weighted
occurrences**. No grammar changes.
