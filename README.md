# MTG Oracle Text → Atomic Structure (Lark / Earley)

Parse Magic: The Gathering oracle text into **atomic, structured
dictionaries** — one typed dict per sentence, with card targets decomposed into
their components (quantifier / status / color / type / controller / zone),
amounts, keywords, etc. The output is intended to feed downstream NLP
pipelines (not human display).

Primary benchmark: the **Foundations (FDN)** set (771 cards, 1,653 segmented
sentences). Generalization is validated against the **Standard** rotation
bundle (21 published sets, 22,196 sentences).

## Quick start

```bash
source myenv/bin/activate          # Python 3.13, Lark 1.3.1
# or: pip install -r requirements.txt

python tools/debug.py "Draw a card" "Tap an untapped creature you control"
python tools/run.py --data FDN.json                  # full coverage (cached, fast)
python tools/run.py --data Standard.json --dump failures_std.txt
python tools/run.py --data Standard.json --sets OTJ,WOE     # subset of sets
```

**Start here:** `docs/PIPELINE.md` documents the full data flow, the canonical parser
configurations (`larkparser.py`), the caches, and where the coreference pass sits.
`docs/DETERMINISTIC-COREF.md` documents the anaphora resolver design and numbers.

`run.py` is the main entry point. It is **cached and parallel** (see
*Performance*): a first Standard check takes ~25–35 min; any re-run with an
unchanged grammar is near-instant.

## Layout

```
grammar/grammar.lark    the Lark grammar (Earley, ambiguity='resolve')
paths.py                repo layout + import bootstrap + data-file resolution
core/                   parse -> interpret pipeline
coref/                  anaphora detection, resolver, models, evaluation
tools/                  runners, coverage, quality checks, dataset maintenance
tests/                  golden / regression suites
data/                   corpora and labelled datasets
docs/                   design notes and audit logs
mtd/                    FDN convenience accessors
.cache/                 derived caches (git-ignored)
```

Modules are still imported by their bare names (`import rulecoref`).
`paths.py` puts the repo root, `core/` and `coref/` on `sys.path`, so scripts
can live in any subdirectory; data files are resolved by bare name
(`FDN.json` → `data/FDN.json`).

**Data** (`data/`)

| file | purpose |
|---|---|
| `FDN.json` | Oracle text for all 771 Foundations cards |
| `Standard.json` | (git-ignored) 21-set Standard rotation bundle from mtgjson |
| `classic.json` | (git-ignored) M10–M15 + M19–M21 core-set bundle |
| `coref_standard.json` | dev dataset: teacher-labelled anaphors over `classic.json` |
| `coref_dataset.json` | training split for the attention baseline |
| `coref_benchmark.json` | 48-card human-gold coreference benchmark |
| `all_sentences.txt` | flat sentence dump used by the early survey tools |

**Grammar pipeline** (`core/`)

| file | purpose |
|---|---|
| `setdata.py` | Unified loader for FDN and mtgjson (bundle) formats |
| `preprocess.py` | Strip reminders, split oracle into sentences, strip saga/leveler prefixes |
| `larkparser.py` | Canonical parser factory (`interp` / `ptree` configurations) |
| `interpret.py` | `Interpreter` — top-down tree walker, tree → typed dicts |
| `lists.py` | `and/or` list protection (round-trips lists through `LISTTOK`) |
| `ptree.py` | **The** parse: one tree per text, yielding mention spans **and** structure; disk-cached, parallel precompute, regex fallback |
| `pmentions.py`, `pstruct.py` | Thin shims over `ptree`, kept for existing callers |

**Coreference** (`coref/`)

| file | purpose |
|---|---|
| `anaphora.py` | Lexical anaphor enumeration over raw text: `it/its/they/them/their`, `that X`, `the rest` |
| `mentions.py` | Candidate mention spans: regex ∪ parser spans, bare pronouns filtered |
| `refs.py` | Mention **inventory**: maximal-span cleaning + `head_type`, `number`, `definiteness`, `is_self`, `is_target`, `sentence`, `clause` |
| `rulecoref.py` | **Deterministic resolver**: filters → possessive binding → recency → entity clustering → `rewritten_text` |
| `coref_eval.py` | **Unified entity-aware evaluation** for rule and attention resolvers (same fixed candidate pool) |
| `dataset_validation.py` | Validate span/gold invariants; `--source` checks `normalize_with_map` grounding |
| `resolve_pipeline.py` | `--resolve` seam: rewrite → re-parse → interpret; measures how many anaphora markers disappear from the output |
| `resolve.py` | Attention-over-mentions baseline + `--eval` |
| `transformer.py`, `vocab.py` | (legacy) Lark `Transformer` and shared vocabulary |
| `label_cases.py` | Offline teacher harness: builds per-anaphor cases, labels with an LLM |
| `validate_teacher.py` | Teacher agreement / candidate recall against human gold |
| `train_head.py`, `sweep_head.py` | Frozen-encoder mention ranker (baseline) + hyperparameter sweep |
| `ensemble_label.py` | Majority vote across several teacher runs |

