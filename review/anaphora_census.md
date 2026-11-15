# Anaphora census (Standard / classic / FDN + current Standard snapshot)

Inventory: `coref/anaphora.py` (`find_anaphors`) — pronouns and contractions (it/its/it's/itself, they/them/their/theirs/themselves), the phrase "the rest", and demonstratives `that/those/these + head noun`. Scalar anaphors ("that many/much") are deliberately excluded by the module. Segments are non-modal `preprocess.segment` sentences; "first segment" is sentence index 0 of the card, "later" is any subsequent sentence. Corpora loaded with the current `setdata.load` name sets.

## 1. Regex census

| corpus | cards | cards with ≥1 anaphor | anaphor sentence occurrences | unique texts | first-segment occ | later-segment occ |
|---|---:|---:|---:|---:|---:|---:|
| Standard | 8,921 | 3,682 (41.3%) | 4,891 | 2,156 (27.1% of 7,966) | 1,021 | 3,870 |
| classic | 2,486 | 648 (26.1%) | 823 | 563 (26.2% of 2,148) | 253 | 570 |
| FDN | 763 | 260 (34.1%) | 337 | 190 (25.0% of 761) | 86 | 251 |

Kinds (anaphor occurrences, Standard): pronoun 5,071, demonstrative 1,263, phrase 191 (a sentence can carry several anaphors).

## 2. Output-side census (Standard snapshot, 7,265 parsed)

| symptom | texts | occurrences | paths |
|---|---:|---:|---:|
| `{ref: anaphora}` | 840 | 1,988 | 54 |
| raw pronoun as a value | 1,033 | 2,389 | 101 |
| `kind: anaphora` | 57 | 128 | 13 |
| `possessive` marker | 74 | 178 | 21 |

Text/occurrence counts overlap across categories (the same site often carries both `ref: anaphora` and a raw pronoun). Top `ref: anaphora` paths by occurrence:

| path | texts | occurrences |
|---|---:|---:|
| `[].effect[].card.card_type` | 204 | 453 |
| `[].effect.card.card_type` | 114 | 360 |
| `[].effect.target.card_type` | 120 | 278 |
| `[].effect.source.card_type` | 77 | 138 |
| `[].effect.on.card_type` | 66 | 136 |
| `[].effect[].target.card_type` | 32 | 101 |
| `[].effect.inner.card.card_type` | 31 | 89 |
| `[].instead.card.card_type` | 12 | 55 |

The symptom is concentrated in `card_type` slots: the interpreter records the pronoun where a typed target belongs.

## 3. Context dependence of later-segment sentences

For each later anaphor sentence, regex-mention inventory (`refs.build(parser=False)`) over the concatenated earlier segments; a candidate is compatible when number matches (when known) and, for demonstratives, the head type is compatible (`refs.type_compatible`). Self-mentions ("this creature") count.

| corpus | later anaphor occurrences | with an earlier compatible mention | share |
|---|---:|---:|---:|
| Standard | 3,870 | 2,766 | **71.5%** |
| classic | 570 | 402 | 70.5% |
| FDN | 251 | 138 | 55.0% |

That 71.5% (2,766 Standard card-sentences) is the population a context-aware resolver can fix with text-local antecedents. The remainder either has no earlier mention (the antecedent is implicit — the card itself, a player, or an event) or needs the structured mention inventory rather than regex heads.

## 4. Cost of resolver-side mentions

Measured per card with regex mentions (`refs.build(parser=False)` + `find_anaphors` + `rulecoref.resolve(rewrite=False)`), 3 reps median per card, 50 anaphora cards and 50 controls from Standard:

| group | median | p95 | max |
|---|---:|---:|---:|
| anaphora cards (n=50) | 0.797 ms | 1.061 ms | 1.348 ms |
| control cards (n=50) | 0.229 ms | 0.663 ms | 0.683 ms |

Full-Standard estimate at the anaphora median: **7.1 s for 8,921 rows** (4.1 s for 5,158 unique names). This excludes the ptree/parse-mention path: there is **no `ptree_1e032c36fb62eaea.json` cache** for the current grammar, so parser mentions would require a full ptree rebuild (corpus-scale parse) before they are usable; regex mentions need no cache.

## What this implies for wiring

Anaphora is not a tail: 41% of Standard cards carry one, 3,870 later-segment occurrences are context-dependent, and 71.5% of those have a text-local compatible antecedent — the resolver's actual addressable population is ~2.8k Standard card-sentences (plus the first-segment cases where the antecedent is the card itself). Output-side, the damage concentrates in `card_type` slots, so the flag should be wired where the interpreter emits `ref: anaphora`/raw pronouns rather than applied as a post-hoc text rewrite. Regex mentions cost ~0.8 ms/card, so a full-Standard pass is seconds and safe to run unconditionally; parser mentions are the expensive path and need a ptree cache (absent for the current grammar), so they should stay behind the flag until that cache exists. The control median (0.23 ms) shows the cost is driven by anaphora cards, not by card count alone.
