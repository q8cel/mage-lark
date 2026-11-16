#!/usr/bin/env python3
"""Golden tests for tools/ir_render.py on v6 review items.

Run with ``./myenv/bin/python tests/test_ir_render.py`` from the repo root.
The goldens are real interpreted outputs (Z001 activated with a relative amount,
Z006 duration, Z007 triggered with a trailing condition, Z004 static keyword,
Z021 quoted ability, Z047 if-clause); every one must render with zero fallback.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PACK = ROOT.parent / "swarm" / "work" / "human_review_v6" / "items.json"

import ir_render  # noqa: E402

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition)))
    print(f"  [{'ok' if condition else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise SystemExit(f"golden test failed: {name} {detail}")


def text_of(line):
    return ir_render.line_text(line)


def roles(ir):
    return [line["role"] for line in ir["lines"]]


def main():
    if not PACK.exists():
        raise SystemExit(f"missing v6 pack: {PACK}")
    items = {e["id"]: e for e in json.loads(PACK.read_text(encoding="utf-8"))}

    for hid, card in (("Z001", "Blazing Bomb"), ("Z004", "Red Tiger Mechan"),
                      ("Z006", "Thwip!"), ("Z007", "Scalestorm Summoner"),
                      ("Z021", "Down in the Valley"), ("Z047", "Cheering Crowd")):
        check(f"{hid} present in the v6 pack",
              hid in items and items[hid]["card"] == card)

    # Z001: activated ability, mana+permanent cost, relative amount.
    ir = ir_render.render(items["Z001"]["output"])
    check("Z001 roles", roles(ir) == ["TYPE", "COST", "DO"], roles(ir))
    check("Z001 header", text_of(ir["lines"][0]) == "[activated]")
    check("Z001 cost", text_of(ir["lines"][1]) == "pay {T}; sacrifice THIS",
          text_of(ir["lines"][1]))
    do = text_of(ir["lines"][2])
    check("Z001 do-line", "deal damage" in do and "→ target creature" in do, do)
    check("Z001 amount", "[amount = relative('its' power, equal)]" in do, do)
    check("Z001 zero fallback", ir["stats"]["fallback"] == 0,
          str(ir["stats"]["fallback_shapes"]))
    check("Z001 graph size",
          len(ir["graph"]["nodes"]) == 8 and len(ir["graph"]["edges"]) == 8,
          f"{len(ir['graph']['nodes'])}n/{len(ir['graph']['edges'])}e")
    check("Z001 node kinds",
          {n["kind"] for n in ir["graph"]["nodes"]} ==
          {"verb", "subject", "object", "amount", "cost", "anaphor"},
          str({n["kind"] for n in ir["graph"]["nodes"]}))
    check("Z001 anaphora edge is dashed",
          any(e.get("dashed") and e["role"] == "anaphora" for e in ir["graph"]["edges"]))

    # Z006: two effects, both with until-end-of-turn duration.
    ir = ir_render.render(items["Z006"]["output"])
    check("Z006 roles", roles(ir) == ["DO", "DO"], roles(ir))
    texts = [text_of(line) for line in ir["lines"]]
    check("Z006 stat change",
          "+2/+2" in texts[0] and "[duration: until end of turn]" in texts[0], texts[0])
    check("Z006 keyword grant", "flying" in texts[1], texts[1])
    check("Z006 zero fallback", ir["stats"]["fallback"] == 0,
          str(ir["stats"]["fallback_shapes"]))
    check("Z006 graph size",
          len(ir["graph"]["nodes"]) == 7 and len(ir["graph"]["edges"]) == 5,
          f"{len(ir['graph']['nodes'])}n/{len(ir['graph']['edges'])}e")

    # Z007: triggered ability with a trailing if.
    ir = ir_render.render(items["Z007"]["output"])
    check("Z007 roles", roles(ir) == ["TYPE", "WHEN", "DO", "IF"], roles(ir))
    check("Z007 trigger text", text_of(ir["lines"][1]) == "Whenever this creature attacks",
          text_of(ir["lines"][1]))
    check("Z007 token text",
          text_of(ir["lines"][2]) == "create 3/1 red Dinosaur creature token",
          text_of(ir["lines"][2]))
    check("Z007 condition text",
          text_of(ir["lines"][3]) == "if you control a creature with power >= 4",
          text_of(ir["lines"][3]))
    check("Z007 zero fallback", ir["stats"]["fallback"] == 0,
          str(ir["stats"]["fallback_shapes"]))
    check("Z007 graph", len(ir["graph"]["nodes"]) == 6 and len(ir["graph"]["edges"]) == 5,
          f"{len(ir['graph']['nodes'])}n/{len(ir['graph']['edges'])}e")
    check("Z007 has a condition node",
          any(n["kind"] == "condition" for n in ir["graph"]["nodes"]))

    # Z004: static keyword line.
    ir = ir_render.render(items["Z004"]["output"])
    check("Z004 roles", roles(ir) == ["TYPE", "KEYWORDS"], roles(ir))
    check("Z004 keywords", text_of(ir["lines"][1]) == "Warp; {1}; {R}",
          text_of(ir["lines"][1]))
    check("Z004 zero fallback", ir["stats"]["fallback"] == 0)

    # Z021: quoted ability keeps the inner clause.
    ir = ir_render.render(items["Z021"]["output"])
    quote = text_of(ir["lines"][0])
    check("Z021 quoted ability", "quote:" in quote and "Whenever a land you control enters"
          in quote, quote)
    check("Z021 zero fallback", ir["stats"]["fallback"] == 0,
          str(ir["stats"]["fallback_shapes"]))

    # Z047: if-clause.
    ir = ir_render.render(items["Z047"]["output"])
    check("Z047 roles", roles(ir) == ["TYPE", "IF", "THEN"], roles(ir))
    check("Z047 headers", text_of(ir["lines"][0]) == "[if]")
    check("Z047 then", "add mana" in text_of(ir["lines"][2]), text_of(ir["lines"][2]))
    check("Z047 zero fallback", ir["stats"]["fallback"] == 0,
          str(ir["stats"]["fallback_shapes"]))

    # structural invariants across all goldens
    for hid in ("Z001", "Z004", "Z006", "Z007", "Z021", "Z047"):
        ir = ir_render.render(items[hid]["output"])
        for line in ir["lines"]:
            check(f"{hid} line fields",
                  isinstance(line["role"], str) and line["path"].startswith("$")
                  and isinstance(line["fragments"], list))
            for frag in line["fragments"]:
                check(f"{hid} fragment fields",
                      set(frag) >= {"text", "path", "kind"}
                      and frag["path"].startswith("$") and frag["text"].strip())
        ids = {node["id"] for node in ir["graph"]["nodes"]}
        check(f"{hid} graph ids unique", len(ids) == len(ir["graph"]["nodes"]))
        for edge in ir["graph"]["edges"]:
            check(f"{hid} edge endpoints", edge["from"] in ids and edge["to"] in ids)
        check(f"{hid} graph is small", len(ir["graph"]["nodes"]) <= 26,
              str(len(ir["graph"]["nodes"])))

    # odd inputs must not crash
    for value in ({}, [], None, "raw", [{"type": "unparsed", "fragment": "x"}],
                  [{"nested": {"deep": [{"a": {"b": {"c": 1}}}]}}]):
        ir = ir_render.render(value)
        check(f"render survives {type(value).__name__} input",
              isinstance(ir["lines"], list))

    print(f"\nchecks passed: {len(CHECKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
