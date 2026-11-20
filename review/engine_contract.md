# Engine contract — parser shapes → builder → mage-ir

Source of truth: `/home/q8/Documents/mage-ng` (read-only). `tools/build_cards.py` 1,063 lines; `crates/mage-ir/src/lib.rs` 664 lines. Parser artifact: `compile_standard.jsonl` SHA `eb1baa8e03487bb7…` (21,996 rows, card IR `46ea69cf…`). References are `file:line`.

## Pipeline and invocation

The builder does **not** read `compile_standard.jsonl`. `main()` (build_cards.py:896) runs mage-lark's compiler live (build_cards.py:917-925):

```
cmd = [lark/myenv/bin/python, lark/tools/compile_card.py,
       --data <set-json>, --out <recs.jsonl>, --workers N]
subprocess.run(cmd, check=True)
```

No `--card` and no `--sets` are passed to `compile_card.py`. The builder's own `--card` (build_cards.py:906-907) only filters `names` after the full set is compiled (build_cards.py:953-955). It then groups records by card, assembles each card via `card_ir.build_card`, converts every segment with `convert_segment` (build_cards.py:638), and writes mage-ng IR frames (lib.rs:119-143). Blanket dedupe is per card at build time, not setdata (see §Dedupe).

## Card frame (lib.rs:119-143)

| parser/artifact field | builder | engine IR |
|---|---|---|
| `card` | `frame_from_mtgjson(info, name, text)` (build_cards.py:860) uses the mtgjson frame, not the parser | `Card.name` |
| `set_code` | never read | **absent** — `Card` has no set_code |
| mtgjson `manaCost` | stripped of T/E/Q/S | `mana_cost: Vec<String>` |
| mtgjson types/subtypes/supertypes | copied | `type_line` |
| mtgjson `power`/`toughness` `*`/`-` | note `adapted power '*' not representable`, set `None` (build_cards.py:870-875) | `Option<i32>` |
| mtgjson `loyalty` | int if numeric | `loyalty` |
| `layout == token` | `token: true` | `Card.token` |
| sentence `text` | display only | `Card.text` |

Basics are special-cased: the builder emits its own five frames with `activated/tap/add_mana` (build_cards.py:944-962) and skips the set's basics (build_cards.py:975-977). Reminder text at the segment level only produces a `bug` note in `convert_segment` (build_cards.py:642-646).

## Target sets (`TargetSet`, lib.rs:244-278)

`norm_target_set` (build_cards.py:218-265) takes the parser card-target dict; `TargetSet` is `deny_unknown_fields`.

