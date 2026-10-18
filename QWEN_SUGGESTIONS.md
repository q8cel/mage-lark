# Architectural Recommendations: MTG Oracle Text Parsing and Coreference

This document contains independent architectural advice for the current MTG Oracle-text parsing project. It is intended to be read by humans or implementation agents working on the repository.

The advice assumes the current architecture described in the project README:

- Python 3.13
- Lark 1.3.1
- Earley parser with `ambiguity='resolve'`
- primary benchmark: FDN, 771 cards, 1,653 sentences
- generalization benchmark: Standard bundle, 21 sets, ~22k sentences
- cached and parallel `run.py`
- content-preservation checking via `content_check.py`
- deterministic coreference pipeline around:
  - `anaphora.py`
  - `mentions.py`
  - `ptree.py`
  - `refs.py`
  - `rulecoref.py`
  - `resolve_pipeline.py`
- execution machine: older Xeon, many threads but relatively slow single-thread performance

---

## 1. Executive Summary

The project already has many strong architectural elements:

- sentence deduplication,
- grammar-hash-keyed parse cache,
- parallel batch parsing,
- golden output tests,
- content-preservation checking,
- deterministic coreference design,
- clear separation between grammar and interpreter.

The main architectural risk is not that Lark is “too slow” in principle. The main risk is that the system is becoming a monolithic pipeline where expensive parsing, coreference, rewriting, and validation are too tightly coupled.

The most important recommendations are:

1. **Do not migrate away from Lark as the first step.**
   - The current bottleneck is architectural, not merely linguistic or language-specific.

2. **Separate the system into explicit stages.**
   - preprocessing,
   - sentence parsing,
   - typed-atom interpretation,
   - mention extraction,
   - coreference decisions,
   - resolved semantic atoms,
   - optional rewritten text.

3. **Make coreference a graph/reference-resolution problem, not a text-rewrite-and-reparse problem.**
   - `rewrite -> re-parse -> interpret` should not be the primary coreference mechanism.

4. **Add deterministic fast paths before Earley.**
   - generic keyword lists,
   - simple activated abilities,
   - simple triggered abilities,
   - simple one-shot effects,
   - modal headers.

5. **Cache by stage, not only by final run.**
   - Changing resolver rules should not invalidate parsing.
   - Changing the interpreter should not invalidate coreference.
   - Changing preprocessing should invalidate only downstream artifacts that truly depend on it.

6. **Treat full Standard and full coreference benchmarks as nightly/batch operations.**
   - Normal development should run on FDN, golden tests, small Standard subsets, and cached artifacts.

7. **Design for the old Xeon.**
   - Prefer coarse-grained batch parallelism.
   - Do not assume 28 threads means 28 effective fast workers.
   - Make worker count explicit and configurable.

---

## 2. Current Architecture: What Is Already Good

The current project has several strong design decisions that should be preserved.

### 2.1 Parse cache keyed by grammar hash

This is correct and valuable:

```text
.cache/parse_<grammar-hash>.json
```

It gives near-instant re-runs when the grammar is unchanged.

### 2.2 Sentence deduplication

MTG Oracle text has many repeated sentences. Deduplicating unique sentence texts is a major architectural win.

### 2.3 Content-preservation checking

`content_check.py` is one of the most important parts of the repository.

Parsing coverage alone is not enough. A sentence can parse successfully and still silently lose important content: numbers, colors, zones, mana symbols, keywords, card types, etc.

Any future architectural change must preserve and extend this content-preservation discipline.

### 2.4 Golden output tests

`test_output.py` is an important regression guard.

Any refactoring, parser replacement, or coreference change should preserve the golden outputs unless there is an explicit, reviewed reason to change them.

### 2.5 Deterministic coreference

A deterministic resolver is appropriate for this domain. MTG text is constrained enough that rule-based resolution can be effective, inspectable, and testable.

The existence of `rulecoref.py`, `test_coref.py`, and `DETERMINISTIC-COREF.md` is a good sign.

---

## 3. Main Architectural Risks

### 3.1 Coreference is coupled to expensive parsing

The current coreference path appears to rely heavily on:

```text
ptree.py
    one tree per text
    keep_all_tokens=True
    propagate_positions=True
```

and then:

```text
resolve_pipeline.py
    rewrite -> re-parse -> interpret
```

This is expensive because:

