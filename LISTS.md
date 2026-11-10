# Deterministic list capture

Oracle text contains two different kinds of comma list.  They must not be
collapsed into one operator:

```text
Birds and Frogs you control get +1/+1
  items: Birds, Frogs          kind: set          logic: union
  connector: and               shared suffix: you control

noncreature, nonland card
  items: noncreature, nonland  kind: property     logic: intersection
  connector: implicit          head: card
```

The surface connector (`and`, `or`, `and/or`, implicit) and the semantic logic
(`union`, `intersection`) are stored separately.  Type overlap is irrelevant:
a Bird-Frog is in `Bird ∪ Frog`, and a multitype artifact creature still fails
`noncreature ∩ nonland`.

## Classification

* **Set/type items** denote sets of objects.  Their coordination is a union:
  * `Birds and Frogs`
  * `a Bird, Frog, Otter, or Rat`
  * `artifact, creature, or planeswalker`
  * `graveyard, hand, and/or library`
* **Property items** denote properties of a shared object.  `and` or an
  implicit comma is intersection; `or` is union:
  * `noncreature, nonland card`
  * `nontoken, non-Angel creature`
  * `red, white, and blue creature`
  * `white, blue, black, or red`
* **Quantity items** are a union of values (`one, two, or three`).
* **Type lines** such as `Angel Cleric` are a conjunction of subtypes and are
  handled by the type-line parser, not by oracle list capture.
* Keyword lists, effect sequencing (`draw a card, then discard`), and
  comparator phrases (`or less`, `or more`) are not captured as list objects.

## Representation

`lists.py` captures a complete list NP and replaces it with a self-contained
token:

```text
@@L<hex-encoded JSON>@@
```

The JSON object contains:

```text
kind, logic, connector, items, text
shared_prefix, shared_suffix, head
```

The grammar accepts `LISTTOK` where a complete NP is accepted:
`card_target`, `types`, `enchant_target`, and `any_text`.  The interpreter
returns the decoded object from those slots.  Conditions expose it through:

```json
{"text": "that creature is a Bird, Frog, Otter, or Rat",
 "lists": [{"kind": "set", "logic": "union", ...}]}
```

## Scope limits

Capture is deliberately conservative.  Lists in slots the current grammar
does not model as a complete NP (for example some `Put a ...`, `Reveal ...`,
cost, copy, or choice slots) are left as source text so existing behavior is
preserved.  Keyword-only and color-only lists are also left alone until their
downstream grammars accept list tokens.
