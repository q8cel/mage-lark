# Human review v7 — analysis

Pack `swarm/work/human_review_v7` (artifact SHA `45b5f423…`). Labels: **73 ok / 13 bug / 14 legit** (verified; matches the stated counts). 27 items carry notes; all are clustered below.

## 1. Score

`swarm/scripts/human_audit_eval.py --pack swarm/work/human_review_v7`:

- labelled 100 / 100; no ledger verdicts (parser-grade pack).
- **weighted population wrong rate 13.1%** (95% CI 6.4%–19.7% design-based normal; 7.8%–21.1% weighted Wilson, n_eff=100).
- strata (labelled / raw bug rate): size 1: 64 / 18.8%; size 2–4: 19 / 0.0%; size 5+: 17 / 5.9%.
- substitution axis: 10 labelled, 2 bugs, 20.2% weighted; no-substitution 90, 11 bugs, 12.3%.
- Denominator: **9,530** clean non-keyword per-card records (11,648 clean − 2,118 keyword-only), from 13,357 unique records.

## 2. Note clusters

| class | ids (bug / legit) | count |
|---|---|---:|
| cross-sentence / context anaphora | A004*, A022, A033*, A070, A095 | 5 |
| contextual referent (manifest dread → "that creature") | A026*, A092* | 2 |
| quoted-ability context | A031*, A051, A079 | 3 |
| duplicate `count` | A046, A050, A058, A089 | 4 |
| scope / quantifier | A028*, A035*, A047 | 3 |
| missing fields (amount / X / duration) | A056*, A064*, A065* | 3 |
| ability-as-whole | A012*, A010 | 2 |
| play-vs-cast | A084* | 1 |
| zone / controller | A055 | 1 |
| entity naming / list scope | A009 | 1 |
| timing / mana-loss semantics | A002* | 1 |
| oracle-text incompleteness | A021 | 1 |

`*` = bug (13 total); the rest are legit. Corrections to the prompt's read: A022/A070/A095 are legit, not bugs; A031 is primarily a quoted-ability context bug (also cross-sentence); A026/A092 are the same manifest-dread misbinding (both bugs); A046/A050/A058/A089 are legit duplicate-count observations.

## 3. Duplicate `count` — confirmed

All four records carry the same amount twice, at two paths of the same `put_counter` action:

| id | sentence | `[].effect.count` | `[].effect.counter.count` |
|---|---|---|---|
| A046 | put a +1/+1 counter on target creature | 1 | 1 |
| A050 | put a stun counter on it | 1 | 1 |
| A058 | put X +1/+1 counters on each legendary creature | "X" | "X" |
| A089 | put four -1/-1 counters on target creature | 4 | 4 |

Handler: `i_put_counter_action` sets `effect.count` from `counter_amount`; `_finalize`'s counter-string normalisation (core/interpret.py, the `for ckey in ('counter','counters')` block) rewrites the `counter` string into `{kind, count}` and copies `node['count']` into `counter.count`. Same value, two representations. Keep `effect.count` (the action-level amount) and drop the mirrored `counter.count` (or make `counter` kind-only).

## 4. Corpus size of each family

| family | records | unique texts | notes |
|---|---:|---:|---|
| segment starts `If you do` | 362 | 119 | cross-sentence context |
| segment starts `If you don't` | 69 | 22 | cross-sentence context |
| segment starts `This way` | 0 | 0 | never segment-initial |
| segment starts `That many` | 0 | 0 | never segment-initial |
| `named <X>` in text | 112 | 50 | 54 unique cards |
| quoted ability on a created token | 143 | 82 | |
| duplicate `count` paths | 1,212 | 629 | A046 family |
| `can't be blocked by more than one` | 14 | 10 | A035 family |
| `play a land` | 14 | 4 | A084 family |
| `Gift a card` | 19 | 1 | A012 family |
| `until/for` clause with no duration key | 202 | 111 | A065 family (broader) |
| `duration` stored as a string | 59 | 25 | A065 exact shape |
| `empower` without X/xdef | 46 | 21 | A064 family |
| amount stored as a ≥3-word string | 15 | 8 | A056 family |
| target `or`-list with a shared target | 116 | 44 | A028/A035 family |

## What to build first

1. **Card-level context.** `If you do` / `If you don't` open 431 records, and the cross-sentence anaphora class is the largest note class (5/27 notes, 3 bugs). The compiler needs the preceding sentence's plan as context (event refs, `that many`, `that card`, `discarded this way`) rather than sentence-local interpretation. Sizes justify it: 362 + 69 segments, plus 202 `until`-clause/context records that also need neighbouring text.
2. **Quoted abilities parsed independently with preserved text.** 143 records / 82 texts carry token-attached quotes; 3 notes (A031/A051/A079). Parse the quote as its own card with the quoted name as `~`, insert the structured ability into the host, and keep the original quote string.

Then the ordered small-bug list by size:

- duplicate `count` (1,212 records) — handler-level dedupe, trivial.
- missing `duration` for until/for clauses (202 records; 59 stored as strings) — extend the duration parser.
- target/scope or-lists (116 records; A028/A035) — one target applied to the whole list, plus the "more than one" bound (14 records).
- `named` entity naming (112 records, 54 cards) — carry the name as an entity, not a loose token.
- `empower` X (46), `Gift a card` (19), `play a land` vs cast (14), blocked-by-more-than-one (14), amount strings (15).