- `keep_all_tokens=True` increases tree size,
- `propagate_positions=True` adds overhead,
- parsing whole texts is more expensive than parsing individual sentences,
- rewritten text may need reparsing,
- coreference changes may force parsing work to be repeated.

This is likely why anaphora resolution is much more expensive than verification.

### 3.2 Text rewriting makes coreference fragile

Rewriting text and reparsing it has several problems:

- rewritten text may fail to parse,
- rewritten text may change semantic content,
- rewritten text may introduce new ambiguity,
- content preservation becomes harder,
- coreference errors become parser errors,
- debugging becomes harder because the pipeline is no longer monotonic.

Rewritten text may still be useful as a compatibility or display artifact, but it should not be the primary semantic output.

### 3.3 One grammar is doing too much

The Lark grammar currently handles:

- sentence structure,
- ability types,
- keyword fallback,
- card targets,
- optional fields,
- joins,
- timing,
- effects,
- conditions,
- modal structure,
- generic keyword lists.

This is a lot for one Earley grammar.

As coverage grows, ambiguity grows. As ambiguity grows, Earley cost grows.

The solution is not necessarily a different parser. The solution is to reduce the amount of ambiguity the parser has to resolve.

### 3.4 Full-corpus runs are too close to normal development

A first Standard parse taking ~15–20 minutes is reasonable as a batch benchmark. It is too expensive for every small change.

Similarly, full coreference resolution over Standard should not be part of normal verify loops unless specifically testing coreference at scale.

### 3.5 Cache invalidation is too coarse

The parse cache is keyed by grammar hash. That is necessary, but not sufficient for a multi-stage pipeline.

Ideally:

- changing only coreference rules should not invalidate parse caches,
- changing only the interpreter should not invalidate mention caches,
- changing only ptree extraction should not invalidate grammar parsing,
- changing only downstream NLP formatting should not invalidate coreference.

The pipeline needs stage-level caches and stage-level version hashes.

---

## 4. Recommended Target Architecture

The recommended architecture is a staged pipeline with explicit artifacts.

```text
Raw MTGJSON / FDN data
        |
        v
preprocess.py
    normalized oracle text
    sentence segmentation
    saga/leveler prefix stripping
        |
        v
sentence index
    unique sentence texts
    card/sentence IDs
        |
        v
fast path classifier / template parser
    generic keywords
    simple activated abilities
    simple triggered abilities
    simple effects
    modal headers
        |
        v
Lark/Earley fallback
    grammar.lark
    parse trees / typed atoms
        |
        v
interpret.py
    typed dictionaries per sentence
        |
        v
mention extraction
    regex mentions
    parser-enriched mentions
        |
        v
mention inventory / document model
    mention IDs
    heads
    number
    definiteness
    sentence/clause context
        |
        v
coreference resolver
    filters
    possessive binding
    recency
    entity clustering
        |
        v
coreference decisions
    anaphor -> antecedent bindings
    rule provenance
        |
        v
resolved semantic atoms
    downstream NLP output
        |
        v
optional rewritten text
    compatibility / display only
```

The key principle is:

> Parsing should produce stable semantic atoms.  
> Coreference should bind references between atoms.  
> Rewriting text should be a derived, optional artifact.

---

## 5. Parsing Recommendations

### 5.1 Keep Lark for now

Do not replace Lark immediately.

Lark is not the main architectural problem. The problem is that too much ambiguity is being pushed into one general Earley grammar.

A different parser generator will not automatically solve:

- generic keyword ambiguity,
- card-target overconsumption,
- long-tail MTG constructions,
- optional-field explosion,
- content-preservation bugs,
- coreference rewrite costs.

Before considering migration, reduce ambiguity and split the parsing problem.

### 5.2 Add a fast-path layer before Earley

Create a deterministic fast-path module, for example:

```text
fastpath.py
```

Its job is to recognize high-frequency MTG patterns without invoking Earley.

Candidates for fast paths:

#### Generic keyword lists

Examples:

```text
Flying
Trample
Ward 2
Cycling {2}
Warp {1}{W}
Toxic 1
```

The README already notes that the generic keyword fallback adds ambiguity and increases full Standard re-parse time.

This is one of the best first candidates for moving out of the grammar.

The fast path should produce the same semantic shape as the current `generic_kw_list` interpretation.

#### Simple activated abilities

Examples:

```text
{T}: Add {G}.
{T}: Draw a card.
{1}{G}, {T}: Target creature gains trample until end of turn.
Sacrifice a creature: Draw a card.
```