| parser shape | builder behavior | engine IR | loss |
|---|---|---|---|
| `card_type: {kind:"this_card", value:"~"}` | `norm_card_type_one` → `{'kind':'this_card'}` (build_cards.py:196-197) | `this_card: true` (lib.rs:246) | — |
| `card_type: {kind:"type", value, list}` | kept, value/all list lowercased (198-205) | `CardType::Type {value,list}` (327-335) | — |
| `card_type: {kind:"anaphora"}` or any `ref`/`raw` | emits `CardType::Raw {raw, ref_}` + `adapted anaphora card_type … kept as raw` (189-215) | `Raw` (335-343) | no link id on the type; `link` field not carried |
| `card_type: {kind:"link", link:…}` | falls to `gap card_type {…}` → `None` | dropped | link not modelled in `CardType` |
| `card_type` list (union) | each item normalized; single stays single, >1 becomes JSON list (178-187) | `CardTypeSel::Union` (280-290) | — |
| `quantifier: 2` / `"target"` etc. | int, digit-string, words a/an/target/each/all/any/any number of/one or more (119-150) | `Quantifier::N/One` (209-240) | — |
| `quantifier: {up_to:N}` / `{at_least:N}` | passed through | `UpTo`/`AtLeast` (222-232) | — |
| `quantifier: {amount:1, relation:">="}` | `gap quantifier shape {…}` (build_cards.py:132-136), returns `None` | dropped | **our current shape is not accepted** |
| `colors: "white"` / `["white",…]` | string→one-element list, list lowercased (build_cards.py:249-252) | `colors: Option<Vec<String>>` (256) | — |
| `controller: "you control"` | `norm_player_ref` alias table (76-101) → bare PlayerRef | `controller: Option<PlayerRef>` (259) | relation/possessor lost |
| `controller: {kind:"player",ref,relation,of}` | only `ref` is read (build_cards.py:105-107); `relation`/`of` ignored | no fields for them in `TargetSet` | **lossy**; see Q(a) |
| `status: ["attacking","blocking"]` | each element lowercased / JSON-stringified (build_cards.py:243-247) | `status: Option<Vec<String>>` (253-255) | logic (`status_logic`) not carried |
| `zone: {zone, prep, possessor}` | `norm_zone` (152-176): `prep=from` → `in_zone=zone`; destination preps → dropped; `possessor` ignored | `in_zone: Option<Zone>` (269-271) | source/destination and possessor lost |
| `otherness: "other"` | lowercased string | `otherness: Option<String>` (249-251) | — |
| `nontoken: ["nonland"]` | **flattened to `True`** + `adapted nontoken […] flattened to true` (build_cards.py:236-241) | `nontoken: Option<bool>` (247-249) | list detail lost |
| `modifier: {unparsed:true,…}` | `gap unparsed modifier …` note only, not copied (build_cards.py:254-258) | absent | modifier dropped |
| `anaphor`, `this_that`, `card_class`, `label` | popped silently (build_cards.py:260-262) | absent | — |
| `link` | never read; target sets have no link | absent | link ids only survive in `Amount::ThatMany` |
| target set non-dict | `gap target set is str: …` (build_cards.py:223-228) → `None` | dropped | — |

`card_type` kinds the builder knows: this_card, type, anaphora/ref/raw, creature_type (maps to `type creature` with a gap note). Everything else is a `gap card_type …` note and `None` (build_cards.py:206-215).

## Effects (`Effect`, lib.rs:430-484)

`norm_effect` (build_cards.py:424-574) maps the parser effect dict. Keys ending in the whitelist at build_cards.py:554-561 that are not consumed produce `adapted effect field 'X' dropped`; `condition`, `predicate`, `restriction` etc. are not whitelisted, so they generate that note.

