# Engine notes audit — artifact `733af921…`

Artifact `compile_standard.jsonl` SHA `733af9214bd22da2…`, 21,996 rows / 12,981 unique records / 7,738 unique texts / 5,158 cards; card IR `b1629962…`. FDN honest 95.9%, classic 94.2%; claims commit `421cca4`.

## Claims

**4,157 claims / 2,908 records** — stringy 2,157, content_loss 1,715, invariant 203, anaphora_agreement 69, empty_slot 13. Previous artifact `4ea84d68`: 4,159 / 2,908.

## Summary

| item | metric | final | status |
|---|---|---:|---|
| 1 modal | groups / options / continuations / typed effect clauses | 259 / 626 / 96 / 673 | CLOSED |
| 2 duplicates | rows / unique / duplicate rows | 21,996 / 12,981 / 9,015 | REMAINING |
| 3 reminder | parenthetical-only / basic rows | 0 / 368 | CLOSED |
| 4 verbs | `deals` / `loses` / `can't` | 0 / 0 / 0 | CLOSED |
| 5 controller | strings / objects / mapped / residual | 0 / 3,772 / 3,590 / 182 | PARTIAL |
| 5 who | objects / aliasable / unmappable | 181 / 167 / 14 | PARTIAL |
| 6 X | X string sites | 0 | CLOSED |
| 7 copy_of | unresolved rows / shapes / no-link | 40 / 6 / 34 | PARTIAL |
| 8 add_mana | choose_one / mana_choice | 227 / 0 | CLOSED |
| 9 targets | any-target / malformed long strings | 132 / 2 | PARTIAL |
| 10 actor | actor lists | 0 | CLOSED |
| 11 zone | discard effects missing zone | 0 | CLOSED |
| 12 quantifier | missing effect-target / bad dict shapes | 0 / 0 | CLOSED |
| 13 colours | top-level / label | 919 / 2 | PARTIAL |
| 14 static | static_text sites / unique shapes | 14 / 3 | CLOSED |
| 15 modifier | modifier_text sites / unique | 0 / 0 | CLOSED |
| 16 unparsed | parse_fail sites / unparsed-only records | 1,332 / 697 | REMAINING |
| 17 set_code | codes / missing | 21 / 0 | CLOSED |

## Tail detail

- **static_text:** 14 sites / 3 shapes — `you control` 9, `you control without flying` 4, `you control that entered the battlefield this turn` 1. Expected 14/3 confirmed.
- **modifier_text:** 0 sites (expected 0).
- **copy_of:** 40 unresolved rows / 6 shapes / 34 no-link rows. Raw tail: 26 rows across 11 cards and 3 shapes, all `{kind:"anaphora", raw, ref, status:"unresolved"}` (raw `it`, raw `them` ×2).
- **controller:** 0 bare strings, 3,772 objects, 3,590 mapped sites, 182 residual — `owner` 121, `you` 24, `they` 23, `their owners` 5, `her owner` 4, `controlled by different players` 3, `those players` 2.
- **who:** 181 objects; 167 aliasable; 14 unmappable (`a player` 13, `another player` 1); 1,377 five-value strings with 0 outside vocabulary.
- **duplicates:** 9,015 duplicate rows; 7,738 unique texts; `set_code` 21/0.
- **unparsed:** 1,332 `parse_fail` sites, 697 unparsed-only records, 0 empty outputs; `static_text` is down to 14.
- **Other:** modal 259/626/96/673; any-target 132; quantifier 0 missing / 0 bad shapes; zone discard missing 0; actor 0; colours 919 top-level / 2 label; malformed long targets 2 rows / 1 unique (`38f9ce3ec91d`).

## Type-of-target condition ask

Engine notes (`notes/parser_issues.md:188-190`) request `{"kind":"type","of":"target","value":"zombie"}` for "if it's a <type> card". Current artifact has **1,050 `if` types**, **0 type-of-target conditions**; 50 use `kind:"state"` (45 with `card_type`), all with `subject:{this_card}`, which is the wrong referent for these cards. Examples:
- Cemetery Recruitment `2300faa320df` — "If it's a Zombie card, draw a card": `condition:{kind:"state",state:{card_type:{kind:"type",value:"Zombie"}},subject:{this_card}}`.
- Fecund Greenshell `4388e36d8a16` — "If it's a land card, you may put it onto the battlefield tapped": same shape with `land`.
- Hauntwoods Shrieker `09ca145cd06f` — "If it's a creature card, you may turn it face up": same shape with `creature`.

The parser will emit `{kind:"type", of:<target>, value:<type>}` for these instead.
