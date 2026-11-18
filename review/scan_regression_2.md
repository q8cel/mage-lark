# Scan regression check 2 — artifact `198a60b5…`

Artifact `compile_standard.jsonl` SHA `198a60b56d951c16…`, 22,217 records / 13,357 unique. Same mechanical detectors as `scan_regression.md`; previous column is that file.

## 1. Delta table

| class | scan_regression | now | delta | verdict |
|---|---:|---:|---:|---|
| self-reference unmarked (bare phrase string, no `this_card`) | 102 | **102** | 0 | held |
| duplicate `count` on `put_counter` | 0 | **0** | 0 | held |
| unresolved keyword items | 350 items / 92 values | **321 items / 90 values** | -29 / -2 | improved; Saddle 30, Station 27, Scry 22, Spree 21, Bargain 20 still dominate |
| Surveil/Discover unresolved items | 29 | **0** | -29 | held (fixed) |
| `may` lost | 26 | **26** | 0 | held |
| `card_type` `or` connectors / type strings with " or " | 1 / 0 | **1 / 0** | 0 | held (no `or` text residue); 637 legitimate type lists |
| `effect.count` duplicated | 0 | **0** | 0 | held |
| `counter` with "its"/"their" | 0 | **0** | 0 | held |
| `attacking or blocking` single-string | 10/12 | **1/12** (9 structured status, 2 list, 1 string) | -9 | held (big improvement); sample `8ff047a606cc` is the remaining string |
| cost target "from your graveyard" without zone | 0 | **0** | 0 | held |
| `mana_value` comparison lacking `total` | 14 | **5** | -9 | improved, residual |
| `amount.relation: equal` with no referent | 1 | **1** | 0 | residual |
| self-reference (secondary) rows | 157 | 157 | 0 | unchanged |

The held fixes are stable: duplicate count 0, may wrapper 26, cost zones 0, `or` type strings 0, self-reference residue 102. Two improvements landed: `attacking or blocking` is now a structured status list in 11/12 records (1 string left) and `mana_value`-without-`total` fell 14 -> 5; Surveil/Discover unresolved went 29 -> 0. The unresolved-keyword pool is still 321 items (Saddle/Station/Scry/Spree/Bargain are the top values).

## 2. Anaphora marker recount (one definition each)

Two different things were being counted; they are not comparable.

| definition | previous artifact `45b5f423` | now `198a60b5` |
|---|---:|---:|
| output fields carrying `{ref: anaphora}` or `kind: anaphora` — per row | 896 | **1,545** |
| same, unique sentence texts | 392 | **670** |
| `anaphora` metadata entries — per row (all statuses) | 6,525 | **6,525** |
| metadata entries on unique texts / unique triples | 2,918 / — | **2,918 / 3,700** |
| metadata status: resolved / no-resolution / ambiguous (rows) | 5,680 / 765 / 80 | **5,784 / 658 / 83** |

**6,525 is the metadata-entry row sum**, identical before and after (the `anaphora` list length per record did not change). **955 was an output-marker metric**, not this metadata count; on the output-marker definition the counts actually *rose* (896 -> 1,545 per row; 392 -> 670 unique). So the 955 -> 6,525 jump is a definition change, not a regression: statuses shifted slightly toward resolved (5,680 -> 5,784, no-resolution 765 -> 658), and output ref/kind fields became more numerous. The number to watch is the output-marker count (1,545), not 6,525.

## 3. Claims

Regenerated against `198a60b5` with the artifact-scan content-loss source (`review/certain_defects_artifact.tsv`: 2,175 lossy rows): **3,535 claims / 2,671 records** — stringy 1,562, content_loss 1,681, invariant 209, anaphora_agreement 69, empty_slot 14. Previous `7c4a588f` claims: 3,543 (stringy 1,570, content_loss 1,681); delta -8, entirely stringy.

## 4. Follow-up artifact `2e9019ca…` (link propagation, keyword actions)

- `amount.of` / `count_of.of` nodes with `kind: that_many|this_way`: **41 total, 0 without `link`** (all carry a link).
- `type: static_ability` keyword lines for {Surveil, Scry, Discover, Saddle, Station, Spree, Bargain}: **0**.
- Unresolved keyword items: **201 items / 85 values** (vs 321 / 90 on `198a60b5`); the seven keyword actions above no longer appear. Remaining top values: Teamwork 12, Mobilize 11, Storied 9, Increment 9, Dinosaurs 6, Tiered 6, Earthbend 6, Vehicles 5, Goblins 5, Spiders 5.
- Claims against `2e9019ca`: **3,536** (2,670 records) — stringy 1,561 (-1), content_loss 1,683 (+2), invariant 209, anaphora_agreement 69, empty_slot 14. Total +1 vs `198a60b5` (3,535).

## 5. Follow-up artifact `e35ef8b4…` (link post-pass, keyword actions)

Artifact `e35ef8b4…` (fresh compile `ef223b4a…` + bounded link post-pass: 230 link keys added, 11 prose referents replaced), card IR `5fd3ca9f…`. 22,217 records / 13,357 unique.

- (a) Referent slots (`ref`, `referent`, `antecedent`, `of`) holding one of {this way, that many, the rest, that card, them} as a string: **0**.
- Adjacent phrase strings remain (not referent slots): `card:"the rest"` 85 (all carry `rest:true`), `zone:"them"` 78 (nested `card.zone.zone`), `quantifier:"that many"` 12, `up_to:"that many"` 3, `on:"them"` 7, `controller` "…gained control of this way" 2; `raw:"them"` 87 and `fragment` prose are free-text fallbacks.
- (b) `type: keyword_action` nodes: **149** — Saddle 30, Station 27, Surveil 26, Scry 22, Spree 21, Bargain 20, Discover 3. Records combining a `keyword_action` with any `note:"unresolved"`: **0**.
- Unresolved keyword items overall: **201 items / 85 values** (unchanged from `2e9019ca`); top Teamwork 12, Mobilize 11, Storied 9, Increment 9, Dinosaurs 6, Tiered 6, Earthbend 6, Vehicles 5.
- Claims against `e35ef8b4`: **3,538** (2,671 records) — stringy 1,559 (-2), content_loss 1,687 (+4), invariant 209, anaphora_agreement 69, empty_slot 14. Total +2 vs `2e9019ca` (3,536); artifact-loss scan 2,181 lossy rows (+6).
