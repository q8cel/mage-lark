#!/usr/bin/env python3
"""Local review UI for MTG parser outputs.

Serves a stdlib-only, offline web app over a review pack:

  ./myenv/bin/python tools/review_ui.py --pack ../swarm/work/human_review_v5 --open

The pack supplies the item list (``key.json``, ``meta.json``), the sheets and the
``labels.tsv`` the reviewer may already be editing in vim.  The artifact
(``compile_standard.jsonl``) supplies the judged sentence, the resolved text and
the interpreted output for each item.  Machine claims come from ``review/``:
``claims.json`` when present, otherwise the audit TSVs joined by
``(card, sid, sentence_index)`` / ``sid`` / sentence text.

State is append-only ``<pack>/labels.jsonl`` plus ``<pack>/review_state.json``
(lane assignment, per-claim accept/reject decisions, import fingerprints).
``--export`` writes a vim-compatible ``<pack>/labels.tsv``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "review_ui"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ir_render  # noqa: E402  (ships next to this file)

VERDICTS = ("ok", "bug", "legit")
AXES = ("target", "actor", "zone", "quantity", "referent",
        "condition", "timing", "polarity", "other")
BATCH = 10
STATE_FILE = "review_state.json"
LABELS_FILE = "labels.jsonl"
TSV_FILE = "labels.tsv"

MISSING = object()


# ---------------------------------------------------------------------------
# token / content alignment, mirroring swarm/scripts/content_loss_scan.py
# ---------------------------------------------------------------------------

FUNCTION = set("""
a an the this that these those each every any all some no not none another other
i you your yours we our ours they them their theirs he him his she her hers it its
me my mine us
to from of on at in into onto by for with without within during before after
and or but nor so yet then than as if when whenever where which who whom whose
is are was were be been being am do does did done doing have has had having
can could may might must shall should will would
up down out back over under again further once here there very just also only
more most less least much many few little own same such
can't cannot don't doesn't didn't won't wouldn't isn't aren't wasn't weren't
it's that's they're you're we're
one
""".split())

_NUM = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
        'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
        'twenty': 20}

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


def toks(text):
    return [t for t in TOKEN_RE.findall(text.lower())]


def norm(token):
    t = token.replace('\u2019', "'")
    if t in _NUM:
        return str(_NUM[t])
    if t.endswith("'s"):
        t = t[:-2]
    return t


def stem(t):
    t = norm(t)
    if re.fullmatch(r'\d+', t):
        return t
    for suf in ('ies', 'ves', 'ing', 'ed', 'es', 's'):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            t = t[:-len(suf)]
            if suf == 'ies':
                t += 'y'
            break
    return t


ALIAS = {'get': 'change', 'gets': 'change', 'getting': 'change',
         'got': 'change'}

# Content words legitimately carried by structure (human-calibrated upstream).
REPRESENT = {
    'number': {'count', 'quantity', 'value', 'amount', 'total', 'xdef'},
    'equal': {'op', 'equal', 'relation', 'count'},
    'greater': {'op', 'greater', 'more'},
    'less': {'op', 'less', 'fewer'},
    'among': {'among', 'of', 'set', 'items'},
    'turn': {'turn', 'time', 'duration', 'timing', 'when', 'window'},
    'target': {'target', 'quantifier'},
    'cast': {'cast'},
    'counter': {'counter', 'counters'},
    'counters': {'counter', 'counters'},
    'additional': {'additional', 'extra'},
    'base': {'base', 'pt'},
    'attacking': {'attacking', 'attack', 'attacks'},
    'amount': {'amount', 'value', 'count', 'kind'},
    'resolved': {'resolved', 'first', 'time', 'state'},
    'loses': {'lose', 'keyword'},
}
FUNCTION.update({'already', 'delirium', 'long'})


def output_words(obj):
    words = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                words.extend(toks(k))
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, bool):
            return
        elif isinstance(o, (int, float)):
            words.append(str(o))
        elif isinstance(o, str):
            words.extend(toks(o))

    walk(obj)
    return words


def survives(word, out_stems, out_raw):
    w = ALIAS.get(word.lower(), stem(word))
    if not w:
        return True
    cw = w.lstrip('+-')
    for o in out_stems:
        co = o.lstrip('+-')
        if co == cw or (len(cw) >= 4 and (co.startswith(cw) or cw.startswith(co))):
            return True
    reps = REPRESENT.get(norm(word)) or REPRESENT.get(word.lower())
    if reps and any(r in out_raw for r in reps):
        return True
    return False


# ---------------------------------------------------------------------------
# JSON paths.  The app and the claim reports speak one dialect:
#   $                 root
#   $[0]              first element of the root list (reports write "[]")
#   $[0].effect.zone  object key
#   $[0].keywords[*]  any element (reports write "[]" too)
# ---------------------------------------------------------------------------

_STEP_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\[\*\]")


def parse_path(path):
    p = (path or "").strip()
    if p in ("", "$"):
        return []
    if p.startswith("$"):
        p = p[1:]
    steps = []
    pos = 0
    while pos < len(p):
        m = _STEP_RE.match(p, pos)
        if not m:
            return None
        if m.group(1) is not None:
            steps.append(("key", m.group(1)))
        elif m.group(2) is not None:
            steps.append(("idx", int(m.group(2))))
        else:
            steps.append(("idx", None))
        pos = m.end()
    return steps


def resolve_path(output, path):
    steps = parse_path(path)
    if steps is None:
        return MISSING
    node = output
    for kind, name in steps:
        if kind == "key":
            if isinstance(node, dict) and name in node:
                node = node[name]
            else:
                return MISSING
        else:
            idx = 0 if name is None else name
            if isinstance(node, list) and 0 <= idx < len(node):
                node = node[idx]
            else:
                return MISSING
    return node


def canon_claim_path(path):
    """Report paths (``[].a[]``) -> app paths (``$[0].a[0]``)."""
    p = (path or "").strip()
    if not p:
        return ""
    if p.startswith("$"):
        p = p[1:]
    p = p.replace("[]", "[0]").replace("[*]", "[0]")
    if not p.startswith("["):
        p = "." + p
    return "$" + p


def shorten(value, limit=90):
    try:
        s = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(value)
    return s if len(s) <= limit else s[:limit - 1] + "…"


def find_hits(word, output, limit=24):
    """Paths whose key or value stem-matches ``word``."""
    w = ALIAS.get(word.lower(), stem(word))
    hits = []
    seen = set()

    def add(path):
        if path not in seen and len(hits) < limit:
            seen.add(path)
            hits.append(path)

    def word_match(token):
        tw = stem(token)
        if not tw or not w:
            return False
        a, b = w.lstrip('+-'), tw.lstrip('+-')
        return a == b or (len(a) >= 4 and (b.startswith(a) or a.startswith(b)))

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                child = path + "." + k
                if word_match(k):
                    add(child)
                walk(v, child)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + f"[{i}]")
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            if word_match(str(node)):
                add(path)
        elif isinstance(node, str):
            if norm(word.lower()) in {norm(t) for t in toks(node)}:
                add(path)

    walk(output, "$")
    return hits


def align(text, output, missing_units):
    """Word spans of the judged sentence with their content status."""
    out_raw = set(output_words(output))
    out_stems = {stem(w) for w in out_raw}
    missing_set = {norm(u) for u in missing_units}
    spans = []
    for m in TOKEN_RE.finditer(text):
        raw = m.group(0)
        low = raw.lower()
        hits = []
        claim_missing = False
        if low in FUNCTION or len(low) <= 1:
            cls = "function"
        else:
            ok = survives(low, out_stems, out_raw)
            claim_missing = norm(low) in missing_set
            cls = "found" if ok and not claim_missing else "missing"
            hits = find_hits(low, output)
        spans.append({"start": m.start(), "end": m.end(), "text": raw,
                      "cls": cls, "hits": hits, "claim_missing": claim_missing})
    return spans


# ---------------------------------------------------------------------------
# pack + artifact + claims
# ---------------------------------------------------------------------------

def norm_text(text):
    return " ".join((text or "").split())


def split_row(line):
    """id / verdict / note from one labels.tsv line (matches human_audit_eval)."""
    if "\t" in line:
        hid, rest = line.split("\t", 1)
        if "\t" in rest:
            vfield, tail = rest.split("\t", 1)
        else:
            vfield, tail = rest, ""
        parts = vfield.split(None, 1)
        verdict = parts[0].lower() if parts else ""
        note = parts[1] if len(parts) > 1 else ""
        if tail:
            note = note + "\t" + tail if note else tail
    else:
        parts = line.split(None, 2)
        hid = parts[0] if parts else ""
        verdict = parts[1].lower() if len(parts) > 1 else ""
        note = parts[2] if len(parts) > 2 else ""
    return hid.strip(), verdict.strip(), note.strip()


def read_tsv(path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if row and any(cell.strip() for cell in row):
                rows.append(row)
    return rows


def latest_stringy(paths):
    """Newest stringy_report[_N].tsv by numeric suffix."""
    best = None
    best_n = -1
    for p in paths:
        m = re.fullmatch(r"stringy_report(?:_(\d+))?\.tsv", p.name)
        if not m:
            continue
        n = int(m.group(1)) if m.group(1) else 1
        if n > best_n:
            best, best_n = p, n
    return best


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_card_rows(raw):
    """Card oracle text as [{sentence_index, text}] from a string or list."""
    rows = []
    if isinstance(raw, str):
        for i, line in enumerate(ln for ln in raw.splitlines() if ln.strip()):
            rows.append({"sentence_index": i, "text": line})
    elif isinstance(raw, list):
        for i, row in enumerate(raw):
            if isinstance(row, str):
                rows.append({"sentence_index": i, "text": row})
            elif isinstance(row, dict):
                rows.append({"sentence_index": row.get("sentence_index", i),
                             "text": row.get("text") or row.get("original_text") or ""})
    return rows


def load_items_json(path):
    """{id: entry} from items.json (list, or {id: entry}, or {items: [...]})."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot parse {path}: {exc}")
    entries = data
    if isinstance(data, dict):
        entries = data.get("items") or data.get("records") or data
        if isinstance(entries, dict):
            entries = [dict(entry, id=entry.get("id", hid))
                       for hid, entry in entries.items()]
    if not isinstance(entries, list):
        raise SystemExit(f"{path}: expected a list of items")
    out = {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id"):
            out[entry["id"]] = entry
    return out


def file_sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Pack:
    def __init__(self, pack_dir, artifact=None, claims_dir=None,
                 import_path=None, do_import=True):
        self.dir = Path(pack_dir).resolve()
        if not self.dir.is_dir():
            raise SystemExit(f"pack directory not found: {self.dir}")
        key_path = self.dir / "key.json"
        self.key = (json.loads(key_path.read_text(encoding="utf-8"))
                    if key_path.exists() else {})
        meta_path = self.dir / "meta.json"
        self.meta = (json.loads(meta_path.read_text(encoding="utf-8"))
                     if meta_path.exists() else {})
        # items.json (v6+) carries the same item payloads the UI serves; older
        # packs only have key.json, so identity comes from there.
        self.items_path = self.dir / "items.json"
        self.items_json = load_items_json(self.items_path)
        self.embedded = {}
        self.embedded_cards = {}
        if self.items_json:
            self._merge_items_json()
        if not self.key:
            raise SystemExit(f"missing {key_path} and {self.items_path}")
        for hid in sorted(self.key):
            entry = self.key[hid]
            if not all(entry.get(f) is not None for f in ("card", "sid", "sentence_index")):
                raise SystemExit(f"{hid}: item is missing card/sid/sentence_index")
        self.ids = sorted(self.key)
        self.strata = {it.get("id"): it.get("stratum")
                       for it in self.meta.get("items", []) if isinstance(it, dict)}
        for hid, entry in self.key.items():
            if entry.get("stratum") is not None:
                self.strata[hid] = entry["stratum"]
        self.warnings = []
        self.claims_mode = "none"
        self.claims_meta = {}
        self.parser_cache = {}
        self.artifact_path = self._find_artifact(
            artifact, required=any(hid not in self.embedded for hid in self.ids))
        self.claims_dir = Path(claims_dir).resolve() if claims_dir else ROOT / "review"
        self.import_path = (Path(import_path).resolve() if import_path
                            else self.dir / TSV_FILE)
        self.lock = threading.RLock()
        self.state = self._load_state()
        self.records = {}
        self.cards = defaultdict(list, self.embedded_cards)
        if self.artifact_path is not None:
            self._index_artifact()
        self.artifact_sha = (file_sha256(self.artifact_path)
                             if self.artifact_path else "")
        self.claims_sha = ""
        self._load_claims()
        self.labels = {}
        self.lane = {}
        self.claim_state = {}
        self._load_labels()
        self._assign_lanes()
        self.import_seen = self.state.setdefault("imported", {})
        self.import_skips = self.state.setdefault("import_skip", {})
        self.claim_state = {hid: rec for hid, rec in
                            self.state.get("claims", {}).items()
                            if hid in self.key}
        self.imported_rows = sum(1 for rec in self.labels.values()
                                 if rec.get("source") == "import")
        self.import_warnings = []
        if do_import and self.import_path and self.import_path.exists():
            self.import_labels()

    # -- paths ---------------------------------------------------------
    def _find_artifact(self, artifact, required=True):
        cands = []
        if artifact:
            cands.append(Path(artifact))
        else:
            src = self.meta.get("source") or ""
            cands += [ROOT / "compile_standard.jsonl",
                      self.dir.parent.parent / "compile_standard.jsonl",
                      ROOT / Path(src).name if src else ROOT / "compile_standard.jsonl"]
        for cand in cands:
            p = Path(cand)
            if not p.is_absolute():
                p = (Path.cwd() / p) if artifact else p
            if p.exists():
                return p.resolve()
        if not required:
            return None
        raise SystemExit("artifact not found; pass --artifact compile_standard.jsonl "
                         f"(tried: {', '.join(str(c) for c in cands)})")

    def _merge_items_json(self):
        """Fold items.json entries into the key map and cache embedded payloads."""
        for raw_entry in self.items_json.values():
            entry = dict(raw_entry)
            hid = entry.get("id")
            if not hid:
                continue
            if isinstance(entry.get("record"), dict):
                entry = {**entry["record"], **{k: v for k, v in entry.items()
                                               if k != "record"}}
            if entry.get("sentence_index") is None:
                for alias in ("index", "sentence_idx", "si"):
                    if entry.get(alias) is not None:
                        entry["sentence_index"] = entry[alias]
                        break
            base = dict(self.key.get(hid) or {})
            for field in ("card", "sid", "sentence_index", "weight", "stratum",
                          "commit", "artifact_sha256"):
                if entry.get(field) is not None:
                    base[field] = entry[field]
            self.key[hid] = base
            if any(k in entry for k in ("output", "original_text", "sentence")):
                self.embedded[hid] = {
                    "card": base.get("card"),
                    "sid": base.get("sid"),
                    "sentence_index": base.get("sentence_index"),
                    "original_text": (entry.get("original_text")
                                      or entry.get("sentence") or entry.get("text") or ""),
                    "resolved_text": entry.get("resolved_text")
                    or entry.get("original_text") or entry.get("sentence") or "",
                    "anaphora": entry.get("anaphora") or [],
                    "output": entry.get("output"),
                }
            raw_cards = (entry.get("cards") or entry.get("card_text")
                         or entry.get("full_card_text"))
            if raw_cards and base.get("card"):
                rows = normalize_card_rows(raw_cards)
                if rows:
                    self.embedded_cards[base["card"]] = rows

    # -- state ---------------------------------------------------------
    def _load_state(self):
        path = self.dir / STATE_FILE
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, ValueError):
                pass
        return {"version": 1, "lanes": {}, "claims": {}, "imported": {}, "import_skip": {}}

    def _save_state(self):
        payload = {
            "version": 1,
            "pack": str(self.dir),
            "lanes": self.lane,
            "claims": self.claim_state,
            "imported": self.state.get("imported", {}),
            "import_skip": self.state.get("import_skip", {}),
            "updated": now_iso(),
        }
        atomic_write(self.dir / STATE_FILE,
                     json.dumps(payload, indent=1, sort_keys=True) + "\n")

    def _load_labels(self):
        path = self.dir / LABELS_FILE
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("id"):
                    self.labels[rec["id"]] = rec

    def _append_label(self, rec):
        with (self.dir / LABELS_FILE).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    # -- lanes ---------------------------------------------------------
    def _assign_lanes(self):
        stored = self.state.get("lanes") or {}
        if set(stored) >= set(self.ids):
            self.lane = {hid: stored[hid] for hid in self.ids}
            return
        ranked = sorted(self.ids, key=lambda hid: hashlib.sha256(
            hid.encode("utf-8")).hexdigest())
        lane = {}
        for rank, hid in enumerate(ranked):
            lane[hid] = "triage" if rank % 2 == 0 else "blind"
        self.lane = lane
        self.state["lanes"] = dict(lane)
        self._save_state()

    # -- artifact ------------------------------------------------------
    def _index_artifact(self):
        wanted = {(self.key[hid]["card"], self.key[hid]["sid"]) for hid in self.ids}
        wanted_cards = {self.key[hid]["card"] for hid in self.ids}
        with self.artifact_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                card = rec.get("card")
                sid = rec.get("sid")
                if (card, sid) in wanted:
                    triple = (card, sid, rec.get("sentence_index"))
                    self.records.setdefault(triple, rec)
                if card in wanted_cards and card not in self.embedded_cards:
                    self.cards[card].append(
                        (rec.get("sentence_index"), rec.get("original_text") or ""))
        for card, rows in list(self.cards.items()):
            pairs = []
            for row in rows:
                if isinstance(row, dict):
                    pairs.append((row.get("sentence_index"), row.get("text") or ""))
                else:
                    pairs.append((row[0], row[1]))
            seen = set()
            uniq = []
            for si, text in sorted(pairs, key=lambda r: (r[0] if r[0] is not None else -1)):
                if (si, text) in seen:
                    continue
                seen.add((si, text))
                uniq.append({"sentence_index": si, "text": text})
            self.cards[card] = uniq

    def record_for(self, hid):
        if hid in self.embedded:
            return self.embedded[hid]
        k = self.key[hid]
        rec = self.records.get((k["card"], k["sid"], k["sentence_index"]))
        if rec is not None:
            return rec
        for (card, sid, _si), r in self.records.items():
            if card == k["card"] and sid == k["sid"]:
                return r
        return None

    def output_for(self, hid):
        rec = self.record_for(hid)
        return rec.get("output") if rec else None

    def card_text(self, card):
        return self.cards.get(card, [])

    # -- claims --------------------------------------------------------
    def _load_claims(self):
        cd = self.claims_dir
        self.cd_text = defaultdict(list)
        self.stringy = defaultdict(list)
        self.structure = defaultdict(list)
        self.inv_text = defaultdict(list)
        self.ana = defaultdict(list)
        self.claim_json = {}
        self._claim_cache = {}
        self.claims_json_path = cd / "claims.json"
        self.stringy_path = latest_stringy(sorted(cd.glob("stringy_report*.tsv"))) if cd.is_dir() else None
        if not cd.is_dir():
            self.warnings.append(f"claims directory missing: {cd}")
            return
        for row in read_tsv(cd / "certain_defects.tsv"):
            if not row or row[0].strip().lower() == "sid":
                continue
            sid = row[0].strip()
            if len(row) < 6:
                continue
            units = row[2] if len(row) > 2 else ""
            rec = {"sid": sid, "words": row[1] if len(row) > 1 else "",
                   "missing_units": units.split(), "score": row[3] if len(row) > 3 else "",
                   "flags": row[4] if len(row) > 4 else "",
                   "sentence": row[5] if len(row) > 5 else ""}
            rec["text_key"] = norm_text(rec["sentence"])
            self.cd_text[rec["text_key"]].append(rec)
            self.cd_text["sid:" + sid].append(rec)

        if self.stringy_path:
            for row in read_tsv(self.stringy_path):
                if len(row) < 4 or not row[0].strip():
                    continue
                sid = row[0].strip()
                if sid.lower() == "sid":
                    continue
                self.stringy[sid].append(
                    {"path": row[1], "value": row[2], "tokens": row[3],
                     "score": row[4] if len(row) > 4 else ""})

        for row in read_tsv(cd / "structure_report.tsv"):
            if len(row) < 4:
                continue
            sid = row[0].strip()
            if sid.lower() == "sid":
                continue
            self.structure[sid].append(
                {"path": row[1], "shape": row[2], "missing": row[3],
                 "weight": row[4] if len(row) > 4 else ""})

        inv = ROOT / "invariant_flags.tsv"
        if not inv.exists():
            inv = cd / "invariant_flags.tsv"
        for row in read_tsv(inv):
            if len(row) < 3:
                continue
            if row[0].strip().lower() in ("flag", "kind", "type"):
                continue
            self.inv_text[norm_text(row[2])].append(
                {"flag": row[0].strip(), "detail": row[1].strip(), "sentence": row[2]})

        for row in read_tsv(cd / "anaphora_agreement.tsv"):
            if not row or row[0].strip().lower() == "card":
                continue
            if len(row) < 8:
                continue
            rec = {"card": row[0].strip(), "sid": row[1].strip(),
                   "sentence_index": row[2].strip(), "surface": row[3].strip(),
                   "antecedent": row[4].strip(), "head_type": row[5].strip(),
                   "number": row[6].strip(), "violation": row[7].strip(),
                   "severity": row[8] if len(row) > 8 else "",
                   "evidence": row[9] if len(row) > 9 else ""}
            self.ana[(rec["card"], rec["sid"], rec["sentence_index"])].append(rec)
            self.ana[("sid", rec["sid"], rec["sentence_index"])].append(rec)

        data = None
        if self.claims_json_path.exists():
            try:
                data = json.loads(self.claims_json_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.warnings.append(f"claims.json is malformed ({exc}); joined the audit TSVs instead")
                data = None
        if isinstance(data, dict):
            self.claims_meta = {
                "generated_at": data.get("generated_at", ""),
                "artifact_sha256": data.get("artifact_sha256", ""),
                "counts": data.get("counts", {}),
            }
            entries = data.get("records") or data.get("entries") or data.get("items") or []
            if isinstance(entries, list) and entries:
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    triple = (e.get("card"), e.get("sid"), e.get("sentence_index"))
                    self.claim_json[triple] = self._norm_json_claims(e.get("claims"))
                self.claims_mode = "claims.json"
            else:
                self.warnings.append("claims.json has no records; joined the audit TSVs instead")
        elif data is not None:
            self.warnings.append("claims.json has an unexpected shape; joined the audit TSVs instead")
        elif not self.claims_json_path.exists():
            self.warnings.append("claims.json absent; joined the audit TSVs instead")
        if not self.claim_json:
            self.claims_mode = ("tsv" if (self.stringy or self.structure or self.cd_text
                                          or self.inv_text or self.ana) else "none")
        claimed_sha = self.claims_meta.get("artifact_sha256") or ""
        if claimed_sha and self.artifact_sha and claimed_sha != self.artifact_sha:
            self.warnings.append(
                "claims.json was generated for artifact sha "
                f"{claimed_sha[:12]}… but the loaded artifact is {self.artifact_sha[:12]}… "
                "— claims are shown, unresolved paths are dropped")
        claims_path = self.claims_json_path
        if claims_path.exists():
            self.claims_sha = file_sha256(claims_path)
            pack_claims_sha = self.meta.get("claims_sha256") or ""
            if pack_claims_sha and pack_claims_sha != self.claims_sha:
                self.warnings.append(
                    "pack meta names claims sha " + pack_claims_sha[:12]
                    + "…, loaded claims.json is " + self.claims_sha[:12]
                    + "… — claims may be stale")
        pack_sha = self.meta.get("artifact_sha256") or ""
        if pack_sha and self.artifact_sha and pack_sha != self.artifact_sha:
            self.warnings.append(
                f"pack meta names artifact sha {pack_sha[:12]}…, loaded artifact is "
                f"{self.artifact_sha[:12]}… — item texts may have changed since the pack was built")

    @staticmethod
    def _norm_json_claims(claims):
        out = []
        for c in claims or []:
            if isinstance(c, str):
                out.append({"kind": "claim", "path": "", "text": c,
                            "value": "", "missing_units": []})
            elif isinstance(c, dict):
                kind = c.get("kind") or c.get("type") or "claim"
                path = c.get("path") or c.get("json_path") or ""
                text = (c.get("detail") or c.get("text") or c.get("message")
                        or json.dumps(c, ensure_ascii=False))
                units = c.get("missing_units") or c.get("missing") or []
                if isinstance(units, str):
                    units = units.split()
                if units:
                    text = f"{text} (missing: {' '.join(units)})"
                out.append({"kind": str(kind), "path": str(path), "text": str(text),
                            "value": c.get("value", ""), "missing_units": units,
                            "severity": str(c.get("severity", ""))})
        return out

    def claims_for(self, hid):
        if hid in self._claim_cache:
            return self._claim_cache[hid]
        k = self.key[hid]
        rec = self.record_for(hid)
        output = rec.get("output") if rec else None
        text = (rec.get("original_text") if rec else "") or ""
        text_key = norm_text(text)
        triple = (k["card"], k["sid"], k["sentence_index"])
        claims = []
        seen = set()

        def add(kind, path, text_, value="", source="", units=(), severity=""):
            key = f"{kind}|{path}|{text_}"
            if key in seen:
                return
            seen.add(key)
            claims.append({"key": key, "kind": kind, "path": path,
                           "text": text_, "value": shorten(value) if value != "" else "",
                           "source": source, "missing_units": list(units),
                           "severity": severity})

        def usable_path(path):
            path = canon_claim_path(path)
            if not path:
                return ""
            if output is None:
                return path
            return path if resolve_path(output, path) is not MISSING else ""

        # claims.json is the consolidated claim set; when it has this item, use
        # it alone.  Otherwise join the audit TSVs below (same semantics).
        consolidated = self.claim_json.get(triple)
        if consolidated:
            for c in consolidated:
                kind = c["kind"]
                path = usable_path(c["path"])
                detail = c["text"]
                severity = c.get("severity", "")
                if kind == "content_loss":
                    units = c["missing_units"] or (
                        [detail] if " " not in detail else detail.split())
                    add(kind, "", f"content-loss scan: '{detail}' missing from output",
                        "", "claims.json", units, severity)
                elif kind == "empty_slot":
                    add(kind, path,
                        f"required slot '{detail}' missing under this node",
                        "", "claims.json", (), severity)
                elif kind == "stringy":
                    add(kind, path, f"prose in a structured slot: {detail}",
                        detail, "claims.json", (), severity)
                elif kind in ("anaphora", "anaphora_agreement"):
                    extra = self._ana_detail(triple, detail)
                    add(kind, path, f"anaphora agreement: {extra}",
                        "", "claims.json", (), severity)
                else:
                    add(kind, path, detail, c.get("value", ""),
                        "claims.json", c.get("missing_units") or (), severity)
            self._claim_cache[hid] = claims
            return claims

        units = []
        for cd in self.cd_text.get(text_key, []):
            units = cd["missing_units"]
            add("content_loss", "",
                f"content-loss scan: missing content units ({len(units)}, "
                f"score {cd['score']})", "", "certain_defects.tsv", units)
            break

        for row in self.stringy.get(k["sid"], []):
            path = usable_path(row["path"])
            if output is not None and not path:
                continue
            add("stringy", path,
                f"prose in a structured slot: {shorten(row['value'])} "
                f"({row['tokens']} tokens)", row["value"],
                self.stringy_path.name if self.stringy_path else "stringy_report")

        for row in self.structure.get(k["sid"], []):
            path = usable_path(row["path"])
            if output is not None and not path:
                continue
            add("empty_slot", path,
                f"required slot '{row['missing']}' missing under this node",
                "", "structure_report.tsv")

        for row in self.inv_text.get(text_key, []):
            add("invariant", "", f"{row['flag']}: {row['detail']}",
                "", "invariant_flags.tsv")

        atriple = (k["card"], k["sid"], str(k["sentence_index"]))
        for row in self.ana.get(atriple, []):
            path = self._anaphora_path(output, row["surface"])
            add("anaphora", path,
                f"'{row['surface']}' -> '{row['antecedent']}' "
                f"({row['violation']}, {row['severity']})", "", "anaphora_agreement.tsv")

        self._claim_cache[hid] = claims
        return claims

    def _ana_detail(self, triple, fallback):
        rows = self.ana.get((triple[0], triple[1], str(triple[2])), [])
        if not rows:
            rows = self.ana.get(("sid", triple[1], str(triple[2])), [])
        if len(rows) == 1:
            row = rows[0]
            return f"'{row['surface']}' -> '{row['antecedent']}' ({row['violation']})"
        return fallback

    @staticmethod
    def _anaphora_path(output, surface):
        """First JSON node holding the anaphor surface verbatim."""
        if output is None or not surface:
            return ""
        target = surface.lower()
        found = []

        def walk(node, path):
            if found:
                return
            if isinstance(node, dict):
                for key, val in node.items():
                    if isinstance(val, str) and val.strip().lower() == target:
                        found.append(path + "." + key)
                        return
                    walk(val, path + "." + key)
            elif isinstance(node, list):
                for i, val in enumerate(node):
                    walk(val, path + f"[{i}]")

        walk(output, "$")
        return found[0] if found else ""

    # -- import / export -----------------------------------------------
    def import_labels(self, path=None):
        path = Path(path).resolve() if path else self.import_path
        if not path or not path.exists():
            return {"imported": 0, "skipped": 0, "unknown": [], "path": str(path or "")}
        text = path.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        imported = skipped = 0
        unknown = []
        duplicates = []
        seen = set()
        for line in lines:
            if not line.strip():
                continue
            hid, verdict, note = split_row(line)
            if not hid or hid.lower() == "id":
                continue
            if not verdict:
                continue
            if hid not in self.key:
                unknown.append(hid)
                continue
            if hid in seen:
                duplicates.append(hid)
                continue
            seen.add(hid)
            if verdict not in VERDICTS:
                unknown.append(f"{hid}:{verdict}")
                continue
            sig = hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]
            if self.import_skips.get(hid) and sig in self.import_skips[hid]:
                skipped += 1
                continue
            if self.import_seen.get(hid) == sig:
                skipped += 1
                continue
            existing = self.labels.get(hid)
            if existing and existing.get("op") != "undo" and \
                    existing.get("verdict") == verdict and existing.get("note") == note:
                # already recorded (imported row, or a UI label already exported)
                self.import_seen[hid] = sig
                skipped += 1
                continue
            axis, cpath = (self._infer_from_note(note, hid) if verdict == "bug"
                           else ("", ""))
            rec = {"id": hid, "verdict": verdict, "axis": axis, "path": cpath,
                   "note": note, "claims_accepted": [], "claims_rejected": [],
                   "lane": self.lane.get(hid, ""), "source": "import",
                   "timestamp": now_iso(), "raw": line}
            with self.lock:
                self.labels[hid] = rec
                self._append_label(rec)
                self.import_seen[hid] = sig
                self.state["imported"] = self.import_seen
            imported += 1
        self._save_state()
        self.imported_rows = sum(1 for rec in self.labels.values()
                                 if rec.get("source") == "import")
        self.import_warnings = ([f"unknown ids: {sorted(set(unknown))[:5]}"] if unknown else []) + \
            ([f"duplicate ids: {sorted(set(duplicates))[:5]}"] if duplicates else [])
        return {"imported": imported, "skipped": skipped,
                "unknown": sorted(set(unknown)), "duplicates": sorted(set(duplicates)),
                "path": str(path)}

    def _infer_from_note(self, note, hid):
        """Recover axis and JSON path from a loosely-written vim note."""
        output = self.output_for(hid)
        axis = ""
        low = note.lower()
        axis_words = [
            ("target", r"\btarget\b|\bquantifier\b"),
            ("actor", r"\bactor\b|\bcontroller|controlled\b|\bowner\b|\bwho\b"),
            ("zone", r"\bzone\b|graveyard|battlefield|exile|\blibrary\b|\bhand\b|bottom|top of"),
            ("quantity", r"\bquantity\b|\bamount\b|\bcount\b|\bnumber\b|\bsum\b|\blife\b|\bx is\b"),
            ("referent", r"\breferent\b|antecedent|pronoun|\bit\b ->|wrong antecedent"),
            ("condition", r"\bcondition\b|\bunless\b|\bif\b|\bwhen\b|\btrigger"),
            ("timing", r"\btiming\b|\bphase\b|\bturn\b|\bbeginning\b|\buntil\b|\bend of\b|\bstep\b"),
            ("polarity", r"\bpolarity\b|\bnegat|\bnot\b|\binstead\b|\bcan't\b|\bcannot\b"),
        ]
        for name, pat in axis_words:
            if re.search(pat, low):
                axis = name
                break
        if not axis:
            axis = "other"
        path = ""
        if output is not None:
            for cand in re.findall(r"(\$[A-Za-z0-9_.\[\]*]+|\[\][A-Za-z0-9_.\[\]]+)", note):
                cpath = canon_claim_path(cand)
                if cpath and resolve_path(output, cpath) is not MISSING:
                    path = cpath
                    break
            if not path:
                keys = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"|`([A-Za-z_][A-Za-z0-9_]*)`',
                                  note)
                for q, b in keys:
                    key = q or b
                    hit = self._first_key_path(output, key)
                    if hit:
                        path = hit
                        break
        return axis, path

    @staticmethod
    def _first_key_path(output, key):
        found = []

        def walk(node, path):
            if found:
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == key:
                        found.append(path + "." + k)
                        return
                    walk(v, path + "." + k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, path + f"[{i}]")

        walk(output, "$")
        return found[0] if found else ""

    def render_row(self, rec):
        note = (rec.get("note") or "").replace("\t", " ").replace("\n", " ")
        return f"{rec['id']}\t{rec.get('verdict','')}\t{note}"

    def export(self, out=None):
        out = Path(out).resolve() if out else self.dir / TSV_FILE
        lines = ["id\tverdict\tnote"]
        written = 0
        for hid in self.ids:
            rec = self.labels.get(hid)
            if rec and rec.get("op") != "undo" and rec.get("verdict"):
                line = rec.get("raw") if rec.get("source") == "import" and rec.get("raw") \
                    else self.render_row(rec)
                written += 1
            else:
                line = f"{hid}\t\t"
            lines.append(line.replace("\r", ""))
        payload = "\n".join(lines) + "\n"
        if out.exists():
            old = out.read_text(encoding="utf-8-sig")
            if old != payload:
                shutil.copy2(out, out.with_name(out.name + ".bak"))
        atomic_write(out, payload)
        return {"path": str(out), "rows": written, "lines": len(lines) - 1}

    def parser_view(self, hid):
        """Parser span roles for the judged sentence (cached per item)."""
        with self.lock:
            if hid in self.parser_cache:
                return self.parser_cache[hid]
            if hid not in self.key:
                raise ApiError(404, f"unknown item id: {hid}")
            rec = self.record_for(hid)
            text = (rec.get("original_text") if rec else "") or ""
            started = time.perf_counter()
            payload = {"available": False, "source": "unavailable", "ms": 0.0,
                       "spans": [], "error": ""}
            try:
                for extra in (str(ROOT), str(ROOT / "core"), str(ROOT / "coref")):
                    if extra not in sys.path:
                        sys.path.insert(0, extra)
                import paths as _paths
                _paths.bootstrap()
                import ptree
                spans = ptree.structure(text)
                source = "cache"
                if not spans:
                    spans = ptree.nodes(text)
                    source = "parse"
                payload.update(available=True, source=source, spans=[
                    {"start": s.get("start"), "end": s.get("end"),
                     "node": s.get("node"), "role": s.get("role"),
                     "verb": s.get("verb"), "predicate": bool(s.get("predicate")),
                     "in_condition": bool(s.get("in_condition")),
                     "text": text[s.get("start", 0):s.get("end", 0)]}
                    for s in spans])
            except Exception as exc:  # noqa: BLE001 - report, never fail the UI
                payload["error"] = f"{type(exc).__name__}: {exc}"
            payload["ms"] = round((time.perf_counter() - started) * 1000, 1)
            self.parser_cache[hid] = payload
            return payload

    # -- mutation ------------------------------------------------------
    def commit_label(self, hid, verdict, axis, path, note_text, accepted, rejected):
        with self.lock:
            if hid not in self.key:
                raise ApiError(404, f"unknown item id: {hid}")
            verdict = (verdict or "").strip().lower()
            if verdict not in VERDICTS:
                raise ApiError(400, f"verdict must be one of {', '.join(VERDICTS)}")
            axis = (axis or "").strip()
            if axis and axis not in AXES:
                raise ApiError(400, f"unknown axis: {axis}")
            path = (path or "").strip()
            value = ""
            if verdict == "bug" and path:
                node = resolve_path(self.output_for(hid), path)
                if node is MISSING:
                    raise ApiError(400, f"path does not exist in this output: {path}")
                value = shorten(node, 140)
            note = compose_note(axis if verdict == "bug" else "",
                                path if verdict == "bug" else "", value,
                                note_text or "")
            rec = {"id": hid, "verdict": verdict,
                   "axis": axis if verdict == "bug" else "",
                   "path": path if verdict == "bug" else "",
                   "note": note,
                   "claims_accepted": sorted({str(x) for x in accepted or []}),
                   "claims_rejected": sorted({str(x) for x in rejected or []}),
                   "lane": self.lane.get(hid, ""), "source": "ui",
                   "timestamp": now_iso(), "op": "label"}
            self.labels[hid] = rec
            self._append_label(rec)
            if hid in self.claim_state:
                self.claim_state.pop(hid, None)
                self._save_state()
            return rec

    def undo(self, hid):
        with self.lock:
            if hid not in self.key:
                raise ApiError(404, f"unknown item id: {hid}")
            prev = self.labels.get(hid)
            rec = {"id": hid, "op": "undo", "verdict": None, "axis": "",
                   "path": "", "note": "", "claims_accepted": [], "claims_rejected": [],
                   "lane": self.lane.get(hid, ""), "source": "ui",
                   "timestamp": now_iso()}
            self.labels.pop(hid, None)
            self._append_label(rec)
            if prev and prev.get("source") == "import":
                sig = self.import_seen.pop(hid, None)
                if sig:
                    self.import_skips.setdefault(hid, []).append(sig)
                self.state["imported"] = self.import_seen
            elif prev is None:
                sig = self.import_seen.pop(hid, None)
                if sig:
                    self.import_skips.setdefault(hid, []).append(sig)
                self.state["imported"] = self.import_seen
            self.claim_state.pop(hid, None)
            self._save_state()
            return rec

    def set_claim(self, hid, claim_key, decision):
        with self.lock:
            if hid not in self.key:
                raise ApiError(404, f"unknown item id: {hid}")
            state = self.claim_state.setdefault(
                hid, {"accepted": [], "rejected": [], "note": ""})
            accepted = set(state.get("accepted", []))
            rejected = set(state.get("rejected", []))
            if decision == "accept":
                accepted.add(claim_key)
                rejected.discard(claim_key)
            elif decision == "reject":
                rejected.add(claim_key)
                accepted.discard(claim_key)
            elif decision == "clear":
                accepted.discard(claim_key)
                rejected.discard(claim_key)
            else:
                raise ApiError(400, f"unknown decision: {decision}")
            state["accepted"] = sorted(accepted)
            state["rejected"] = sorted(rejected)
            self.claim_state[hid] = state
            self.state["claims"] = self.claim_state
            self._save_state()
            return state

    # -- views ---------------------------------------------------------
    def counts(self):
        counts = {v: 0 for v in VERDICTS}
        imported = 0
        for rec in self.labels.values():
            if rec.get("op") == "undo" or not rec.get("verdict"):
                continue
            v = rec["verdict"]
            counts[v] = counts.get(v, 0) + 1
            if rec.get("source") == "import":
                imported += 1
        done = sum(counts.values())
        return {"ok": counts.get("ok", 0), "bug": counts.get("bug", 0),
                "legit": counts.get("legit", 0), "done": done,
                "unlabeled": len(self.ids) - done, "imported": imported}

    def state_payload(self):
        items = []
        for hid in self.ids:
            rec = self.labels.get(hid)
            done = bool(rec and rec.get("op") != "undo" and rec.get("verdict"))
            entry = {"id": hid, "card": self.key[hid]["card"], "done": done,
                     "verdict": rec.get("verdict") if done else "",
                     "source": rec.get("source", "") if done else ""}
            if done:
                entry["lane"] = self.lane.get(hid, "")
            items.append(entry)
        return {
            "pack": str(self.dir),
            "artifact": str(self.artifact_path or ""),
            "claims_dir": str(self.claims_dir),
            "claims_json": self.claims_json_path.exists(),
            "claims_mode": self.claims_mode,
            "claims_meta": {"generated_at": self.claims_meta.get("generated_at", ""),
                            "artifact_sha256": self.claims_meta.get("artifact_sha256", "")},
            "artifact_sha256": self.artifact_sha,
            "claims_sha256": self.claims_sha,
            "stringy_report": self.stringy_path.name if self.stringy_path else None,
            "warnings": list(self.warnings),
            "n": len(self.ids), "batch": BATCH,
            "axes": list(AXES), "verdicts": list(VERDICTS),
            "items": items,
            "counts": self.counts(),
            "lanes": {"triage": sum(1 for v in self.lane.values() if v == "triage"),
                      "blind": sum(1 for v in self.lane.values() if v == "blind")},
            "import": {"path": str(self.import_path),
                       "rows": self.imported_rows,
                       "warnings": self.import_warnings},
        }

    def item_payload(self, hid):
        if hid not in self.key:
            raise ApiError(404, f"unknown item id: {hid}")
        k = self.key[hid]
        rec = self.record_for(hid)
        if rec is None:
            raise ApiError(500, f"no artifact record for {hid} "
                                f"({k['card']} / {k['sid']} / {k['sentence_index']})")
        lane = self.lane.get(hid, "")
        claims = self.claims_for(hid)
        missing_units = []
        for claim in claims:
            if claim["kind"] == "content_loss":
                missing_units.extend(claim["missing_units"])
        output = rec.get("output")
        label = self.labels.get(hid)
        if label and label.get("op") == "undo":
            label = None
        claim_state = self.claim_state.get(hid)
        if claim_state is None and label:
            claim_state = {"accepted": label.get("claims_accepted", []),
                           "rejected": label.get("claims_rejected", []), "note": ""}
        payload = {
            "id": hid, "card": k["card"], "sid": k["sid"],
            "sentence_index": k["sentence_index"], "weight": k.get("weight"),
            "commit": k.get("commit"), "stratum": self.strata.get(hid),
            "original_text": rec.get("original_text", ""),
            "resolved_text": rec.get("resolved_text", ""),
            "anaphora": rec.get("anaphora", []),
            "output": output,
            "cards": self.card_text(k["card"]),
            "tokens": align(rec.get("original_text", ""), output, missing_units),
            "ir": ir_render.render(output),
            "claims": claims if lane == "triage" else [],
            "claim_state": claim_state or {"accepted": [], "rejected": [], "note": ""},
            "label": label,
        }
        if lane and label:
            payload["lane"] = lane
        return payload


