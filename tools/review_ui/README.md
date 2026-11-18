# review-ui

A local, offline web UI for human review of MTG parser outputs. It is a
labelling tool, not a nicer markdown sheet: machine claims sit inline with
accept/reject keys, bug notes are built by clicking the offending JSON node, the
judged sentence is aligned word by word against the output, and state is
append-only so a vim session and the UI can coexist.

```
cd /home/q8/Documents/mage-lark
./myenv/bin/python tools/review_ui.py --pack ../swarm/work/human_review_v6 --open
# older packs: --pack ../swarm/work/human_review_v5
```

Stdlib only (`http.server`), no build step, no CDN, no external requests.
Defaults: `--port 8765`, `--artifact compile_standard.jsonl` (or `meta.json`'s
`source`), `--cards compile_cards.jsonl`, claims read from the repo's `review/`.

## Semantic views

The output is shown as **semantics, not JSON**, by default. `tools/ir_render.py`
is a stdlib schema-aware renderer over the interpreted output:

* `render(output) -> {"lines", "graph", "stats"}` — logical-form lines (`[activated]`,
  `COST pay {2}, {T}; sacrifice THIS`, `DO THIS deal_damage → target(creature)
  [amount = relative(its power, equal)]`, `WHEN …`, `IF …`, `THEN …`, `DURATION …`,
  `STATIC …`, `KEYWORDS …`), a small semantic graph (nodes for verbs, subjects,
  objects, amounts, conditions, costs; role-labelled edges, dashed anaphora edges)
  and coverage stats. Every fragment carries the JSON `path` it came from.
  Unmapped constructs render as `⟨key: value⟩` and are counted as fallback.

The UI has four views, cycled with `v` or the buttons in the output header:

| view | content |
| --- | --- |
| semantic (default) | logic-form lines; click any fragment to select its JSON path for the bug note |
| graph | layered left→right DAG (condition/cost gates, verb, object/amount); click a node to select it |
| card | card-level pane: segments, cross-segment links, entities, `whole_text_parse` |
| json | the raw tree, kept for debugging; the claim and token links jump here |

The **card view** reads `compile_cards.jsonl` (indexed once by card name at
startup, `--cards PATH` to override) and shows the card as one unit rather than
dot-separated sentences: every segment in order with its index, text, link
badges and its own semantic render; each `links` entry as `from → to · kind ·
detail` (a click scrolls to the target segment and writes `segment 2 → 1:
event_positive — condition refers to the previous segment event` inline under
it); a segment badge `↔ N links (kinds)`; a red `self-link — suspicious` flag
and tint whenever `from == to` (the current fixer bug), plus `dangling segment`
when the target does not exist; a `whole_text_parse: true|false` badge so cards
that rely on the link fallback are visible; and an entities pane with the quoted
text and its parsed sentence side by side (the quote is located inside the
segment output, e.g. Beau on Bonny Pall). Missing cards or a missing
`compile_cards.jsonl` say so instead of failing; the view is additive and loads
lazily on first open.

The **parser view** (`p`, or the button under the sentence) runs
`core/ptree.structure(text)` on demand — falling back to `ptree.nodes(text)` on a
cache miss — and paints the judged sentence by span role (`subject`, `object`,
`predicate`, `in_condition`) with a span → role → verb → node table and the
measured time. It is cached per item; if ptree is unavailable the app says so
instead of failing. Nothing under `core/` is modified.

Coverage over the corpus (13,357 unique records):

```
./myenv/bin/python tools/ir_render.py --artifact compile_standard.jsonl --unique
```

currently renders 97.1% of fragments semantically with 0 crashes; the remaining
fallback is mostly raw unparsed prose (`unparsed.fragment`, condition/if text
fragments) plus a small long tail of unmodelled keys.

## What the app does beyond layout

