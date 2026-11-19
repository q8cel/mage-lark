# Engine notes audit — artifact `e35ef8b4…`

Artifact `compile_standard.jsonl` SHA `e35ef8b411a6e0fa…`, 22,217 rows / 13,357 unique records / 7,966 unique sentence texts; card IR `5fd3ca9f…`. Occurrence counts are on unique records unless the row says rows (modal, duplicates, reminder). Sources: `engine-notes/parser_issues.md`, `engine-notes/fdn_notes.md`, `setdata.load('data/FDN.json')`, `data/Standard.json`.

## Summary

| # | metric | count | note |
|---|---|---:|---|
| 1 | bullet records / source option bullets | 0 / 427 | options dropped outright, not just un-nested |
| 1 | choose-one cards present / missing | 82 / 131 | of 213 source cards |
| 1 | choose-one rows / unique texts | 137 / 41 | 73 carry `verb: choose, object: one` |
| 2 | artifact rows / unique records / duplicate rows | 22,217 / 13,357 / 8,860 | |
| 2 | FDN items / unique name+text / extra printings | 763 / 509 / 254 | max 6 printings |
| 3 | parenthetical-only rows / basic rows | 0 / 0 | artifact has no parentheses; FDN basics are 20 items / 5 texts |
| 4 | `deals` / `deal_damage` | 87 / 451 | 80 / 339 records |
| 4 | `loses` / `lose_life` | 3 / 217 | 3 / 183 records |
| 5 | player-string slots | 2,039 | 19 groups; `to:"you"` 6, `card:"you"` 0 |
| 6 | `verb: "can't"` records | 192 | 151 unique texts |
| 7 | X-as-string sites | 244 | 33 `{kind:number,value:X}`, 185 records |
| 8 | `who` outside 5-value vocabulary | 180 / 938 | 17 values |
| 9 | `verb: enters` occurrences | 1,761 | 233 tapped, 85 with, 1,443 trigger |
| 10 | `nontoken` fields | 189 | all list-valued, 0 flattened |
| 11 | `copy_of` raw without link | 11 | anaphor/raw without link 0 |
| 12 | fdn_notes top issues parser-side / engine-side | 256 / 226 of 482 | 25 rows |

## Detail

1. **Modal.** No artifact text starts with `•`; all modal options are gone (not merely flattened). 137 rows / 41 unique texts / 82 cards still contain "choose one", 73 of them with the useless `{"verb":"choose","object":"one"}` shell. The Standard source has 213 unique choose-one texts with 427 `•` options; 131 cards are missing entirely (e.g. Abrade, Aerith Rescue Mission, Agate Assault). Examples: `012686e0f57c`, `06adf03342d3`, `079eb7c6c978`.
2. **Duplicate printings.** 22,217 rows collapse to 13,357 unique records (8,860 duplicate rows) and 7,966 unique texts. FDN: 763 items, 509 unique name+text pairs, 506 unique texts, 254 extra printings; top counts 6 (Herald of Eternal Dawn, Bloodthirsty Conqueror, Twinflame Tyrant), 5 (Exemplar of Light, Kaito, Cunning Infiltrator). Duplicate sids are shared per sentence hash, e.g. Terra/Oko/Dion/… (`03f0feececb0`, `0b384b11cfdb`, `23eb984c72fb`).
3. **Reminder text.** The artifact contains no parentheses at all and no basic land rows, so parenthetical-only text is already 0 there. In `setdata.load('data/FDN.json')` the basics are 20 items with 5 unique fully-parenthetical texts (e.g. `({T}: Add {W}.)`); the builder substitutes frames, so this is a source/builder issue, not a live artifact defect.
4. **Verb variants.** `deals` 87 occurrences / 80 records vs `deal_damage` 451 / 339; `loses` 3 / 3 vs `lose_life` 217 / 183. Both spellings coexist, so the canonicalisation has not happened. Examples: deals `4382fe970c98`, deal_damage `4ebabb7051af`, loses `5bd8f6c8aa2f`, lose_life `d8bc7f431969`.
5. **Player strings in card-set slots.** 2,039 slots carry player text. Controller strings dominate: "you control" 1,563 (1,273 records), "an opponent controls" 203 (163), "you" 153 (144), "you don't control" 20, "that player controls" 15, "target player" 13. `to:"you"` 6 records; `card:"you"` 0. Examples: `91a4f4845615` (you control), `09141fe24add` (an opponent controls), `a1ee7564c3a7` (to:you).
6. **`verb: "can't"`.** 192 records / 151 unique texts carry it as an effect verb (e.g. `dd22519ddb95` "your opponents can't cast spells…", `299449f86f17` "Target creature can't block", `e3008c13033d`).
7. **X-as-string.** 33 sites are `{kind:"number", value:"X"}`; 244 string sites total, 185 records: `token.count` 67, `change.power` 51, `change.toughness` 34, `quantifier.up_to` 17, `quantifier` 7, `amount.count` (kind mana) 9, `stat_filter.value` 20. Examples: `fe78da50972d`, `03c3a74d477b`, `e514e2d9b2b8`.
8. **`who`.** 938 values; 180 are outside the fixed {you, opponent, an opponent, each opponent, each player} vocabulary (case-insensitive). Top outside: Target player 49, Target opponent 40, target opponent 30, target player 20, that player 8, any number of target players 6, a player 6, Its controller 5, defending player 4, That player 4, its controller 2, then one-offs. Examples: `5f2f60c76549`, `e3008c13033d`, `1b4d4e7c2010`.
9. **`enters`.** 1,761 `verb: enters` occurrences in 1,075 records: 233 `tapped`, 85 `with`, 1,443 trigger uses ("When this creature enters"). The state-rule uses should be a dedicated type; the trigger uses are legitimate. Examples: `7621cf5dc729`, `f2e4f3ef9052`, `0c2bf062d101`.
10. **`nontoken`.** 189 fields, all list-valued: `["nonland"]` 137, `["nontoken"]` 43, `["noncreature"]` 22, plus mixed/other lists. No `true` flattening in the artifact — the flattening happens builder-side, so parser output is fine; engine should consume lists. Examples: `d9fe4fe165b9`, `2d2a06898ef3`, `09141fe24add`.
11. **`copy_of` / anaphora.** 11 `copy_of` objects still contain `{raw:"it"|"them", ref:"anaphora"}` with no `link` (e.g. `8f7477a51f62` raw "them", `d58320563b2b` raw "it", `09b961ef7f20`). Anaphor/raw targets without a link: 0.
12. **fdn_notes cross-check.** The 25 top-issue rows total 482 note occurrences: **256 parser-side**, **226 engine-side** (see table below). Artifact cross-checks agree where measurable: 0 bullet records vs 16 modal notes; 8,860 duplicate rows vs 116 duplicate notes; 6 `to:"you"` + 0 `card:"you"` vs 33 target-you notes; 192 can't records vs 14 notes; 189 nontoken records vs 8 notes; 95 `static_text` + 711 `parse_fail` unparsed occurrences vs 8 unparsed notes; 797 unparsed-only records and 0 empty outputs vs 47 no-executable-ability notes (mostly parser-side frames/unparsed).

