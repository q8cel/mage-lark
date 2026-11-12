# Deterministic anaphora resolution — design analysis

Status: implemented in `rulecoref.py` / `refs.py`. This document keeps the
original design analysis and measurements; the numbers below are historical
unless marked current. Everything is measured against the teacher-labelled
anaphor occurrences in `coref_standard.json`, using the existing `mentions.py` /
`anaphora.py` inventory. No model, no LLM.

**Current state (2026-11-12):** the canonical harness is `coref_eval.py`; it
scores entity-aware clusters over a fixed candidate pool shared by every
resolver. The measured numbers, the commit history, and the known label
inconsistencies are in the section below. Everything after it is the historical
design analysis unless marked current.

## Current state (2026-11-12, measured)

**Corpus.** `data/coref_standard_v2.json` is the honest evaluation set. It
repairs 18 label indices (15 became correct), marks 28 unreconstructible or
ambiguous cases to be skipped with `--exclude-cataphora`, and leaves the
original `coref_standard.json` untouched for continuity. All numbers below use
the current grammar-hash ptree cache (see the cache note at the end).

| run | entity | exact | resolved | no-resolution | ambiguous |
|---|---:|---:|---:|---:|---:|
| v2 `--exclude-cataphora` baseline | 3,102/3,352 = 92.5 % | 2,906 = 86.7 % | 3,497 | 109 | 63 |
| **v2 `--exclude-cataphora` final (primary)** | **3,141/3,352 = 93.7 %** | **2,947 = 87.9 %** | **3,500** | **109** | **60** |
| v1 baseline (continuity) | 3,087/3,380 = 91.3 % | 2,891 = 85.5 % | 3,524 | 109 | 64 |
| v1 final (continuity) | 3,125/3,380 = 92.5 % | 2,931 = 86.7 % | 3,527 | 109 | 61 |

The v2 run excludes 28 marked cases; 4 gold spans remain unscoreable. Total
movement is **+39 entity, +41 exact** on v2 and +38/+40 on v1; status moves
**+3 resolved, −3 ambiguous, no-resolution unchanged**, so no abstention was
traded for guesses.

**Resolver commits (each measured with the full cache; v2 entity/exact deltas).**

| commit | class | change | delta |
|---|---|---|---:|
| `9c58134` | wrong pick | `among them` / `the rest` bind the source collection, not an enumerated subset | +10 / +11 |
| `1fe91c5` | wrong class | verb/predicate priors: damage-to-`them`→player, counter-on-object, target-trigger self, `gained control`→player, `as though they had flash`→spell/card | +11 / +12 |
| `fa9cbf9` | possessive | copy-exception `its other types` binds the new token; `enter tapped as a copy` binds self | +5 / +5 |
| `e55f43b` | wrong pick | match the word `token`, not the substring in `nontoken` (copy-source self-binding) | +2 / +2 |
| `bfb5c63` | possessive | `its owner` follows the object moved by `return`/`put` | +4 / +4 |
| `d0246b0` | wrong class | `its mana cost` binds the object of the last `cast` verb | +4 / +4 |
| `c40371f` | possessive | `their mana costs` / `their total power` bind the named plural spells/creatures | +3 / +3 |

**Known gold inconsistencies — do not chase these without repairing the labels.**

- **Reveal-from-among coordinated lists.** `put it into your hand` after
  `reveal … from among them` is labelled the top-X collection only when the
  revealed NP is a coordinated type list (`a Goblin, Swamp, or Mountain card`);
  the identical single-type shape (`a creature card with power 3 or less`) is
  labelled the revealed card. Same semantics, two conventions.
- **`if it's not their turn`.** Adrenaline Jockey and Eddymurk Crab are golded
  the spell/self; March of the World Ooze and Scytheclaw Raptor are golded the
  player. A uniform resolver rule is not a net win.
- **Equipment `in addition to its other types`.** White Mage's Staff, Sage's
  Nouliths and Black Mage's Rod gold `creature` (Equipped creature), while Red
  Mage's Rapier and Thief's Knife gold the quote-internal `this creature`.
  A uniform subject rule breaks a currently correct case.