A fast path can at least split:

```text
cost : effect
```

even if the effect still goes to Lark.

#### Simple triggered abilities

Examples:

```text
When ~ enters the battlefield, draw a card.
Whenever ~ attacks, draw a card.
Whenever a creature you control dies, put a +1/+1 counter on ~.
At the beginning of your upkeep, you lose 1 life.
```

The fast path can split:

```text
trigger , effect
```

and parse the pieces separately.

#### Simple one-shot effects

Examples:

```text
Draw a card.
Draw two cards.
You gain 3 life.
Target creature gets +2/+2 until end of turn.
Destroy target artifact.
Exile target creature.
Put two +1/+1 counters on target creature.
```

#### Modal headers

Examples:

```text
Choose one —
Choose one or both —
Choose two —
```

Modal headers and bullets can be segmented deterministically.

### 5.3 Fast-path output must pass existing quality gates

Any fast path must be validated by:

```bash
python test_output.py
python content_check.py FDN.json
python content_check.py Standard.json
```

Fast paths must not silently drop content.

Content preservation is more important than parse speed.

### 5.4 Cache fast-path results separately

Fast-path results should have their own cache key, for example:

```text
.cache/fastpath_<fastpath-version>.json
```

Key inputs:

- fast-path version,
- normalized sentence text,
- keyword lexicon version,
- preprocessing version.

This allows fast-path logic to evolve without invalidating Lark parse caches, and vice versa.

### 5.5 Classify sentence type before parsing

Add an explicit sentence classifier.

Possible classes:

```text
keyword
activated
loyalty
triggered
static
conditional_static
modal
effect
unknown
```

Then dispatch to the appropriate parser or subgrammar.

This reduces the search space for each sentence.

It also makes failure analysis easier:

```text
Which sentence types fail most often?
Which sentence types are slowest?
Which sentence types lose content?
```

### 5.6 Consider subgrammars for deterministic fragments

Once sentence types are classified, some fragments may be parseable with stricter grammars.

For example:

- activated ability cost/effect splitting,
- trigger header parsing,
- modal header parsing,
- keyword parsing.

Some of these may even be LALR-compatible if isolated.

Do not attempt to make the entire grammar LALR. That is probably not viable. But small deterministic subgrammars can be useful.

### 5.7 Continue moving ambiguity out of grammar rules

The README already notes an important lesson:

> Rule-form optionals after a matched token are unreliable in Earley — prefer terminal-level solutions or restructure.

This is a good principle. Continue applying it.

Useful techniques:

- pre-tokenize multiword MTG expressions,
- use lexical terminals for fixed phrases,
- group optional fields,
- avoid broad overlapping alternatives,
- move keyword recognition outside the grammar,
- use lexicons instead of open-ended rules.

Examples of multiword expressions worth lexicalizing:

```text
enters the battlefield
leaves the battlefield
is put into a graveyard
at the beginning of your upkeep
until end of turn
you control
you don't control
for each
for each other
base power and toughness
```

### 5.8 Reduce `card_target` ambiguity further

The `card_target` grouping into `lead`, `core`, and `zone_mod` was a good performance fix.

However, `card_target` is still likely a major ambiguity source, especially for greedy overconsumption.

Consider a dedicated target chunker.

For example:

```text
all attacking creatures you control in your graveyard
```

could be pre-chunked into:

```json
{
  "quantifier": "all",
  "status": ["attacking"],
  "card_type": "creature",
  "controller": "you",
  "zone": "graveyard"
}
```

Then the grammar can parse a sentence skeleton with a placeholder:

```text
Destroy <TARGET_1>.
```

or attach the pre-parsed target after parsing.

This would reduce Earley’s workload and improve control over greedy target boundaries.

### 5.9 Build MTG lexicons

The grammar should rely more on curated lexicons and less on open-ended syntax.

Useful lexicons:

- card types,
- supertypes,
- subtypes,
- colors,
- zones,
- statuses,
- counters,
- keywords,
- keyword actions,
- ability words,
- trigger events,
- player selectors,
- timing phrases.

Sources:

- MTGJSON,
- Scryfall,
- Comprehensive Rules,
- corpus mining from Standard/FDN/classic sets.

Lexicons should be versioned and cache-keyed.

---

## 6. Coreference Recommendations

This is the area where the largest architectural improvement is likely possible.

### 6.1 Coreference should produce bindings, not rewritten text

