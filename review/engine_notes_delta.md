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

## Questions sent to the engine agent

Verify the channel first: `sha256sum compile_standard.jsonl` must start `a8bd9eb4…`.

(d) **Quantifier shape:** the artifact emits `{amount: 1, relation: ">="}` for "one or more" (72 sites). What shape does the engine consume — that object, `{at_least: 1}`, or something else? The parser adopted `{relation, amount}` from the reviewer's earlier feedback, so we need the schema before changing it.

(e) **Duplicates:** the engine can dedupe itself with `set_code` + `setdata.load(..., dedupe_printings=True)` (FDN 763→509, Standard 8,921→5,412). If it prefers a shipped artifact, we can publish `compile_standard_deduped.jsonl` (same records, winners only, ~5,412 rows) — awaiting which it wants.

## Pull 2026-11-23 — no engine commits since `b5d0c90`

`git -C /home/q8/Documents/mage-ng pull --ff-only` reports **already up to date**. HEAD is still `b5d0c90492556f6e2d8d3cda705d2111918bd74a`; `git log b5d0c90..HEAD` is empty. `notes/parser_issues.md` (334 lines) and `notes/fdn_notes.md` are unchanged, and `tools/build_cards.py` / `crates/mage-ir/src/lib.rs` are unchanged, so none of the previously reported builder-side fixes have landed. Artifact is still `2d8c4bdb…`, so `review/claims.json` was not regenerated. The label-lift work (`f0ef083`, `0c4f6de` in mage-lark) is live-only and not in this artifact; the next rebuild will include it.

### New-note classification (items 13-19, the live-play batch added at `b5d0c90`)

| note | card(s) | artifact field (2d8c4bdb) | side | rows / unique |
|---|---|---|---|---:|
| 13 zone restrictions lost | Ambush Wolf; Burglar Rat | Ambush Wolf: `effect.zone:"graveyard"`, target `card` has no `in_zone`; Burglar Rat: `discard` card has no `in_zone`/effect zone | **builder** (effect.zone never copied) + **parser** (no `in_zone` on discard) | 1,062 / 605 effect.zone-without-card-zone; 426 / 183 discard-no-zone |
| 14 modal flattened | Deadly Plot; Abrade | nested `type:"choose_one"` with 626 options / 96 continuations; no sibling flattening | **fixed** (parser); builder now handles it | 259 groups |
| 15 any target dropped | Burst Lightning | `to:{card_type:{kind:"any"}, player_target:true, quantifier:"any"}` | **fixed parser** | 130 / 76 |
| 16 colour filters lost | Deathmark | `colors:["green","white"]` inside `label`; 917 colour sites total, 2 inside `label` | **builder** (`norm_target_set` pops `label`); parser label lift is live-only | 2 / 2 label cases |
| 17 return destination is destination | Aetherize | `to:{zone:"hand",prep:"to"}` on all 738 return effects; target set carries the battlefield status | **fixed parser**; builder return bug still reads `obj['to']` | 734 / 426 |
| 18 predicate-less target sets | — | 0 empty `card:{}` sets for card-using verbs in this artifact | **fixed parser** | 0 |
| 19 quantifier inconsistency | Feed the Cycle; Explosive Getaway; Coordinated Clobbering; Pox Plague | absent 96 sites; `{at_least,at_most}` 16; `{kind}` 8; `half` 4; `that many` 13; coordinated targets keep quantifier inside `label` | **parser** (normalize/label lift, live-only) + **builder** (`norm_quantifier` rejects these; label popped) | 131 / 88 |

Modal follow-up: Bushwhack is fixed; Chandra/Muldrotha/Strongbox are not bullet modals (their notes are about loyalty/during/choose-one-of-them paths, not modal flattening).

### Builder status after the pull

Still unfixed in `b5d0c90` (verified in code): return destination (`build_cards.py:476-483` reads `obj['to']`), `add_mana.choose_one` (no branch; `Effect.mana` single symbol), top-level `restriction`/`static_ability`/`enters_tapped`/`enters_with` (fall through to unknown), `Effect.zone/from/condition` never populated, `Amount::ThatMany` emits `{that_many:link}` vs `{link}`, `nontoken` lists flattened, `norm_target_set` pops `label`. No `ReturnToBattlefield` verb has been added (`lib.rs` still has only `ReturnToHand`/`ReturnToLibrary`). Remaining parser list: zone emissions for discard/hand, normalize quantifier long tail (`at_most`, `half`, `that many`, `kind`, absent), label lift (live-only until rebuild), and the already-known zero-target/label fields.

