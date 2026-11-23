# Engine notes audit — artifact `4ea84d68…`

Artifact `compile_standard.jsonl` SHA `4ea84d687423cb1a…`, 21,996 rows / 12,981 unique records / 7,738 unique texts / 5,158 cards; card IR `2e3a991c…`. Gates: FDN 1,673/1,673 parse, honest 95.7%; classic 94.1%. This rebuild includes the copy_of/who/controller tails (`cdfbb9c`) and the review TSV (`203e9e3`).

## Claims

**4,159 claims / 2,908 records** — stringy 2,159, content_loss 1,715, invariant 203, anaphora_agreement 69, empty_slot 13. Content-loss scan: 2,156 lossy rows. Previous artifact `63650de6`: 4,180 claims / 2,924 records (stringy 2,182, content_loss 1,713).

## Summary

| item | metric | final | status |
|---|---|---:|---|
| 1 modal | groups / options / continuations / typed effect clauses | 259 / 626 / 96 / 673 | CLOSED |
| 2 duplicates | rows / unique / duplicate rows | 21,996 / 12,981 / 9,015 | REMAINING |
| 3 reminder | parenthetical-only / basic rows | 0 / 368 | CLOSED |
| 4 verbs | `deals` / `loses` / `can't` | 0 / 0 / 0 | CLOSED |
| 5 controller | bare strings / objects / mapped / residual | 0 / 3,759 / 3,577 / 182 | PARTIAL |
| 5 who | objects / aliasable / unmappable | 180 / 166 / 14 | PARTIAL |
| 6 X | X string sites | 0 | CLOSED |
| 7 copy_of | unresolved rows / cards / shapes | 40 / 17 / 6 | PARTIAL |
| 8 add_mana | choose_one / mana_choice | 227 / 0 | CLOSED (parser) |
| 9 targets | any-target / long prose / malformed strings | 132 / 0 / 2 | PARTIAL |
| 10 actor | actor lists | 0 | CLOSED |
| 11 zone | discard effects missing zone | 0 | CLOSED |
| 12 quantifier | missing effect-target / bad dict shapes | 0 / 0 | CLOSED |
| 13 colours | top-level / label sites | 919 / 2 | PARTIAL |
| 14 static | static_text sites / unique shapes | 30 / 12 | PARTIAL |
| 15 modifier | modifier_text sites / unique | 25 / 6 | PARTIAL |
| 16 set_code | codes / missing | 21 / 0 | CLOSED |

## Tail detail

- **copy_of:** 40 unresolved rows / 17 cards / 6 shapes. The raw no-link tail is 26 rows across 11 cards and 3 shapes, all `{kind:"anaphora", raw, ref, status:"unresolved"}` (raw `it`, raw `them` ×2); the other unresolved shapes carry `this_that`/`anaphor` with 6 having links.
- **who:** 180 `{kind:"player",ref,selection}` objects, of which 166 are aliasable and 14 are not (`a player` 13, `another player` 1); 1,377 five-value strings remain (you/each opponent/an opponent/each player/opponent), all aliasable.
- **controller:** 0 bare strings; 3,759 player/controller objects, 3,626 `kind:player` refs, 3,577 mapped sites. Residual 182 sites: `owner` 121, `you` 24, `they` 23, `their owners` 5, `her owner` 4, `controlled by different players` 3, `those players` 2.
- **Malformed targets:** 2 rows / 1 unique sid (`38f9ce3ec91d`, "each of up to two other target s"); the long prose target class is 0.
- **static_text:** 30 sites / 12 unique shapes — top: `you control` 5, `You control enchanted creature` 3, `you control without flying` 3.
- **modifier_text:** 25 sites / 6 unique shapes — top: `you've discarded this turn` 5, `you've cast this turn` 2.
- **Other:** modal 259/626/96/673; quantifier 0 missing / 0 bad shapes (target 1,180, a 1,002, int 111, all 206, up_to 301, at_least 2); any-target 132; colours 919 top-level + 2 label; actor 0; duplicates 9,015; set_code 21/0.

Builder-side items from `engine_notes_delta.md` remain pending in the engine; no builder commit has changed them as of engine HEAD `bcd4a0e` (the pull also added engine-side any-target/colour/mana/zone consumers, but not the parser-contract bugs listed there).