| parser shape | builder behavior | engine IR | loss |
|---|---|---|---|
| `verb` in VERB_MAP (build_cards.py:401-419) | mapped; `deals`→`deal_damage`, `loses`→`lose_life`, `return`→`return_to_hand`, `play`→`cast`; `may` unwrapped and executed as mandatory | `Effect.verb: Verb` (320-351) | optionality lost (`adapted 'may …'`) |
| unknown verb | `skipped verb 'X' not in engine`; effect `None` → ability becomes `unsupported` | no effect | — |
| `who: "You"` / `who: {kind:"player",ref}` | `norm_player_ref` → `out.who` (build_cards.py:438-455) | `who: Option<PlayerRef>` (433-435) | relation/of ignored |
| `actor: ["Its","controller"]` | `gap actor list […]`, who not set | absent | — |
| object keys `card,target,object,on,to` in that priority (build_cards.py:421, 457-470) | first present is used as TargetSet; player string becomes `player_target` (build_cards.py:461-468) | `card` / `player_target` (438-441, 471-473) | — |
| `amount: 3` / `"3"` | int / digit int | `Amount::N` (354-356) | — |
| `amount: {kind:"number",value:N}` | int | `Amount::N` | — |
| `amount: {kind:"number",value:"X"}` | `skipped amount 'X' … not representable`, returns 0 | `Amount::N(0)` | X lost (notes it) |
| `amount: {kind:"mana",symbols}` | returns `(None, symbols)` | used by `add_mana` only: `Effect.mana` single first symbol | extra symbols dropped |
| `amount: {kind:"mana_choice",options:[[s],[s]]}` | `adapted mana_choice … -> adds all symbols`, returns all syms | `Effect.mana` first symbol only | choice lost |
| `amount: {kind:"that_many",link}` | returns `{'that_many': link}` (build_cards.py:298-299) | `Effect.amount` expects `N` or `{link}` (`Amount::ThatMany`, lib.rs:354-360); `{"that_many":…}` does **not** deserialize | builder-side serialization mismatch |
| `add_mana` + `amount.symbols` | `Effect.mana` = first symbol; note when >1 (`add_mana […] -> first symbol`) | `Effect.mana: Option<String>` (455-457) | choice lost |
| `add_mana` + `{choose_one: [{symbols},…]}` (our new 227 statements) | `norm_effect` has no `choose_one` handling; no amount/life → `Effect {verb:add_mana, mana:None}` and `choose_one` hits “effect field 'choose_one' dropped” | no mana emitted | **builder-side gap**, see Q(b) |
| `add_mana` + `mana_choice` | see mana_choice above | first symbol | — |
| `zone` / `to` destination | `to` can be the object; `return_to_hand` reads `obj.to.zone`→`return_to` (build_cards.py:463-468) | `Effect.zone/from` exist (444-450) but are **never populated** | parser `zone` key silently ignored |
| `duration` | `until end of turn` / `permanent` / `while`→permanent with note (build_cards.py:308-330) | `Duration` (382-390) | while conditions lost |
| `condition` | not whitelisted → `effect field 'condition' dropped` | `Effect.condition` exists (474-476) but never set | conditions dropped |
| `then` / `and` lists | recursively normed into `then` (build_cards.py:531-536) | `Effect.then` (481-483) | — |
| `shared_effects` | `norm_effect` returns `None` (no note) unless reached via `as_long`, where it expands items+shared target (build_cards.py:770-790) | multiple static effects | top-level `shared_effects` lost |
| `type:"restriction"` / `verb:"restrict"` | `convert_segment` has no `restriction` case → `skipped output type 'restriction' unknown` (build_cards.py:846-849) | unsupported | engine has no restriction ability |
| `effect:{type:"enters_tapped"}` | handled inside `t=='effect'` (build_cards.py:680-684) | `Ability::EntersTapped` (518-523) | — |
| `effect:{type:"enters_with"}` | counters if static int; dynamic → unsupported (684-710) | `EntersTapped {counters}` | dynamic counters lost |
| top-level `type:"enters_tapped"` / `"enters_with"` | no case → `skipped output type … unknown` | unsupported | builder-side mismatch |
| `type:"keyword_action"` | `skipped keyword action … not executable` (build_cards.py:807-813) | unsupported | engine lacks scry/etc. |
| `type:"static_ability"` | no case → unknown → unsupported | unsupported | builder-side mismatch |
| `type:"static_keyword"` | keyword list mapped; keyword costs dropped (build_cards.py:660-677) | `Ability::Keyword` | ward/equip cost lost |

## Abilities / segments (`Ability`, lib.rs:516-561)

`convert_segment` (build_cards.py:638-851) dispatches on the parser `type`:

| parser type | builder behavior | engine IR |
|---|---|---|
| `effect` | `norm_effect`; enters_tapped/with special-cased | `Ability::Effect` |
| `triggered` | `norm_trigger` supports events enters/becomes→enters, dies, attacks; `when` upkeep/end_step only; other event verbs or phases → unsupported note (build_cards.py:608-636, 728-740) | `Ability::Triggered {event,effect}`; `Event` only Enters/Dies/Attacks/Upkeep/EndOfTurn (lib.rs:497-505) |
| `activated` | `norm_cost` + effect; failed cost/effect → unsupported (741-756) | `Ability::Activated {cost,effect}`; `Cost` Mana/Tap/Untap/SacrificeSelf/PayLife (487-494) |
| `static` | effects (or a single effect dict) → static | `Ability::Static` |
| `as_long` | unparsed condition → unsupported; else effect; `shared_effects` expands | `Ability::Static` |
| `until` | duration attached to each effect | `Ability::Effect` with duration |
| `choose_one` | iterates `options[].output` (and `continuations`) items with `type=="effect"`; each option → one ModalMode; >1 effect chained via `then`; no modes → unsupported (814-841) | `Ability::Modal {choose:1,modes:[{text,effect}]}` (536-561) |
| `loyalty` / `replacement` / `if` / `additional_cost` / `during` | `skipped ability type 'X' not executable yet`, unsupported with reason (842-845) | `Unsupported {reason}` |
| `keyword_action` | unsupported, note (807-813) | `Unsupported` |
| unknown type | `skipped output type 'X' unknown` (846-849) | `Unsupported` |
| non-dict output entry | `gap output entry …` (650-652) | skipped |
| unparsed marker | `skipped unparsed (reason)` | `Unsupported {reason}` |