## Pull 2026-11-24 — engine HEAD `2c074fd`

`git pull --ff-only` moved the engine `bcd4a0e..2c074fd` (10 commits): `764af49` indestructible/scry, `71e168c` reanimation/scry lands, `10358e8` verb docs, `8aac216` planeswalker loyalty, `0bcb756` attack planeswalkers, `35a14a3` Raid trigger conditions, `adefbb9` auras/equipment, `59951a2` cost modifiers, `0c0f1c4` "if you do" branches, `2c074fd` if-condition contract docs. `notes/parser_issues.md` gained the if-condition contract and updated the engine-side table; `notes/fdn_notes.md` was regenerated (694 lines changed).

### Builder fixes (diff `bcd4a0e..2c074fd`)

| outstanding item | status |
|---|---|
| return destination read | **fixed**: reads `eff.get('to')`; maps `battlefield`→`return_to_battlefield` (+`tapped`), library→`return_to_library` (`build_cards.py` ~496-510) |
| top-level `enters_tapped`/`enters_with` | **fixed** per notes table |
| top-level `restriction`/`static_ability` | still fall through to unknown |
| general `Effect.condition` | `if` conditions + Raid/unless populated via new `norm_condition`; arbitrary effect conditions still not |
| `add_mana.choose_one` | fixed earlier; notes confirm `mana_choice` |
| `Amount::ThatMany` | fixed earlier (`{"link":…}`) |
| `set_code` | **fixed**: `Card.set_code` |
| `nontoken` flattening | still flattened |
| `label` | still popped (`norm_target_set`) |
| controller `relation`/`of`, target `link` | still not modelled |

### New IR / verbs

`Verb::{Scry, Attach, CostMod}`; `Condition::PreviousHappened`; `Effect.raised_cost`/`tapped`; `Ability::Loyalty`. New supported verbs/abilities: scry, enchant/attach, cost_mod, loyalty, "if you do" branches, Raid trigger conditions, auras/equipment.

### New parser-side notes vs artifact `4ea84d68`

| new note | artifact count (4ea84d68) | classification |
|---|---:|---|
| `if` `event_ref` skipped (5) | 421 `event_ref` conditions, shape `{actor,anaphor:true,kind,event_ref,polarity}` | already-fixed shape (builder handles `anaphor:true`); 5 residual are conditions outside the `if` branch → builder-side |
| `if` `spell_state kicked` (5) | 75 `spell_state` conditions | builder/engine: needs kicker model; notes say parser should keep emitting |
| "if it's a <type> card" (32 `if` remaining) | `if` types 1,050; no type-of-target condition shape yet | **parser-side**: emit `{"kind":"type","of":"target","value":...}` |
| `may` flag for optional actions | 1,316 `verb:"may"` wrappers | parser emits may; builder unwraps by design → engine decision (engine-side) |
| `restrict` verb (16) | 306 `verb:"restrict"` sites / 314 restriction types | builder-side (top-level restriction unhandled) |
| `put` verb (12) | 888 `verb:"put"` | builder-side (engine lacks verb) |
| `surveil`/`gain_quote`/`become`/`pay` (5+5+6+7) | 176/136/300/164 sites | builder-side (engine verbs) |
| effect field `action`/`targets`/`direction` dropped (11+10+10) | 242/124/215 sites | builder-side normalization gaps |
| `indestructible`/`double strike` keyword (9+5) | 166 indestructible keyword values; double strike absent from set | builder-side keyword set |
| anaphora raw copy_of (7) | 26 raw no-link rows / 11 cards / 3 shapes | parser-side residual tail (already counted) |
| `amount {kind:"x"}` (7) | 809 `kind:"x"` | engine-side (explicit X, no value) |
| `nontoken` flattened (10) | 428 list-valued sites | builder-side flattening |
| no executable abilities (33) | 30 static_text sites / 717 unparsed-only | parser unparsed + frame-only engine mix |
| duplicate printings (116) | 9,015 duplicate rows | parser/compiler dedupe |

Nothing in the new batch is a regression in the tails: copy_of/who/controller/Drakuseth/modifier/static counts are unchanged from `4ea84d68`, and the new `if` contract is the main parser-side request (`type`/`kicked` shapes, `may` flag).
