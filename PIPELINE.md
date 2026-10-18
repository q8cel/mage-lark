# Pipeline: how the pieces fit

What runs, in what order, on what data, and which caches it touches. Read this
before changing any module: most surprises here come from *which* of the three
parser configurations a caller uses.

```
                      setdata.load(path)
              items=(name, text, code), types, names, sets
                              │
                              ▼
             preprocess.segment(text, names)        names→`~`, strip reminders,
             [{text, modal, bullet}]                split lines → sentences
                              │
        ┌─────────────────────┼──────────────────────┬──────────────────────────┐
        │                     │                      │                          │
  (A) COVERAGE         (B) INTERPRETATION      (C) COREFERENCE              (D) OFFLINE LABELS
      run.py            demo_output.py,          refs.py + rulecoref.py        label_cases.py
                        interpret.interpret()                                   train_head.py
        │                     │                      │                        resolve.py
        ▼                     ▼                      ▼                          │
  Lark.parse            Lark.parse             anaphora.find_anaphors(text)      │
  keep_all_tokens=      keep_all_tokens=      + ptree.nodes(text)               │
    True                  False (API) /         ONE parse → spans + structure    │
                          True (demo)          (regex fallback per segment)      │
        │                     │                      │                          │
        ▼                     ▼                      ▼                          │
  parsed / failed      Interpreter.interp      refs.clean → refs.annotate        │
  + failures dump      → semantic dicts       rulecoref.resolve                 │
        │                     │                 → entities, status, rewrite      │
        ▼                     ▼                      ▼                          ▼
   coverage %          effect dicts           resolutions JSON            coref_dataset.json
                                              + rewritten_text            + ranker weights
```

## Stages

| # | stage | function | output | cache file |
|---|---|---|---|---|
| 1 | load | `setdata.load(path)` | `items (name, text, code)`, `types`, `names`, `sets` | `seg_<data>_<setdata>.pkl` |
| 2 | normalise + segment | `setdata.normalize_text` -> `preprocess.segment` | `[{text, modal, bullet}]` | `sent_<data>_<preprocess>_<setdata>.pkl` |
| 3 | parse | `Lark.open(grammar.lark, earley, ambiguity='resolve')` | tree | `parse_<grammarhash>.json` (coverage only: 1/0 per sentence) |
| 4a | interpret | `Interpreter.interp(tree)` | typed dicts (`effect`, `if`, …) | — |
| 4b | parse once | `ptree.nodes(text)` | records `{start, end, node, role, verb, predicate, in_condition}`, regex fallback per unparseable segment | `ptree_<grammarhash>.json` |
| 4b' | mention spans | `mentions.candidate_mentions(text, parser=True)` → `ptree.mentions` | `{surface, start, end}` (derived from 4b) | same as 4b |
| 4c | anaphor spans | `anaphora.find_anaphors(text)` | `{surface, start, end, kind}` | — (pure regex) |
| 4d | tree structure | `ptree.structure(text)` | `role` (subject/object), `verb`, `predicate`, `in_condition` | same as 4b (cache-read only, never parses) |
| 5 | inventory | `refs.clean` → `refs.annotate` | `+ head_type, number, definiteness, is_self, is_target, sentence, clause`, and `role`/`verb`/`predicate` when struct is supplied | — |
| 6 | resolve | `rulecoref.resolve(text, mentions, anaphors)` | entities, per-anaphor status, `rewritten_text` | — |
| 6b | resolve + re-parse (`--resolve`) | `resolve_pipeline.py`: rewrite -> `segment` -> `Lark` -> `Interpreter` | semantic dicts with the anaphora markers replaced by concrete mentions | — |
| 7 | label (offline) | `label_cases.py` → Qwen 27B on `:9000` | `coref_dataset.json`, `coref_standard.json` | `.cache/label_cases/` (prompt hash) |
| 8 | train (offline) | `train_head.py` | frozen MiniLM + tiny MLP | `enc_<model>_L<layer>.pkl` |

Stages 1–3 are shared. Stage 4 splits into three parallel consumers that do not
depend on each other.

## Text normalisation invariants (`setdata.normalize_text`)

One function produces every canonical text, and it has to satisfy two properties:

