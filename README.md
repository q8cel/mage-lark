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
python quick_test.py -n 150        # ~2-4 min sampled coverage (fast iteration)
python test_parse.py --dump failures.txt   # full corpus (~40 min, source of truth)
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
- **Atomic `card_target`**: `quantifier status_list? colors? possessive?
  card_kind? modifier? controller? zone?`. E.g.
  `"all attacking creatures"` →
  `{quantifier:'all', status:'attacking', card_type:'creature'}`.
  A proper-noun subtype can prefix the noun inside `card_kind`
  (`"Zombie creature card"` → `card_type:'Zombie creature'`).
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
- **Performance**: the grammar's size + ambiguity makes Earley ~1.2–1.5 s /
  sentence (full corpus ≈ 40 min). Greedy `CARDNAME+` as a standalone
  optional field was a major slowdown; type prefixes are therefore folded
  into `card_kind` (tied to a required noun) to keep the search space small.
  `quick_test.py` (sampled) is for fast iteration; `test_parse.py` is the
  source of truth.

## Status

Coverage on the 1,665 segmented FDN sentences:

| round | coverage |
|---|---|
| initial baseline | 17.2 % |
| after case-insensitivity + atomic targets | 48.6 % |
| after sentence-structure + verb expansion | 69.3 % (full) |
| after atomic-decomposition fix (Interpreter) + pattern batches | ~80–88 % (sample; full run in progress) |

Remaining failures are a long tail of diverse patterns (complex returns,
"as long as … where X is …" definitions, multi-part emblems, custom keyword
clauses, "rather than" alternative costs, "separate into piles"). The strategy
is to keep targeting the highest-frequency patterns batch by batch.
