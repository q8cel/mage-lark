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

python debug.py "Draw a card" "Tap an untapped creature you control"
python run.py --data FDN.json                  # full coverage (cached, fast)
python run.py --data Standard.json --dump failures_std.txt
python run.py --data Standard.json --sets OTJ,WOE     # subset of sets
```

`run.py` is the main entry point. It is **cached and parallel** (see
*Performance*): a first Standard check takes ~15–20 min; any re-run with an
unchanged grammar is near-instant.

## Layout

| file | purpose |
|---|---|
| `FDN.json` | Oracle text for all 771 Foundations cards |
| `Standard.json` | (git-ignored) 21-set Standard rotation bundle from mtgjson |
| `mtd/__init__.py` | FDN loader: `all_oracle_text()`, `card_type_set()`, `name_set()` |
| `setdata.py` | Unified loader for FDN and mtgjson (bundle) formats |
| `preprocess.py` | Strip reminders, split oracle into sentences, strip saga/leveler prefixes |
| `grammar.lark` | The Lark grammar (Earley, `ambiguity='resolve'`) |
| `interpret.py` | `Interpreter` — top-down tree walker, tree → typed dicts |
| `transformer.py` | (legacy) Lark `Transformer` — superseded by `interpret.py` |
| `run.py` | **Main runner**: cached + parallel coverage over a whole set/bundle |
| `test_parse.py`, `test_parallel.py` | Earlier (uncached) runners |
| `debug.py`, `show.py` | Parse + dump the tree for raw sentences |
| `demo_output.py` | Show the **actual interpreted dicts** for example sentences/cards |
| `content_check.py` | **Content-preservation** discovery: input content units vs. output |
| `check_interp_grammar.py` | Static interpreter↔grammar rule-name sync checker |
| `test_output.py` | 15 **golden output tests** (regression guard for the interpreter) |
| `audit_output.py` | Flag suspicious outputs (empty dict, pronoun-as-type, …) |
| `quick_test.py`, `analyze.py`, `vocab.py` | Sampling / corpus exploration helpers |

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
python content_check.py classic.json          # % of parsed sentences that lose content
python content_check.py classic.json --dump   # write all (unit, sentence) pairs to content_missing.tsv
python test_output.py                         # golden tests: 15/15 must pass
python check_interp_grammar.py                # interpreter handlers vs. grammar rules
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
   `multiprocessing.Pool` (24 workers by default), each worker holding its own
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
| copy / return / exile / Ward / trigger batches | **98.5 % (1,628/1,653, 25 failures)** |

The 25 remaining FDN failures are all **unique** complex one-offs (multi-clause
effects with internal commas, nested X-defs, "for each / for each other"
distributions, "loses all abilities and is a X with base power and toughness"
where the greedy leading `card_target` over-consumes). No common sub-pattern
remains.

**Standard generalization** (22,179 sentences, 21 sets):

| stage | coverage |
|---|---|
| as-tuned-on-FDN (no changes) | 62.7 % |
| + open keyword fallback, "enters the battlefield", main-phase timing, "return … transformed", saga/leveler prefix strip | 70.0 % (15,541/22,196) |
| + classic-set grammar work (walk keywords, tokens, can't/can, cost mods, loyalty effects, …) + name-normalization data fix | **71.7 % (15,902/22,179)** |

The gap between FDN (98.5 %) and Standard (71.7 %) is the key finding. It is
**not** caused by hardcoded cases — the grammar has no card names, numbers, or
colors baked in. It is caused by **FDN being a narrow set**: the 21 published
sets use many more keywords, mechanics, and syntax constructions than FDN
ever did. The remaining Standard failures are a long tail of distinct
constructions (new keywords like `prepared`/`Job select`, `It's an X` type
shifts, `the rest` distributions, modal instructions, `collect evidence` and
other 2024–26 mechanics). Each is a separate, legitimate MTG pattern that FDN
simply didn't exercise. Closing the gap means either adding those patterns or
tuning on a more representative set.

**Classic generalization** (4,279 sentences, 9 core sets: M10–M15 + M19–M21,
2,586 cards, downloaded via mtgjson): classic sets are a more representative
test than FDN but predate the 2024–26 mechanics that dominate Standard.

| stage | coverage |
|---|---|
| as-tuned-on-FDN (pre data-fix) | 76.3 % |
| + basic-land/keyword name-normalization fix, walk keywords, token keywords, protection, can't/can patterns, phase/extra-turn, cost modifiers | **79.2 % (3,388/4,279, 609 unique failures)** |

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