def compose_note(axis, path, value, text):
    parts = []
    if axis:
        parts.append(f"{axis}:")
    if path:
        parts.append(f"{path}: {value}")
    text = (text or "").strip()
    if text:
        parts.append(("— " + text) if parts else text)
    return " ".join(parts)


def atomic_write(path, payload):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        fh.write(payload)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "review-ui/1.0"

    def log_message(self, fmt, *args):
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # -- helpers -------------------------------------------------------
    def _send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False))

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 4_000_000:
            raise ApiError(413, "request body too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "body must be JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "body must be a JSON object")
        return data

    # -- routes --------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html", "text/html; charset=utf-8")
            if path == "/app.js":
                return self._static("app.js", "application/javascript; charset=utf-8")
            if path == "/style.css":
                return self._static("style.css", "text/css; charset=utf-8")
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/state":
                return self._json(200, self.server.pack.state_payload())
            if path == "/api/item":
                hid = (query.get("id") or [""])[0]
                return self._json(200, self.server.pack.item_payload(hid))
            if path == "/api/parser":
                hid = (query.get("id") or [""])[0]
                return self._json(200, self.server.pack.parser_view(hid))
            if path == "/api/help":
                return self._json(200, HELP)
            raise ApiError(404, f"no route: {path}")
        except ApiError as exc:
            self._json(exc.status, {"error": exc.message})
        except Exception as exc:  # noqa: BLE001 - report to the browser
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/api/label":
                data = self._body()
                pack = self.server.pack
                rec = pack.commit_label(
                    data.get("id"), data.get("verdict"), data.get("axis", ""),
                    data.get("path", ""), data.get("note", ""),
                    data.get("claims_accepted", []), data.get("claims_rejected", []))
                return self._json(200, {"ok": True, "record": rec,
                                        "counts": pack.counts()})
            if path == "/api/undo":
                data = self._body()
                pack = self.server.pack
                rec = pack.undo(data.get("id"))
                return self._json(200, {"ok": True, "record": rec,
                                        "counts": pack.counts()})
            if path == "/api/claim":
                data = self._body()
                pack = self.server.pack
                state = pack.set_claim(data.get("id"), data.get("key"),
                                       data.get("decision"))
                return self._json(200, {"ok": True, "claim_state": state})
            if path == "/api/import":
                pack = self.server.pack
                result = pack.import_labels()
                return self._json(200, {"ok": True, **result,
                                        "counts": pack.counts(),
                                        "state": pack.state_payload()})
            if path == "/api/export":
                pack = self.server.pack
                if pack.import_path and pack.import_path.exists():
                    pack.import_labels()
                result = pack.export()
                return self._json(200, {"ok": True, **result})
            raise ApiError(404, f"no route: {path}")
        except ApiError as exc:
            self._json(exc.status, {"error": exc.message})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _static(self, name, ctype):
        target = STATIC / name
        if not target.exists():
            raise ApiError(404, f"missing static asset: {name}")
        self._send(200, target.read_bytes(), ctype)