1. **Line breaks are preserved.** Oracle text puts one ability per line. Collapsing
   them merges `Trample, haste` with the `When this Vehicle enters, ...` trigger
   that follows, and the result parses as neither — measured as the single largest
   cause of parse failure for anaphora-bearing sentences (35 of 179 failures).
2. **The transform is exactly length-preserving**: a whitespace run becomes one
   space, or one newline where the line break was. Verified over all 10,446
   FDN+Standard cards: zero length changes, and the only differing characters are
   space -> newline (10,134). This is what makes a dataset upgrade a character
   swap (`upgrade_texts.py`) instead of a span remapping.

Anything that re-derives text must go through this function — several call sites
had the whitespace collapse inlined, which is how the two forms drifted apart.

## The three parser configurations (the main gotcha)

Same grammar, several `Lark` settings, and **no shared cache**:

| caller | `keep_all_tokens` | `propagate_positions` | what it can do |
|---|---|---|---|
| `ptree.py` — the coref path | **True** | **True** | mention spans **and** structure from one parse |
| `run.py` | True | False | coverage only (no spans) |
| `interpret.py` library API | False | False | typed dicts; anaphor becomes `null` |
| `demo_output.py` | True | False | typed dicts; anaphor becomes `{"ref":"anaphora"}` |

`ptree` replaced the earlier pair (`pmentions` with `keep_all_tokens=False` for
spans + `pstruct` with `True` for structure), which parsed every sentence twice.
Verified equivalent: both configurations produce **byte-identical mention spans**,
and `True` has the bonus that a bare pronoun keeps its span instead of collapsing
to an empty `card_target`. `pmentions.py` and `pstruct.py` are now thin shims.

Consequences that have bitten us already:

- `Exile it` → with `keep_all_tokens=False` the pronoun **disappears**: the tree
  yields an empty `card_target` and the dict says `{"card_type": null}`. With
  `True` it survives as `{"ref": "anaphora", "raw": "it"}` — still no *span*.
- The coverage cache stores only `1/0` per sentence, so it cannot be reused by
  anything that needs offsets.
- `pmentions` deliberately parses with `propagate_positions=True`, which is why
  it is slow (~25–40 s per long card) and why its cache matters.

Any new consumer must state which configuration it needs. Do not "reuse" the
coverage cache for structure.

## Where coreference sits

`rulecoref` is a **post-segmentation discourse pass, parallel to interpretation —
not downstream of it.** It runs on normalised text plus mention spans, and calls
the parser only to harvest mention spans (`card_target` / `player` / `token`
nodes with positions), never to read semantics.

Why not consume `interpret()` output:

1. **No offsets.** The resolver must rewrite text, build a mention graph, and
   enumerate *every* anaphor occurrence; `interpret()` reports anaphors only when
   the pronoun lands in a typed slot (`card_kind`), with no position at all.
2. **Dropped material.** Conditions (`if_sentence`) become `any_text` strings and
   modifier clauses are flattened (an `attached to that creature` clause arrives
   as a sibling `card_target`), so several anaphors never appear in the dicts.
3. **Config fragility.** Anaphor survival is a function of `keep_all_tokens`
   (see the table above), so depending on it would be depending on a flag.

### Current state: not wired in

Nothing in `run.py`, `interpret.py`, `demo_output.py` or `resolve.py` imports
`refs`/`rulecoref`; the only import is `train_head.py` reusing `gold_clusters`
for a shared metric. There is **no `--resolve` flag yet**. Today it is a
standalone CLI:

```bash
python refs.py --card "Fiery Annihilation"        # inspect the inventory
python rulecoref.py "Fiery Annihilation"          # resolve one card
python rulecoref.py "Fiery Annihilation" --json   # full JSON contract
python rulecoref.py --eval coref_standard.json    # dev: 3,403 teacher labels
python rulecoref.py --bench                       # test: 72 human gold
python rulecoref.py --eval X.json --ablate number,type
```

### Verified seam: resolution feeds the compiler (`--resolve`)

`resolve_pipeline.py` measures it; `demo_output.py --resolve` shows it:

```
python demo_output.py --data FDN.json --resolve "Fiery Annihilation deals 5 damage to target creature. ..."
python resolve_pipeline.py --data FDN.json --limit 158
```

