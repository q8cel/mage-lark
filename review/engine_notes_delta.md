# Engine notes delta — notes vs artifact `a8bd9eb4…`

Notes: `/home/q8/Documents/engine-notes/fdn_notes.md` (mtime 2026-11-19 21:20) and `parser_issues.md`. Artifact: `compile_standard.jsonl` SHA `a8bd9eb4062b34c7…`, 21,996 rows / 12,981 unique keys / 5,158 cards, card IR `bf9d167d…`. The notes predate the artifact by ~5 hours and still describe the pre-rebuild output.

Parsing: top table = 25 rows / 482 note occurrences. Per-card section = 902 `observed:` lines, 265 distinct strings, 94 templates. Response for the engine agent: `engine-notes/parser_response.md`.

## Top table: stale vs open

| classification | rows | occurrences |
|---|---:|---:|
| fixed in `a8bd9eb4` | 3 | 63 |
| parser-open in `a8bd9eb4` | 4 | 185 |
| engine-side (missing verb/type/keyword) | 18 | 234 |
| **total** | **25** | **482** |

Top-table fixed: modal 16, target set str "you" 33, `verb:"can't"` 14. Parser-open: duplicate printings 116, no executable abilities 47, unmapped player ref 14, `static_text` unparsed 8. Engine-side: the remaining 18 rows (trigger verbs, ability types, Flash, missing verbs, equip cost, trigger phase, nontoken flattening).

## Classification table

Counts are note occurrences: `top` = top-table count, `card` = per-card observed lines. Proof is measured on `a8bd9eb4`.