HELP = {
    "navigation": {
        "j / k": "next / previous item (wraps, batches of 10)",
        "g / G": "first / last item",
        "[ / ]": "previous / next machine claim",
        "?": "toggle this help",
    },
    "verdict": {
        "o": "ok", "b": "bug", "l": "legit",
        "1-9": "axis for a bug (target, actor, zone, quantity, referent, "
               "condition, timing, polarity, other)",
        "click JSON node": "record path: value in the note (sets verdict bug)",
        "Enter": "commit the label and advance",
        "u": "undo the current item's label",
    },
    "claims": {
        "y": "accept the focused claim",
        "n": "reject the focused claim",
        "y/n again": "clear the decision",
    },
    "views": {
        "v": "cycle semantic / graph / json output views",
        "p": "parser span view for the judged sentence",
    },
    "json tree": {
        "click key/value": "select that node for the bug note (path: value)",
        "click \u25b8 / \u25be": "expand / collapse that node",
        "e": "collapse all / expand all",
        "\u2191 / \u2193": "move the tree focus",
        "\u2190 / \u2192": "collapse / expand the focused node",
        "s": "select the focused node",
    },
    "housekeeping": {
        "i": "re-import labels.tsv from the pack",
        "x": "export labels.tsv",
        "r": "reload state from the server",
    },
}