For every item it shows the judged sentence with each content word marked
**green** (found in the output by the content-loss scan's stemmed/allowlisted
match), **red** (the scan says missing), or **grey** (function word from the
allowlist); clicking a token lists the JSON paths where it landed, or says it did
not. Machine claims (content-loss units, prose in a structured slot, empty
required slots, invariant flags, anaphora-agreement violations) are listed at
their JSON paths in the `triage` lane and confirmed or rejected one key at a
time — rejections are recorded as data, not discarded. A `bug` verdict is
committed by clicking a node in the collapsible JSON tree (or a claim's path);
the note is then composed as `axis: path: value — free text` with no typing
needed, and the axis comes from the axis chips. Axes are `anaphora`
(unresolved/wrong anaphora, "this creature" not binding to `~`), `list`
(coordination/list shape), `keyword` (unresolved or mis-shaped keyword/ability),
`modal` (may/must/optionality, lost or added negation), then `target`, `actor`,
`zone`, `quantity`, `referent`, `condition`, `timing`, `polarity`, `other`;
digits `1`–`9` cover the first nine, the rest are click-only. Old names and loose
spellings (`antecedent`, `coordination`, `keyword_ability`, `optionality`, …)
are accepted as aliases and normalise to a canonical axis, so imported vim notes
keep mapping, and clicking an anaphora claim preselects the `anaphora` axis.
Items are hash-assigned to a
`triage` lane (claims shown) or a `blind` lane (claims hidden, measuring the
parser alone); the lane is persisted in the state file and only revealed in the
UI after the item is labelled. Ten-item batches with a clickable progress strip
and per-label persistence make it resumable, and `u` undoes a label.

## Keys

| key | action |
| --- | --- |
| `j` / `k` | next / previous item |
| `g` / `G` | first / last item |
| `o` / `b` / `l` | verdict `ok` / `bug` / `legit` |
| `1`–`9` | bug axis: anaphora, list, keyword, modal, target, actor, zone, quantity, referent |
| click chip | the remaining axes: condition, timing, polarity, other |
| click key/value | select that JSON node for the bug note (`path: value`) |
| click ▸ / ▾ | expand / collapse that node (toggling never changes the path) |
| `e` | collapse all / expand all |
| `↑` / `↓` | move the tree focus |
| `←` / `→` | collapse / expand the focused node |
| `s` | select the focused node |
| `Enter` | commit the label and advance to the next unlabelled item in the batch |
| `u` | undo the current item's label |
| `[` / `]` | previous / next machine claim |
| `y` / `n` | accept / reject the focused claim (again to clear) |
| `i` / `x` / `r` | re-import `labels.tsv` / export `labels.tsv` / reload state |
| `v` | cycle semantic / graph / json views |
| `p` | parser span view for the judged sentence |
| `?` | help overlay |

The tree opens fully by default (outputs are 7–41 nodes), so every leaf is
reviewable without clicking. Clicking a key/value label selects that node;
clicking its ▸/▾ triangle toggles it, so expanding never changes the note path.
`e` collapses or expands the whole tree for the current view — that preference
lives only in the session, never in `labels.jsonl`. Arrow keys walk the visible
tree and `s` selects the focused node. Clicking a claim's path, or a sentence
token's landing path, expands the ancestors and scrolls the node into view.
`Escape` clears the selection.

## Pack formats

A pack is either v6 (`items.json`) or v3–v5 (`key.json` + the artifact):

* `items.json` — a list of items with the payloads the UI serves: `id`, `card`,
  `sid`, `sentence_index`, `sentence` (the judged text), `card_text` (full oracle
  text, string or list), `resolved_text`, `anaphora`, `output`, `weight`. When it
  is present the UI reads items from it and does not parse the sheets; the
  artifact is optional if every item embeds its output.
* `key.json` — identity only (`card`, `sid`, `sentence_index`, `weight`,
  `commit`); item text and output are looked up in the artifact, whose 22k
  records are indexed once at startup by `(card, sid, sentence_index)`.
* `meta.json` — `artifact_sha256` and, for v6, `claims_sha256`; both are compared
  with the files actually loaded and a mismatch yields a non-blocking banner.

## Lanes

`hash(id)` decides the lane deterministically: ids are ranked by
`sha256(id)` and alternate `triage` / `blind`, giving an exact 50/50 split for
the 100-item pack. The split is written to `<pack>/review_state.json` and to
every `labels.jsonl` record, never to the sheets. Blind items return no claims
from the API; the lane badge appears only after the item is labelled.

## Importing the vim `labels.tsv`

The reviewer may already be editing `<pack>/labels.tsv` (`id<TAB>verdict<TAB>note`).
On startup (or with `--import other.tsv`, or `i` in the UI) the file is read:

* the first token of the verdict column is the verdict (`ok|bug|legit`), the
  rest of the line is free-text note, so a loosely typed
  `bug "zone": it should be exile` is understood;
* rows with a blank verdict are ignored; unknown ids and duplicates are reported
  and skipped (the eval script rejects both);
* each imported row is appended to `labels.jsonl` with `source: "import"` and its
  raw line preserved;
* for a `bug` note that names a JSON path (`$.effect...`, `[].effect...`) or a
  quoted/backticked key (`"zone"`), the axis and path are inferred for display
  **only when they resolve in that item's output** — nothing is invented;
* the file is never modified by importing, and re-importing the same content is
  a no-op (per-row fingerprints in `review_state.json`).

Exports never duplicate imported rows: the imported line is written back
verbatim; UI labels are written as `id<TAB>verdict<TAB>note`; unlabelled ids keep
blank rows so the file stays diff-stable. Undoing an imported row suppresses
that exact row on later imports.

## Export

Click `export`, press `x`, or run:

```
./myenv/bin/python tools/review_ui.py --pack ../swarm/work/human_review_v5 --export
```

This writes `<pack>/labels.tsv` (override with `--export-out PATH`) in vim- and
eval-compatible form, backing up a differing previous file as `labels.tsv.bak`.
`swarm/scripts/human_audit_eval.py --pack <dir>` accepts the result.

State lives in two append-only files inside the pack:

* `labels.jsonl` — one record per label or undo:
  `{id, verdict, axis, path, note, claims_accepted, claims_rejected, lane,
  timestamp, source, op}` (`source` is `ui` or `import`; latest record per id
  wins);
* `review_state.json` — lane map, per-item claim decisions, import fingerprints.

## How claims are joined

`review/claims.json` is the consolidated source when it exists: an object
`{artifact_sha256, generated_at, counts, records}`, where each record is
`{card, sid, sentence_index, claims}` and each claim has
`{kind, path, detail, severity, source}`. It is joined by
`(card, sid, sentence_index)`; claims whose JSON path no longer resolves are
shown without a link (the artifact may have moved on).

When `claims.json` is absent or malformed the audit TSVs in `review/` are joined
instead, with the same semantics:

| file | join | claim |
| --- | --- | --- |
| `certain_defects.tsv` | sentence text (or `sid`) | missing content units, at sentence level |
| `stringy_report_N.tsv` (highest N) | `sid` | prose in a structured slot, at `path` |
| `structure_report.tsv` | `sid` | empty required slot, at `path` |
| `invariant_flags.tsv` | sentence text | invariant flag (e.g. `bare_modifier`) |
| `anaphora_agreement.tsv` | `(card, sid, sentence_index)` | anaphor bound to a bad antecedent |

The loaded artifact and `claims.json` are SHA-256 hashed at startup and compared
with each other and with `meta.json`'s `artifact_sha256` / `claims_sha256`; a
mismatch shows a warning banner (non-blocking) and an item with no claims is
simply a normal item. A v6 pack with matching SHAs shows no banner.

## Files

```
tools/review_ui.py            server: pack/artifact/claims, import, export, HTTP API
tools/ir_render.py            semantic renderer: logical-form lines, graph, stats
tools/review_ui/index.html    shell
tools/review_ui/app.js        keyboard state machine, tree, claims, alignment
tools/review_ui/style.css     dark, monospace, no webfonts
tests/test_review_ui.py       smoke test (HTTP, import, export, eval round-trip)
tests/test_ir_render.py       golden renderer tests on v6 items
```

## Smoke test

```
./myenv/bin/python tests/test_ir_render.py
./myenv/bin/python tests/test_review_ui.py
./myenv/bin/python tests/test_review_ui.py --pack ../swarm/work/human_review_v6
```

Copies the pack to a temp dir (with two loosely typed vim rows), starts the
server on an ephemeral port, and checks: 100 items, 50/50 lanes, import (2 rows)
and its idempotency, lane hiding, claims gating, claim accept persistence, label
+ note composition, undo, export, that `human_audit_eval.py` accepts the TSV,
and that state survives a restart. Every item payload must also carry a semantic
`ir` whose fragment paths are JSON paths, so a broken renderer fails the smoke
test. With `items.json` it also checks that the
item text and card text come from it and that the SHA banner is absent when the
declared SHAs match.

A final phase copies the pack again, drops the user's in-progress
`human_review_v5/labels.tsv` in, and imports it: rows whose ids exist in the pack
must import, v5-only ids must be reported as unknown, and the file must be left
byte-identical. It then simulates verdicts typed into that file to exercise both
sides at once.
