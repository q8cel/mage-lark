# MTG Oracle Text → Atomic Structure (Lark / Earley)

Parse Magic: The Gathering Foundations (FDN) oracle text into **atomic,
structured dictionaries** — one typed dict per sentence, with card targets
decomposed into their components (quantifier / status / color / type /
controller / zone), amounts, keywords, etc. The output is intended to feed
downstream NLP pipelines (not human display).

## Quick start

```bash
source myenv/bin/activate          # Python 3.13, Lark 1.3.1

python debug.py "Draw a card" "Tap an untapped creature you control"
python quick_test.py -n 150        # ~1-2 min sampled coverage (fast iteration)
python test_parse.py --dump failures.txt   # full corpus (~15-20 min, source of truth)
```

## Layout

| file | purpose |
|---|---|
| `FDN.json` | Oracle text for all 771 Foundations cards |
| `mtd/__init__.py` | Load `all_oracle_text()`, `card_type_set()`, `name_set()` |
| `preprocess.py` | Strip parenthetical reminders, split oracle into sentences |
| `grammar.lark` | The Lark grammar (Earley, `ambiguity='resolve'`) |
| `interpret.py` | `Interpreter` — top-down tree walker, tree → typed dicts |
| `transformer.py` | (legacy) Lark `Transformer` — superseded by `interpret.py` |
| `debug.py` | Parse + dump the tree for a few raw sentences (no preprocessing) |
| `quick_test.py` | Parse a fixed random sample; report % + top failures |
| `test_parse.py` | Parse the whole corpus; report coverage, dump failures |
| `analyze.py`, `vocab.py` | Corpus/vocabulary exploration helpers |

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
  transformer resolves proper-noun types against the real card-type set.
- **Case-insensitive verb/function terminals** (`V_DRAW`, `V_THIS`, …) with
  `\b` boundaries: MTG capitalizes the first word of each sentence, so
  literals like `"draw"` would miss `"Draw"`.
- **Atomic `card_target`**: the fields (`this_that / quantifier / otherness /
  nontoken / status_list / colors / possessive / card_kind / with_modifier /
  controller / in_zone`) are all optional and order-sensitive. E.g.
  `"all attacking creatures"` →
  `{quantifier:'all', status:'attacking', card_type:'creature'}`.
  A proper-noun subtype can prefix the noun inside `card_kind`
  (`"Zombie creature card"` → `card_type:'Zombie creature'`).
  For **performance** the 13 optional fields are grouped into three wrappers —
  `lead` (this_that/quantifier/otherness/nontoken), `core` (status_list/colors/
  possessive/card_kind), `zone_mod` (with_modifier/controller/in_zone) — which
  preserves the exact left-to-right order but stops the Earley chart from
  combinatorially exploding over 13 independent optionals. The interpreter
  finds each field **by name anywhere in the subtree** (recursive `_find_all`),
  so the grouping is invisible to the output.
- `~` (tilde) = the card itself → `{'kind':'this_card'}`.
- **Sentence types**: `activated` (`{T}: …`), `loyalty` (`[+1]: …`),
  `triggered` (`When/Whenever/As …, …`), `static`, `static_keyword`,
  `if` (conditional), `modal` (`Choose one`), `effect` (bare).
  Time-conditioned statics: `as_long`, `during`, `until`.

## Parser notes / caveats

- **Earley + `ambiguity='resolve'`**: the grammar is deliberately
  ambiguous (many optional fields, overlapping alternatives). Earley finds a
  parse when one exists and resolves ambiguity by preferring the parse that
  consumes the most input.
- **Rule-form optionals after a matched token are unreliable** in Earley —
  prefer terminal-level solutions or restructure. (E.g. the `JOIN` terminal
  `/,\\s*(then|and)\\b|\\bthen\\b|\\band\\b|,/` handles comma/`then`/`and`
  joins, which a rule-form `"," ("then"|"and")?` did not.)
- **Performance**: the original grammar hit **pathological Earley blowup** —
  a single keyword sentence took ~2 s and complex ones 30 s+ (≈ 2 h full
  run). The cause was `card_target`'s 13 independent optional *complex*
  fields: the Earley chart grew to ~1M items per sentence. Grouping them into
  the three `lead`/`core`/`zone_mod` wrappers (above) cut parse time ~20×
  (a keyword sentence is now ~0.1 s; full corpus ≈ 15–20 min at ~0.6 s/item).
  Greedy `CARDNAME+` as a standalone optional field was an earlier slowdown;
  type prefixes are folded into `card_kind` (tied to a required noun) for the
  same reason.
- **Sentence splitting is `~`-aware**: after name-normalization a card's name
  becomes `~` (a tilde, not an uppercase letter), so a period boundary like
  `"…has menace. ~ gets +5/+5…"` is only recognised as a new sentence because
  the splitter also treats `~` as a sentence-start (alongside uppercase and
  `(`). Periods inside double-quoted granted abilities are still not splits.

## Status

Coverage on the 1,665 segmented FDN sentences:

| round | coverage |
|---|---|
| initial baseline | 17.2 % |
| after case-insensitivity + atomic targets | 48.6 % |
| after sentence-structure + verb expansion | 69.3 % (full) |
| after Interpreter fix + pattern batches | 83.6 % (full) |
| after `card_target` performance fix + pattern batches | 89.9 % (full) |
| after token/deal-damage/counter/verb-terminal batches | 93.8 % (full) |
| after cast/spend/draw/search + event batches | 96.9 % (full) |
| after copy/return/exile/Ward/trigger batches | 98.4 % (full) |

The remaining ~27 failures (1.6 %) are all **unique** complex one-offs —
multi-clause effects with internal commas ("…put them onto the battlefield,
then shuffle"), nested X-defs, "for each / for each other" distributions,
"loses all abilities and is a X with base power and toughness 1/1" (the leading
greedy `card_target` over-consumes), and a handful of novel constructions.
They no longer share common sub-patterns, so further gains require
sentence-specific rules.
| after split/loyalty/`and-or`/`as-long-as` batches | **92.7 % (full, 1543/1665)** |

Remaining failures are a long tail of diverse patterns (complex returns,
"as long as … where X is …" definitions, multi-part emblems, custom keyword
clauses, "rather than" alternative costs, "separate into piles"). The strategy
is to keep targeting the highest-frequency patterns batch by batch.
