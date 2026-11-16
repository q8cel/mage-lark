# Anaphora tradeoff (stricter resolver, rebuilt artifact)

Artifact `compile_standard.jsonl`, SHA-256 `c1b84208…` (22,217 records / 5,153 cards). Pre-fix reference: resolved bindings 4,504, violations 439, pass 90.3%, markers 893 unweighted / 3,654 weighted. No pre-fix copy of the artifact exists, so status/antecedent transitions are measured on the pre-fix resolve-plan cache (2,167 sentence texts; the current rebuild has no new plan cache).

## 1. Marker instances in the current artifact

Markers are `{ref: anaphora}` leaves in the compiled outputs.

| measure | current | pre-fix |
|---|---:|---:|
| unique sentence texts (dedupe by `original_text`, representative output) | 392 | 893 |
| per-card occurrence weight (unique-text markers × corpus occurrences) | 884 | 3,654 |
| raw row count (sum over all 22,217 records) | 896 | — |

The output-side ref markers fell by 501 unweighted (56%) and ~2,770 weighted (76%). The pre-fix "893 unweighted" is numerically closest to the current raw row count (896), so the pre-fix unweighted figure may have counted marker instances across records rather than unique texts; under that reading marker instances are flat (+3) while unique-text markers halved. Both readings are reported rather than picking one silently.

## 2. Status/antecedent trade

| measure | value |
|---|---:|
| resolved bindings, pre-fix -> now | 4,504 -> 3,241 (**-1,263, -28%**) |
| pre-fix plan overlap (sentence texts) | 2,167 |
| resolved -> unresolved/ambiguous in the overlap | 269 |
| unresolved/ambiguous -> resolved in the overlap | 7 |
| resolved -> resolved with a different antecedent | 116 |
| resolved -> resolved with the same antecedent | 2,388 |

On the overlap, 269 of 2,773 pre-fix resolved bindings (9.7%) stopped resolving and 116 of 2,504 still-resolved bindings (4.6%) changed antecedent. The overlap is a plan-cache subset, not a random sample; the global net drop (-1,263) is the authoritative trade figure.

## 3. Remaining violations (150 bindings)

| violation | rows | share of 150 bindings |
|---|---:|---:|
| not_a_mention | 83 | 55% |
| self_binding | 45 | 30% |
| cross_clause | 29 | 19% |
| number_mismatch | 8 | 5% |
| kind_mismatch | 5 | 3% |

170 rows over 150 bindings (some bindings carry two violations). Pass rate: 3,091 / 3,241 = 95.4% (was 90.3%, 439 bad bindings). The precision gain is concentrated in owner/kind/number checks. What is left is mostly antecedent labels that do not correspond to a mention span (83) and self-binding where a target is acted on (45); cataphora (29) is next.

## Read

The trade is 1,263 fewer resolved bindings for 289 fewer provable violations (439 -> 150) and +5.1 points of precision. Marker instances in outputs dropped much more than bindings, which means the stricter resolver also left fewer refs in the compiled output; the remaining 150 are dominated by two families, so further tightening has a clear target (mention-span validation for antecedent labels, then the self-binding clause rule).