Important modal detail: `convert_segment` requires each option/continuation item to have `type=="effect"` (build_cards.py:819-825). Our artifact's `continuations[]` entries are `{output:[…]}` without a `type`, so their effects are silently skipped; only `options[].output` effects become `ModalMode.effect`. Continuation effects are therefore lost builder-side.

## Tokens (`TokenDef`, lib.rs:407-424)

`norm_token` (build_cards.py:332-399):

| parser token field | builder | IR |
|---|---|---|
| `count` int/digit | count | `Effect.amount` (create_token) |
| `count` other | `gap token count …` | amount 1 |
| `types` | split type words vs subtypes; if no type word, first label becomes type | `type_line` |
| `power_toughness` | as_int | `p`,`t` |
| `named` | name | `name` |
| `colors` | lowered list | `colors` |
| `kw` | known KEYWORDS only | `keywords` |
| `copy_of` | `copy_of = True`, name "Copy", note `adapted … approximated as a blank named token` | `copy_of: bool` |
| `except`/`quote`/`xdef`/`for_each`/`of_those_tokens`/`card_class` | dropped with adapted notes | — |
| `tapped` | bool | `tapped` |

## Players and players-in-slots

`norm_player_ref` (build_cards.py:103-117) is the only player normalizer. It accepts a string or dict (`ref`/`value`/`player`), lowercases/trims, and maps through `PLAYER_ALIASES` (build_cards.py:76-101) to `PlayerRef` (lib.rs:193-207). `relation`/`of` are ignored. `PLAYER_ALIASES` contains long forms (`an opponent controls`, `defending player`, `target player`, `its controller`, `you don't control`, …) mapping mostly to `opponent`. `who`, `controller`, trigger `player`, and player objects all use it. An unmapped ref produces `gap unmapped player ref '…'` and `None`.

## Dedupe and set_code

- Builder reads mtgjson directly: `json.load(args.set_json)['data']['cards']` (build_cards.py:939-950), chooses the first normal-layout printing per name (941-948).
- Parser records come from the live compile; per card it dedupes on `(sentence_index, original_text, resolved_text, json.dumps(output, sort_keys=True))` (build_cards.py:984-1000) and notes `adapted N duplicate record(s) from multiple printings` if any were removed.
- It never reads `set_code`; `setdata.load(dedupe_printings=True)` is not used. `Card` has no set_code field (lib.rs:119-143).

## norm_* note categories

All notes are `(cat, card, sentence, detail, suggestion)` with cat in bug/gap/adapted/skipped (build_cards.py:36-38, 1030-1043):

- `bug`: fully-parenthetical segment (642-646).
- `gap`: unmapped player ref, quantifier shape, unmapped zone, card_type kind/dict, target set non-dict, unparsed modifier, amount shape, duration/while, token count, actor list, cost action, trigger when/verb, as_long condition, output entry, keyword not in engine, effect field dropped.
- `adapted`: anaphora card_type raw, nontoken list flattened, mana_choice adds all, may optionality, add_mana first symbol, token copy_of/token field dropped, keyword cost dropped, duplicate printings, `*` P/T.
- `skipped`: unknown verb, unparsed, trigger verb not executable, enters-with dynamic, keyword_action, choose_one with no modes, ability types if/loyalty/replacement/additional_cost/during, unknown output type, no executable abilities.

## Answers derived from the code

