# Engine notes audit — final artifact `a8bd9eb4…`

Artifact `compile_standard.jsonl` SHA `a8bd9eb4062b34c7…`, 21,996 records / 12,981 unique records / 7,738 unique sentence texts / 5,158 cards; card IR `bf9d167d…`. Every record now carries `set_code`. Comparison baseline `cae5db66…` (22,585 rows / 13,362 unique). fdn_notes.md still predates this rebuild, so its top-issue table remains a classification, not a fresh count.

## Summary

| item | metric | final | status |
|---|---|---:|---|
| 1 modal | choose_one groups / nested options / continuations | 259 / 626 / 96 | CLOSED |
| 1 modal | bullet records | 0 | CLOSED |
| 2 duplicates | rows / unique records / duplicate rows | 21,996 / 12,981 / 9,015 | REMAINING |
| 2 duplicates | unique texts / cards | 7,738 / 5,158 | REMAINING |
| 2 duplicates | FDN items / unique name+text / extra printings | 763 / 509 / 254 | REMAINING |
| 3 reminder | parenthetical-only rows / basic rows | 0 / 368 | CLOSED |
| 4 verbs | `deals` / `loses` | 0 / 0 | CLOSED |
| 4 verbs | `deal_damage` / `lose_life` | 536 (401 rec) / 219 (188 rec) | CLOSED |
| 5 player strings | controller string values (rows) | 671 | REMAINING |
| 5 player strings | controller player objects (rows) | 2,996 | INFO |
| 5 player strings | `to:"you"` / `card:"you"` | 0 / 0 | CLOSED |
| 6 can't | records with `verb:"can't"` | 0 | CLOSED |
| 7 X | number-X / any X string sites | 0 / 0 | CLOSED |
| 8 who | who fields (rows) / outside vocabulary | 1,557 / 180 | PARTIAL |
| 9 enters | state forms `enters tapped` / `with` | 0 | CLOSED |
| 9 enters | legitimate trigger `enters` | 1,413 (989 rec) | CLOSED |
| 10 nontoken | nontoken fields / flattened true | 248 / 0 | NO PARSER ACTION |
| 11 copy_of | linked / unresolved | 26 / 6 | PARTIAL (links done, 6 unresolved) |
| 12 set_code | codes / records missing | 21 / 0 | CLOSED |
| 12 unparsed | static_text / parse_fail | 95 / 711 | REMAINING |

Claims against `a8bd9eb4`: **3,831 claims / 2,812 records** — stringy 1,788, content_loss 1,758, invariant 203, anaphora_agreement 69, empty_slot 13. The stringy policy excludes `text` leaves nested under choose_one `options[]`/`continuations[]` (source text by design), which removed 482 claims from the naive 2,270. Vs `cae5db66` (3,552): +279 total, stringy +229, content_loss +57, invariant -6, empty_slot -1; the stringy delta is real output movement (147 new option-output claims now nested under `options[].output`, controller player-object refs, and old shared-controller paths renamed), not modal prose. Content-loss scan: 2,207 lossy rows (was 2,197).

## Reconciliation notes

- **Modal** is now nested and closed: 259 `choose_one` groups across 178 cards, 626 option objects (all parsed), 96 continuations, and 0 standalone bullet records. Option texts: 321 distinct.
- **Controller strings:** 671 is the count of `controller` values that are still strings across all rows (20 distinct forms; 255 on unique records). Top forms: `you` 307, `owner` 121, `your opponents control` 45, `that player controls` 33, `you don't control` 26, `you cast` 24, `they control` 23, `target player` 20, `you own` 15, `target opponent controls` 11, `you don't own` 10, then controller/owner/opponent one-offs. The other 2,996 controller values are already `{kind:player,...}` (`you` 2,711, `an opponent` 285).
- **Who:** 1,557 / 180 outside is the all-rows count; on unique records it is 937 / 104. The earlier report's 110 / 938 used the unique-record definition, so this is the same definition with the small post-rebuild delta (110 -> 104, 938 -> 937), not a change in semantics. Outside forms: Target player 49, target player 20, that player 8, any number of target players 6, a player 6, Its controller 5, defending player 4, That player 4, its controller 2, plus `players`, `that opponent`, `any opponent`, `Another player`, and controller-of forms.
- **X:** 0 sites — no `"X"` string in outputs anywhere, including `{kind:number}`.
- **copy_of:** 26 linked sites across rows (11 unique records), 6 unresolved unique cases (`that_card`, `that_creature`, `that_permanent`; 14 row-sites). The 6 is the unique-case count; linked 26 is the row count.
- **Set_code:** 21 codes, 0 missing — FIN 1,815, FDN 1,628, DFT 1,554, MSH 1,308, LCI 1,149, MKM 1,141, FRA 1,115, ECL 1,090, TDM 1,086, BLB 1,078, TLA 1,056, DSK 1,044, OTJ 1,025, EOE 956, WOE 955, SOS 876, HOB 810, SPM 792, TMT 768, OM1 486, BIG 264.
- **Printings/dedupe:** 21,996 rows collapse to 12,981 unique records (9,015 duplicate rows) and 7,738 unique texts. FDN still 763 items / 509 unique name+text / 254 extra printings (6 max); set_code now lets downstream tools dedupe, but the compile still emits duplicate rows.
- **Basics:** 368 rows now present (Plains 80, Island/Swamp/Mountain/Forest 72 each), 0 parenthetical-only text, 0 parentheses anywhere.

## Closed / remaining

**Closed:** modal nesting (259/626/96, 0 bullets); `deals`/`loses`; `to:"you"`/`card:"you"`; `verb:"can't"`; X strings; `enters tapped`/`enters with`; `copy_of` links; `set_code` coverage; reminder/basics.

**Remaining:** duplicate printings (9,015 duplicate rows; FDN 254 extra printings); 671 controller strings by form; `who` outside vocabulary (180 rows / 104 unique); 6 unresolved `copy_of` cases; 791 unparsed-only records (711 parse_fail + 95 static_text).

**Not parser work:** trigger verbs the engine lacks, ability types (if/loyalty/replacement), keyword Flash, missing effect verbs (enchant/cost_mod/put/scry/counter), equip cost, trigger phases — 226 of the 482 fdn_notes top-issue occurrences; and `nontoken` is all list-valued (builder-side flattening only).