The primary output of coreference should be:

```json
{
  "anaphor_id": "m17",
  "antecedent_id": "m9",
  "rule": "recency",
  "confidence": "deterministic"
}
```

not merely:

```text
rewritten_text
```

Rewritten text can still be generated, but it should be a derived artifact.

### 6.2 Build an explicit mention model

A mention should be a first-class object.

Suggested fields:

```python
@dataclass
class Mention:
    id: str
    card_id: str
    sentence_id: int
    span: tuple[int, int]
    text: str
    head_text: str
    head_type: str
    number: str              # singular / plural
    definiteness: str
    is_self: bool
    is_target: bool
    clause_id: str | None
    in_condition: bool
    source: str              # regex / parser / fallback
```

This model should be stable and cacheable.

### 6.3 Build an explicit coreference decision model

A decision should also be first-class:

```python
@dataclass
class CorefDecision:
    anaphor_id: str
    antecedent_id: str | None
    rule: str
    candidates_considered: list[str]
    rejected_candidates: dict[str, str]
    confidence: str
    trace: dict
```

This makes debugging and evaluation much easier.

### 6.4 Store provenance for every decision

For each resolved anaphor, store enough information to answer:

- What were the candidates?
- Which rule selected the winner?
- Which candidates were rejected?
- Why were they rejected?
- Was the decision based on regex mentions or parser-enriched mentions?
- Was the parser involved?
- Was the decision deterministic or uncertain?

Example:

```json
{
  "anaphor": "It",
  "chosen": "target creature",
  "rule": "recency",
  "candidates": [
    {
      "text": "~",
      "rejected": "self_not_allowed"
    },
    {
      "text": "target creature",
      "chosen": true
    }
  ]
}
```

### 6.5 Make `ptree.py` optional enrichment

`ptree.py` is powerful but expensive.

It should not be mandatory for every coreference decision.

Recommended cascade:

```text
Level 0: anaphora.py
    detect possible anaphors lexically

Level 1: mentions.py
    regex mention spans

Level 2: refs.py
    mention inventory cleaning and features

Level 3: rulecoref.py
    deterministic rules over mention graph

Level 4: ptree.py
    optional structural enrichment for hard cases
```

Use full parse enrichment only when:

- there are multiple plausible antecedents,
- possessive binding is ambiguous,
- `that X` needs structural confirmation,
- `the rest` needs set reasoning,
- mention head type is unknown,
- recency alone is insufficient.

### 6.6 Do not require a whole-text parse tree

The README says `ptree.py` builds:

```text
one tree per text
```

For coreference, that may be too expensive.

Most MTG coreference can be handled with:

- sentence-local mention structure,
- cross-sentence recency,
- type agreement,
- number agreement,
- possessive binding.

A lightweight document model is usually enough:

```json
{
  "card_id": "...",
  "sentences": [
    {
      "sentence_id": 1,
      "text": "...",
      "mentions": ["m1", "m2"]
    },
    {
      "sentence_id": 2,
      "text": "...",
      "mentions": ["m3"]
    }
  ],
  "mentions": [...],
  "coref": [...]
}
```

This avoids parsing entire card texts as one large tree.

### 6.7 Represent `the rest` as a set expression

MTG uses constructions like:

```text
Each creature you control gets +1/+1.
The rest get -1/-1 until end of turn.
```

Instead of rewriting `The rest` into English, represent it semantically:

```json
{
  "type": "set_difference",
  "base": {
    "type": "card_target",
    "card_type": "creature",
    "controller": "you"
  },
  "exclude_ref": "m4"
}
```

or:

```json
{
  "type": "the_rest",
  "domain_ref": "m2",
  "excluded_ref": "m4"
}
```

This is more precise and avoids fragile text rewriting.

### 6.8 If rewriting is necessary, isolate it

If some downstream component truly requires rewritten text, make it a separate stage:

```text
coref decisions
    ↓
rewrite engine
    ↓
rewritten sentences
    ↓
parse rewritten sentences
    ↓
content-check rewritten sentences
    ↓
resolved atoms
```

Important requirements:

- cache rewritten sentences separately,
- fail soft if rewritten text does not parse,
- preserve the original parsed atoms,
- mark the output with a status such as:

```json
{
  "coref_status": "rewrite_parse_failed"
}
```

Do not allow rewrite failures to destroy already-good parsed atoms.

### 6.9 Coref should be idempotent

