#!/usr/bin/env python3
"""Schema-aware semantic renderer for interpreted MTG output.

``render(output)`` turns one interpreted record into logical-form lines, a small
semantic graph and coverage stats.  It is deterministic, stdlib-only and has no
side effects.

    from ir_render import render
    ir = render(record_output)
    ir["lines"]    # [{"role": "DO", "path": "$[0].effect",
                   #   "fragments": [{"text": "...", "path": "$[0].effect.verb"}]}]
    ir["graph"]    # {"nodes": [{"id", "label", "kind", "path"}], "edges": [...]}
    ir["stats"]    # {"semantic": n, "fallback": n, "fallback_shapes": [...]}

Every fragment carries the JSON path it came from, so a viewer can select the
exact node a phrase refers to.  Constructs the renderer does not know are shown
as ``⟨key: value⟩`` and counted as fallback.

Coverage run over the corpus::

    python tools/ir_render.py --artifact compile_standard.jsonl --unique
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

MAX_GRAPH_NODES = 28

# Keys that only carry bookkeeping; ignoring them is not a semantic gap.
METADATA = {"note", "reason", "source", "label", "connector", "shared_prefix",
            "shared_suffix", "logic", "unparsed", "parse_fail", "grammar",
            "interp", "commit", "confidence", "evidence"}


def norm_path(path):
    return re.sub(r"\[\d+\]", "[]", path or "")


def json_short(value, limit=60):
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


SUBJECT_VERBS = {"enters", "dies", "attacks", "blocks", "becomes", "leaves",
                 "transforms", "phase_out", "turns", "exploits"}
VERB_TEXT = {"create_token": "create", "gain_quote": "gain"}


def pretty(token):
    token = str(token)
    if token in VERB_TEXT:
        return VERB_TEXT[token]
    return token.replace("_", " ")


class Renderer:
    def __init__(self, output):
        self.output = output
        self._depth = 0
        self.semantic = 0
        self.fallback = 0
        self.shapes = collections.Counter()
        self.shape_example = {}
        self.nodes = []
        self.edges = []
        self._used_paths = set()

    # ---- token plumbing ------------------------------------------------
    def tok(self, text, path, kind="semantic"):
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            return None
        if kind == "semantic":
            self.semantic += 1
        else:
            self.fallback += 1
        return {"text": text, "path": path, "kind": kind}

    def frags(self, *items):
        out = []
        for item in items:
            if not item:
                continue
            if isinstance(item, list):
                out.extend(x for x in item if x)
            elif isinstance(item, dict):
                out.append(item)
        return out

    def join(self, groups, sep=" "):
        out = []
        for group in groups:
            group = [x for x in group or [] if x]
            if not group:
                continue
            if out:
                out.append({"text": sep, "path": group[0]["path"], "kind": "semantic"})
            out.extend(group)
        return out

    def fb(self, path, key, value, shape=None):
        shape = shape or (norm_path(path) + "." + key)
        self.shapes[(shape, json_short(value))] += 1
        self.shape_example.setdefault(shape, json_short(value))
        return self.tok(f"⟨{key}: {json_short(value)}⟩", path, "fallback")

    def fb_token(self, path, text, shape, value=""):
        self.shapes[(shape, value)] += 1
        self.shape_example.setdefault(shape, value)
        return self.tok(f"⟨{text}⟩", path, "fallback")

    # ---- scalars -------------------------------------------------------
    def scalar(self, value, path, key=None):
        if value is None:
            return []
        if isinstance(value, bool):
            return [self.tok("yes" if value else "no", path)]
        if isinstance(value, (int, float)):
            return [self.tok(str(value), path)]
        text = str(value)
        if re.fullmatch(r"-?\d+", text):
            return [self.tok(text, path)]
        return [self.tok(text, path)]

    # ---- generic dispatch ----------------------------------------------
    def phrase(self, node, path, ctx="value"):
        self._depth += 1
        if self._depth > 80:
            self._depth -= 1
            return [self.fb_token(path, "too deep", "depth.overflow", path)]
        try:
            return self._phrase(node, path, ctx)
        finally:
            self._depth -= 1

    def _phrase(self, node, path, ctx="value"):
        if node is None:
            return []
        if isinstance(node, (str, int, float, bool)):
            return self.scalar(node, path)
        if isinstance(node, list):
            groups = [self.phrase(item, f"{path}[{i}]", ctx) for i, item in enumerate(node)]
            return self.join([g for g in groups if g], ", ")
        if not isinstance(node, dict):
            return self.scalar(node, path)
        if not node:
            return []
        kind = node.get("kind")
        if ctx == "obj":
            return self.object_phrase(node, path)
        if ctx == "amount":
            return self.amount_phrase(node, path)
        if ctx == "cond":
            return self.condition_phrase(node, path)
        if ctx == "cost":
            return self.cost_phrase(node, path)
        if ctx == "dur":
            return self.duration_phrase(node, path)
        if ctx == "event":
            return self.event_phrase(node, path)
        if kind is not None and (ctx == "kind" or "verb" not in node):
            return self.kind_phrase(node, path)
        if "verb" in node:
            return self.effect_phrase(node, path)
        if "action" in node:
            return self.cost_phrase(node, path)
        return self.object_phrase(node, path)

    def extra(self, node, path, consumed, ctx):
        out = []
        for key, value in node.items():
            if key in consumed or key in METADATA:
                continue
            if value in (None, {}, [], ""):
                continue
            out.append(self.fb(path, key, value))
        return [x for x in out if x]

    # ---- kind descriptors ---------------------------------------------
    KIND_HANDLERS = {}

    def kind_body(self, node, path):
        """(phrase, consumed_keys) for a ``kind`` descriptor, no extra walk."""
        kind = node.get("kind")
        if not isinstance(kind, str):
            body = self.phrase(kind, path + ".kind", "value")
            return [x for x in body if x], {"kind"}
        handler = self.KIND_HANDLERS.get(kind)
        if handler is None and re.fullmatch(
                r"[+-]\d+/[+-]\d+|\d+/\d+", kind):
            body = []
            used = {"kind"}
            if "count" in node:
                body += self.scalar(node["count"], path + ".count")
                used.add("count")
            body.append(self.tok(kind, path))
            return body, used
        if handler is None:
            return [self.fb(path, "kind", kind, f"kind:{kind}")], {"kind"}
        body, used = handler(self, node, path)
        return body, {"kind"} | set(used)

    def kind_phrase(self, node, path):
        body, consumed = self.kind_body(node, path)
        prefix = []
        if "count" in node and "count" not in consumed:
            prefix = self.scalar(node["count"], path + ".count")
            consumed = consumed | {"count"}
        if "unit" in node and "unit" not in consumed:
            body = body + [self.tok(str(node["unit"]), path + ".unit")]
            consumed = consumed | {"unit"}
        if "relation" in node and "relation" not in consumed:
            body = body + [self.tok(str(node["relation"]), path + ".relation")]
            consumed = consumed | {"relation"}
        suffix = []
        if "set" in node and "set" not in consumed:
            suffix = [self.tok("of", path)] + self.object_phrase(node["set"],
                                                                  path + ".set")
            consumed = consumed | {"set"}
        if "of" in node and "of" not in consumed:
            value = node["of"]
            suffix = ([self.tok("of " + pretty(value), path + ".of")]
                      if isinstance(value, str)
                      else [self.tok("of", path)] + self.phrase(value, path + ".of", "value"))
            consumed = consumed | {"of"}
        return self.join([prefix + body + suffix +
                          self.extra(node, path, consumed, "kind")])

    def _k_type(self, node, path):
        return self.scalar(node.get("value"), path + ".value"), {"value"}

    def _k_this_card(self, node, path):
        return [self.tok("THIS", path)], {"value"}

    def _k_number(self, node, path):
        out = self.scalar(node.get("value"), path + ".value")
        if "unit" in node:
            out.append(self.tok(node["unit"], path + ".unit"))
        used = {"value", "unit"}
        return out, used

    def _k_mana(self, node, path):
        symbols = node.get("symbols") or node.get("mana") or []
        out = [self.tok("".join(symbols) if isinstance(symbols, list) else str(symbols),
                        path + ".symbols")]
        return out, {"symbols", "mana"}

    def _k_mana_choice(self, node, path):
        options = node.get("options") or []
        parts = []
        for i, option in enumerate(options):
            parts += self.phrase(option, f"{path}.options[{i}]", "value")
        body = self.join([parts], ", ")
        head = [self.tok("one of", path)] if body else [self.tok("one mana", path)]
        return head + body, {"options"}

    def _k_x(self, node, path):
        return [self.tok("X", path)], set()

    def _k_relative(self, node, path):
        of = node.get("of")
        relation = node.get("relation", "equal")
        inner = self.phrase(of, path + ".of", "value")
        text = "relative("
        out = [self.tok(text, path)]
        out += inner
        out += [self.tok(f", {relation})", path + ".relation")]
        return out, {"of", "relation"}

    def _k_possessive(self, node, path):
        possessor = node.get("possessor")
        stat = node.get("stat")
        out = self.phrase(possessor, path + ".possessor", "value")
        if stat:
            out.append(self.tok(f"{stat}", path + ".stat"))
        return out, {"possessor", "stat"}

    def _k_anaphora(self, node, path):
        word = (node.get("possessive") or node.get("raw") or node.get("ref")
                or node.get("value") or "anaphor")
        used = {"possessive", "raw", "ref", "value", "anaphor"}
        return [self.tok(f"'{word}'", path)], used

    def _k_event_ref(self, node, path):
        out = [self.tok("event_ref(", path)]
        if "actor" in node:
            out += self.scalar(node["actor"], path + ".actor")
        if "polarity" in node:
            out.append(self.tok(f", {node['polarity']}", path + ".polarity"))
        out.append(self.tok(")", path))
        return out, {"actor", "polarity"}

    def _k_control(self, node, path):
        actor = node.get("actor", "you")
        target = node.get("card_target") or node.get("target") or node.get("object")
        if isinstance(target, dict) and target.get("controller"):
            target = {k: v for k, v in target.items() if k != "controller"}
            out = [self.tok(str(actor), path + ".actor"), self.tok("control", path)]
        else:
            out = [self.tok(str(actor), path + ".actor"), self.tok("control", path)]
        out += self.phrase(target, path + ".card_target", "obj")
        return out, {"actor", "card_target", "target", "object"}

    def _k_count(self, node, path):
        of = node.get("of")
        out = []
        if "count" in node:
            out += self.scalar(node["count"], path + ".count")
        if isinstance(of, str):
            out.append(self.tok("count of " + pretty(of), path + ".of"))
        else:
            out.append(self.tok("count", path))
            out += self.phrase(of, path + ".of", "value")
        used = {"of"} | ({"count"} if "count" in node else set())
        return out, used

    def _k_stat_filter(self, node, path):
        stat = node.get("stat")
        op = node.get("op")
        value = node.get("value")
        out = [self.tok(str(stat), path + ".stat"), self.tok(str(op), path + ".op")]
        out += self.scalar(value, path + ".value")
        return out, {"stat", "op", "value"}

    def _k_set(self, node, path):
        items = node.get("items") or node.get("value")
        return self.phrase(items, path + ".items", "value"), {"items", "value"}

    def _k_all(self, node, path):
        return [self.tok("all", path)], set()

    def _k_any_target(self, node, path):
        return [self.tok("any target", path)], set()

    def _k_keyword(self, node, path):
        return self.scalar(node.get("value") or node.get("keyword"), path + ".value"), \
            {"value", "keyword"}

    def _k_creature_type(self, node, path):
        return self.scalar(node.get("value"), path + ".value"), {"value"}

    def _k_predicate(self, node, path):
        out = []
        used = set()
        for key in ("value", "verb"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        for key in ("verbs", "negated", "polarity", "by", "voice", "agent"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_that_many(self, node, path):
        return [self.tok("that many", path)], set()

    def _k_that_much(self, node, path):
        return [self.tok("that much", path)], set()

    def _k_spell_state(self, node, path):
        state = node.get("state") or node.get("value") or "spell"
        return [self.tok(pretty(state), path + ".state")], {"state", "value"}

    def _k_trigger_limit(self, node, path):
        out = [self.tok("once", path)]
        if node.get("value") not in (None, ""):
            out += [self.tok("per", path), self.scalar(node["value"], path + ".value")]
        return out, {"value"}

    def _k_choice(self, node, path):
        value = node.get("value")
        return self.phrase(value, path + ".value", "value"), {"value"}

    def _k_start_engines(self, node, path):
        return [self.tok("start your engines", path)], set()

    def _k_finality(self, node, path):
        out = [self.tok("finality", path)]
        if node.get("value") is not None:
            out += self.scalar(node["value"], path + ".value")
        return out, {"value"}

    def _k_stun(self, node, path):
        out = [self.tok("stun", path)]
        if node.get("count") is not None:
            out += self.scalar(node["count"], path + ".count")
        return out, {"count"}

    def _k_copy(self, node, path):
        out = [self.tok("copy", path)]
        out += self.phrase(node.get("of"), path + ".of", "obj")
        return out, {"of"}

    def _k_target_ref(self, node, path):
        return self.scalar(node.get("value") or node.get("ref"), path + ".value"), \
            {"value", "ref"}

    def _k_count_of(self, node, path):
        out = [self.tok("count of", path)]
        out += self.phrase(node.get("of"), path + ".of", "value")
        return out, {"of"}

    def _k_event_filter(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "event", "filter", "verb", "negated"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out or [self.tok("event filter", path)], used

    def _k_card(self, node, path):
        out = []
        used = {"kind"}
        for key in ("card_type", "quantifier", "card_class", "value", "controller"):
            if key in node:
                if key == "card_type":
                    out += self.phrase(node[key], path + ".card_type", "kind")
                else:
                    out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_gift(self, node, path):
        out = [self.tok("gift", path)]
        out += self.phrase(node.get("value") or node.get("of"), path + ".value", "value")
        return out, {"value", "of"}

    def _k_half(self, node, path):
        out = [self.tok("half", path)]
        out += self.phrase(node.get("of"), path + ".of", "value")
        return out, {"of"}

    def _k_triggered_ability(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "event", "effect", "sentence"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out or [self.tok("triggered ability", path)], used

    def _k_property(self, node, path):
        out = [self.tok("property", path)]
        out += self.phrase(node.get("value") or node.get("name"), path + ".value", "value")
        return out, {"value", "name"}

    def _k_targets(self, node, path):
        out = [self.tok("targets", path)]
        out += self.phrase(node.get("value") or node.get("of"), path + ".value", "value")
        return out, {"value", "of"}

    def _k_color(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "colors", "color", "of"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_count_filter(self, node, path):
        out = [self.tok("count", path)]
        out += self.phrase(node.get("of"), path + ".of", "value")
        used = {"of"}
        for key in ("op", "value", "stat"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_mana_per(self, node, path):
        out = [self.tok("per", path)]
        out += self.phrase(node.get("of") or node.get("value"), path + ".of", "value")
        return out, {"of", "value"}

    def _k_names(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "names", "name"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_counter(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "name"):
            if key in node:
                out.append(self.tok(str(node[key]), path + "." + key))
                used.add(key)
        out.append(self.tok("counter", path))
        return out, used

    def _k_player(self, node, path):
        out = []
        used = {"kind"}
        for key in ("quantifier", "value", "player", "controller"):
            if key in node:
                if key == "quantifier" and isinstance(node[key], str):
                    out.append(self.tok(_quantifier_text(node[key]), path + "." + key))
                else:
                    out += self.scalar(node[key], path + "." + key)
                used.add(key)
        if not out:
            out = [self.tok("player", path)]
        return out, used

    def _k_spell(self, node, path):
        out = []
        used = {"kind"}
        for key in ("card_type", "card_class", "value", "quantifier", "status",
                    "controller", "this_that"):
            if key in node:
                if key == "card_type":
                    out += self.phrase(node[key], path + "." + key, "kind")
                elif key == "quantifier" and isinstance(node[key], str):
                    out.append(self.tok(_quantifier_text(node[key]), path + "." + key))
                elif isinstance(node[key], list):
                    out.append(self.tok(" ".join(str(v) for v in node[key]),
                                        path + "." + key))
                else:
                    out += self.scalar(node[key], path + "." + key)
                used.add(key)
        if not out:
            out = [self.tok("spell", path)]
        return out, used

    def _k_state(self, node, path):
        out = []
        used = {"kind"}
        for key in ("value", "state", "card_type", "verb"):
            if key in node:
                if key == "card_type":
                    out += self.phrase(node[key], path + "." + key, "kind")
                else:
                    out += self.phrase(node[key], path + "." + key, "value")
                used.add(key)
        return out, used

    def _k_event(self, node, path):
        body = [k for k in node.items() if k[0] != "kind"]
        return self.event_phrase(dict(body), path), {"kind"}

    def _k_color_of(self, node, path):
        of = node.get("of")
        inner = self.phrase(of, path + ".of", "value")
        return [self.tok("color of", path)] + inner, {"of"}

    def _k_mana_spent(self, node, path):
        out = [self.tok("mana spent", path)]
        out += self.phrase(node.get("object"), path + ".object", "obj")
        return out, {"object", "action"}

    def _k_ref(self, node, path):
        word = node.get("ref") or node.get("raw") or "it"
        used = {"ref", "raw", "anaphor"}
        return [self.tok(f"'{word}'", path)], used

    def _k_for(self, node, path):
        out = [self.tok("for", path)]
        out += self.phrase(node.get("object") or node.get("of"), path + ".object", "value")
        return out, {"object", "of"}

    def _k_quoted_ability(self, node, path):
        out = [self.tok("quote:", path)]
        sentence = node.get("sentence")
        if isinstance(sentence, list):
            for i, sub in enumerate(sentence):
                sub_path = f"{path}.sentence[{i}]"
                if isinstance(sub, dict) and sub.get("type"):
                    for j, line in enumerate(self.clause(sub, sub_path)):
                        if out and j == 0:
                            out.append(self.tok("|", sub_path))
                        out += line["fragments"]
                else:
                    out += self.phrase(sub, sub_path, "value")
        else:
            out += self.phrase(sentence, path + ".sentence", "value")
        return out, {"sentence"}

    KIND_HANDLERS = {
        "type": _k_type, "this_card": _k_this_card, "number": _k_number,
        "mana": _k_mana, "mana_choice": _k_mana_choice, "x": _k_x,
        "relative": _k_relative, "possessive": _k_possessive,
        "anaphora": _k_anaphora, "event_ref": _k_event_ref, "control": _k_control,
        "count": _k_count, "stat_filter": _k_stat_filter, "set": _k_set,
        "all": _k_all, "any_target": _k_any_target, "keyword": _k_keyword,
        "creature_type": _k_creature_type, "predicate": _k_predicate,
        "that_many": _k_that_many, "that_much": _k_that_much,
        "spell_state": _k_spell_state, "trigger_limit": _k_trigger_limit,
        "choice": _k_choice, "start_engines": _k_start_engines,
        "finality": _k_finality, "stun": _k_stun, "copy": _k_copy,
        "target_ref": _k_target_ref, "event": _k_event, "color_of": _k_color_of,
        "mana_spent": _k_mana_spent, "ref": _k_ref, "for": _k_for,
        "quoted_ability": _k_quoted_ability, "state": _k_state,
        "player": _k_player, "spell": _k_spell, "counter": _k_counter,
        "count_of": _k_count_of, "event_filter": _k_event_filter, "card": _k_card,
        "gift": _k_gift, "half": _k_half, "triggered_ability": _k_triggered_ability,
        "property": _k_property, "targets": _k_targets, "color": _k_color,
        "count_filter": _k_count_filter, "mana_per": _k_mana_per,
        "names": _k_names,
    }

    # ---- objects --------------------------------------------------------
    def object_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.phrase(node, path, "value")
        out = []
        consumed = set()
        if "kind" in node and "card_type" not in node and node.get("kind") != "cost":
            body, used = self.kind_body(node, path)
            out += body
            consumed |= used

        quantifier = node.get("quantifier")
        if quantifier is not None:
            if isinstance(quantifier, int):
                out += self.scalar(quantifier, path + ".quantifier")
            else:
                out.append(self.tok(_quantifier_text(quantifier), path + ".quantifier"))
            consumed.add("quantifier")

        if "up_to" in node:
            out.append(self.tok(f"up to {node['up_to']}", path + ".up_to"))
            consumed.add("up_to")

        this_that = node.get("this_that")
        if this_that:
            out.append(self.tok(str(this_that), path + ".this_that"))
            consumed.add("this_that")

        if "power_toughness" in node:
            pt = node["power_toughness"]
            if isinstance(pt, dict):
                out.append(self.tok(f"{pt.get('power')}/{pt.get('toughness')}",
                                    path + ".power_toughness"))
            consumed.add("power_toughness")

        for key, prefix in (("otherness", ""), ("colors", ""), ("status", "")):
            if key in node and node[key] not in (None, [], ""):
                value = node[key]
                if isinstance(value, list):
                    text = " ".join(str(v) for v in value)
                    out.append(self.tok(text, path + "." + key))
                else:
                    out.append(self.tok(str(value), path + "." + key))
                consumed.add(key)

        if "card_type" in node:
            out += self.phrase(node["card_type"], path + ".card_type", "kind")
            consumed.add("card_type")
        if "types" in node:
            types = node["types"]
            text = " ".join(str(t) for t in types) if isinstance(types, list) else str(types)
            out.append(self.tok(text, path + ".types"))
            consumed.add("types")
        if "card_class" in node:
            if "card_type" not in node:
                out.append(self.tok(str(node["card_class"]), path + ".card_class"))
            consumed.add("card_class")
        if "noncreature" in node:
            out.append(self.tok("noncreature", path + ".noncreature"))
            consumed.add("noncreature")
        if "nontoken" in node:
            value = node["nontoken"]
            if isinstance(value, list):
                out.append(self.tok("non" + "/".join(str(v) for v in value), path + ".nontoken"))
            else:
                out.append(self.tok("nontoken", path + ".nontoken"))
            consumed.add("nontoken")
        if "controller" in node:
            out.append(self.tok(str(node["controller"]), path + ".controller"))
            consumed.add("controller")
        if "stat" in node:
            out.append(self.tok(str(node["stat"]), path + ".stat"))
            consumed.add("stat")
        if "attached_to" in node:
            out += [self.tok("attached to", path)] + \
                self.object_phrase(node["attached_to"], path + ".attached_to")
            consumed.add("attached_to")
        if "options" in node:
            out.append(self.tok(pretty(node["options"]), path + ".options"))
            consumed.add("options")
        if "library_position" in node:
            out.append(self.tok(pretty(node["library_position"]), path + ".library_position"))
            consumed.add("library_position")
        if "damage" in node:
            out.append(self.tok(f"{node['damage']} damage", path + ".damage"))
            consumed.add("damage")
        if "to" in node and isinstance(node["to"], dict):
            out += [self.tok("to", path + ".to")] + self.object_phrase(node["to"],
                                                                       path + ".to")
            consumed.add("to")
        if "owner" in node:
            out += [self.tok("owner", path), self.scalar(node["owner"], path + ".owner")]
            consumed.add("owner")
        if "count" in node and "counter" not in node:
            out += self.scalar(node["count"], path + ".count")
            consumed.add("count")
        for key in ("kw", "keywords", "keyword"):
            if key in node:
                value = node[key]
                if isinstance(value, list) and value and isinstance(value[0], list):
                    value = [v for group in value for v in group]
                out += self._keyword_list(value, path + "." + key)
                consumed.add(key)
        if "cast_by" in node:
            out += [self.tok("cast by", path), self.scalar(node["cast_by"], path + ".cast_by")]
            consumed.add("cast_by")
        if "modifier" in node:
            modifier = node["modifier"]
            if isinstance(modifier, dict) and modifier.get("kind") == "stat_filter":
                out.append(self.tok("with", path))
                out += self.kind_phrase(modifier, path + ".modifier")
            else:
                out += self.phrase(modifier, path + ".modifier", "value")
            consumed.add("modifier")
        for key in ("keyword", "keywords"):
            if key in node:
                out += self._keyword_list(node[key], path + "." + key)
                consumed.add(key)
        if "counter" in node:
            out += self.phrase(node["counter"], path + ".counter", "kind")
            out.append(self.tok("counter", path + ".counter"))
            consumed.add("counter")
        if "quote" in node:
            out += self.phrase(node["quote"], path + ".quote", "value")
            consumed.add("quote")
        if "copy_of" in node:
            out += [self.tok("copy of", path)] + \
                self.phrase(node["copy_of"], path + ".copy_of", "obj")
            consumed.add("copy_of")
        if "named" in node:
            out.append(self.tok(f"named {node['named']}", path + ".named"))
            consumed.add("named")
        if "zone" in node:
            out += self.zone_phrase(node, path)
            consumed |= {"zone", "possessor", "prep", "anaphor", "possessive"}
        if "top" in node:
            out += [self.tok("top", path + ".top")] if node["top"] else []
            consumed.add("top")
        if "position" in node:
            out.append(self.tok(str(node["position"]), path + ".position"))
            consumed.add("position")
        if "tapped" in node:
            out.append(self.tok("tapped", path + ".tapped"))
            consumed.add("tapped")
        if "ref" in node or "raw" in node:
            word = node.get("raw") or node.get("ref")
            out.append(self.tok(f"'{word}'", path))
            consumed |= {"ref", "raw", "anaphor"}
        if "items" in node or "or" in node or "and" in node:
            key = "or" if "or" in node else "and" if "and" in node else "items"
            sep = " or " if key == "or" else " and " if key == "and" else ", "
            items = node.get(key)
            groups = [self.phrase(item, f"{path}.{key}[{i}]", "obj")
                      for i, item in enumerate(items or [])]
            body = self.join([g for g in groups if g], sep)
            if body:
                out.append(self.tok("(", path + "." + key))
                out += body
                out.append(self.tok(")", path + "." + key))
            consumed.add(key)
        out += self.extra(node, path, consumed, "obj")
        return self.join([out])

    def _keyword_list(self, value, path):
        if isinstance(value, str):
            return [self.tok(value, path)]
        out = []
        for i, item in enumerate(value or []):
            item_path = f"{path}[{i}]"
            if isinstance(item, dict):
                out += self.phrase(item, item_path, "kind")
            else:
                out.append(self.tok(str(item), item_path))
        return out

    def zone_phrase(self, node, path):
        prep = node.get("prep") or "in"
        possessor = node.get("possessor")
        zone = node.get("zone")
        out = [self.tok(str(prep), path + ".prep")]
        if possessor:
            possessor_text = {"you": "your", "they": "their", "it": "its"}.get(
                str(possessor), str(possessor))
            out.append(self.tok(possessor_text, path + ".possessor"))
        out.append(self.tok(str(zone), path + ".zone"))
        return out

    # ---- amounts --------------------------------------------------------
    def amount_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        kind = node.get("kind")
        if kind is not None:
            return self.kind_phrase(node, path)
        out = []
        if "set" in node:
            out += [self.tok("set of", path)] + self.object_phrase(node["set"],
                                                                    path + ".set")
            node = {k: v for k, v in node.items() if k != "set"}
        if "of" in node and not isinstance(node["of"], dict):
            out.append(self.tok(pretty(node["of"]), path + ".of"))
        if "count" in node:
            out += self.scalar(node["count"], path + ".count")
        elif "value" in node:
            out += self.scalar(node["value"], path + ".value")
        if "counter" in node:
            out += self.phrase(node["counter"], path + ".counter", "kind")
            out.append(self.tok("counter", path + ".counter"))
        if "unit" in node:
            out.append(self.tok(str(node["unit"]), path + ".unit"))
        consumed = {"count", "value", "counter", "unit"}
        if "of" in node and not isinstance(node["of"], dict):
            consumed.add("of")
        out += self.extra(node, path, consumed, "amount")
        return self.join([out])

    # ---- conditions -----------------------------------------------------
    def condition_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        if "verb" in node or "subject" in node:
            return self.event_phrase(node, path)
        out = []
        consumed = set()
        if "kind" in node:
            body, used = self.kind_body(node, path)
            out += body
            consumed |= used
        if "fragment" in node:
            out.append(self.fb_token(path, f"fragment: {node['fragment']}",
                                     norm_path(path) + ".fragment", node["fragment"]))
            consumed.add("fragment")
        if "if" in node:
            out += [self.tok("if", path)] + self.phrase(node["if"], path + ".if", "cond")
            consumed.add("if")
        if "unless" in node:
            out += [self.tok("unless", path)] + self.phrase(node["unless"], path + ".unless", "cond")
            consumed.add("unless")
        if "condition" in node:
            out += self.phrase(node["condition"], path + ".condition", "cond")
            consumed.add("condition")
        if "quantity" in node:
            out += self.quantity_phrase(node["quantity"], path + ".quantity")
            consumed.add("quantity")
        if "state" in node:
            out += self.phrase(node["state"], path + ".state", "value")
            consumed.add("state")
        if "source" in node and isinstance(node["source"], (dict, list)):
            out += self.phrase(node["source"], path + ".source", "value")
            consumed.add("source")
        if "event" in node:
            out += self.event_phrase(node["event"], path + ".event")
            consumed.add("event")
        if "this_turn" in node and node["this_turn"]:
            out.append(self.tok("this turn", path + ".this_turn"))
            consumed.add("this_turn")
        out += self.extra(node, path, consumed, "cond")
        return self.join([out])

    def quantity_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        out = []
        consumed = set()
        for key, word in (("at_least", "at least"), ("at_most", "at most"),
                          ("value", ""), ("count", "")):
            if key in node:
                if word:
                    out.append(self.tok(word, path + "." + key))
                out += self.scalar(node[key], path + "." + key)
                consumed.add(key)
        for key in ("op", "unit", "stat"):
            if key in node:
                out.append(self.tok(str(node[key]), path + "." + key))
                consumed.add(key)
        return self.join([out + self.extra(node, path, consumed, "quantity")])

    # ---- costs ----------------------------------------------------------
    def cost_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        action = node.get("action")
        out = []
        consumed = {"action", "kind"}
        action_text = {
            "pay_mana": "pay", "pay_life": "pay", "pay_energy": "pay",
            "sacrifice": "sacrifice", "discard": "discard", "exile": "exile",
            "tap": "tap", "untap": "untap", "mill": "mill", "reveal": "reveal",
            "return": "return", "remove_counter": "remove", "loyalty": "loyalty",
            "pay_x": "pay", "behold": "behold", "blight": "blight",
            "collect_evidence": "collect evidence", "waterbend": "waterbend",
        }.get(action, pretty(action) if action else "cost")
        out.append(self.tok(action_text, path + ".action"))
        if "mana" in node:
            mana = node["mana"]
            out.append(self.tok(" ".join(mana) if isinstance(mana, list) else str(mana),
                                path + ".mana"))
            consumed.add("mana")
        if "amount" in node:
            out += self.amount_phrase(node["amount"], path + ".amount")
            consumed.add("amount")
        for key in ("card", "target", "card_target"):
            if key in node:
                out += self.phrase(node[key], path + "." + key, "obj")
                consumed.add(key)
        if "value" in node:
            out += self.scalar(node["value"], path + ".value")
            consumed.add("value")
        out += self.extra(node, path, consumed, "cost")
        return self.join([out])

    # ---- durations ------------------------------------------------------
    def duration_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        if node.get("kind") == "until" or "event" in node or "phase" in node:
            event = node.get("event") or node.get("phase")
            out = [self.tok("until", path + ".kind")]
            if node.get("player") and str(node["player"]) not in ("you", "your"):
                out.append(self.tok(str(node["player"]), path + ".player"))
            if node.get("which"):
                out.append(self.tok(str(node["which"]), path + ".which"))
            out.append(self.tok(pretty(event) if event else "further notice",
                                path + ".event"))
            return self.join([out])
        return self.phrase(node, path, "value")

    # ---- events ---------------------------------------------------------
    def event_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.scalar(node, path)
        if ("kind" in node and "verb" not in node and "subject" not in node
                and "event" not in node and node.get("kind") != "event"):
            return self.kind_phrase(node, path)
        out = []
        consumed = {"kind"}
        if "state" in node:
            out += self.phrase(node["state"], path + ".state", "value")
            consumed.add("state")
        subject = node.get("subject")
        if subject is not None:
            subj = self.phrase(subject, path + ".subject", "obj")
            if subj:
                out += subj
            consumed.add("subject")
        if "ability_word" in node:
            out.append(self.tok(f"[{node['ability_word']}]", path + ".ability_word"))
            consumed.add("ability_word")
        if "verb" in node:
            out.append(self.tok(pretty(node["verb"]), path + ".verb"))
            consumed.add("verb")
        elif "subject" in node:
            pass
        if "verbs" in node:
            out.append(self.tok(", ".join(pretty(v) for v in node["verbs"]), path + ".verbs"))
            consumed.add("verbs")
        for key in ("object", "card", "to", "into"):
            if key in node and node[key] not in (None, {}):
                out += self.phrase(node[key], path + "." + key, "obj")
                consumed.add(key)
        if "counter" in node:
            out += self.phrase(node["counter"], path + ".counter", "kind")
            out.append(self.tok("counter", path + ".counter"))
            consumed.add("counter")
        if "count" in node:
            out += self.scalar(node["count"], path + ".count")
            consumed.add("count")
        if "window" in node:
            out.append(self.tok(str(node["window"]), path + ".window"))
            consumed.add("window")
        if "ordinal" in node:
            out.append(self.tok(str(node["ordinal"]), path + ".ordinal"))
            consumed.add("ordinal")
        if "alone" in node and node["alone"]:
            out.append(self.tok("alone", path + ".alone"))
            consumed.add("alone")
        if node.get("this_way"):
            out.append(self.tok("this way", path + ".this_way"))
            consumed.add("this_way")
        if "this_turn" in node:
            if node["this_turn"]:
                out.append(self.tok("this turn", path + ".this_turn"))
            consumed.add("this_turn")
        if "event" in node and isinstance(node["event"], dict):
            out += self.event_phrase(node["event"], path + ".event")
            consumed.add("event")
        if "polarity" in node and node["polarity"] not in ("positive",):
            out.append(self.tok(str(node["polarity"]), path + ".polarity"))
            consumed.add("polarity")
        if "condition" in node:
            out += [self.tok("if", path)] + self.condition_phrase(node["condition"],
                                                                  path + ".condition")
            consumed.add("condition")
        out += self.extra(node, path, consumed, "event")
        return self.join([out])

    # ---- effects --------------------------------------------------------
    def effect_phrase(self, node, path):
        if isinstance(node, list):
            groups = [self.effect_phrase(item, f"{path}[{i}]") for i, item in enumerate(node)]
            return self.join([g for g in groups if g], "; ")
        if not isinstance(node, dict):
            return self.scalar(node, path)
        verb = node.get("verb")
        out = []
        consumed = {"verb"}
        if verb == "may" and "inner" in node:
            out.append(self.tok("may", path + ".verb"))
            out += self.effect_phrase(node["inner"], path + ".inner")
            consumed.add("inner")
            for key, value in node.items():
                if key in consumed or key in METADATA or value in (None, {}, [], ""):
                    continue
                out += self._effect_detail(key, value, path, consumed)
            return self.join([out])

        subject = node.get("source") or node.get("who") or node.get("actor") \
            or node.get("who_does")
        if subject is None and verb in SUBJECT_VERBS and isinstance(node.get("card"), dict):
            subject = node["card"]
        if subject is not None and "source" in node:
            subj = self.phrase(node["source"], path + ".source", "obj")
            if subj:
                out += subj
        elif subject is not None and verb in SUBJECT_VERBS and isinstance(node.get("card"), dict):
            out += self.phrase(node["card"], path + ".card", "obj")
            consumed.add("card")
        elif "who" in node:
            out += self.scalar(node["who"], path + ".who")
        elif "actor" in node:
            out += self.scalar(node["actor"], path + ".actor")
        elif "who_does" in node:
            out += self.scalar(node["who_does"], path + ".who_does")
        consumed |= {"source", "who", "actor", "who_does"}

        out.append(self.tok(pretty(verb), path + ".verb"))

        for key, value in node.items():
            if key in consumed or key in METADATA or value in (None, {}, [], ""):
                continue
            out += self._effect_detail(key, value, path, consumed)
        return self.join([out])

    def _effect_detail(self, key, value, path, consumed):
        sub = path + "." + key
        out = []
        if key in ("target", "card", "to", "object", "from", "on", "into"):
            connector = {"target": "→", "card": "→", "to": "→", "object": "→",
                         "from": "←", "on": "on", "into": "into"}[key]
            out.append(self.tok(connector, sub))
            out += self.phrase(value, sub, "obj")
        elif key in ("amount", "count", "xdef"):
            out.append(self.tok(f"[{key} =", sub))
            if key == "amount":
                out += self.amount_phrase(value, sub)
            else:
                out += self.scalar(value, sub)
            out.append(self.tok("]", sub))
        elif key == "change":
            if isinstance(value, dict):
                p, t = value.get("power"), value.get("toughness")
                text = f"{_signed(p)}/{_signed(t)}"
                out.append(self.tok(text, sub))
            else:
                out += self.scalar(value, sub)
        elif key in ("keywords", "keyword"):
            out += self._keyword_list(value, sub)
        elif key == "types":
            text = " ".join(str(t) for t in value) if isinstance(value, list) else str(value)
            out.append(self.tok(text, sub))
        elif key == "token":
            out += self.phrase(value, sub, "obj")
            out.append(self.tok("token", sub))
        elif key == "counter":
            out += self.phrase(value, sub, "kind")
            out.append(self.tok("counter", sub))
        elif key == "with":
            out.append(self.tok("with", sub))
            out += self.with_phrase(value, sub)
        elif key == "for_each":
            out.append(self.tok("for each", sub))
            out += self.phrase(value, sub, "value")
        elif key == "duration":
            out.append(self.tok("[duration:", sub))
            out += self.duration_phrase(value, sub)
            out.append(self.tok("]", sub))
        elif key in ("zone", "destination"):
            if isinstance(value, dict):
                out.append(self.tok("to", sub))
                out += self.object_phrase(value, sub)
            else:
                out.append(self.tok(f"to {value}", sub))
        elif key == "owner":
            out += [self.tok("owner", sub), self.scalar(value, sub)]
        elif key == "position":
            out.append(self.tok(str(value), sub))
        elif key == "top":
            if value:
                out.append(self.tok("top", sub))
        elif key == "cards":
            out += self.scalar(value, sub)
            out.append(self.tok("cards", sub))
        elif key == "from_among":
            out += [self.tok("from among", sub)] + self.object_phrase(value, sub)
        elif key == "without_paying":
            out.append(self.tok("without paying", sub))
        elif key == "additional_land":
            out.append(self.tok("additional land", sub))
        elif key == "by":
            out += [self.tok("by", sub)] + self.phrase(value, sub, "obj")
        elif key == "player":
            out += [self.tok("player", sub), self.scalar(value, sub)]
        elif key in ("condition", "trailing_if", "if"):
            out.append(self.tok("if", sub))
            out += self.condition_phrase(value, sub)
        elif key == "up_to":
            out.append(self.tok(f"up to {value}", sub))
        elif key == "tapped":
            out.append(self.tok("tapped", sub))
        elif key == "inner":
            out += self.effect_phrase(value, sub)
        elif key == "quote":
            out += self.phrase(value, sub, "value")
        elif key == "mode":
            out += [self.tok("mode", sub), self.scalar(value, sub)]
        elif key == "otherwise":
            out += [self.tok("otherwise", sub), self.effect_phrase(value, sub)]
        elif key in ("ref", "raw"):
            out.append(self.tok(f"'{value}'", sub))
        elif key == "action":
            out.append(self.tok(pretty(value), sub))
        elif key == "per":
            out += [self.tok("per", sub)] + self.phrase(value, sub, "value")
        elif key == "symbol":
            out.append(self.tok(str(value), sub))
        elif key == "modal":
            out.append(self.tok(str(value), sub))
        elif key == "direction":
            out.append(self.tok(str(value), sub))
        elif key == "instead":
            if value:
                out.append(self.tok("instead", sub))
        elif key == "in_addition":
            if value:
                out.append(self.tok("in addition", sub))
        elif key == "rest":
            if value:
                out.append(self.tok("the rest", sub))
        elif key == "placement":
            out.append(self.tok(f"on the {value}", sub))
        elif key == "order":
            out.append(self.tok(f"in {value} order", sub))
        elif key == "timing" and isinstance(value, dict):
            out.append(self.tok("at the", sub))
            if value.get("position"):
                out.append(self.tok(str(value["position"]), sub + ".position"))
            out.append(self.tok("of the", sub))
            if value.get("which"):
                out.append(self.tok(str(value["which"]), sub + ".which"))
            if value.get("phase"):
                out.append(self.tok(pretty(value["phase"]), sub + ".phase"))
            for key2, val2 in value.items():
                if key2 in ("position", "which", "phase"):
                    continue
                out += self.scalar(val2, sub + "." + key2)
        elif key == "predicate":
            out += self.phrase(value, sub, "value")
        elif key == "stat":
            out.append(self.tok(str(value), sub))
        elif key in ("value", "unit", "op", "symbols", "mana"):
            out += self.scalar(value, sub) if key != "symbols" else \
                [self.tok("".join(value) if isinstance(value, list) else str(value), sub)]
        elif key == "kind":
            out += self.kind_phrase({"kind": value}, sub) if isinstance(value, str) else []
        else:
            accepted = False
            if isinstance(value, (dict, list)):
                out += self.phrase(value, sub, "value")
                accepted = True
            if not accepted:
                out.append(self.fb(path, key, value, norm_path(path) + ".⟨" + key + "⟩"))
        consumed.add(key)
        return out

    def with_phrase(self, node, path):
        if not isinstance(node, dict):
            return self.phrase(node, path, "value")
        out = []
        consumed = set()
        if "count" in node:
            out += self.scalar(node["count"], path + ".count")
            consumed.add("count")
        if "counter" in node:
            out += self.phrase(node["counter"], path + ".counter", "kind")
            out.append(self.tok("counter", path))
            consumed.add("counter")
        if "card_type" in node:
            out += self.phrase(node["card_type"], path + ".card_type", "kind")
            consumed.add("card_type")
        for key in ("for_each", "additional", "base", "values", "and"):
            if key in node:
                if key == "for_each":
                    out.append(self.tok("for each", path + ".for_each"))
                    out += self.phrase(node[key], path + ".for_each", "value")
                else:
                    out += self.phrase(node[key], path + "." + key, "value")
                consumed.add(key)
        out += self.extra(node, path, consumed, "with")
        return self.join([out])

    # ---- graph ----------------------------------------------------------
    def gnode(self, label, kind, path):
        if len(self.nodes) >= MAX_GRAPH_NODES:
            return None
        if not label:
            return None
        label = re.sub(r"\s+", " ", label).strip()
        if len(label) > 46:
            label = label[:45] + "…"
        node = {"id": f"n{len(self.nodes) + 1}", "label": label, "kind": kind,
                "path": path}
        self.nodes.append(node)
        self._used_paths.add(path)
        return node["id"]

    def gedge(self, source, target, role, dashed=False):
        if not source or not target or source == target:
            return
        edge = {"from": source, "to": target, "role": role}
        if dashed:
            edge["dashed"] = True
        if edge not in self.edges:
            self.edges.append(edge)

    # ---- clauses --------------------------------------------------------
    def clause(self, node, path):
        if not isinstance(node, dict):
            return [self.line("RAW", path, self.scalar(node, path))]
        ctype = node.get("type")
        handler = getattr(self, "clause_" + str(ctype), None) if ctype else None
        word = node.get("ability_word")
        xdef = node.get("xdef")
        if word is not None or xdef is not None:
            node = {k: v for k, v in node.items() if k not in ("ability_word", "xdef")}
        lines = []
        if handler is not None:
            lines = handler(node, path)
        else:
            header = [self.tok(f"[{ctype or 'clause'}]", path)]
            body = []
            consumed = {"type"}
            for key, value in node.items():
                if key in consumed or key in METADATA or value in (None, {}, [], ""):
                    continue
                if key in ("effect", "if", "instead", "condition", "trigger", "cost",
                           "duration", "keywords", "target"):
                    continue
                body.append(self.fb(path, key, value))
            lines = [self.line("CLAUSE", path, header + body)]
        if word:
            lines.insert(0, self.line("WORD", path + ".ability_word",
                                      [self.tok(f"[{word}]", path + ".ability_word")]))
        if xdef is not None:
            lines.append(self.line("XDEF", path + ".xdef",
                                   [self.tok("xdef =", path + ".xdef")] +
                                   self.xdef_phrase(xdef, path + ".xdef")))
        return lines

    def line(self, role, path, frags):
        flat = []

        def add(item):
            if not item:
                return
            if isinstance(item, list):
                for sub in item:
                    add(sub)
            elif isinstance(item, dict) and "text" in item:
                flat.append(item)
            else:
                self.fb_token(path, f"unrendered: {json_short(item)}",
                              norm_path(path) + ".line.junk", json_short(item))

        for item in frags:
            add(item)
        frags = flat
        return {"role": role, "path": path, "fragments": frags,
                "kind": "fallback" if any(f["kind"] == "fallback" for f in frags)
                else "semantic"}

    def _effect_lines(self, role, effect, path):
        if isinstance(effect, list):
            return [self.line(role, f"{path}[{i}]",
                              self.effect_phrase(item, f"{path}[{i}]"))
                    for i, item in enumerate(effect)]
        return [self.line(role, path, self.effect_phrase(effect, path))]

    # -- per-type clause renderers ---------------------------------------
    def clause_activated(self, node, path):
        self._cost_nodes = []
        lines = [self.line("TYPE", path, [self.tok("[activated]", path)])]
        verb_id = object_id = amount_id = dest_id = dur_id = None
        if "cost" in node:
            costs = node["cost"] if isinstance(node["cost"], list) else [node["cost"]]
            frags = []
            cost_ids = []
            for i, cost in enumerate(costs):
                cpath = f"{path}.cost[{i}]"
                phrase = self.cost_phrase(cost, cpath)
                if phrase:
                    if frags:
                        frags.append({"text": ";", "path": cpath, "kind": "semantic"})
                    frags += phrase
                    cost_ids.append((self.join([phrase]), cpath))
            lines.append(self.line("COST", path + ".cost", frags))
            self._cost_nodes = cost_ids
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
            if isinstance(eff, dict):
                verb_id = self.gnode(pretty(eff.get("verb", "")), "verb", path + ".effect.verb")
                object_id = self._graph_object(eff, path + ".effect", verb_id)
                amount_id = self._graph_amount(eff, path + ".effect", verb_id, object_id)
                dest_id = self._graph_destination(eff, path + ".effect", verb_id)
                dur_id = self._graph_duration(eff, path + ".effect", verb_id)
                self._graph_subject(eff, path + ".effect", verb_id)
                for phrase, cpath in getattr(self, "_cost_nodes", []):
                    cid = self.gnode(_phrase_text(phrase), "cost", cpath)
                    self.gedge(cid, verb_id, "cost")
        if "duration" in node:
            lines.append(self.line("DURATION", path + ".duration",
                                   [self.tok("[duration:", path + ".duration")] +
                                    self.duration_phrase(node["duration"], path + ".duration") +
                                    [self.tok("]", path + ".duration")]))
            dur_id = self.gnode(_phrase_text(self.duration_phrase(node["duration"],
                                                                 path + ".duration")),
                                "duration", path + ".duration")
            self.gedge(verb_id, dur_id, "duration")
        return lines

    def clause_effect(self, node, path):
        lines = []
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
            verb_id = self._graph_effect(eff, path + ".effect")
        consumed = {"type", "effect"}
        if "target" in node:
            lines.append(self.line("SUBJECT", path + ".target",
                                   self.object_phrase(node["target"], path + ".target")))
            consumed.add("target")
        for cond_key in ("condition", "if"):
            if cond_key in node:
                lines.append(self.line("IF", path + "." + cond_key,
                                       [self.tok("if", path + "." + cond_key)] +
                                       self.condition_phrase(node[cond_key],
                                                             path + "." + cond_key)))
                consumed.add(cond_key)
        if "duration" in node:
            lines.append(self.line("DURATION", path + ".duration",
                                   [self.tok("[duration:", path + ".duration")] +
                                   self.duration_phrase(node["duration"], path + ".duration") +
                                   [self.tok("]", path + ".duration")]))
            consumed.add("duration")
        extra = self.extra(node, path, consumed, "clause")
        if extra:
            lines.append(self.line("OTHER", path, extra))
        if not lines:
            lines = [self.line("CLAUSE", path, [self.tok("[effect]", path)])]
        return lines

    def clause_choose(self, node, path):
        frags = [self.tok("[choose]", path)]
        if "choose" in node:
            frags.append(self.tok(f"choose {node['choose']}", path + ".choose"))
        lines = [self.line("CHOOSE", path, frags)]
        for key in ("choices", "modes", "effects", "options"):
            value = node.get(key)
            if isinstance(value, list):
                for i, item in enumerate(value):
                    sub = f"{path}.{key}[{i}]"
                    if isinstance(item, dict) and item.get("type"):
                        lines += self.clause(item, sub)
                    else:
                        lines.append(self.line("OPTION", sub,
                                               self.phrase(item, sub, "value")))
        consumed = {"type", "choose", "choices", "modes", "effects", "options"}
        extra = self.extra(node, path, consumed, "clause")
        if extra:
            lines.append(self.line("OTHER", path, extra))
        return lines

    def clause_level(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[level]", path)])]
        if "level" in node:
            lines.append(self.line("LEVEL", path + ".level",
                                   [self.tok("level", path + ".level"),
                                    self.tok(str(node["level"]), path + ".level")]))
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
        extra = self.extra(node, path, {"type", "level", "effect"}, "clause")
        if extra:
            lines.append(self.line("OTHER", path, extra))
        return lines

    def clause_class(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[class]", path)])]
        if "cost" in node:
            lines.append(self.line("COST", path + ".cost",
                                   self.cost_phrase(node["cost"], path + ".cost")))
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
        extra = self.extra(node, path, {"type", "cost", "effect"}, "clause")
        if extra:
            lines.append(self.line("OTHER", path, extra))
        return lines

    def xdef_phrase(self, node, path):
        if isinstance(node, dict) and "xdef" in node:
            return self.xdef_phrase(node["xdef"], path + ".xdef")
        if isinstance(node, list):
            parts = []
            for i, item in enumerate(node):
                if isinstance(item, str):
                    parts.append(self.tok(item, f"{path}[{i}]"))
                else:
                    parts += self.phrase(item, f"{path}[{i}]", "value")
            return parts
        return self.phrase(node, path, "value")

    def _graph_keywords(self, eff, path, verb_id):
        value = eff.get("keywords") or eff.get("keyword")
        if not value or not isinstance(value, list):
            return
        for i, keyword in enumerate(value):
            text = keyword if isinstance(keyword, str) else json_short(keyword, 30)
            kid = self.gnode(str(text), "keyword", f"{path}.keywords[{i}]")
            self.gedge(verb_id, kid, "keyword")

    clause_loyalty = clause_activated
    clause_cost_dash = clause_activated
    clause_spree_mode = clause_activated

    def clause_triggered(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[triggered]", path)])]
        trigger = node.get("trigger")
        event_id = None
        if isinstance(trigger, dict):
            when = trigger.get("when")
            event = trigger.get("event") or {}
            frags = []
            if when:
                frags.append(self.tok(str(when), path + ".trigger.when"))
            frags += self.event_phrase(event, path + ".trigger.event")
            lines.append(self.line("WHEN", path + ".trigger", frags))
            event_id = self.gnode(_phrase_text(frags), "event", path + ".trigger.event")
            subj = event.get("subject") if isinstance(event, dict) else None
            if isinstance(subj, dict) and subj:
                sp = self.object_phrase(subj, path + ".trigger.event.subject")
                sid = self.gnode(_phrase_text(sp), "subject",
                                 path + ".trigger.event.subject")
                self.gedge(sid, event_id, "subject")
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
            verb_id = self._graph_effect(eff, path + ".effect")
            if verb_id:
                self.gedge(event_id, verb_id, "trigger")
                cond_key = ("trailing_if" if "trailing_if" in node
                            else "if" if "if" in node else None)
                if cond_key:
                    cond = node[cond_key]
                    lines.append(self.line("IF", path + "." + cond_key,
                                           [self.tok("if", path + "." + cond_key)] +
                                           self.condition_phrase(cond, path + "." + cond_key)))
                    self._graph_condition(cond, path + "." + cond_key, verb_id)
        return lines

    def clause_if(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[if]", path)])]
        cond = node.get("condition")
        verb_id = None
        if cond is not None:
            lines.append(self.line("IF", path + ".condition",
                                   [self.tok("if", path + ".condition")] +
                                   self.condition_phrase(cond, path + ".condition")))
            verb_id = self._graph_condition(cond, path + ".condition", None)
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("THEN", eff, path + ".effect")
            if isinstance(eff, dict):
                vid = self.gnode(pretty(eff.get("verb", "")), "verb", path + ".effect.verb")
                self.gedge(verb_id, vid, "condition")
                self._graph_object(eff, path + ".effect", vid)
                self._graph_amount(eff, path + ".effect", vid)
        return lines

    def clause_until(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[until]", path)])]
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
        if "duration" in node:
            lines.append(self.line("DURATION", path + ".duration",
                                   [self.tok("[duration:", path + ".duration")] +
                                   self.duration_phrase(node["duration"], path + ".duration") +
                                   [self.tok("]", path + ".duration")]))
        return lines

    def clause_static(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[static]", path)])]
        if "target" in node:
            lines.append(self.line("SUBJECT", path + ".target",
                                   self.object_phrase(node["target"], path + ".target")))
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("STATIC", eff, path + ".effect")
            self._graph_effect(eff, path + ".effect")
        return lines

    def clause_static_keyword(self, node, path):
        keywords = node.get("keywords") or []
        frags = []
        for i, keyword in enumerate(keywords):
            frags += self._keyword_list([keyword], f"{path}.keywords")
            if i < len(keywords) - 1:
                frags.append({"text": ";", "path": path + ".keywords", "kind": "semantic"})
        return [self.line("TYPE", path, [self.tok("[static_keyword]", path)]),
                self.line("KEYWORDS", path + ".keywords", frags)]

    def clause_additional_cost(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[additional_cost]", path)])]
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("COST", eff, path + ".effect")
        return lines

    def clause_replacement(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[replacement]", path)])]
        if "if" in node:
            lines.append(self.line("IF", path + ".if",
                                   [self.tok("if", path + ".if")] +
                                   self.condition_phrase(node["if"], path + ".if")))
        if "instead" in node:
            lines.append(self.line("INSTEAD", path + ".instead",
                                   [self.tok("instead", path + ".instead")] +
                                   self.effect_phrase(node["instead"], path + ".instead")))
        return lines

    def clause_as_long(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[as_long]", path)])]
        if "condition" in node:
            lines.append(self.line("AS LONG AS", path + ".condition",
                                   [self.tok("as long as", path + ".condition")] +
                                   self.condition_phrase(node["condition"],
                                                         path + ".condition")))
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
        return lines

    def clause_during(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[during]", path)])]
        if "time" in node:
            time = node["time"]
            text = " ".join(str(t) for t in time) if isinstance(time, list) else str(time)
            lines.append(self.line("TIME", path + ".time",
                                   [self.tok("during", path), self.tok(text, path + ".time")]))
        eff = node.get("effect")
        if eff is not None:
            lines += self._effect_lines("DO", eff, path + ".effect")
        return lines

    def clause_craft(self, node, path):
        lines = [self.line("TYPE", path, [self.tok("[craft]", path)])]
        if "cost" in node:
            cost = node["cost"]
            if isinstance(cost, str):
                lines.append(self.line("COST", path + ".cost",
                                       [self.tok("craft with", path + ".cost"),
                                        self.tok(cost, path + ".cost")]))
            else:
                lines.append(self.line("COST", path + ".cost",
                                       self.cost_phrase(cost, path + ".cost")))
        if "with" in node:
            lines.append(self.line("WITH", path + ".with",
                                   [self.tok("with", path + ".with")] +
                                   self.object_phrase(node["with"], path + ".with")))
        return lines

    def clause_modal(self, node, path):
        frags = [self.tok("[modal]", path)]
        if "choose" in node:
            frags.append(self.tok(f"choose {node['choose']}", path + ".choose"))
        return [self.line("CHOOSE", path, frags)]

    def clause_unparsed(self, node, path):
        text = node.get("fragment") or ""
        return [self.line("UNPARSED", path,
                          [self.fb_token(path, f"unparsed: {text}",
                                         "unparsed.fragment", text)])]

    # -- graph helpers ----------------------------------------------------
    def _graph_subject(self, eff, path, verb_id):
        node = eff.get("source")
        key = "source"
        if not isinstance(node, dict) and eff.get("verb") in SUBJECT_VERBS \
                and isinstance(eff.get("card"), dict):
            node, key = eff["card"], "card"
        if isinstance(node, dict) and node:
            phrase = self.object_phrase(node, path + "." + key)
            sid = self.gnode(_phrase_text(phrase), "subject", path + "." + key)
            self.gedge(sid, verb_id, "subject")
            self._graph_anaphora(node, path + "." + key, sid)

    def _graph_object(self, eff, path, verb_id):
        for key in ("target", "to", "card", "object", "token"):
            node = eff.get(key)
            if isinstance(node, dict) and node:
                phrase = self.object_phrase(node, path + "." + key)
                kind = "token" if key == "token" else "object"
                oid = self.gnode(_phrase_text(phrase), kind, path + "." + key)
                self.gedge(verb_id, oid, "object")
                self._graph_anaphora(node, path + "." + key, oid)
                return oid
        return None

    def _graph_amount(self, eff, path, verb_id, object_id=None):
        node = eff.get("amount")
        if node is None:
            return None
        phrase = self.amount_phrase(node, path + ".amount")
        aid = self.gnode(_phrase_text(phrase), "amount", path + ".amount")
        self.gedge(verb_id, aid, "amount")
        if object_id:
            self.gedge(object_id, aid, "of")
        self._graph_anaphora(node, path + ".amount", aid)
        if isinstance(node, dict):
            if node.get("kind") == "possessive":
                poss = node.get("possessor")
                if isinstance(poss, dict) and (poss.get("anaphor")
                                               or poss.get("kind") in ("anaphora", "ref")):
                    word = poss.get("possessive") or poss.get("raw") or poss.get("ref") or "its"
                    aid2 = self.gnode(f"anaphor: {word}", "anaphor",
                                      path + ".amount.of.possessor")
                    self.gedge(aid, aid2, "anaphora", dashed=True)
            inner = node.get("of")
            if isinstance(inner, str):
                phrase = [self.tok(pretty(inner), path + ".amount.of")]
                iid = self.gnode(_phrase_text(phrase), "amount", path + ".amount.of")
                self.gedge(aid, iid, "of")
            elif isinstance(inner, dict):
                phrase = self.phrase(inner, path + ".amount.of", "value")
                iid = self.gnode(_phrase_text(phrase), "amount", path + ".amount.of")
                self.gedge(aid, iid, "of")
                self._graph_anaphora(inner, path + ".amount.of", iid)
                poss = inner.get("possessor") if inner.get("kind") == "possessive" else None
                if isinstance(poss, dict) and (poss.get("anaphor")
                                               or poss.get("kind") in ("anaphora", "ref")):
                    word = poss.get("possessive") or poss.get("raw") or poss.get("ref") or "its"
                    pnode = self.gnode(f"anaphor: {word}", "anaphor",
                                       path + ".amount.of.possessor")
                    self.gedge(iid, pnode, "anaphora", dashed=True)
            if isinstance(node.get("possessor"), dict):
                phrase = self.phrase(node["possessor"], path + ".amount.possessor", "value")
                pid = self.gnode(_phrase_text(phrase), "subject",
                                 path + ".amount.possessor")
                self.gedge(aid, pid, "of")
                self._graph_anaphora(node["possessor"], path + ".amount.possessor", pid)
        return aid

    def _graph_effect(self, eff, path):
        if isinstance(eff, list):
            for i, item in enumerate(eff):
                self._graph_effect(item, f"{path}[{i}]")
            return None
        if not isinstance(eff, dict):
            return None
        verb_id = self.gnode(pretty(eff.get("verb", "")), "verb", path + ".verb")
        self._graph_subject(eff, path, verb_id)
        self._graph_object(eff, path, verb_id)
        self._graph_amount(eff, path, verb_id)
        self._graph_destination(eff, path, verb_id)
        self._graph_duration(eff, path, verb_id)
        self._graph_keywords(eff, path, verb_id)
        return verb_id

    def _graph_condition(self, cond, path, verb_id):
        if not isinstance(cond, dict):
            return None
        phrase = self.condition_phrase(cond, path)
        cid = self.gnode(_phrase_text(phrase), "condition", path)
        self.gedge(cid, verb_id, "condition")
        for key in ("card_target", "target", "object"):
            inner = cond.get(key)
            if isinstance(inner, dict):
                phrase = self.object_phrase(inner, path + "." + key)
                oid = self.gnode(_phrase_text(phrase), "object", path + "." + key)
                self.gedge(cid, oid, "of")
                self._graph_anaphora(inner, path + "." + key, oid)
        for key in ("quantity", "amount"):
            inner = cond.get(key)
            if isinstance(inner, dict):
                phrase = self.quantity_phrase(inner, path + "." + key)
                qid = self.gnode(_phrase_text(phrase), "amount", path + "." + key)
                self.gedge(cid, qid, "of")
        return cid

    def _graph_destination(self, eff, path, verb_id):
        for key in ("zone", "destination"):
            node = eff.get(key)
            if node is None:
                continue
            if isinstance(node, dict):
                phrase = self.object_phrase(node, path + "." + key)
            else:
                phrase = [self.tok(str(node), path + "." + key)]
            did = self.gnode(_phrase_text(phrase), "destination", path + "." + key)
            self.gedge(verb_id, did, "destination")
            return did
        return None

    def _graph_duration(self, eff, path, verb_id):
        node = eff.get("duration")
        if not isinstance(node, dict):
            return None
        phrase = self.duration_phrase(node, path + ".duration")
        did = self.gnode(_phrase_text(phrase), "duration", path + ".duration")
        self.gedge(verb_id, did, "duration")
        return did

    def _graph_anaphora(self, node, path, parent_id):
        if not isinstance(node, dict):
            return
        if node.get("anaphor") or node.get("kind") in ("anaphora", "ref"):
            word = node.get("possessive") or node.get("raw") or node.get("ref") or "anaphor"
            aid = self.gnode(f"anaphor: {word}", "anaphor", path)
            self.gedge(parent_id, aid, "anaphora", dashed=True)


GLUE_BEFORE = re.compile(r"^[,;:.)\]]")


def line_text(line):
    """Plain text of a line, gluing punctuation tokens to their neighbours."""
    out = ""
    for frag in line.get("fragments", []):
        text = frag["text"]
        if out and not GLUE_BEFORE.match(text) and not out.endswith(("(", "[")):
            out += " "
        out += text
    return out


def _quantifier_text(value):
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return {"any_number": "any number of", "up_to": "up to"}.get(text, text)


def _signed(value):
    if value is None:
        return "?"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"+{value}" if value > 0 else str(value)
    return str(value)


def _phrase_text(phrase):
    words = []

    def walk(items):
        for item in items or []:
            if isinstance(item, list):
                walk(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text and text not in ("[", "]"):
                    words.append(text)
            elif isinstance(item, str) and item.strip():
                words.append(item)

    walk(phrase)
    return " ".join(words)


def render_clauses(output):
    r = Renderer(output)
    lines = []
    if isinstance(output, list):
        for i, clause in enumerate(output):
            lines += r.clause(clause, f"$[{i}]")
    elif isinstance(output, dict):
        lines += r.clause(output, "$")
    else:
        lines = [r.line("RAW", "$", r.scalar(output, "$"))]
    return r, lines


def _finish(r, lines, top=10):
    items = [{"shape": shape, "value": value, "count": count}
             for (shape, value), count in r.shapes.most_common(top or None)]
    return {"lines": lines,
            "graph": {"nodes": r.nodes, "edges": r.edges},
            "stats": {"semantic": r.semantic, "fallback": r.fallback,
                      "fallback_shapes": items}}


def render(output):
    """Render one interpreted output as logical form + graph + stats."""
    r, lines = render_clauses(output)
    return _finish(r, lines, 10)


# ---------------------------------------------------------------------------
# corpus coverage
# ---------------------------------------------------------------------------

def unique_records(path):
    """One record per (card, sid, sentence_index) - 13,357 in the corpus."""
    seen = set()
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            key = (rec.get("card"), rec.get("sid"), rec.get("sentence_index"))
            if key in seen:
                continue
            seen.add(key)
            yield rec


def coverage(path, limit=None):
    semantic = fallback = records = crashes = 0
    shapes = collections.Counter()
    shape_value = {}
    examples = {}
    total = 0
    for rec in unique_records(path):
        records += 1
        if limit and records > limit:
            break
        try:
            r, lines = render_clauses(rec.get("output"))
            ir = _finish(r, lines, None)
        except Exception as exc:  # noqa: BLE001 - coverage must survive bad shapes
            crashes += 1
            print(f"CRASH {rec.get('card')}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        stats = ir["stats"]
        semantic += stats["semantic"]
        fallback += stats["fallback"]
        total += stats["semantic"] + stats["fallback"]
        for item in stats["fallback_shapes"]:
            shapes[item["shape"]] += item["count"]
            shape_value.setdefault(item["shape"], item["value"])
        examples.setdefault("first", (rec.get("card"), ir))
    share = semantic / total if total else 0.0
    return {"records": records, "fragments": total, "semantic": semantic,
            "fallback": fallback, "share": share, "crashes": crashes,
            "shapes": [{"shape": s, "count": c, "example_value": shape_value[s]}
                       for s, c in shapes.most_common(20)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render/cover interpreted outputs")
    ap.add_argument("--artifact", type=Path, default=Path("compile_standard.jsonl"))
    ap.add_argument("--unique", action="store_true", help="dedupe by output json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="print the coverage report as json")
    ap.add_argument("--record", type=int, default=None,
                    help="render the Nth unique record as json")
    args = ap.parse_args(argv)
    if args.record is not None:
        for i, rec in enumerate(unique_records(args.artifact)):
            if i == args.record:
                print(json.dumps({"card": rec.get("card"),
                                  "text": rec.get("original_text"),
                                  "ir": render(rec.get("output"))}, indent=1))
                return 0
        return 1
    report = coverage(args.artifact, args.limit)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"records: {report['records']}  fragments: {report['fragments']}  "
              f"crashes: {report['crashes']}")
        print(f"semantic: {report['semantic']}  fallback: {report['fallback']}  "
              f"share: {report['share']:.1%}")
        print("\ntop fallback shapes:")
        for item in report["shapes"][:10]:
            print(f"  {item['count']:6d}  {item['shape']}   e.g. {item['example_value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
