# Engine notes audit — post-rebuild `cae5db66…`

Artifact `compile_standard.jsonl` SHA `cae5db665e610b86…`, 22,585 rows / 13,362 unique records / 7,966 unique sentence texts / 5,158 cards; fresh compile `0203e399…` + post-pass; card IR `b9a3c973…`. Comparison baseline: `e35ef8b4…` (22,217 rows / 13,357 unique). Occurrences are on unique records unless marked rows. fdn_notes.md predates this rebuild (mtime 21:20 vs artifact 23:24), so its top-issue table is a static classification, not a fresh count.

## Summary

| # | metric | before | after | status |
|---|---|---:|---:|---|
| 1 | bullet records / source option bullets | 0 / 427 | 0 / 427 | REMAINING |
| 1 | choose-one rows / cards / missing | 137 / 82 / 131 | 137 / 82 / 131 | REMAINING |
| 1 | choose verb/object one rows | 73 | 73 | REMAINING |
| 2 | rows / unique records / duplicate rows | 22,217 / 13,357 / 8,860 | 22,585 / 13,362 / 9,223 | REMAINING (worse) |
| 2 | FDN items / unique name+text / extra printings | 763 / 509 / 254 | 763 / 509 / 254 | REMAINING |
| 3 | parenthetical-only rows / basic rows | 0 / 0 | 0 / 368 | CLOSED |
| 4 | `deals` / `loses` occurrences | 87 / 3 | 0 / 0 | CLOSED |
| 4 | `deal_damage` / `lose_life` occurrences | 451 / 217 | 538 / 220 | CLOSED |
| 5 | player-string slots total | 2,039 | 2,033 | PARTIAL |
| 5 | `to:"you"` / `card:"you"` | 6 / 0 | 0 / 0 | CLOSED |
| 5 | controller "you control" / "an opponent" | 1,563 / 203 | 1,563 / 203 | REMAINING (strings) |
| 6 | `verb: "can't"` records | 192 | 0 | CLOSED |
| 7 | `{kind:number,value:X}` sites | 33 | 0 | CLOSED |
| 7 | other X-as-string sites / records | 211 / 185 | 126 / 113 | PARTIAL |
| 8 | `who` outside 5-value vocabulary | 180 | 110 | PARTIAL |
| 9 | `verb: enters` state forms (tapped/with) | 318 | 0 | CLOSED |
| 9 | trigger `enters` occurrences | 1,443 | 1,443 | CLOSED (legitimate) |
| 10 | `nontoken` fields / flattened true | 189 / 0 | 249 / 0 | NO PARSER ACTION (all lists) |
| 11 | `copy_of` raw without link | 11 | 11 | REMAINING |
| 11 | anaphor/raw target without link | 0 | 0 | CLOSED |
| 12 | unparsed static_text / parse_fail | 95 / 711 | 95 / 711 | REMAINING |
| 12 | unparsed-only records / empty outputs | 797 / 0 | 797 / 0 | REMAINING |

Claims against `cae5db66`: **3,552 claims / 2,680 records** — stringy 1,559, content_loss 1,701, invariant 209, anaphora_agreement 69, empty_slot 14. Vs `e35ef8b4` (3,538): +14 total, entirely content_loss (+14); stringy unchanged. Artifact-loss scan: 2,197 lossy rows (was 2,181).

## Closed / zero

- **Verb variants:** `deals` 87 -> 0 and `loses` 3 -> 0; canonical `deal_damage` 538 / `lose_life` 220. Closed.
- **`verb: "can't"`:** 192 -> 0 records. Closed.
- **X as number:** `{kind:"number", value:"X"}` 33 -> 0. Closed for the engine-facing shape; 126 other X strings remain (see below).
- **Enters state rules:** `enters tapped` 233 -> 0, `enters with` 85 -> 0; only the legitimate trigger use remains (1,443). Closed.
- **Player slots:** `to:"you"` 6 -> 0, `card:"you"` 0 -> 0. Closed for the requested slots; controller strings remain.
- **Reminder/basics:** parenthetical-only rows 0; basic land rows 0 -> 368 with no parentheses; FDN basics were 20 items / 5 parenthetical texts. Closed in the artifact.
- **Anaphor/raw targets without link:** 0 -> 0. Closed.
- **`nontoken` flattening:** 249 fields, all list-valued, 0 flattened — parser output was never the problem; builder-side only.