def serve(pack, host, port, open_browser, verbose=False):
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.pack = pack
    httpd.verbose = verbose
    actual = httpd.server_address[1]
    url = f"http://{host}:{actual}/"
    print(f"review-ui: pack {pack.dir}", flush=True)
    print(f"review-ui: {len(pack.ids)} items, claims from {pack.claims_dir}", flush=True)
    print(f"URL {url}", flush=True)
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nreview-ui: stopped", flush=True)
    finally:
        httpd.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Local review UI for parser outputs")
    ap.add_argument("--pack", type=Path, required=True, help="review pack directory")
    ap.add_argument("--artifact", type=Path, default=None,
                    help="artifact jsonl (default: meta.json source, else ./compile_standard.jsonl)")
    ap.add_argument("--claims-dir", type=Path, default=None,
                    help="directory with claims.json / audit TSVs (default: repo review/)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true", help="open a browser")
    ap.add_argument("--import", dest="import_path", type=Path, default=None,
                    help="labels.tsv to ingest (default: <pack>/labels.tsv)")
    ap.add_argument("--no-import", action="store_true", help="skip the startup import")
    ap.add_argument("--export", action="store_true",
                    help="write labels.tsv and exit")
    ap.add_argument("--export-out", type=Path, default=None,
                    help="export path (default: <pack>/labels.tsv)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    pack = Pack(args.pack, artifact=args.artifact, claims_dir=args.claims_dir,
                import_path=args.import_path, do_import=not args.no_import)
    if args.export:
        if args.import_path or (pack.import_path and pack.import_path.exists()):
            result = pack.import_labels(args.import_path)
            if result["imported"] and not args.quiet:
                print(f"imported {result['imported']} rows from {result['path']}")
            for warning in pack.import_warnings:
                print(f"notice: {warning}", file=sys.stderr)
        out = pack.export(args.export_out)
        print(f"exported {out['rows']} labels to {out['path']} ({out['lines']} rows)")
        return 0
    if not args.quiet:
        counts = pack.counts()
        print(f"review-ui: loaded {counts['done']}/{len(pack.ids)} labels "
              f"({counts['imported']} imported)", flush=True)
        for warning in pack.import_warnings:
            print(f"notice: {warning}", file=sys.stderr)
    serve(pack, args.host, args.port, args.open, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