- **`This X becomes … Put a counter on it`.** Gold alternates between the self
  (`this Vehicle`: Rocketeer, Marshals' Pathcruiser, Invasion Submersible) and
  the predicate (`an artifact creature`: Rangers' Refueler, Spire Mechcycle).
- **Duplicate-token / source-vs-copy.** Vaultborn Tyrant has two same-surface
  `a token` spans (gold is the earlier condition token); Mockingbird's gold is
  the copied source while the golden test asserts the copy/self for the
  identical Phantasmal Image shape; Cloning of Shredder and The Apprentice's
  Folly contain same-surface token spans; copy-token exceptions are labelled
  token for Molten Duplication/Saheeli/Ember Island but source for Nexus of
  Becoming/Applied Geometry.
- **Bench is a dev subset, not held-out.** 48/49 bench cards occur in dev and
  68 of 71 labelled cases are literally shared; only 3 are unique. Smoke only:
  regex 67/71 entity (94.4 %), 60/71 exact; parser 66/71 (93.0 %), 60/71 exact.
  The single regex entity difference is Genesis Wave: dev/teacher gold is
  `the top X cards`, bench human gold is `any number of permanent cards`.

**ptree-cache requirement for the golden suite.** `tests/test_coref.py` skips
every card-based test (27 of 41, leaving 14 parser-free tests) when the current
grammar hash has no `ptree_<grammarhash>.json` and no legacy
`pmentions_<grammarhash>.json`. With the cache present the suite is **41/41
passed, 0 skipped** (~23 s). Build it with:

```bash
python core/ptree.py --build --data FDN.json --workers 10          # 251 s, 501 texts
python core/ptree.py --build --sample coref_standard.json --workers 10
                                                                   # 1,155 s, 1,984 new texts
```

The 20 non-FDN golden-test cards (`classic.json`/`Standard.json`) were
precomputed directly (20 texts / 38 new sentences, 43 s); alternatively build
`--data classic.json` and `--data Standard.json`. Current cache sizes:
`ptree_8f294968de.json` 1,164,012 B, `psent_8f294968de.json` 1,180,501 B.

**Does the evaluator depend on that cache?** The candidate pool comes from the
dataset's stored candidates and does not use ptree. `rulecoref.resolve` reads
`ptree.peek` for structural fields, but only `role` is consumed, by the
possessive-role family. A missing cache therefore makes those rules inert; all
other rules are text/mention based. Before/after pairs were always measured in
the same cache state, so the deltas are comparable; the absolute full-cache
baseline above is the one to use.

---

## 1. What the parser actually gives us (Fiery Annihilation)

```
~ deals 5 damage to target creature. Exile up to one target Equipment attached
to that creature. If that creature would die this turn, exile it instead.
```

Parse of S1 (`Exile up to one target Equipment attached to that creature`):

```
exile_action
  Exile
  card_target            <-- the effect's object
    lead  -> quantifier: up to one, target
    core  -> card_kind: types Equipment
    zone_mod
  card_target            <-- "attached to that creature", parsed as a SIBLING
    lead  -> this_that: that
    core  -> card_kind: types creature
```

Parse of S2 (`If that creature would die this turn, exile it instead`):

```
if_sentence
  If
  any_text               <-- the whole condition, unanalysed tokens
    that creature would die this turn
  effect
    exile_action
      exile
      card_target
        lead                  <-- EMPTY
        core -> card_kind     <-- EMPTY
        zone_mod
  instead_suffix
```

### Loss 1 — the anaphor survives only as a bare token, and only in some configs

Whether a pronoun reaches the semantic dict depends on `keep_all_tokens`, and the
tree uses **three different settings** (see docs/PIPELINE.md):

| entry point | `keep_all_tokens` | `Exile it` becomes |
|---|---|---|
| `interpret.interpret()` (library API), `pmentions` | **False** | `{"card": {"card_type": null}}` — pronoun gone |
| `run.py`, `demo_output.py` | True | `{"card": {"card_type": {"ref": "anaphora", "raw": "it"}}}` |

Raw tree diff for the same sentence:

```
DEF 'Exile it' -> ... | exile_action | Exile | card_target | lead | core | card_kind | zone_mod
ALL 'Exile it' -> ... | exile_action | Exile | card_target | lead | core | card_kind | it
```

So the loss is a **config inconsistency**, not a grammar property. But even in the
`True` configuration the survivor is only the raw string `"it"`: there is no
character **span**, and `Interpreter` reports anaphors only when the pronoun lands
in a typed slot (`card_kind`), so `Nine-Lives Familiar`'s six `it` occurrences
collapse to one node.

**Consequence:** a resolver cannot work off `interpret()` output, because it
needs offsets (to rewrite the text, to build the mention graph, and to enumerate
*every* occurrence rather than only the slot-typed ones). It must read
`(normalised text, parse tree with positions)`. Fixing the config so every call
site keeps tokens is still worth doing, but it is orthogonal.

### Loss 1b — `interpret.interpret()` also mangles one modifier form

```
DEF "Return it to its owner's hand" -> {"verb": "return", "card": {"card_type": null},
                                        "to": "Return"}        <-- stray value
ALL "Return it to its owner's hand" -> {"verb": "return", "card": {..."it"},
                                        "to": "Return to its owner's hand"}
```

Not used by the resolver, but it is a real interpreter bug worth an issue.

### Loss 2 — modifier clauses are dropped

`attached to that creature` becomes a **sibling `card_target`** of the exile
action, and `interpret()` keeps only the first one. The mention is still
recoverable from the tree, but the *attachment relation* is lost, so "that
creature" cannot be bound to "the thing this Equipment is attached to" — only to
"the most recent creature", which happens to be right here.

### What the inventory looks like

```
C[0]   0-  1  '~'                            (self)
C[1]  20- 35  'target creature'              creature, target
C[2]  43- 69  'up to one target Equipment'   equipment, up-to-one target
C[3]  53- 69  'target Equipment'             equipment  <-- nested in C[2]
C[4]  82- 95  'that creature'                creature   <-- anaphor 0
C[5] 100-113  'that creature'                creature   <-- anaphor 1
A[0]  82- 95  'that creature'  demonstrative
A[1] 100-113  'that creature'  demonstrative
A[2] 141-143  'it'             pronoun
```

---

## 2. The processing model I would build

Five stages, all deterministic, all JSON-in/JSON-out, no torch.

### Stage 1 — Mention inventory (must be cleaned)

Inventory quality is not a detail, it is the single biggest deterministic win
measured so far (see §4). Rules:

- span maximality: drop any candidate strictly contained in another
  (`target Equipment` ⊂ `up to one target Equipment`)
- dedupe identical spans; keep one entry per span
- drop bare determiners and other junk (`target`, `that`, `the`)
- attach, per mention: `head_type`, `number`, `definiteness`, `is_target`,
  `is_self`, `sentence_index`, `clause_id`, `role` (subject / object / modifier /
  possessor)

### Stage 2 — Entity aliasing (anaphors become mentions of an entity)

Once an anaphor is resolved, its span enters the inventory as an **alias** of the
antecedent entity. Later anaphors can chain through it. Without this,
"that creature" in S2 resolves to the *anaphor* "that creature" in S1 rather than
to the entity, and the chain is only accidentally right.

Entity = {set of spans that co-refer}. Resolution output should be
"entity id", not "candidate index".

### Stage 3 — Compatibility filter (hard constraints, applied first)

| filter | rule |
|---|---|
| self-exclusion | the anaphor's own span never a candidate |
| precedence | antecedent must start before the anaphor (0 cataphora in 3,403 labels) |
| number | `it/its/itself` → singular; `they/them/their/themselves` → plural |
| type lattice | `creature` ⊆ `permanent` ⊆ `card`/`object`; `equipment` ⊆ `artifact` ⊆ `permanent`; `spell`, `player/opponent`, `token` |
| non-entity | `counter`, `amount`, `pile-of-N` never candidates for a pronoun |

### Stage 4 — Scoring cascade (soft preferences, in order)

1. **same-clause object binding** — `its owner / its controller / its power`
   binds to the object NP of the governing verb in the same clause. 257
   occurrences in the Standard set. This is a rule, not a preference.
2. **self-reference** — if the anaphor's clause has `~` / `this <type>` as its
   subject (or the clause is an ability of the card itself), and the predicate is
   self-directed (`dies`, `leaves the battlefield`, `attacks`), prefer self.
3. **verb/type prior** — `would die` → permanent; `cast`/`counter` → spell;
   `attach` → equipment/aura; `sacrifice` → permanent you control;
   `exile`/`return`/`mill` → any card. Narrows the pool before recency.
4. **definiteness match** — `that player` → most recent *opponent*;
   `the token` → most recent token; `that spell` → the spell on the stack.
5. **recency** — nearest preceding compatible mention (rank-1 = 57.5%,
   ≤3 = 96.5%).
6. **scope barrier** — never cross a modal bullet boundary (`•`) or a
   `Choose one —` branch; prefer same sentence; allow cross-sentence only when
   the current sentence has no compatible mention.

### Stage 5 — Set-valued anaphors

`the rest`, `the other`, `those cards`, `each of them` resolve to a **set**, not
one mention:

```
the rest := <collection NP> − <the subset just singled out>
```

e.g. "Look at the top five cards of your library. Put one into your hand and the
rest on the bottom" → `the rest` = `the top five cards` − `one`.
Current accuracy on `kind=phrase`: **19%** (96 cases) — it is a missing rule, not
a hard problem.

---

## 3. Walkthroughs

### Fiery Annihilation (easy, and it needs 3 rules)

| # | anaphor | first candidate | resolution |
|---|---|---|---|
| A[0] | `that creature` (in "attached to …") | type=creature → C[1], C[3] excluded (equipment) | **target creature** |
| A[1] | `that creature` (in "If … would die") | C[4] is an alias of target creature | target creature |
| A[2] | `it` (in "exile it instead") | nearest entity = C[5] → alias | target creature |

Note what each rule contributes: type filter (A[0]), aliasing (A[1]), recency
(A[2]). Pure "nearest mention" gets A[0] wrong (nearest is `target Equipment`)
only if the type filter is absent; it gets A[1]/A[2] right by luck.

### Harder cases and the rule that carries them

| card text fragment | trap | deterministic rule |
|---|---|---|
| `Put a +1/+1 counter on target creature. It gains flying.` | nearest mention is the counter | non-entity filter (counters never antecedents) |
| `Return target creature to its owner's hand.` | `its` = the returned creature | same-clause object binding |
| `Destroy target creature. Its controller creates a Treasure token.` | `its` = the creature, not "target creature" only | possessive → governing object; then `.controller` projection |
| `Each opponent sacrifices a creature. They draw a card.` | `they` = opponents, not `a creature` | number agreement (plural pool ∖ singular mentions) |
| `This creature deals damage equal to its power to target creature.` | `its` = self, even though `target creature` follows | possessive in subject-side phrase → clause subject |
| `Exile target creature you control, then return that card to the battlefield.` | `that card` = the exiled creature (zone change) | head-type lattice: creature ⊂ card |
| `Look at the top five cards. Put one into your hand and the rest on the bottom.` | set difference | set-valued rule (§2 stage 5) |
| `Mill two cards. You may put a creature card from among them onto the battlefield.` | `them` = the milled cards | set-valued + `from among them` binds to the collection NP |
| `Choose one — • Exile target creature. • Return target creature to its owner's hand.` | no resolution across branches | modal scope barrier |
| `Exile target artifact or creature. Its controller …` | disjunctive head type | object binding wins over type |

### Where determinism genuinely runs out

- Two compatible mentions in the same clause with no syntactic asymmetry:
  `Target creature you control deals damage to target creature you don't control.
  If that creature would die …` — MTG convention is last-mentioned, and recency
  gets it, but it is a convention, not a proof.
- Anaphora whose antecedent is only identified by *game semantics*
  (`it` = "the permanent that was exiled this way"), when several permanents
  were exiled as a batch. Recency picks one; truth is a set.
- Replacement/triggered-effect stacks where the antecedent lives in a
  conditional branch that was never taken.

These are the cases where a statistical backoff earns its place — and they are a
minority, which is the whole point.

---

## 4. Measured evidence (3,403 teacher labels, `coref_standard.json`)

### How shallow is the problem?

Rank of the gold antecedent among preceding **mentions** (raw candidate list):

| rank | share | cumulative |
|---|---|---|
| 1 (nearest) | 57.5% | 57.5% |
| 2 | 29.9% | 87.4% |
| 3 | 9.1% | 96.5% |
| 4+ | 3.5% | 100% |
| cataphoric (after the anaphor) | **0.0%** | — |

Rank of the gold antecedent among preceding **entities** (mentions clustered by
the teacher labels, i.e. an anaphor's own span is not a new entity):

| rank | share | cumulative |
|---|---|---|
| 1 (nearest entity) | **67.2%** | 67.2% |
| 2 | 24.1% | 91.3% |
| 3 | 6.6% | 98.0% |
| 4+ | 1.9% | 100% |

Avg 3.6 mentions but only 3.3 entities per card. Recency over *entities* is ~10
points better than over mentions — an anaphor must never count as its own
antecedent's competitor. Nothing looks forward, and 98% of answers are within
the last three entities. This is a shallow, local ranking problem, not a
discourse problem.

### Inventory is dirty, and cleaning it is worth more than a model

7,797 candidates over 2,141 cards (3.6/card): **8% nested** inside another
candidate, **10% duplicate surface within the same card**, 34 bare determiners.
14% of gold antecedents have a same-surface twin (so index-based scoring
understates every method, the neural head included).

### Rule cascade, dirty inventory (index scoring)

| rules | accuracy |
|---|---|
| nearest preceding mention | 56.7% |
| + drop counters/non-entities | 59.9% |
| + number agreement | 62.6% |
| + demonstrative head-type compatibility | 64.0% |

### Cascade over entities, cleaned inventory, **with oracle aliasing**

> Caveat: these numbers cluster mentions using the *gold* labels, so anaphor
> chaining is perfect. They are an upper bound, **not** achievable by a system
> that has to cluster from its own predictions. See "Implemented (v1)" below for
> the leak-free numbers.

n = 3,284 (historical: 119 gold sub-spans were treated as absorbed; the current
harness maps them to the containing maximal mention).

| rules | accuracy |
|---|---|
| nearest preceding **entity** | 68.3% |
| + number agreement | 72.3% |
| + type compatibility | **75.3%** |

For reference, the same cascade over raw candidates on the cleaned inventory
scores 71.7% (index) / 76.9% (surface-normalised), and per anaphor kind by
surface match: pronoun 80%, demonstrative 73%, phrase ("the rest") 19%.

Three rules, ~40 lines, no model: **75.3%** with oracle aliasing. The neural
mention-ranker's 80% was measured on the *uncleaned* inventory with *index*
scoring, so the two numbers are not directly comparable.

### Two heuristics that do NOT work (measured)

| rule | result |
|---|---|
| "a self mention (`~`/`this X`) in the same sentence wins" | 75.3% → **70.8%** (over-predicts self) |
| "same-sentence entity preferred" | 75.3% → **70.8%** |
| verb/type prior (`die`→permanent, `cast`→spell, ...) | 71.3% → **70.5%** |

All three need the clause's **syntactic role** (which NP is the subject, which
verb actually governs the anaphor), not a surface scan of the clause. Do not
ship the surface versions. The verb prior is implemented and left *off* by
default (`--ablate` can enable it for experiments).

---

## 4b. Implemented (v1) — measured, leak-free

`refs.py` (inventory) + `rulecoref.py` (cascade). Rules that ship:

1. inventory cleaning (maximal spans, dedupe, no bare determiners)
2. self-exclusion + strict left-to-right precedence
3. number agreement
4. entity-type lattice (demonstratives only)
5. counters are not entities (pronouns)
6. same-clause object binding for `its owner / its controller / its power`
7. recency, then entity clustering from the system's own predictions

| measurement | value |
|---|---|
| dev: 3,395 teacher labels, entity-aware | **73.0%** |
| human bench: 71 resolvable cases, entity-aware | **79%** (56/71) |
| nearest-mention baseline (same protocol) | 56% |
| raw encoder attention | 67% |
| frozen-encoder mention-ranker (same protocol) | **85%** (61/72) |
| teacher (Qwen 27B) | 88% |

Per anaphor kind (dev): pronoun 73%, demonstrative 71%, `the rest` **90%**
(set rule, see §4c).

Status mix on dev: 94.5% resolved, 5.0% ambiguous, 0.5% no-resolution. Of the
294 occurrences the teacher marked "no antecedent", the rules abstained on 69.

Residual (dev): 615 type mismatch, 231 wrong pick with the same type, 119 gold
spans absorbed by cleaning. The type-mismatch bucket is where the 12-point gap
to the neural head lives: it needs **syntactic role**, i.e. the parse tree —
which is exactly why the surface verb prior above does not close it.

### 4c. Set-valued anaphora - implemented

`the rest` does not denote a mention; it denotes *a collection minus the subset
just singled out*. The shipped rule (`set_rest` in `rulecoref.py`):

1. a set anaphor has **no number agreement**, so the number filter is skipped
   (without this, `the rest` was pushed into singular candidates),
2. the antecedent is the most recent preceding **plural collection NP**
   (a mention with `number == pl` and a head noun),
3. the result is flagged `set_valued: true, op: "minus"` — additive to the
   contract, so consumers that ignore it are unaffected.

| metric | before | after |
|---|---|---|
| `the rest` (96 occurrences) | 31/96 = 32% | **86/96 = 90%** |
| dev overall | 71.3% | **72.9%** |

Set support is deliberately single-hop: the output names the *collection* and the
subtraction, not the resulting membership (that needs the game state, e.g. "the
top five cards" minus "the one you put into your hand").

### 4d. Where the remaining parse failures are

A census over 400 sampled anaphor-bearing dev sentences (current grammar, after the
line-break fix): **165 fail (41%)**, and the failures are *flat-weighted* — each
exact sentence accounts for 1-2 anaphor occurrences. Clustering by pattern instead
of exact text is what makes them actionable:

| pattern | count (of 179 pre-fix failures) | cause |
|---|---|---|
| keyword blob (`Trample, haste When this ...`) | 35 | **fixed**: line breaks are now preserved |
| `until end of turn` | 20 | grammar (/`become` + multi-word types) |
| `each player / each opponent` | 20 | grammar |
| `counters on it/them` | 18 | grammar |
| `you may cast` | 11 | grammar |
| mid-sentence `•` bullets | 10 | **fixed** by the same line-break change |

After the line-break fix the fail rate went 45% -> **41%**, i.e. 179 -> 165 of 400.
The six rules added in the same round (become-until-end-of-turn with multi-word
types, fight each other, until-your-next-end-step / at-the-beginning timing, suspect,
search-...-with-that-name-and-exile-them) each fix 1-3 sentences, with 0 regressions
on a 143-sentence frequency sample.

After the parse-speed fix (become_action; see docs/PIPELINE.md) and the line-break fix
the numbers moved to: dev sentences 54.3% parse, anaphors with structure **58.0%**
(was 48.2%), mention records with a role 48.0% (was 37.9%). Coverage keeps improving,
but the structural rules still do not: with structure at 58% the lexical verb prior
is still negative (72.2% vs 73.0%) and `drop-predicate-nominals` is still inert.

**Implication for planning:** grammar coverage is no longer what limits coreference
accuracy - the parse tree buys 1 bench case. It is a product goal (parsing cards), not
a coref-accuracy goal. The frequent patterns are also gone (master's 12 commits
ate them); what remains is a long tail. Grammar work now fixes a handful of
occurrences per rule, so rules must be batched and gated, and the payoff per turn is
measured in a few tenths of a point of structure coverage.

### 4f. Three resolver bugs found by auditing the bench misses

Dumping each miss with its candidate pool and fired evidence (instead of just the
final answer) exposed bugs, not missing rules:

1. **Pronoun number.** `number()` fell back to "ends with s -> plural", so `its` was
   plural and every singular possessive was filtered against plural candidates.
   Pronouns now carry their number explicitly.
2. **Distributive determiners.** The fix above reordered the checks so `head_type`
   short-circuited before the determiner test: `Each player` became singular, which
   broke "Each player ... their library". Determiners (`each/every/all/those/these`)
   are now checked first.
3. **Type lattice direction.** `type_compatible('card','creature')` was False (a
   creature mention could not be "that card") while `type_compatible('creature',
   'card')` was True (a generic card could be "that creature"). Unknown-type
   mentions (a bare `You`) also satisfied any requirement. The filter now prefers
   typed candidates and accepts either direction (`--type-mode`).

Plus two rules from the same audit:

- **possessive role from the introducing phrase** (corpus-derived over 755
  possessives — `of their choice`, `equal to its power` -> subject;
  `under its owner's control`, `into their graveyard` -> object);
- **argument type**: `put a counter on it` requires a permanent (a player cannot
  take counters), and `except it ...` inside a copy-token clause binds to the token.

- **quoted granted abilities**: `target creature gains "When this creature dies,
  return it ..."` - an anaphor inside the quote belongs to the ability's own scope,
  and if that scope has no mentions it belongs to the *recipient* of the grant. The
  subtler half: a `this X` mention inside a quote is **not** a self-reference to the
  card, so it must be aliased to the recipient instead of being unioned into the
  card's entity. That single aliasing bug was making both Fake Your Own Death
  anaphors resolve to the card.

The audit also exposed a harness bug: `--ablate` never reached the benchmark path
(it called `resolve()` without `rules`), so earlier bench ablations were silently
comparing a rule against itself. Fixed; every number above is now ablation-checked.

| | before | after |
|---|---|---|
| dev (3,395) | 73.0% | **77.3%** |
| human bench (71) | 77% | **97%** (69/71) |
| per kind | pronoun 73 / demonstrative 71 / rest 90 | 73 / **79** / **93** |

### 4g. Where dev and human labels disagree (and why that caps agreement)

Adjudicating the last bench misses turned up a systematic disagreement. In a
*replacement* effect the anaphor usually refers **into the condition**, and the teacher
labels that correctly while a plausible-looking rule finds it counter-intuitive:

| card | text | correct antecedent |
|---|---|---|
| Tishana's Tidebinder | "If an ability of an artifact, creature, or planeswalker is countered this way, **that permanent** loses all abilities" | `an artifact` (inside the condition) |
| Celestial Reunion | "If ... the revealed card is the chosen type, put **that card** onto the battlefield" | `the revealed card` (inside) |
| Innkeeper's Talent | "If you would put counters on a permanent or player, put ... on **that permanent or player** instead" | `a permanent or player` (inside) |
| Tragic Banshee | "target creature ... gets -1/-1. If a creature died this turn, **that creature** gets -13/-13 instead" | `target creature an opponent controls` (the card's target) |

I implemented a "conditional scope" rule (prefer antecedents outside an `If ... ,`
clause) and measured it: **+1 bench case, -6 dev occurrences**, and the per-case audit
showed it fixed 0 and broke 6 — because three of those six are cases where the rule is
simply wrong. It was removed. Tragic Banshee remains the one bench case where the
human label and the teacher label are irreconcilable by any single rule.

Two practical consequences:

- dev accuracy (teacher labels) and bench accuracy (human labels) cannot converge: the
  teacher is wrong on some of exactly the constructions that are hardest, so dev
  **understates** the resolver and is not a clean optimisation target.
- a benchmark label that disagrees with the resolver is not automatically a resolver
  bug. `Genesis Wave`'s `them` ("put ... from among **them**") refers to the revealed
  top X cards, which is what the resolver returns; the gold points at the subset being
  put onto the battlefield. That label is left untouched pending a second annotator,
  rather than edited to match my own output.

### 4h. The measurement instrument (and why dev understates the resolver)

Three label sources exist, and they are not interchangeable:

| set | size | labels | what it measures |
|---|---|---|---|
| `coref_benchmark.json` | 72 (71 resolvable) | human | correctness |
| `coref_standard.json` (dev) | 3,380 labelled occurrences / 2,141 cards | teacher (Qwen 27B) | agreement with the teacher |
| FDN dataset | 261 cards | teacher | same |

**Correction (2026-11-12): the bench is a dev subset, not a held-out
benchmark.** Matching `(card, text, anaphor span)` across the `coref_eval --dump`
records found 49 unique bench cards / 72 rows, of which 48 cards, 71 rows by
card and 69 rows by normalized text also occur in dev; **68 of the 71 labelled
bench cases are exactly the same occurrence as a labelled dev case**, leaving
only 3 unique bench cases. On those 68 shared cases the human and teacher gold
surfaces agree on 49 (19 differ), which is the known annotator gap. Dev is built
from `Standard.json`, whose bundle includes the `FDN` set used by the bench, so
dev and bench are not separate corpora: the bench cannot measure
generalization, and a dev-tuned fix will move it almost automatically.

**Label-index repair (`coref_standard_v2.json`, 2026-11-12).** Of the 289 dev
misses, 46 were label/index artifacts rather than resolver failures (31
cataphoric/gold-after-anaphor + 15 duplicate-same-surface). `coref_standard_v2.json`
repairs 18 where an earlier mention of the same entity exists (15 now agree with
the resolver; 3 remain genuine misses), keeps the one true forward reference but
marks it excluded, and marks 27 as excluded (`exclude: "label"`) because no
single earlier mention is reconstructible (missing inventory, set-valued, or
ambiguous duplicate). The original `coref_standard.json` is untouched.
Corrected dev numbers with `--exclude-cataphora`: **92.7 % entity-aware / 86.8 %
exact on 3,352 labels**; split: resolved 3,497, no-resolution 109, ambiguous 63,
excluded 28, teacher `no antecedent` 317. Without exclusions (repairs only) v2 is
**91.9 % / 86.0 % on 3,380 labels**. The corrected headline is +1.3 pp over the
old 91.4 %, and the fixers should be measured against v2.

The historical 70-case overlap is superseded by the exact-occurrence count above; on those shared cases three things can be scored:

| on those 70 cases | score |
|---|---|
| teacher vs human gold | 89% (62/70) |
| **resolver vs human gold** | **97%** (68/70) |

So dev = 77.3% does not mean the resolver is 77% correct: it agrees with an
89%-accurate annotator on a harder distribution. Optimising dev means converging on
the teacher, i.e. shedding the advantage.

Part of the remaining gap is bookkeeping, not error. Strict scoring counts "the teacher
picked a different mention of the same object" as a miss, and the evaluator now reports
both:

| dev scoring | score |
|---|---|
| strict (mention-index within the teacher's cluster) | 77.3% |
| **soft** (the teacher's mention lies inside the entity we bound) | **81.5%** |
| gold spans dropped by our inventory cleaning (counted as misses) | 119 (3.5%) |
| teacher said "no antecedent" (excluded from the denominator) | 302 |

The soft/strict gap (4.2%) is dominated by one systematic difference: our canonical
mention keeps the quantifier (`up to one target creature`) where the stored teacher
label is the shorter span (`target creature`). Those are the same object and our form is
arguably more complete, so the strict number understates the resolver by roughly
4-8 points depending on how the cleaning losses are counted.

**Can a better local annotator fix that?** Tested with an ensemble of three runs of the
same model (reasoning `low`, `high`, and a step-by-step prompt) on the bench:

| annotator | vs human gold (surface scoring) |
|---|---|
| `low` | 85% |
| `high` | 87% |
| `step` | 88% |
| majority of 3 (>=2 agree) | 91% |
| **majority, entity-scored** (same metric as the resolver) | **97%** |
| unanimous subset (3/3), entity-scored | **98%** |

Surface scoring penalises "a different mention of the same entity" (`it` -> `that
creature` when the entity *is* `target creature`); under the resolver's own
entity-aware metric the ensemble reaches the resolver's level, and unanimity is
slightly better (58/59, the single error being the disputed Genesis Wave label).

Conclusions that follow, and that shape the next step:

1. **No local ensemble exceeds the resolver**, so no local annotator can serve as the
   yardstick for it. Only human adjudication can raise the instrument above 97%.
2. **Unanimity is the best local confidence signal** (~98%): cases where all three
   annotators agree can be used as labels, and the rest are exactly the cases worth a
   human's attention.
3. Reasoning helps on semantic cases (it fixed the `the rest` set case, pile
   references and a condition-scope case) but **not** on the granted-ability idiom,
   which the resolver now gets right - further evidence that the resolver encodes
   MTG-specific knowledge the teacher lacks.

**Stratified sample.** `strat_sample.py` draws from dev across anaphor kind x
whether the sentence yields parser structure, because the distribution is skewed:

| stratum | occurrences |
|---|---|
| pronoun + structure | 1,601 |
| pronoun, no structure | **1,051** |
| demonstrative + structure | 369 |
| demonstrative, no structure | 278 |
| "the rest", no structure | 71 |
| "the rest" + structure | 25 |

31% of dev occurrences (all of the no-structure pronouns) sit in sentences the grammar
cannot parse - which is why structure coverage and resolver accuracy move
independently.

**Workflow** (all tooling is in the repo):

```bash
python tools/strat_sample.py 400                      # .cache/strat_sample.json
python coref/ensemble_label.py .cache/strat_sample.json \
       --out .cache/strat_labels.json           # 3 annotators, resumable
python tools/analyze_strat.py                         # accuracy estimate + review queue
```

`ensemble_label.py` health-checks the endpoint first and aborts cleanly if
`llama-server` is down (it checks `~/teacher.sh`'s port 9000, plain HTTP, no key), keeps
completed cases across restarts, and refuses to count a case with fewer than two votes
as done. `analyze_strat.py` writes `review_queue.json`: every case where the resolver
disagrees with the ensemble or the ensemble itself is split - the human pass, when it
happens, is only over that queue.

### 4e. Grammar work - what it bought

Sentences that parse gain structure (roles), and their mentions stop falling back
to regex. Seven patterns were added (`put_library_action` with `owner_subject`,
comma-joined tutor chains, `tapped and transformed`, `until the end of your next
turn`, `one of them ... and the rest/other into ...`, `you may choose ... from
it`, `sacrifice ... at the beginning of your next end step`, `life equal to its
mana value`).

| measurement | value |
|---|---|
| FDN unique sentences re-checked | 703 |
| coverage before -> after | 85.5% -> **85.9%** |
| newly parsing | 3 |
| **newly failing (regressions)** | **0** |

Regression gate: parse every sentence with the `HEAD` grammar and with the new
one, diff the outcomes. Worth running on every grammar change — the first cut of
this batch silently broke three `return ... under its owner's control` sentences
by dropping a `?`.

A second, more important finding: **`normalize_names` had no word boundaries**, so
45 Standard card names that are word prefixes (`Sear`, `Ash`, `Burn`, `Opt`, ...)
clobbered ordinary words — `Search your library` became `~ch your library` in 91
dev card texts. Fixed with letter/digit lookarounds; output on all 763 FDN cards
is byte-identical. The stored dev texts keep the old corruption, so ~12 of the
remaining parse failures are artefacts of the old dataset, not grammar.

### Structural features (ptree, pilot)

`ptree.py` extracts from the tree, per mention node: `role` (ordered action
children → subject before the verb token, object after), governing `verb`
(nearest `*_action` ancestor) and `predicate` (a copula complement, e.g.
`it's an artifact`). Measured on a 240-text / 353-occurrence structured sample
(that sample is harder than the corpus average: 66.3% baseline):

| rule | sample accuracy |
|---|---|
| structure off | 66.3% |
| **+ `drop-predicate-nominals`** | **68.0%** |
| + "self mention as clause subject wins" | 68.0% (fires 18x, changes 8 picks, 4 fixed / 4 broken → **removed**) |
| lexical verb prior (surface scan) | 70.5% vs 71.3% on full dev → **rejected** |

Only the predicate-nominal rule survives. The rest of the structural headroom
needs **subject binding**: a possessive inside an object NP
(`the top N cards of **their** library`) belongs to the clause *subject*, while a
possessive beside the object (`to **its** owner's hand`) belongs to the *object*.
That rule was implemented and measured on the rebuilt cache. **It is a wash
(-1 occurrence) and its precondition almost never holds: 6 of 755 possessive
anaphors have a container role.** The reason is coverage, not logic:

| measurement (dev, 3,403 occurrences) | value |
|---|---|
| anaphors whose sentence yields any structure | **58.0%** (1,617 / 2,790) |
| possessive anaphors with a container role | 6 / 755 |
| mention records that come from the regex fallback | ~35% |
| card texts that parse nowhere | 739 / 2,497 (29.6%) |
| accuracy on texts that parse | 73.6% |
| accuracy on texts that do not parse | 71.5% |

So structure currently buys **nothing**, and not because the rules are wrong: the
constructions that decide the hard cases (`Each player exiles the top seven cards
of **their** library`) do not parse. The rule was removed.

**Conclusion: grammar coverage and mention-inventory quality are the levers, not
more resolver rules.** The bench went 73% -> **79%** across the grammar batch and
the merged parse, while the rules themselves were unchanged — the gain came from
candidates (pronoun spans now kept, the zero-node regex fallback) and from
sentences that now parse. The structural rules still contribute nothing because
only 48% of anaphors sit in a parsed sentence.

### 4e. Dataset repair (contaminated dev texts)

91 dev records carried the `~ch` clobbering. `repair_dataset.py` rebuilds each
one from the ORIGINAL oracle text (identity check: re-running the *buggy*
normalizer on the source must reproduce the stored text exactly), then remaps
spans with a diff-based offset map.

The subtle part: the clobbered `~ch` also produced a **bogus `~` mention** in the
candidate list (it looked like the card self-reference). Those spans no longer
reproduce their surface after the repair, so they are dropped and the teacher's
indices remapped.

| | |
|---|---|
| records repaired | 93 (91 unique cards) |
| bogus mentions dropped | 113 |
| teacher labels lost (pointed at a bogus mention) | 8 |
| clobbered tokens remaining | **0** |
| dev after repair | 73.0% on 3,395 occurrences (was 72.9% on 3,403) |

The rewrite path works and round-trips: every resolution carries the entity's
canonical surface, so a resolved card can be re-parsed with the pronouns
replaced (`~ deals 5 damage to target creature. Exile up to one target Equipment
attached to target creature. If target creature would die this turn, exile
target creature instead.`).

### Residual after the four rules (~790 errors)

| bucket | count | needs |
|---|---|---|
| picked another mention, gold is self (`~`/`this X`) | 234 | self-reference rule (stage 4.2) |
| pronoun number / type-lattice direction / possessive role | fixed | see §4f |
| type mismatch (card↔opponent, creature↔card, card↔player, creature↔token, …) | 149 | verb/type prior + type lattice |
| partial/qualifier span (`target creature` vs `target creature you control`) | 60 | maximality + longest-match |
| other | 110 | — |
| `the rest` (kind=phrase) | 78 -> **10** | set rule (**done**, see §4c) |

Every bucket in that table maps to a rule in §2. None of them requires a model.

---

## 5. Implementation shape (when we do it)

```
refs.py        mention inventory: spans + head_type + number + sentence/clause
               + role + is_self/is_target; text+tree in, JSON out; no torch
rulecoref.py   the cascade: compatibility filters -> ordered preferences ->
               entity aliasing -> rewrite; JSON in/out; no torch
```

Both are written (v1). CLI:

```
python coref/refs.py --card "Fiery Annihilation"        # inspect the inventory
python coref/rulecoref.py "Fiery Annihilation"         # resolve one card
python coref/rulecoref.py "Fiery Annihilation" --json  # full JSON contract
python coref/coref_eval.py --dataset coref_standard.json       # unified, entity-aware
python coref/coref_eval.py --bench --mentions parser           # human gold, parser pool
python coref/coref_eval.py --bench --mentions regex            # human gold, regex pool
python coref/rulecoref.py --eval X.json --ablate number,type   # ablations
```

They must not import `resolve.py` (torch) and must not depend on `interpret.py`
output (§1, Loss 1). Optional separate fix: make `interpret.py` keep anaphor
tokens (`keep_all_tokens=True` for the anaphor-bearing rules, or an explicit
`ref` field carrying the span) — useful regardless, but not required for the
resolver.

### Evaluation protocol (no LLM needed, reuses existing labels)

- dev: 3,380 valid teacher labels in `coref_standard.json` (no model, so no leakage)
- test: the 72 human-gold cases in `coref_benchmark.json` (touch once per change)
- scoring: **entity** match (alias-aware), report per kind and per failure bucket
- always report the `-1`/no-antecedent prediction rate; the rule engine must be
  able to abstain, which the current neural head cannot

### Deliverable

`--resolve` stays opt-in and deterministic: `parser + rulecoref` produce
resolutions, `torch` never imported. The neural head remains available as an
optional comparator behind a separate flag.

---

## 6. Open decisions

1. Do we accept the entity/alias output contract (`entity ids`, not candidate
   indices)? It makes evaluation honest and it is what the game semantics wants.
2. Do we extend `interpret.py` to keep anaphors (Loss 1), or keep the resolver
   strictly text+tree? (Recommendation: text+tree first, `interpret` later.)
3. Do we want the rule engine to abstain (emit `no-resolution`) or always
   produce a best guess? Abstention is what makes the residual measurable.
4. ~~Is `the rest` / set-valued resolution in scope for v1?~~ **Done** — see §4c.