| observed class | top | card | classification | artifact proof / count |
|---|---:|---:|---|---|
| modal flattened / modal option | 16 | 22 | **fixed** | 259 choose_one groups, 626 options, 96 continuations, 0 bullets |
| target set str "you" | 33 | 37 | **fixed** | `to:"you"` 0, `card:"you"` 0; 2,996 player objects |
| `verb:"can't"` | 14 | 14 | **fixed** | 0 records |
| X strings / token count "X" | — | 2 + 2 | **fixed** | 0 string `"X"` sites |
| as_long condition fragment | — | 1 | **fixed** | 0 unparsed as_long |
| output-entry label wrappers | — | 5 | **fixed** | 0 mixed top-level entries |
| `enters` effect without tapped/counters | — | 1 | **fixed** | 0 state uses; trigger `enters` 1,413 |
| reminder/basics (parser_issues) | — | — | **fixed** | 0 parentheses; 368 basic rows with add_mana |
| deals/loses verb variants (parser_issues) | — | — | **fixed** | 0 / 0 |
| duplicate printings | 116 | 116 | **parser-open** | 9,015 duplicate rows (21,996/12,981); set_code now present + `dedupe_printings=True` exists, but shipped artifact not deduped |
| unparsed `static_text` | 8 | 9 | **parser-open** | 95 unique / 162 rows; 791 unparsed-only records; examples `1cc39663edbc`, `b5d1820965a3`, `2b61d6d79aa2` |
| unparsed modifier fragment | — | 1 | **parser-open** | 29 `modifier_text` rows; examples `4238dc412264`, `d4c4ec509f0a`, `72703be2cf4d` |
| unmapped player ref | 14 | 31 | **parser-open** | 671 controller string values across rows (20 forms; 255 unique); examples `4ebabb7051af`, `d2e2acd5ba09`, `9795afb5b3d2` |
| `who` free string | — | — | **parser-open** | 104 unique / 180 rows outside the 5-value vocabulary; examples `e3008c13033d`, `c95c622218e1`, `a6d4667bb905` |
| long target string | — | 1 | **parser-open** | 20 row-sites (Alesha form); example `bdcdab21434a` |
| anaphora/copy_of raw | — | 12 | **parser-open** | 26 linked; 6 unresolved unique (14 row-sites); examples `0499f86df2d5`, `1a82fae6f2b8` |
| actor list | — | 2 | **parser-open** | 14 sites (`["Its","controller"]`); examples `153cb8680e11`, `b6faa7b4aab9`, `6b5a89bb41c2` |
| quantifier shape `{amount:1,relation:">="}` | — | 1 | **parser-open** | 72 sites; example `37647d76e6e7` |
| no executable abilities | 47 | 47 | **mixed** | 0 empty outputs; 791 unparsed-only records → parser-open for unparsed, engine for vanilla/frame |
| `card_type` link/property shapes | — | 4 | **unverifiable** | some are engine link handling, some anaphora; needs per-card check |
| `output type None` | — | 1 | **unverifiable** | wrapper has no `type` key; builder schema complaint, not demonstrably parser-wrong |
| verb not in engine | 53 | 121 | **engine-side** | enchant 13, cost_mod 11, put 11, scry 11, counter 7 in top table; per-card 121 |
| ability type not executable | 59 | 68 | **engine-side** | if 34, loyalty 15, replacement 10 |
| trigger event verb missing | 39 | 64 | **engine-side** | cast 18, deals 13, gain 8 |
| trigger verb not executable | 39 | 58 | **engine-side** | put_counter 22, create_token 10, draw 7 |
| keyword not in engine set | 20 | 41 | **engine-side** | Flash 20 |
| optionality dropped | — | 37 | **engine-side** | may wrappers exist (1,316); engine executes mandatory |
| effect field dropped | — | 38 | **engine-side** | engine IR limitation |
| cost dropped (equip/kicker/flashback/ward/action) | 9 | 42 | **engine-side** | equip 9 top; wrapper costs dropped builder-side |
| trigger when/phase not executable | 7 | 9 | **engine-side** | engine trigger model |
| duration shape | — | 6 | **engine-side** | durations are structured objects |
| amount not representable | — | 16 | **engine-side** | relative/that-many amounts |
| power/toughness not representable | — | 5 | **engine-side** | `*` P/T |
| add_mana/mana_choice | — | 65 | **engine-side** | parser already emits `{kind:"mana_choice",options:…}`; builder "adds all symbols" |
| nontoken flattened | 8 | 14 | **engine-side** | artifact has 248 list-valued `nontoken`, 0 flattened |
| keyword action Scry | — | 2 | **engine-side** | keyword action support |
| token field dropped | — | 2 | **engine-side** | engine token schema |
| equip cost dropped | 9 | — | **engine-side** | builder drops equip costs |

## Parser-open classes on the artifact (counts)

| class | count | examples |
|---|---:|---|
| duplicate printings | 9,015 duplicate rows; FDN 254 extra printings | Terra `03f0feececb0`, Oko `00cb09292f59` |
| unparsed static_text | 95 unique / 162 rows | `1cc39663edbc`, `b5d1820965a3`, `2b61d6d79aa2` |
| unparsed modifier fragments | 29 rows | `4238dc412264`, `d4c4ec509f0a`, `72703be2cf4d` |
| controller player strings | 671 rows / 255 unique (20 forms) | `4ebabb7051af`, `d2e2acd5ba09`, `9795afb5b3d2` |
| `who` outside vocabulary | 180 rows / 104 unique | `e3008c13033d`, `c95c622218e1`, `a6d4667bb905` |
| long target strings | 20 rows | `bdcdab21434a` |
| copy_of unresolved | 6 unique / 14 rows | `0499f86df2d5`, `1a82fae6f2b8` |
| actor list | 14 | `153cb8680e11`, `b6faa7b4aab9`, `6b5a89bb41c2` |
| quantifier `>=` | 72 | `37647d76e6e7` |
| unparsed-only records | 791 | — |

The notes' 116 duplicate-printings claim is only stale after a rebuild with `setdata.load(..., dedupe_printings=True)`; this artifact still contains the duplicates despite `set_code` on every record.
