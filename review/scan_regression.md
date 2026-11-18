# Scan regression check — artifact `7c4a588f…`

Artifact `compile_standard.jsonl` SHA `7c4a588f7be92bc8…`, 22,217 records / 13,357 unique. Counts are on unique records unless stated; detectors are mechanical and stated per row. Previous values are the fixer's reported post-fix figures.

| class | previous | current | delta | sample sid | verdict |
|---|---:|---:|---:|---|---|
| self-reference unmarked (bare self phrase copied to a string, no `this_card`) | 3,126 | **102** | -3,024 | `8eb2966b2aab` | held; small residual (157 on raw rows) |
| duplicate `count` on `put_counter` (`effect.count` + `effect.counter.count`) | 1,212 / 629 texts | **0** | -1,212 | — | held |
| unresolved keyword items (`note:"unresolved"`) | 485 -> 31 | 350 items / 92 values (39 non-plural) | -135 vs 485 | `fbf4a402093c` | partially held: the fixer's 31 was a narrower no-mana keyword-action subset; 92 distinct values still carry the note, mostly plural type placeholders and card names |
| `may` lost (segment starts "you may", no wrapper) | 347 -> 25 | **26** | held | `2892850c01cc` | held |
| `or` structures in card types | 112 -> 28 | 1 `or`-connector; **0** type strings containing " or "; 634 legitimate type lists | -27 | `672aff644a93` | held for the defect (no `or` text remains); 634 lists are structured type sets |
| `the.push`/`each` aggregates: `effect.count` duplicated | 1,212 | 0 | -1,212 | — | held |
| `counter` with "its"/"their" | — | **0** | — | — | held |
| `attacking or blocking` target representation | fixed | 12 records: **10 single string**, 2 list | — | `8ff047a606cc` | **NOT held**: the single-string form still dominates (10/12) |
| cost target text "from your graveyard" with no zone | 0 | **0** | 0 | — | held |
| `mana_value` comparison lacking `total` | — | **14** | — | `ba494a246af2` | residual (new-ish class; total lost) |
| `amount.relation: equal` with no referent | — | **1** | — | `d45717c87d84` | residual |
| keyword values "Surveil"/"Discover" unresolved | — | **29 items / 29 records** | — | `620025850bf9` | residual |

Definitions used: self-reference = sentence contains `this creature/card/permanent/artifact/token/enchantment`, the output contains the phrase as a bare string value, and no `this_card` appears anywhere. Duplicate count = a `put_counter` node with both `count` and `counter.count`. `may` lost = segment starts with "you may" and the output lacks `"may"`, `modal`, `may:true`, unparsed, and quote. `or` structures = `card_type` with an `or` connector or an `" or "` value. `attacking or blocking` forms are classified by whether the output keeps an `" or "` string (single) or a `card_type` list.

Read: the mass fixes held (duplicate count, modality, self-reference, cost zones). Two residuals are actionable: `attacking or blocking` is still a single string in 10/12 records, and 14 `mana_value` comparisons lose `total`. The unresolved-keyword count is threshold-of-definition, not a regression: 350 note-bearing items remain, dominated by plural type placeholders (Saddle 30, Station 27, Surveil 26, Scry 22, Spree 21), with 29 Surveil/Discover items still unresolved.
