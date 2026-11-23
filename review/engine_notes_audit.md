# Engine notes audit — artifact `63650de6…`

Artifact `compile_standard.jsonl` SHA `63650de69faeab2c…`, 21,996 rows / 12,981 unique records / 7,738 unique texts / 5,158 cards; card IR `f1f4ad8a…`. FDN honest 1,601/1,673 = 95.7%, classic 94.1%. This rebuild includes zone/quantifier semantics, typed modal continuations, label lift, and the Devout changes.

## Claims

**4,180 claims / 2,924 records** — stringy 2,182, content_loss 1,713, invariant 203, anaphora_agreement 69, empty_slot 13. Content-loss scan: 2,154 lossy rows. Previous artifact `2d8c4bdb`: 4,101 claims (stringy 2,062, content_loss 1,754).

## Summary

| item | metric | final | status |
|---|---|---:|---|
| 1 modal | groups / options / continuations / typed effect clauses | 259 / 626 / 96 / 673 | CLOSED |
| 2 duplicates | rows / unique / duplicate rows | 21,996 / 12,981 / 9,015 | REMAINING |
| 3 reminder | parenthetical-only / basic rows | 0 / 368 | CLOSED |
| 4 verbs | `deals` / `loses` / `can't` | 0 / 0 / 0 | CLOSED |
| 5 players | controller bare strings; player/controller objects; unresolved | 0; 3,753 / 3,564; 244 | CLOSED |
| 5 players | `who` objects / five-value strings / outside strings | 180 / 1,377 / 0 | PARTIAL |
| 6 X | X string sites | 0 | CLOSED |
| 7 copy_of | unresolved rows / unique / no-link | 40 / 17 / 6 | PARTIAL |
| 8 add_mana | choose_one / mana_choice | 227 / 0 | CLOSED (parser) |
| 9 targets | any-target / long prose / malformed long | 132 / 0 / 2 | CLOSED |
| 10 actor | actor lists | 0 | CLOSED |
| 11 zone | discard effects missing zone | 0 | CLOSED |
| 12 quantifier | missing effect-target / bad dict shapes | 0 / 0 | CLOSED |
| 13 colours | top-level / label sites | 919 / 2 | PARTIAL |
| 14 static | static_text unique / rows | 21 / 30 | PARTIAL |
| 15 set_code | codes / missing | 21 / 0 | CLOSED |

## Detail

- **Zone/discard:** 0 discard effects lack a zone (`Burglar Rat` now has `card.zone:{zone:"hand"}`); `Ambush Wolf` has both `effect.zone:"graveyard"` and `card.zone:{prep:"from",zone:"graveyard"}`. There are 1,809 `effect.zone` sites, of which 554 have no card zone — those are destination-style zones (library/hand) rather than missing filters.
- **Quantifier:** 0 target-taking effects lack a quantifier and 0 use unsupported dict shapes. Distribution: `target` 1,180, `a` 1,002, int 111, `all` 206, `{up_to}` 301, `{at_least}` 2, `any` 18, `that many` 13, `half` 4, `an` 56, `each` 30, `any number of` 30, `another` 3.
- **Modal:** 259 groups, 626 options, 96 continuations, and 673 recursively typed effect clauses; all 96 continuation entries are `type:"effect"`.
- **Any target:** 132 sites use `card_type:{kind:"any"}` + `player_target:true` + `quantifier:"any"`.
- **Colours:** 919 top-level colour sites; 2 remain inside `label` (Deathmark-style coordinated targets); the label lift is now in the compiler.
- **copy_of:** 40 unresolved rows / 17 unique; 6 unique cases carry `status:"unresolved"` with no fabricated link.
- **Players:** 0 controller strings; 3,753 `{kind:"player",ref}` objects overall, 3,564 controller refs, 244 `unresolved:true`; `who` is 180 objects + 1,377 five-value strings, 0 outside-vocabulary strings.
- **Static/unparsed:** 21 unique / 30 rows `static_text`, 25 `modifier_text` rows remain.
- **Duplicates:** unchanged (9,015 duplicate rows; FDN 254 extra printings); `set_code` still 21 codes / 0 missing.
- **Residuals:** 2 malformed long target strings (`38f9ce3ec91d`, "each of up to two other target s"); actor lists now 0.

Builder-side items from `engine_notes_delta.md` are unchanged (add_mana choose_one branch, return destination read, top-level ability types, Effect.zone/condition population, ThatMany wire shape, nontoken flattening, label handling). The parser side for zone/quantifier/label is now in this artifact; the engine should rebuild `cards/fdn.jsonl` against `63650de6…`.
