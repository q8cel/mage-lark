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
