# Human review v6 — analysis

Pack `swarm/work/human_review_v6` (artifact SHA `5d074f72…`, claims SHA `ddba34a7…`). Labels exported in `labels.tsv`: **68 ok / 19 bug / 13 legit**. The prompt's 67/20/13 is one item off; the analysis follows the file (the same 19 ids appear in `labels.jsonl`).

## 1. Score

`swarm/scripts/human_audit_eval.py --pack swarm/work/human_review_v6`:

- labelled 100 / 100; ledger verdicts: none (parser-grade pack).
- weighted population wrong rate: **18.9%** (95% CI 11.2%–26.6% design-based normal; 12.4%–27.7% weighted Wilson, n_eff=100).
- strata (labelled / raw bug rate): size 1: 63 / 19.0%; size 2–4: 19 / 5.3%; size 5+: 18 / 33.3%.
- v5 substitution axis: 8 labelled, 3 bugs, 37.5% weighted; no-substitution 92, 16 bugs, 17.3%.
- Denominator: clean non-keyword per-card records = **9,499** (11,648 clean − 2,149 keyword-only), drawn from 13,357 unique records (8,860 exact duplicates removed).

## 2. Bug clusters (19)

| class | ids | count |
|---|---|---:|
| keywords / abilities unresolved | Z004, Z068, Z074, Z076 | 4 |
| contextual anaphora not extracted/resolved | Z015, Z018, Z030, Z051 | 4 |
| list / compound semantics | Z049, Z053, Z059, Z067, Z086, Z092 | 6 |
| scalar anaphora (`that many` split) | Z052 | 1 |
| self-reference anaphora (inside a type string) | Z062 | 1 |
| modality / actor / zone | Z047, Z093, Z095 | 3 |

Corrections to the prompt's read: `Z003`, `Z079`, `Z082`, `Z084`, `Z085`, `Z099` are **legit** in the exported labels, not bugs; `Z062` is the only self-reference bug. `Z017` is not a bug in the file. `Z052` is a scalar-anaphora split, not a list bug.

Accepted before/after per class (from the notes):

- **Keywords** (Z004 Warp): before `keywords:[{value:"Warp", note:"unresolved"}, "{1}", "{R}"]`; after a keyword entry `{keyword:"Warp", cost:"{1}{R}"}` (Z068: `{keyword:"Sneak", cost:"{3}{B}{B}"}` as a casting ability, not a bare keyword).
- **Contextual anaphora** (Z015/Z018): before `who:"the exiled card's owner"` and `card_type:{value:"card"}`; after the exiled card is an anaphor node (resolved to the earlier exile) and the owner relation is separate, e.g. `{owner: {ref:"anaphora", surface:"the exiled card"}}`.
- **List/compound**: before `event.object:"an instant or sorcery spell"` (Z049), `card_type:"creature"` with target only on it (Z053), two split effects (Z059/Z086), `cards:[Goblin],[Swamp,Mountain]` plus a duplicate single `card` (Z067); after one list field (`["instant","sorcery"]`, `["creature","planeswalker"]` both targeted) and one action array sharing subject/player.
- **Scalar anaphora** (Z052): before `amount:["that","many"]`; after an anaphor node/quantity resolution.
- **Self-reference** (Z062): before `card_type:"Aura attached to this creature"`; after `card_type:"Aura"` + `modifier:{attached_to:"~"}` (the self reference resolved to `~`).
- **Modality/actor/zone** (Z093): before `verb:"discard"`; after a `may` wrapper around discard. (Z047) mana goes to the player's pool, not "on this creature". (Z095) `target opponent's hand` is a zone.

## 3. Claim recall on the sample

`review/claims.json` has a claim for **6 of 19 bugs = 31.6%** (all `stringy`): Z030, Z049, Z059, Z062, Z092, Z095. It also claims 9 ok and 2 legit items, so precision on claimed items is **6 / 17 = 35.3%**. The claim system is a stringy-site detector here: it catches list/self-reference symptoms (6/6 hits are stringy) and misses the semantic classes entirely (keywords unresolved, contextual anaphora, modality, scalar anaphora).

## 4. Corpus size of the top classes

Computed over the 22,217 artifact records:

| class | records | unique texts |
|---|---:|---:|
| sentence contains "this creature/card/permanent/artifact/token/enchantment" | 3,439 | 1,918 |
| output carries `note:"unresolved"` | 894 | 275 |
| card_type carries an `or` list / "or" value | 858 | 448 |

## What this implies

The human bugs are semantic, not UI-axis noise: the dominant clusters are unresolved keywords (4), anaphora that must be extracted from type/modifier strings (4 contextual + 1 scalar + 1 self), and list/compound actions that share a subject/player (6). The claim system as built is not a substitute: 31.6% recall and 35.3% precision on this sample, and every hit is a stringy-site symptom. The cheap wins that also shrink the claims backlog are the two string families: 894 records still emit `note:"unresolved"` and 858 emit an `or`-list in a card type; the self-reference family is the largest by records (3,439) but mostly affects anaphora marking rather than structure.