**(a) Controller object shape.** `norm_player_ref` accepts a dict but only reads `ref`/`value`/`player` (build_cards.py:103-107). `TargetSet.controller` is `Option<PlayerRef>` (lib.rs:244-278); the IR has no `relation` or `of` field, and long forms exist only as entries in `PLAYER_ALIASES` (build_cards.py:76-101). A `{kind:"player",ref,relation,of}` object loses `relation`/`of` silently. So: either keep a flat string enum (current engine), or extend `TargetSet` with `relation`/`of`; do not ship the richer object expecting it to survive.

**(b) `add_mana` + `choose_one`.** The builder does not know it. `norm_effect` (build_cards.py:424) has no `choose_one` branch; for `{verb:"add_mana", choose_one:[…]}` it emits `Effect {verb:add_mana, mana:None}` and records `adapted effect field 'choose_one' dropped` (build_cards.py:554-563). `norm_amount` only understands `kind:"mana_choice"` (build_cards.py:288-300), which is no longer emitted. `Effect.mana` is a single `Option<String>` (lib.rs:455-457), so a choice needs builder-side expansion into `Ability::Modal` or a new IR field. This is builder-side work, not a parser regression.

**(c) How the builder obtains parser output.** It runs `tools/compile_card.py` as a subprocess with `--data <set-json> --out <tmp> --workers N` (build_cards.py:917-925). It does not pass `--card` or `--sets`; `--card` is the builder's own post-compile name filter (build_cards.py:906, 953-955). It compiles live, so it always uses whatever mage-lark checkout is present; it does not read `compile_standard.jsonl` or pin an artifact SHA.

**(d) Quantifier shapes accepted.** `norm_quantifier` (build_cards.py:119-150) accepts: int; `{up_to:N}`; `{at_least:N}`; the strings a/an/target/each/all/any/any number of/one or more (one or more → `{"at_least":1}`); digit strings. Anything else, including our `{amount:1, relation:">="}`, gets `gap quantifier shape` and is dropped. The IR enum (`Quantifier`, lib.rs:209-240) has exactly One(String), N(u32), UpTo, AtLeast. Emit `{"at_least":1}`.

**(e) Dedupe.** Yes, but not by printing or set_code: per card, the builder dedupes compiled records on `(sentence_index, original_text, resolved_text, json.dumps(output, sort_keys=True))` (build_cards.py:984-1000) and notes the removed count. It does not use `setdata.load(dedupe_printings=True)`, does not read `set_code`, and chooses one mtgjson frame per name (first normal layout) at build_cards.py:939-950. So the artifact's `set_code` and dedupe option are invisible to it; a shipped deduped artifact would help only if the builder is pointed at it (it is not).

## Mismatches the engine side must fix (not parser regressions)

1. `add_mana` internal `choose_one` is unhandled (Q(b)); 227 artifact statements become mana-less adds.
2. `modal` continuations: items lack `type:"effect"`, so `convert_segment` skips them (build_cards.py:819-825).
3. `Amount::ThatMany` serialization: builder emits `{"that_many": link}`, IR expects `{"link": …}` (build_cards.py:298-299 vs lib.rs:354-360).
4. Top-level `restriction`, `static_ability`, `enters_tapped`, `enters_with` types are not cases in `convert_segment` → unsupported.
5. `Effect.zone/from`, `Effect.condition` are never populated; parser `zone`/`condition` are dropped.
6. `set_code` is not in `Card`; builder ignores it.
7. `controller` `relation`/`of` and target-set `link` are dropped.
8. `nontoken` lists are flattened to `true` by the builder, not the parser.

## Parser-side changes to match the code

- Quantifier: emit `{"at_least":1}` / `{"up_to":N}` for our `{amount,relation}` shapes (72 sites), never `{amount,relation}`.
- Always include a quantifier for "any target" (engine has no any-target marker): use `"any"` or a player ref/`player_target`; do not leave it implicit.
- Colors: keep emitting strings/list of color words (builder accepts both).
- Keep player refs as `{kind:"player",ref}`: builder accepts them; do not rely on `relation`/`of` until IR adds fields.
- `add_mana` choose_one: keep the structured form, but engine/builder must learn it; if the engine prefers `mana_choice`, say so.
- Any-target/player targets: `{kind:"player"}` or bare player string in the object slot maps to `player_target`; ensure the shape is explicit.