**Tools** (`tools/`)

| file | purpose |
|---|---|
| `run.py` | **Main runner**: cached + parallel coverage over a whole set/bundle |
| `test_parse.py`, `test_parallel.py` | Earlier (uncached) coverage runners |
| `quick_test.py` | Fast random-sample parse check |
| `debug.py`, `show.py` | Parse + dump the tree for raw sentences |
| `demo_output.py` | Show the **actual interpreted dicts** for example sentences/cards |
| `content_check.py` | **Content-preservation** discovery: input content units vs. output |
| `check_interp_grammar.py` | Static interpreter↔grammar rule-name sync checker |
| `audit_output.py` | Flag suspicious outputs (empty dict, pronoun-as-type, …) |
| `crosscheck.py`, `invariant_check.py` | Cross-model agreement and dataset invariant audits |
| `analyze.py`, `vocab.py`, `analyze_strat.py`, `strat_sample.py` | Sampling / corpus exploration helpers |
| `repair_dataset.py`, `repair_dataset_spans.py`, `remap_dataset.py`, `upgrade_texts.py` | Dataset text/span repair against a source bundle |

**Tests** (`tests/`)

| file | purpose |
|---|---|
| `test_output.py` | 122 **golden output tests** (interpreter regression guard) |
| `test_coref.py` | 41 golden tests for the resolver (behaviour + documented limitations) |
| `test_normalize_map.py` | Tests for normalized-text ↔ original-offset mapping |
| `test_lists.py` | Tests for the list-protection layer |

**Docs** (`docs/`): `PIPELINE.md` (data flow, caches, seams),
`DETERMINISTIC-COREF.md` (resolver design + measurements),
`COREF-AUDIT.md` and `AUDIT-LOOPS.md` (out-of-dev audits),
`LISTS.md`, `QWEN_SUGGESTIONS.md`.


## Design

- **Interpretation is a tree walker, not a Lark `Transformer`.** A bottom-up
  `Transformer` passes already-transformed children (dicts) to parent rule
  methods, so `child.data == 'x'` checks silently fail and the atomic
  decomposition collapses to `{}`. `Interpreter` keeps the raw parse tree and
  dispatches on `node.data`, so identification is always reliable. It runs
  with `keep_all_tokens=True` so literal (anonymous) tokens like `"an"` and
  `"you control"` are present in the tree.
- **Terminals are UPPERCASE** (regex), **rules are lowercase** (structure).
- No hardcoded card names, numbers, or colors in the structural rules —
  `CARDNAME` (proper nouns), `COLOR`, `MANA`, `NUMBER` are lexical; the
  interpreter resolves proper-noun types against the real card-type set.
- **Case-insensitive verb/function terminals** (`V_DRAW`, `V_THIS`, …) with
  `\b` boundaries: MTG capitalizes the first word of each sentence, so
  literals like `"draw"` would miss `"Draw"`.
- **Open keyword vocabulary.** Published MTG has an open set of keywords, so a
  whole-sentence list of `CapitalizedWord [cost]` parses as a generic keyword
  list (`generic_kw_list`), not just a fixed `KEYWORD` terminal. A
  single-word ability (`Station`, `Cycling {2}`, `Warp {1}{W}`) is a keyword;
  a longer ability (`Goblins you control get +1/+1`) is not, because the
  generic rule only matches when the *entire* sentence is a keyword list.
- **Atomic `card_target`**: the fields (`this_that / quantifier / otherness /
  nontoken / status_list / colors / possessive / card_kind / with_modifier /
  controller / in_zone`) are all optional and order-sensitive. E.g.
  `"all attacking creatures"` →
  `{quantifier:'all', status:'attacking', card_type:'creature'}`.
  For **performance** the 13 optional fields are grouped into three wrappers —
  `lead`, `core`, `zone_mod` — which preserves the left-to-right order but
  stops the Earley chart from combinatorially exploding over 13 independent
  optionals. The interpreter finds each field **by name anywhere in the
  subtree** (`_find_all`), so the grouping is invisible to the output.
