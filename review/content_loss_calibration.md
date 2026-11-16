# Content-loss calibration (25 stratified samples)

Scan: `swarm/scripts/content_loss_scan.py` over the frozen Standard snapshot (`Standard_1e032c36_056f23fd`, 4,005 sentences ≥12 words). Original rate: 1,272 / 4,005 = 31.8%. Sample: 25 flagged sentences, stratified by score band (top ≥140, mid 50–139, low <50) and by missing-unit family; each sentence and its full output were read.

Verdicts: `true_loss` = a content unit genuinely absent; `structured_repr` = carried by a key/structure; `allowlist_gap` = legitimate function/ability word; `scan_bug` = matching failure.

| # | sid | missing units (sample) | verdict | why |
|---:|---|---|---|---|
| 1 | d1140697e0db | 10 | scan_bug | output has `power: -10, toughness: -10`; tokenizer compared `10` with `-10` |
| 2 | 1280334d9d9d | 11 | scan_bug | `value: -11` (loyalty cost); signed-number mismatch |
| 3 | ecc49a4ce74c | 13 | scan_bug | `power: -13, toughness: -13`; signed-number mismatch |
| 4 | f16d305f5ae1 | four | true_loss | "four time counters" -> `counter.kind = time` but no count |
| 5 | 55915f6ecc24 | five, dragons | true_loss | "five Dragons this way" dropped; condition object is `+1/+1 counters` |
| 6 | 9146e935b256 | abilities, activate | true_loss | cost_mod target is creatures; "abilities ... activate" absent |
| 7 | f5f407b6e2f7 | ability, resolved | structured_repr | `trailing_if.state = first_time_this_turn` encodes the first resolution |
| 8 | 59d35cde9bbf | able | structured_repr | quoted ability is structured as `verb: attacks_each_combat` |
| 9 | 072d3d41bd81 | activate, abilities | true_loss | "activate abilities of creatures" lost; only spend_mana/as_though kept |
| 10 | 31f19673efdd | activate, ability, source | true_loss | "or activate an ability of an Ally source" branch dropped |
| 11 | 765da95306d1 | activated, abilities, activate | true_loss | "activated abilities ... to activate" reduced to a name modifier |
| 12 | 0ba7a8876825 | additional, time | structured_repr | `verb: trigger_extra` is "triggers an additional time" |
| 13 | 4281547c68f4 | additional, counters | true_loss | "X additional +1/+1 counters" not in the put |
| 14 | b2287c0bf674 | alone | true_loss | "can't attack or block alone" -> predicate lost "alone" |
| 15 | 4cfec947874e | already | allowlist_gap | "for each Angel you already control" approximated by for_each |
| 16 | a33ac8482659 | delirium, among | allowlist_gap | ability word Delirium dropped; `among` carried by `of` |
| 17 | a9afab0bd06e | cast, long, 4, types, among, graveyard | true_loss | whole "as long as four card types among ... graveyard" condition dropped |
| 18 | c6af7c57d283 | amount | structured_repr | `xdef.event = life_gained` carries the amount source |
| 19 | 699742b7fef9 | anywhere, hand | true_loss | "from anywhere other than your hand" zone restriction dropped |
| 20 | f2774cdfa29a | anywhere, owner, library | true_loss | shuffle into owner's library not structured |
| 21 | 7a220b108693 | artifact | structured_repr | "this artifact" represented by `this_card` value `~` |
| 22 | 084acb14c3d2 | artifact, nonland, graveyard, library | true_loss | shuffle effect kept, cards/zones dropped |
| 23 | dd22519ddb95 | artifacts, creatures, enchantments | true_loss | type list under "activate abilities of ..." dropped |
| 24 | 1a1bc3f32465 | attacking | true_loss | "tapped and attacking" -> only `tapped: true` |
| 25 | 648792583a40 | base | true_loss | "base power" reduced to `stat: power` |

Tally: **true_loss 15/25 = 60%**, structured_repr 5, allowlist_gap 2, scan_bug 3. False positives do not dominate; true loss does.

## Fixes applied to the scan

- Signed-number tokenization: `-10` in the output now matches `10` in the text.
- Representation map (keys/values): `number -> count/quantity/value/amount/total/xdef`, `equal -> op/equal/relation/count`, `greater/less -> op/...`, `among -> among/of/set/items`, `turn -> turn/time/duration/timing/when/window`, `target -> target/quantifier`, `cast -> cast`, `counter(s)`, `additional -> additional/extra`, `base -> base/pt`, `attacking`, `amount`, `resolved -> .../state`, `loses -> lose/keyword`.
- Allowlist additions: `already`, `delirium`, `long` (ability/function words). Allowlist otherwise unchanged.

## Calibrated result

Re-run over the same 4,005 sentences: **792 sentences with true missing content = 19.8%** (from 1,272 / 31.8%). This is close to the sample estimate (60% of 31.8% = 19.1%) and is now a calibrated upper bound.

Top 10 calibrated (true) families by sentence count: cast 119, equal 73, spell 61, card 56, creature 54, cards 44, until 34, among 30, end 28, artifact 24.

`review/certain_defects.md` was regenerated with this calibrated number and the representation/allowlist note.