Running coreference multiple times should not repeatedly rewrite already-resolved text.

Use stable mention IDs and decision records.

Avoid cycles like:

```text
rewrite -> resolve -> rewrite -> resolve
```

The resolver should operate on an immutable or versioned mention graph.

---

## 7. Caching and Artifact Design

The pipeline should be resumable, inspectable, and stage-cacheable.

### 7.1 Recommended cache/artifact layers

```text
.cache/preprocess/<preprocess-version+data-hash>.jsonl
.cache/parse/<grammar-hash>.jsonl
.cache/fastpath/<fastpath-version>.jsonl
.cache/mentions/<mention-version+preprocess-hash>.jsonl
.cache/ptree/<ptree-version+grammar-hash>.jsonl
.cache/coref/<coref-version+mention-hash>.jsonl
.cache/resolved/<interp-version+coref-hash>.jsonl
```

The exact storage format can be JSON, JSONL, SQLite, Parquet, or another suitable format. JSONL or SQLite is often better than one large JSON file for incremental work.

### 7.2 Cache invalidation rules

Recommended invalidation behavior:

| Change | Should invalidate |
|---|---|
| `grammar.lark` | parse cache |
| `interpret.py` | resolved atoms, not necessarily parse cache |
| `preprocess.py` | segmentation cache and downstream text-dependent caches |
| `mentions.py` | mention cache |
| `ptree.py` | ptree cache |
| `rulecoref.py` | coref decisions |
| `resolve_pipeline.py` | rewritten/resolved artifacts |
| fast-path logic | fast-path cache |

The goal is:

> Changing one stage should not force all earlier stages to rerun.

### 7.3 Use unit hashes

For cards/sentences, define stable unit hashes.

Example:

```text
sentence_hash = hash(normalized_sentence_text)
card_unit_hash = hash(card_id + normalized_oracle_text + preprocess_version)
```

Then caches can be incremental at the unit level.

If a card’s oracle text has not changed, and the relevant stage version has not changed, skip it.

### 7.4 Store failure artifacts

For each stage, store failure records.

Examples:

```text
parse_failures.jsonl
content_missing.tsv
mention_failures.jsonl
coref_failures.jsonl
rewrite_parse_failures.jsonl
```

Each failure should include:

- dataset,
- card ID,
- sentence ID,
- sentence text,
- stage,
- error category,
- diagnostic information.

This makes long-tail work much easier.

---

## 8. Concurrency Recommendations for the Old Xeon

The target machine has many threads but slow cores. This matters architecturally.

### 8.1 Do not assume 28 threads = 28 effective workers

For CPU-bound Python work, hyperthreads often do not give full throughput. Memory pressure, cache contention, and interpreter overhead can make too many workers slower.

Make worker count explicit:

```bash
python run.py --data Standard.json --workers 12
python rulecoref.py --workers 8
```

Defaulting to 24 workers may be inappropriate on all machines.

A better default is:

```python
min(os.cpu_count(), physical_core_count_or_fallback)
```

or simply a configurable setting.

### 8.2 Use coarse-grained batch parallelism

Avoid fine-grained parallel tasks such as:

```text
one task per sentence
one task per mention
one task per rule
```

Instead use chunks:

```text
500 cards per task
or
2000 unique sentences per task
```

Coarse chunks reduce scheduling overhead and improve cache locality.

### 8.3 Separate CPU-heavy and CPU-light stages

CPU-heavy:

- Lark parsing,
- ptree parsing,
- tree walking,
- regex fallback over many segments.

CPU-light:

- coreference rule application,
- mention filtering,
- decision logging,
- report generation.

These should be separate stages. Resolver development should not repeatedly pay parsing costs.

### 8.4 Provide dev and batch modes

Recommended modes:

```bash
--mode dev
--mode batch
```

Dev mode:

- small subset,
- lower worker count,
- simple logging,
- no full Standard,
- no full coref benchmark.

Batch mode:

- full corpus,
- resumable caches,
- parallel chunks,
- artifact dumps,
- failure reports.

---

## 9. Testing and Verification Strategy

### 9.1 Keep verify cheap

If `verify` currently takes less time than anaphora resolution, keep it that way.

Verify should remain suitable for frequent runs.

Recommended per-commit/per-change verification:

```bash
python test_output.py
python test_coref.py
python check_interp_grammar.py
python run.py --data FDN.json
python content_check.py FDN.json
```

Optionally:

```bash
python run.py --data Standard.json --sets OTJ,WOE
```

### 9.2 Move full Standard and full coref benchmarks to scheduled runs

Full Standard parsing and full coreference resolution should not be part of every development loop.

Run them:

- nightly,
- before releases,
- after major grammar changes,
- after major coref changes.

### 9.3 Build a small coref dev set

Create a small set of cards/sentences exercising all major anaphora patterns:

- `it`
- `its`
- `they`
- `them`
- `their`
- `that creature`
- `that card`
- `the rest`
- possessive binding
- plural antecedents
- self-reference `~`
- target antecedents
- condition-clause antecedents
- ambiguous multiple candidates
- no valid antecedent

This set should be small enough to run constantly.

### 9.4 Add coref decision tests

In addition to golden end-to-end tests, test individual resolver rules.

Examples:

- possessive binding selects the correct possessor,
- recency prefers the nearest compatible mention,
- number agreement blocks singular/plural mismatches,
- self-reference rules handle `~`,
- `the rest` produces a set expression,
- unresolved cases are marked explicitly.

### 9.5 Track failure categories

Coref failures should not be a single metric.

Break them down:

```text
no_anaphora_detected
mention_span_missing
mention_head_unknown
no_candidate_antecedent
candidate_type_mismatch
number_mismatch
possessive_conflict
recency_conflict
parse_failed
rewrite_parse_failed
interpreter_lost_content
```

This makes it clear whether a problem is due to:

- mention extraction,
- parsing,
- resolver logic,
- interpretation,
- rewriting.

---

## 10. Recommended Implementation Plan

The following plan is incremental and avoids a risky rewrite.

### Phase 0: Instrumentation

Before changing behavior, add measurement.

For each sentence/card, record:

- parse time,
- cache hit/miss,
- sentence type,
- sentence length,
- whether fast path was used,
- whether ptree was used,
- coref decision count,
- coref runtime,
- failure category.

This will make later optimizations safe and measurable.

### Phase 1: Separate coref caches

Make it possible to run:

```bash
python build_coref_cache.py --data FDN.json
python rulecoref.py --from-cache --eval
```

Requirements:

- changing resolver rules should not force reparsing,
- changing ptree should not force grammar reparsing unless ptree depends on grammar,
- changing interpreter should not force coref rerun unless resolved atoms depend on it.

### Phase 2: Add fast path for generic keywords

Move generic keyword detection out of Earley.

Steps:

1. Build a keyword lexicon.
2. Add a whole-sentence keyword recognizer.
3. Emit the same output shape as current `generic_kw_list`.
4. Validate with `content_check.py` and `test_output.py`.
5. Measure Standard parse time.

This is likely one of the highest-value early changes.

### Phase 3: Add sentence classification

Create a classifier for:

```text
keyword
activated
loyalty
triggered
static
conditional_static
modal
effect
unknown
```

Use it for:

- dispatch,
- reporting,
- fast paths,
- failure analysis.

### Phase 4: Add fast paths for common templates

Implement deterministic parsers for high-frequency patterns:

- simple activated abilities,
- simple triggered abilities,
- simple draw/life/counter effects,
- modal headers,
- simple targeted effects.

Each fast path must pass content-preservation checks.

### Phase 5: Replace rewrite-first coref with binding-first coref

Change coref output to explicit bindings.

Then:

- produce resolved atoms from bindings,
- generate rewritten text only if needed,
- cache rewritten text separately,
- fail soft on rewrite/parse errors.

### Phase 6: Reduce `card_target` ambiguity

Introduce a target chunker or preparser for noun phrases.

This can be incremental:

- first extract high-confidence targets,
- leave uncertain targets to Earley,
- compare output with existing golden tests.

### Phase 7: Evaluate migration only after stabilization

Only after the above steps should a language/parser migration be considered.

If migration is still desired, the most sensible options are:

- Rust hand-written/template parser,
- TypeScript hand-written/template parser,
- ANTLR with a redesigned grammar.

But migration should be done after the architecture is cleaned up, not as a substitute for cleaning it up.

---

## 11. What Not to Do

### 11.1 Do not replace Lark immediately

A parser migration will not fix:

- ambiguous grammar design,
- expensive coref rewriting,
- missing caches,
- long-tail coverage gaps,
- content-preservation bugs.

Fix the architecture first.

### 11.2 Do not make rewritten text the primary semantic representation

Rewritten text is fragile.