- `~` (tilde) = the card itself → `{'kind':'this_card'}`.
- **Sentence types**: `activated` (`{T}: …`), `loyalty` (`[+1]: …`),
  `triggered` (`When/Whenever/As …, …`), `static`, `static_keyword`,
  `if`, `modal` (`Choose one`), `effect` (bare). Time-conditioned statics:
  `as_long`, `during`, `until`.
- **Saga chapters & levelers**: the `III — …` (saga) and `12+ | …` (leveler)
  prefixes are stripped in preprocessing; the body is an ordinary ability.
  (The chapter/level number is dropped for now.)

## Output quality (content preservation)

Parse *coverage* (can we parse the sentence?) is **not** the same as output
*quality* (does the structured dict actually capture the sentence's content?). A
sentence can parse fine yet silently drop numbers, zones, keywords, or colors.

`content_check.py` measures this. It extracts the "hard content" of each parsed
sentence (numbers, power/toughness, mana symbols, colors, zones, type words,
keywords, named cards → `~`) and verifies every unit survives in the interpreted
output. This is the discovery engine for *silent bugs* — it finds the
"parses but the output is wrong/incomplete" cases without enumerating them by hand.

```bash
python tools/content_check.py classic.json          # % of parsed sentences that lose content
python tools/content_check.py classic.json --dump   # write all (unit, sentence) pairs to content_missing.tsv
python tests/test_output.py                         # golden tests: 44/44 must pass
python coref/dataset_validation.py coref_standard.json coref_dataset.json
python coref/dataset_validation.py coref_standard.json --source Standard.json
python tools/remap_dataset.py coref_standard.json --source Standard.json --dry-run
python tests/test_normalize_map.py
python coref/coref_eval.py --dataset coref_standard.json
python coref/coref_eval.py --bench --mentions regex
python tools/check_interp_grammar.py                # interpreter handlers vs. grammar rules
```

The interpreter was hardened against every class this surfaced; content loss on
the classic set's parsed sentences went from ~32% down to ~2%. The remaining
misses are a small per-pattern long tail (see `content_missing.tsv`).

## Performance

A full Standard check used to be estimated in **days** (sequential Earley at
~0.6 s/sentence × 22k sentences). `run.py` makes it ~15–20 min and re-runs
near-instant, via three layers:

1. **Sentence dedup.** Many sentences repeat across cards; only *unique*
   texts are parsed (Standard: 22,196 occurrences → 8,128 unique).
2. **Parse cache** (`.cache/parse_<grammar-hash>.json`). Maps sentence text →
   parsed/failed, keyed by the hash of `grammar.lark`. Unchanged grammar →
   every sentence is a cache hit → the run is instant. Change the grammar →
   new key → only the corpus re-parses. The cache is shared across datasets
   (FDN texts that also appear in Standard are free).
3. **Multiprocessing.** Unique uncached texts are parsed in a
   `multiprocessing.Pool` (CPU count minus two by default), each worker holding its own
   compiled parser. Plus a load cache (70 MB file read once) and a
   segmentation cache (keyed by data + `preprocess.py` hash).

## Status

**FDN coverage** (1,653 sentences):

| round | coverage |
|---|---|
| initial baseline | 17.2 % |
| case-insensitivity + atomic targets | 48.6 % |
| sentence-structure + verb expansion | 69.3 % |
| Interpreter fix + pattern batches | 83.6 % |
| `card_target` performance fix + batches | 89.9 % |
| token / deal-damage / counter / verb batches | 93.8 % |
| cast / spend / draw / search + event batches | 96.9 % |
| copy / return / exile / Ward / trigger batches | 98.5 % (1,628/1,653, 25 failures) |
| 2026 grammar batch: investigate, exile-all, can't-cast/activate, discard costs, ability words, token/keyword tails | 100.0 % (1,653/1,653, 0 failures) |
| `attn` + `master` merged | **100.0 % (1,653/1,653, 0 failures)** |

FDN is fully covered. No common sub-pattern remains.

**Standard generalization** (22,217 sentences, 21 sets):

| stage | coverage |
|---|---|
| as-tuned-on-FDN (no changes) | 62.7 % |
| + open keyword fallback, "enters the battlefield", main-phase timing, "return … transformed", saga/leveler prefix strip | 70.0 % (15,541/22,196) |
| + classic-set grammar work (walk keywords, tokens, can't/can, cost mods, loyalty effects, …) + name-normalization data fix | 71.7 % (15,902/22,179) |
| + investigate / can't-cast-activate / exile-all / discard-cost / event batches | 78.0 % (17,322/22,217) |
| + high-frequency static phrases, gift/manifest, ability-word prefixes, token tails | 79.8 % (17,725/22,217) |
| + ability-word triggered/static, empower/collect-evidence, stat tails, token-except | 80.7 % (17,933/22,217) |
| + hyphenated keywords, cycle/cloak, enter-untapped, gain-control tails | 81.2 % (18,038/22,217) |
| + devotion/greatest-power X-defs, life-loss events, draw-step triggers, cast-as-long | 81.4 % (18,077/22,217, 2,269 unique failures) |
| + classic-focused batch: multi-zone searches, event/trigger tails, damage expressions, type lists | **84.9 % (18,854/22,217, 1,810 unique failures)** |

The gap between FDN (100.0 %) and Standard (84.9 %) is the key finding. It is
**not** caused by hardcoded cases — the grammar has no card names, numbers, or
colors baked in. It is caused by **FDN being a narrow set**: the 21 published
sets use many more keywords, mechanics, and syntax constructions than FDN
ever did. The remaining Standard failures are a long tail of distinct
constructions (finality-counter return clauses, Vehicle type changes,
transform/emblem wording, `It's an X` type shifts, modal instructions, and
other 2024–26 mechanics). Each is a separate, legitimate MTG pattern that FDN
simply didn't exercise. Closing the gap means either adding those patterns or
tuning on a more representative set.

**Classic generalization** (4,280 sentences, 9 core sets: M10–M15 + M19–M21,
2,586 cards, downloaded via mtgjson): classic sets are a more representative
test than FDN but predate the 2024–26 mechanics that dominate Standard.

| stage | coverage |
|---|---|
| as-tuned-on-FDN (pre data-fix) | 76.3 % |
| + basic-land/keyword name-normalization fix, walk keywords, token keywords, protection, can't/can patterns, phase/extra-turn, cost modifiers | 79.2 % (3,388/4,279, 609 unique failures) |
| + current grammar (ability words, investigate/can't/static/event batches, token/keyword tails, X-defs) | 90.8 % (3,888/4,280, 334 unique failures) |
| + classic-focused batch: multi-zone searches, pile actions, event/trigger tails, damage expressions, additional mana, type lists | 94.1 % (4,028/4,280, 237 unique failures) |
| + `attn` and `master` branches merged (audit loops 1-32 plus the master coverage batches) | **98.2 % (4,201/4,280, 79 unique failures)** |

A **data bug** was the single biggest win: card names that were also basic-
land or keyword vocabulary (Plains, Island, …, Lifelink, Trample, …) were
being turned into `~` during name normalization, which clobbered walk keywords
(`Swampwalk` → `~walk`) and keyword text (`has lifelink` → `has ~`).
`setdata.py` now excludes that shared vocabulary from the per-set name list,
which is why keyword-named cards must not be in the stoplist — it is a
small curated set of the 5 basic lands + real MTG keywords, not a dump of
random words.

The remaining classic failures are a long tail (609 unique, mostly 1× each):
triggered / activated / loyalty **effects** (the trigger and cost clauses
parse; the effects are the open tail), plus diverse statics. They are genuine
MTG constructions, not regressions.

## Parser notes / caveats

- **Earley + `ambiguity='resolve'`**: the grammar is deliberately ambiguous
  (many optional fields, overlapping alternatives). Earley finds a parse when
  one exists and resolves ambiguity by preferring the parse that consumes the
  most input.
- **Rule-form optionals after a matched token are unreliable** in Earley —
  prefer terminal-level solutions or restructure (e.g. the `JOIN` terminal
  handles comma/`then`/`and` joins, which a rule-form `"," ("then"|"and")?`
  did not).
- **Performance**: the original grammar had **pathological Earley blowup** —
  `card_target`'s 13 independent optional complex fields grew the chart to
  ~1M items/sentence. Grouping into `lead`/`core`/`zone_mod` cut it ~20×. The
  generic keyword fallback adds some ambiguity (a full Standard re-parse is
  ~17 min, not ~7), an accepted trade for the open keyword vocabulary.
- **Sentence splitting is `~`-aware and quote-aware**: a card's name becomes
  `~` after normalization, so the splitter treats `~` as a sentence-start
  (alongside uppercase and `(`); periods inside double-quoted granted
  abilities are not splits.