Measured on all 158 FDN cards that contain an anaphor (269 occurrences):

| | before | after |
|---|---|---|
| anaphora markers in the semantic output | 57 | **7** |
| unparsed sentences | 28 | **28** (no regression) |
| cards rewritten | — | 92 / 158 |

Rewrite decisions: 121 edits applied, 49 reverted (the substitution broke that
sentence's parse), 23 skipped because the anaphor is *embedded* in a larger NP's
modifier (`from among them`), 52 possessive, 11 number-mismatch, 6 set-valued.

Two rules make this safe:

1. **per-sentence validation** — `rewrite_text(..., parse_ok=...)` reverts a
   sentence whose edit stops parsing, so a rewrite is only claimed if it compiles;
2. **slot gating** — an anaphor whose containing mention is much larger than the
   anaphor itself is skipped (`slot == "embedded"`); substituting an NP inside a
   modifier produces nonsense even when it parses.

Possessives (`its owner's hand`) and set anaphora (`the rest`) are never rewritten:
the grammar accepts only `its/their/...` in possessor position, and a set needs a
partitive ("the rest of the top five cards"), not a plain NP.

### The second integration seam (not built)

1. **Pre-parse rewrite** — `rulecoref` emits pronoun-free text, which is fed back
   through `segment` → `Lark.parse` → `Interpreter`. Verified on Fiery
   Annihilation: 3/3 rewritten sentences parse, 0 anaphors remain. This makes
   resolution *feed* the compiler.
2. **Post-parse annotation** — attach entity ids to the semantic dicts. Needs
   `interpret` to preserve anaphor spans (i.e. a single, documented parser
   configuration plus an offset field).

## JSON contract

`rulecoref.resolve(text, mentions, anaphors)` returns:

```jsonc
{
  "text": "...",
  "mentions": [ {"surface","start","end","src","head_type","number",
                 "definiteness","is_self","is_target","is_pronoun",
                 "sentence","clause","is_anaphor"} ],
  "entities": [ {"id": 1, "canonical": "target creature",
                 "spans": [ {"surface","start","end","is_anaphor"} ]} ],
  "anaphors": [ {"surface","start","end","kind","status","entity",
                 "antecedent": {"surface","start","end"} | null,
                 "canonical", "antecedent_src", "evidence", "candidates",
                 "set_valued", "op"} ],
  "rewritten_text": "..."
}
```

- `status` ∈ `resolved` | `ambiguous` | `no-resolution`
- `set_valued: true` + `op: "minus"` for collection anaphors (`the rest`): the
  entity named is the collection, and the resolution means "that collection minus
  the subset just singled out"
- `entity` is the cluster id (entity ids, not candidate indices — a correct
  answer that picked a different mention of the same object is still correct)
- `antecedent_src` maps back to the caller's own candidate numbering (used by
  the evaluator; `null` on the live path)
- `evidence` records which rules fired, for debugging

`refs.build(text, parser=True)` produces the `mentions` argument; any caller can
substitute its own list as long as it has `surface`/`start`/`end`.

## Evaluation protocol

| set | what it is | use |
|---|---|---|
| `coref_standard.json` | 3,403 teacher-labelled occurrences (dev) | iterate freely |
| `coref_benchmark.json` | 72 human-gold cases, 49 cards (test) | touch once per change |
| `test_coref.py` | 14 golden/characterization tests over the rules | run before committing |

Scoring is **entity-aware**: build a union-find over the gold labels and accept a
prediction if the picked mention shares a gold cluster with the gold antecedent.
Index-based scoring understates every method — 14% of gold antecedents have a
same-surface twin.

Known reference points (entity-aware, no leakage):

| method | dev | human bench |
|---|---|---|
| nearest mention | — | 56% |
| raw encoder attention (`resolve.py --eval`) | — | 67% |
| deterministic rules (`rulecoref`) | 72.9% | **79%** |
| frozen-encoder mention ranker (`train_head`) | — | 85% |
| teacher (Qwen 27B) | 89% | 88% |

## Caches

All under `.cache/`, all invalidated by a content hash of what they depend on.
Deleting the directory is always safe, never wrong — only slow.