### fdn_notes top issues: parser vs engine

| count | category | observed | side |
|---:|---|---|---|
| 116 | adapted | duplicate records from printings | parser (setdata dedupe) |
| 47 | skipped | no executable abilities (empty/frame) | parser (empty=0, unparsed-only=797; vanilla frames are engine) |
| 34 | skipped | ability type 'if' | engine (type unsupported) |
| 33 | gap | target set str "you" | parser |
| 22 | skipped | trigger verb not executable (put_counter) | engine |
| 20 | gap | keyword 'Flash' not in engine set | engine (keyword table) |
| 18 | skipped | trigger event 'cast' | engine |
| 16 | skipped | modal option of choose-one | parser |
| 15 | skipped | ability type 'loyalty' | engine |
| 14 | gap | unmapped player ref 'an opponent controls' | parser |
| 14 | skipped | verb "can't" | parser (shape) |
| 13 | skipped | verb 'enchant' | engine |
| 13 | skipped | trigger event 'deals' | engine |
| 11 | skipped | verb 'cost_mod' | engine |
| 11 | skipped | verb 'put' | engine |
| 11 | skipped | verb 'scry' | engine |
| 10 | skipped | ability type 'replacement' | engine |
| 10 | skipped | trigger create_token | engine |
| 9 | adapted | equip cost dropped | engine (builder) |
| 8 | skipped | unparsed static_text | parser |
| 8 | skipped | trigger event 'gain' | engine |
| 8 | adapted | nontoken ['nonland'] flattened to true | parser output fine; flattening is builder-side |
| 7 | skipped | verb 'counter' | engine |
| 7 | skipped | trigger event 'draw' | engine |
| 7 | skipped | trigger when phase | engine |

**Not parser work (do not chase):** trigger verbs the engine lacks (put_counter 22, cast 18, deals 13, create_token 10, gain 8, draw 7, attack/phase), ability types if 34 / loyalty 15 / replacement 10, missing keyword Flash 20, and missing effect verbs enchant 13 / cost_mod 11 / put 11 / scry 11 / counter 7 / equip-cost dropping 9. Parser-side actionable set: duplicate printings, modal nesting/retention, player refs and `to:"you"` slots, `can't` shape, nontoken lists (keep them), and the 95 static_text / 711 parse_fail unparsed cases.