The primary representation should be structured atoms plus coreference bindings.

### 11.3 Do not run full Standard on every small change

Use FDN and small Standard subsets for normal development.

Run full Standard as a benchmark.

### 11.4 Do not run full coref in every verify loop

Coref should be cached and separated.

Only run full coref when working on coref or when nightly benchmarks run.

### 11.5 Do not use too many workers by default

On an old Xeon, more threads can make performance worse.

Worker count should be explicit and tunable.

### 11.6 Do not let fast paths bypass content checking

Fast paths are useful, but they must be validated.

Speed must not come at the cost of silent content loss.

### 11.7 Do not invalidate all caches for unrelated changes

Stage-level caches are necessary.

A change in resolver rules should not force a full grammar parse.

---

## 12. Suggested New Modules

The following modules would fit the recommended architecture.

### `fastpath.py`

Deterministic recognition of high-frequency patterns.

Responsibilities:

- generic keyword lists,
- simple activated abilities,
- simple triggered abilities,
- simple effects,
- modal headers.

### `classify.py`

Sentence-type classification.

Outputs:

```text
keyword / activated / loyalty / triggered / static / modal / effect / unknown
```

### `target_chunker.py`

Dedicated parsing/pre-chunking of `card_target` noun phrases.

Outputs structured target components:

```json
{
  "quantifier": "...",
  "status": "...",
  "color": "...",
  "card_type": "...",
  "controller": "...",
  "zone": "..."
}
```

### `coref_model.py`

Dataclasses or schemas for:

- Mention,
- Candidate,
- CorefDecision,
- ResolvedReference.

### `resolved_atoms.py`

Builds final resolved semantic atoms from:

- parsed atoms,
- mention inventory,
- coref decisions.

### `rewrite_compat.py`

Optional module for generating rewritten text from resolved atoms.

This module should be isolated and fail-soft.

---

## 13. Suggested Data Model Sketch

### Mention

```json
{
  "id": "m9",
  "card_id": "...",
  "sentence_id": 2,
  "span": [7, 21],
  "text": "target creature",
  "head_text": "creature",
  "head_type": "card_target",
  "number": "singular",
  "definiteness": "indefinite",
  "is_self": false,
  "is_target": true,
  "clause_id": "main",
  "in_condition": false,
  "source": "regex+parser"
}
```

### Coreference decision

```json
{
  "anaphor_id": "m17",
  "antecedent_id": "m9",
  "rule": "recency",
  "confidence": "deterministic",
  "candidates": [
    {
      "id": "m2",
      "text": "~",
      "rejected_reason": "self_not_allowed"
    },
    {
      "id": "m9",
      "text": "target creature",
      "chosen": true
    }
  ]
}
```

### Resolved atom

```json
{
  "sentence_id": 3,
  "type": "effect",
  "effect": {
    "type": "gain_keyword",
    "subject_ref": "m9",
    "keyword": "flying",
    "duration": "until_end_of_turn"
  },
  "coref_status": "resolved"
}
```

---

## 14. Definition of Done for the Recommended Refactor

A successful refactor should satisfy the following:

1. Existing golden tests still pass.

   ```bash
   python test_output.py
   ```

2. Content preservation does not regress.

   ```bash
   python content_check.py FDN.json
   ```

3. Changing coref rules does not trigger a full grammar parse.

4. Changing interpreter logic does not trigger mention extraction or coref unless necessary.

5. Full Standard parsing remains a batch/benchmark operation.

6. Coreference can be run from cached mention/ptree artifacts.

7. Coref decisions are inspectable and include rule provenance.

8. Rewritten text, if generated, is optional and fail-soft.

9. Worker count is configurable.

10. Failure reports are categorized and resumable.

---

## 15. Final Recommendation

The most important architectural shift is:

> Move from a pipeline where expensive parsing is repeatedly used to resolve text, toward a pipeline where parsing produces stable semantic atoms and coreference resolves references between those atoms.

In concrete terms:

```text
Current expensive pattern:
text -> parse -> rewrite -> parse again -> interpret

Recommended pattern:
text -> parse once -> typed atoms -> mention graph -> coref bindings -> resolved atoms
```

This will make the system:

- faster,
- easier to cache,
- easier to debug,
- easier to test,
- less fragile on slow hardware,
- and better suited for downstream NLP consumption.

Do not begin with a language migration. Begin by decoupling stages, adding fast paths, and making coreference binding-first rather than rewrite-first.