| file | key | contents |
|---|---|---|
| `seg_<data>_<setdata>.pkl` | data + loader | `(items, types, names, sets)` |
| `sent_<data>_<preprocess>_<setdata>.pkl` | data + segmenter | segmented sentence list |
| `parse_<grammar>.json` | grammar | `sentence → 1/0` (coverage) |
| `ptree_<grammar>.json` | grammar + text | **one** record list per card text: spans + `role`/`verb`/`predicate`/`in_condition` |
| `pmentions_<grammar>.json` | grammar + text | **legacy, read-only** span cache being migrated away from |
| `enc_<model>_L<layer>.pkl` | model + layer | per-text hidden states (features) |
| `label_cases/` | model + prompt | teacher responses |

`pmentions.precompute(texts, workers)` fills the span cache in parallel; it is
eager (no progress until done) and the CPU cost is the Earley parse, so budget
~30–40 s per long card divided by core count.

## Rebuild status: done (drift 0)

The unified cache is built: **2,497 texts**, 78.5 min on 27 workers (~1 CPU-minute
per card text), and
`python ptree.py --verify` reports **0 drifting texts** against the legacy span
cache. Note the two traps the verifier caught:

1. Comparing only *parsed* spans produces false drift — the legacy cache never
   recorded whether a span came from the grammar or the regex fallback.
2. `pmentions` fell back to regex when a parse **succeeded but produced no
   mention node** (`If you do, that creature gains first strike…`). The merged
   module initially only fell back on exceptions, which silently dropped those
   mentions from the inventory. Fixed; `--rebuild-stale` re-parses just the
   affected texts (295 texts, 15 min) instead of the whole corpus.

Coverage after the rebuild:

| metric | value |
|---|---|
| texts with at least one parsed mention | 1,758 / 2,497 (70.4%) |
| texts parsed nowhere (regex fallback only) | 739 (29.6%) |
| mention records with `role`/`verb` | 37.9% |
| anaphors whose sentence yields structure | **48.2%** |

## Original rebuild instructions

`ptree`'s cache is empty right now, so the pipeline runs on the legacy span cache
(read-through, spans only) and structural rules are inert. Rebuilding is ~1 hour
of Earley on this host and invalidates nothing else:

```bash
python ptree.py --status                          # coverage of both caches
python ptree.py --build --data FDN.json           # FDN (~770 cards)
python ptree.py --build --sample coref_standard.json   # 2,141 dev cards
python ptree.py --build --sample coref_dataset.json    # 261 more
python ptree.py --verify                          # span drift vs legacy + structure coverage
```

`--verify` is the migration gate: it compares the new cache's mention spans
against the legacy span cache for every shared text and exits non-zero on drift,
then reports what fraction of mentions got a `role`, a governing `verb`, a
`predicate` flag and an `in_condition` flag. Run it before trusting the rebuild.

`--build` uses all cores minus one; `--workers N` overrides, `--limit N` does a
strided sample. Safe to interrupt: the cache is written at the end of each
`precompute` call, and a re-run only parses texts that are still missing.

Until then:

- `ptree.structure(text)` returns `[]` and never parses, so the evaluation path
  cannot silently spend 30 s per card.
- `rulecoref --structured-only` (which filters to cards with structure) returns
  an empty set; drop that flag for normal evaluation.
- The `drop-predicate-nominals` rule is inert, so expect dev ≈ 71.3% rather than
  the ~72.8% the pilot suggests is reachable.

After the rebuild, re-measure, then move to the subject-binding rule (possessive
`their library` → the clause subject), which is the remaining structural win.

## Ground rules

- The deterministic path must not import torch. `resolve.py` and `train_head.py`
  may; `refs.py`, `rulecoref.py`, `mentions.py`, `pmentions.py`, `anaphora.py`,
  `preprocess.py`, `setdata.py` must not.
- Every new stage is JSON-in / JSON-out so it can be ported (C++/Rust/Go).
- Surface heuristics for syntactic role have been measured and **fail** — see
  `DETERMINISTIC-COREF.md` §4. Structural decisions need the tree, not a scan.
- Structural features are *optional*: `rulecoref` looks up `pstruct`'s cache and
  silently runs without them if a text is not cached. It never triggers a parse
  on the evaluation path — rebuild the cache explicitly
  (`python pstruct.py --sample coref_standard.json --limit 240`).