## Remaining (with counts)

- **Modal:** 0 bullet records, 131 of 213 choose-one cards absent entirely, 427 source options absent, 73 choose shells, 137 rows / 82 cards present. Unchanged by the rebuild.
- **Duplicate printings:** 9,223 duplicate rows (up from 8,860); FDN 763 items / 509 unique name+text / 254 extra printings, max 6. `setdata` dedupe has not landed.
- **Player controller strings:** 2,033 player-string slots; "you control" 1,563 (1,273 records), "an opponent" 203 (163; value normalized from "an opponent controls"), "you" 153, "you don't control" 20, "target player" 13. Still strings, not `{kind:player,...}`.
- **Other X strings:** 126 sites / 113 records — `count` 76, `value` 21, `up_to` 17, `quantifier` 7, `modifier` 3, `times` 2. Examples `1c51bdf08917`, `cf436b946804`, `b3c95992ac36`.
- **`who` outside vocabulary:** 110 / 938, 15 distinct values — Target player 49, target player 20, that player 8, any number of target players 6, a player 6, Its controller 5, defending player 4, That player 4, its controller 2, plus one-offs (`players`, `that opponent`, `any opponent`, `Another player`, controller-of forms). Examples `e3008c13033d`, `c95c622218e1`, `1b4d4e7c2010`.
- **`copy_of` raw without link:** 11, unchanged (`8f7477a51f62` raw "them", `d58320563b2b` raw "it", `09b961ef7f20`).
- **Unparsed:** 95 `static_text` + 711 `parse_fail` occurrences, 797 unparsed-only records, 0 empty outputs — unchanged.

## fdn_notes top issues: parser vs engine (classification, 482 note occurrences)

The table still sums to 482: **256 parser-side**, **226 engine-side**. Post-rebuild artifact verification: can't now 0 (was 14 notes), `to/card:"you"` now 0 (was 33 target-you notes), modal still 0 bullets (16 notes relevant), duplicates now 9,223 rows (116 notes), nontoken lists intact (8 notes are builder-side), unparsed still 797 records (8 notes).

| count | category | observed | side |
|---:|---|---|---|
| 116 | adapted | duplicate records from printings | parser (setdata dedupe) |
| 47 | skipped | no executable abilities (empty/frame) | parser (empty=0, unparsed-only=797) |
| 34 | skipped | ability type 'if' | engine |
| 33 | gap | target set str "you" | parser (artifact: to/card "you" 0, but controller strings remain) |
| 22 | skipped | trigger verb put_counter | engine |
| 20 | gap | keyword 'Flash' not in engine set | engine |
| 18 | skipped | trigger event 'cast' | engine |
| 16 | skipped | modal option of choose-one | parser |
| 15 | skipped | ability type 'loyalty' | engine |
| 14 | gap | unmapped player ref 'an opponent controls' | parser (value now "an opponent", still a string) |
| 14 | skipped | verb "can't" | parser (closed) |
| 13 | skipped | verb 'enchant' | engine |
| 13 | skipped | trigger event 'deals' | engine |
| 11 | skipped | verb 'cost_mod' | engine |
| 11 | skipped | verb 'put' | engine |
| 11 | skipped | verb 'scry' | engine |
| 10 | skipped | ability type 'replacement' | engine |
| 10 | skipped | trigger create_token | engine |
| 9 | adapted | equip cost dropped | engine |
| 8 | skipped | unparsed static_text | parser |
| 8 | skipped | trigger event 'gain' | engine |
| 8 | adapted | nontoken flattened to true | builder-side (artifact lists intact) |
| 7 | skipped | verb 'counter' | engine |
| 7 | skipped | trigger event 'draw' | engine |
| 7 | skipped | trigger when phase | engine |

**Not parser work (do not chase):** trigger verbs (put_counter 22, cast 18, deals 13, create_token 10, gain 8, draw 7, attack/phase), ability types if 34 / loyalty 15 / replacement 10, keyword Flash 20, missing effect verbs enchant 13 / cost_mod 11 / put 11 / scry 11 / counter 7, equip cost 9. Parser-side work that remains: modal retention/nesting, duplicate-printings dedupe, controller player strings, residual X strings, `who` normalization, `copy_of` links, and the 797 unparsed records.
