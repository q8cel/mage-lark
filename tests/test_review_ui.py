#!/usr/bin/env python3
"""Smoke test for tools/review_ui.py.

Starts the review server on an ephemeral port against a temporary copy of the
Standard v5 pack, exercises the HTTP API (import, per-item payload, claim
decision, label, undo, export), checks that ``labels.jsonl`` and the exported
``labels.tsv`` round-trip, and confirms ``swarm/scripts/human_audit_eval.py``
accepts the exported file.

Run with ``./myenv/bin/python tests/test_review_ui.py`` from the repo root.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "tools" / "review_ui.py"
ARTIFACT = ROOT / "compile_standard.jsonl"
DEFAULT_PACK = ROOT.parent / "swarm" / "work" / "human_review_v5"
V5_LABELS = ROOT.parent / "swarm" / "work" / "human_review_v5" / "labels.tsv"
EVAL = ROOT.parent / "swarm" / "scripts" / "human_audit_eval.py"
PY = sys.executable

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition)))
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        raise SystemExit(f"smoke test failed: {name} {detail}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def request(port, path, payload=None):
    url = f"http://127.0.0.1:{port}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def request_json(port, path, payload=None):
    status, body = request(port, path, payload)
    try:
        return status, json.loads(body.decode("utf-8"))
    except ValueError:
        return status, {"raw": body.decode("utf-8", "replace")}


def build_pack(tmp, src):
    pack = tmp / "pack"
    pack.mkdir()
    for name in ("key.json", "meta.json", "items.json", "sheet_01.md", "sheet_02.md"):
        if (src / name).exists():
            shutil.copy2(src / name, pack / name)
    key = json.loads((pack / "key.json").read_text(encoding="utf-8"))
    ids = sorted(key)
    rich_id, ok_id = ids[0], ids[1]
    rows = ["id\tverdict\tnote"]
    for hid in ids:
        if hid == rich_id:
            rows.append(f'{hid}\tbug "zone": destination says library but it should be exile')
        elif hid == ok_id:
            rows.append(f"{hid}\tok")
        else:
            rows.append(f"{hid}\t\t")
    (pack / "labels.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return pack, ids, rich_id, ok_id


def start_server(pack, extra=()):
    cmd = [PY, str(UI), "--pack", str(pack), "--artifact", str(ARTIFACT),
           "--port", "0", "--quiet", *extra]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    port = None
    deadline = time.time() + 20
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise SystemExit("server exited during startup:\n" + proc.stdout.read())
            continue
        if line.startswith("URL "):
            port = int(line.strip().rstrip("/").rsplit(":", 1)[1])
            break
    if port is None:
        raise SystemExit("server did not print its URL")
    for _ in range(100):
        try:
            status, _body = request(port, "/api/state")
            if status == 200:
                break
        except (urllib.error.URLError, ConnectionError):
            pass
        time.sleep(0.05)
    return proc, port


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def last_label(path, hid):
    found = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("id") == hid:
            found = rec
    return found


def walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_keys(value)


def leaf_paths(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaf_paths(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from leaf_paths(value, f"{path}[{i}]")
    else:
        yield path


def real_import_case(tmp, src):
    """Copy the pack, drop the user's in-progress v5 labels.tsv in, import it."""
    if not V5_LABELS.exists():
        print("  [skip] real import case: no v5 labels.tsv")
        return
    if src.resolve() == V5_LABELS.parent.resolve():
        print("  [skip] real import case: source pack is the v5 pack")
        return
    pack = tmp / "pack_real"
    pack.mkdir()
    for name in ("meta.json", "key.json", "items.json", "sheet_01.md", "sheet_02.md"):
        if (src / name).exists():
            shutil.copy2(src / name, pack / name)
    shutil.copy2(V5_LABELS, pack / "labels.tsv")
    key = json.loads((pack / "key.json").read_text(encoding="utf-8"))
    if "Y001" not in key:
        with (pack / "labels.tsv").open("a", encoding="utf-8") as fh:
            fh.write("Y001\tok\tstray id from the v5 sheet\n")
    original = (pack / "labels.tsv").read_bytes()
    expected_imported = 0
    expected_unknown = set()
    for line in original.decode("utf-8-sig").splitlines()[1:]:
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        hid = parts[0].strip()
        rest = parts[1].split() if len(parts) > 1 else []
        verdict = rest[0].lower() if rest else ""
        if verdict not in ("ok", "bug", "legit"):
            continue
        if hid in key:
            expected_imported += 1
        else:
            expected_unknown.add(hid)
    proc, port = start_server(pack)
    try:
        status, state = request_json(port, "/api/state")
        check("real import: server started on the v6 pack", status == 200
              and state["n"] == len(key), str(state.get("n")))
        check("real import: import counts", state["counts"]["imported"] == expected_imported,
              f"got {state['counts']['imported']}, expected {expected_imported}")
        check("real import: labels.tsv not modified",
              (pack / "labels.tsv").read_bytes() == original)
        status, resp = request_json(port, "/api/import", {})
        check("real import: unknown ids reported",
              set(resp.get("unknown", [])) == expected_unknown,
              f"got {resp.get('unknown')}, expected {sorted(expected_unknown)}")
        check("real import: no rows re-imported",
              resp.get("imported") == 0, str(resp.get("imported")))
        # Simulate the reviewer having typed verdicts into the same v5 file:
        # rows for v5-only ids stay unknown, rows for v6 ids import.
        v5_ids = []
        for line in original.decode("utf-8-sig").splitlines()[1:]:
            hid = line.split("\t")[0].strip()
            if hid and hid not in key:
                v5_ids.append(hid)
        v5_ids = v5_ids[:3]
        simulate = ["id\tverdict\tnote"]
        for hid in v5_ids:
            simulate.append(f'{hid}\tbug "zone": v5 sheet note for a v5-only id')
        simulate.append(f"{key and sorted(key)[2]}\tlegit\tlooks parsed but cosmetic")
        simulate.append(f"{sorted(key)[3]}\tok\t")
        (pack / "labels.tsv").write_text("\n".join(simulate) + "\n", encoding="utf-8")
        simulated = (pack / "labels.tsv").read_bytes()
        status, resp = request_json(port, "/api/import", {})
        check("in-progress import: v6 rows imported, v5-only rows unknown",
              status == 200 and resp["imported"] == 2
              and set(resp["unknown"]) == set(v5_ids),
              f"imported={resp.get('imported')} unknown={resp.get('unknown')}")
        check("in-progress import: file not modified",
              (pack / "labels.tsv").read_bytes() == simulated)
        status, resp2 = request_json(port, "/api/import", {})
        check("in-progress import: second pass imports nothing",
              resp2["imported"] == 0 and resp2["skipped"] >= 2, str(resp2))
        print(f"  real import: user file {expected_imported} rows imported / "
              f"{len(expected_unknown)} unknown; simulated in-progress file "
              f"2 imported / {len(v5_ids)} unknown")
        return state
    finally:
        stop_server(proc)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    args = ap.parse_args()
    src = args.pack.resolve()
    if not src.is_dir():
        raise SystemExit(f"missing review pack: {src}")
    if not ARTIFACT.exists():
        raise SystemExit(f"missing artifact: {ARTIFACT}")

    tmp = Path(tempfile.mkdtemp(prefix="review-ui-test-"))
    pack, ids, rich_id, ok_id = build_pack(tmp, src)
    print(f"pack: {src}")
    labels_jsonl = pack / "labels.jsonl"
    labels_tsv = pack / "labels.tsv"
    import_bytes = labels_tsv.read_bytes()
    proc = None
    try:
        print("start server")
        proc, port = start_server(pack)

        # ---- state + import -----------------------------------------
        status, state = request_json(port, "/api/state")
        check("GET /api/state", status == 200 and state.get("n") == 100,
              f"status={status}")
        check("100 items, 10 per batch",
              state["n"] == 100 and state["batch"] == 10)
        check("lanes split 50/50",
              state["lanes"] == {"triage": 50, "blind": 50},
              str(state["lanes"]))
        check("two vim rows imported at startup",
              state["counts"]["imported"] == 2,
              f"counts={state['counts']}")
        check("import leaves labels.tsv untouched",
              labels_tsv.read_bytes() == import_bytes)
        unlabeled = [it for it in state["items"] if not it["done"]]
        check("lane hidden on unlabelled items",
              unlabeled and all("lane" not in it for it in unlabeled))
        check("lane recorded on labelled items",
              all(it.get("lane") in ("triage", "blind")
                  for it in state["items"] if it["done"]))
        meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
        claims_file = ROOT / "review" / "claims.json"
        declared_art = meta.get("artifact_sha256")
        declared_claims = meta.get("claims_sha256")
        shas_match = (declared_art == sha256(ARTIFACT)
                      and (not declared_claims or not claims_file.exists()
                           or declared_claims == sha256(claims_file)))
        if shas_match:
            check("no SHA warning banner", state["warnings"] == [], str(state["warnings"]))
            check("state reports the matching SHAs",
                  state["artifact_sha256"] == declared_art
                  and (not declared_claims or state["claims_sha256"] == declared_claims))
        else:
            print(f"  [skip] SHA banner check (pack declares {declared_art[:12] if declared_art else '?'}")
        lanes = json.loads((pack / "review_state.json").read_text())["lanes"]
        check("state file records the lane split",
              len(lanes) == 100 and set(lanes) == set(ids))

        # ---- static assets -----------------------------------------
        for name, needle in (("/", "review-ui"), ("/app.js", "commit"),
                             ("/style.css", "--bg")):
            code, body = request(port, name)
            check(f"static {name}", code == 200 and needle.encode() in body)
        page = request(port, "/")[1].decode() + request(port, "/app.js")[1].decode()
        # the SVG namespace URI is the only http:// string allowed
        check("no external requests in static assets",
              "https://" not in page
              and page.replace("http://www.w3.org/2000/svg", "").count("http://") == 0)

        # ---- imported label shape ----------------------------------
        status, item = request_json(port, f"/api/item?id={rich_id}")
        check("GET /api/item", status == 200 and item["id"] == rich_id)
        label = item.get("label") or {}
        check("imported verdict/note preserved",
              label.get("verdict") == "bug"
              and label.get("note", "").startswith('"zone": destination says library'),
              str(label))
        check("imported axis inferred from the loose note",
              label.get("axis") == "zone", str(label.get("axis")))
        zone_present = any(key == "zone" for key in walk_keys(item.get("output")))
        check("imported path resolved against the output",
              (label.get("path", "").startswith("$") if zone_present else
               label.get("path", "") == "") and label.get("source") == "import",
              str(label.get("path")))
        ir = item.get("ir") or {}
        check("item carries the semantic IR",
              bool(ir.get("lines")) and all(
                  frag["path"].startswith("$")
                  for line in ir["lines"] for frag in line["fragments"]))
        check("semantic IR has a graph",
              isinstance(ir.get("graph", {}).get("nodes"), list)
              and isinstance(ir.get("graph", {}).get("edges"), list))
        check("resolved text and card context present",
              item.get("resolved_text") and len(item.get("cards", [])) >= 1)
        items_json = pack / "items.json"
        if items_json.exists():
            entries = {e["id"]: e for e in json.loads(items_json.read_text())
                       if isinstance(e, dict)}
            first = entries.get(item["id"], {})
            expected_text = (first.get("original_text") or first.get("sentence")
                             or first.get("text") or "")
            check("items.json payload drives the item text",
                  expected_text and item["original_text"] == expected_text)
            check("items.json card_text rendered",
                  any(row["text"] for row in item["cards"]))
        check("content alignment tokens present",
              any(t["cls"] == "found" for t in item["tokens"])
              and any(t["cls"] == "function" for t in item["tokens"]))

        # ---- claim lane gating -------------------------------------
        claims_by_triple = {}
        claims_json = ROOT / "review" / "claims.json"
        if claims_json.exists():
            try:
                data = json.loads(claims_json.read_text(encoding="utf-8"))
                for rec in data.get("records", []):
                    claims_by_triple[(rec.get("card"), rec.get("sid"),
                                      rec.get("sentence_index"))] = rec.get("claims", [])
            except ValueError:
                pass
        key = json.loads((pack / "key.json").read_text())
        triage_claim_item = blind_claim_item = None
        for hid in ids:
            k = key[hid]
            has_claim = bool(claims_by_triple.get(
                (k["card"], k["sid"], k["sentence_index"]))) or bool(
                claims_by_triple.get((k["card"], k["sid"])))
            status, payload = request_json(port, f"/api/item?id={hid}")
            if payload.get("claims") and triage_claim_item is None \
                    and not payload.get("label"):
                triage_claim_item = payload
            if has_claim and lanes[hid] == "blind" and blind_claim_item is None:
                blind_claim_item = payload
            if triage_claim_item and blind_claim_item:
                break
        check("triage item renders machine claims", triage_claim_item is not None)
        check("blind item hides claims",
              blind_claim_item is not None and blind_claim_item["claims"] == [],
              str(blind_claim_item and blind_claim_item.get("claims")))

        # ---- claim decision ----------------------------------------
        claim = triage_claim_item["claims"][0]
        status, resp = request_json(port, "/api/claim", {
            "id": triage_claim_item["id"], "key": claim["key"], "decision": "accept"})
        check("POST /api/claim accepts", status == 200
              and claim["key"] in resp["claim_state"]["accepted"])
        status, payload = request_json(port, f"/api/item?id={triage_claim_item['id']}")
        check("claim decision persists across requests",
              claim["key"] in payload["claim_state"]["accepted"])
        saved_state = json.loads((pack / "review_state.json").read_text())
        check("claim decision in the state file",
              claim["key"] in saved_state["claims"][triage_claim_item["id"]]["accepted"])

        # ---- label a bug with a JSON path --------------------------
        hid = triage_claim_item["id"]
        output = triage_claim_item["output"]
        path = claim.get("path") or next(leaf_paths(output))
        status, resp = request_json(port, "/api/label", {
            "id": hid, "verdict": "bug", "axis": "zone", "path": path,
            "note": "wrong destination",
            "claims_accepted": [claim["key"]], "claims_rejected": []})
        check("POST /api/label", status == 200 and resp.get("ok"), str(resp))
        rec = last_label(labels_jsonl, hid)
        check("labels.jsonl record fields",
              rec["verdict"] == "bug" and rec["axis"] == "zone"
              and rec["path"] == path and rec["lane"] == lanes[hid]
              and rec["source"] == "ui" and rec["timestamp"]
              and rec["claims_accepted"] == [claim["key"]])
        check("note is path: value plus free text",
              rec["note"].startswith(f"zone: {path}:") and "wrong destination" in rec["note"],
              rec["note"])
        status, payload = request_json(port, f"/api/item?id={hid}")
        check("lane revealed after labelling",
              payload.get("lane") == lanes[hid] and payload["label"]["verdict"] == "bug")

        # ---- undo --------------------------------------------------
        status, resp = request_json(port, "/api/undo", {"id": hid})
        check("POST /api/undo", status == 200)
        undone = last_label(labels_jsonl, hid)
        check("undo appended, verdict cleared",
              undone["op"] == "undo" and undone["verdict"] is None)
        status, payload = request_json(port, f"/api/item?id={hid}")
        check("item unlabelled after undo",
              payload["label"] is None and "lane" not in payload)

        # ---- re-label for the export -------------------------------
        status, resp = request_json(port, "/api/label", {
            "id": hid, "verdict": "bug", "axis": "zone", "path": path,
            "note": "", "claims_accepted": [claim["key"]], "claims_rejected": []})
        check("re-label", status == 200)
        status, resp = request_json(port, "/api/label", {
            "id": ids[2], "verdict": "ok", "axis": "", "path": "", "note": ""})
        check("ok label without a path", status == 200 and resp["record"]["note"] == "")

        # ---- import is idempotent ----------------------------------
        status, resp = request_json(port, "/api/import", {})
        check("second import adds nothing",
              status == 200 and resp["imported"] == 0 and resp["skipped"] >= 2,
              str(resp))
        check("import still leaves labels.tsv untouched",
              labels_tsv.read_bytes() == import_bytes)

        # ---- export + eval -----------------------------------------
        status, resp = request_json(port, "/api/export", {})
        check("POST /api/export", status == 200 and Path(resp["path"]).exists())
        exported = labels_tsv.read_text(encoding="utf-8")
        lines = exported.splitlines()
        check("exported header", lines[0] == "id\tverdict\tnote")
        check("exported row count", len(lines) - 1 == 100, str(len(lines) - 1))
        by_id = {}
        for line in lines[1:]:
            parts = line.split("\t")
            by_id.setdefault(parts[0], []).append(line)
        check("export has no duplicate ids",
              all(len(v) == 1 for v in by_id.values()))
        check("imported rows survive export verbatim",
              by_id[rich_id][0].startswith(f'{rich_id}\tbug "zone":') and
              by_id[ok_id][0].startswith(f"{ok_id}\tok"))
        check("UI label exported",
              by_id[hid][0].startswith(f"{hid}\tbug\t") and path in by_id[hid][0],
              by_id.get(hid))

        if EVAL.exists():
            result = subprocess.run([PY, str(EVAL), "--pack", str(pack)],
                                    capture_output=True, text=True, cwd=str(ROOT.parent))
            check("human_audit_eval.py accepts the exported labels.tsv",
                  result.returncode == 0,
                  f"rc={result.returncode}\n{result.stdout}\n{result.stderr}")
            check("eval reads the exported rows",
                  "labels.tsv" in result.stdout or "labelled" in result.stdout,
                  result.stdout[:400])
        else:
            print(f"  [skip] eval script missing: {EVAL}")

        # ---- persistence across restart ----------------------------
        stop_server(proc)
        proc = None
        before = labels_jsonl.read_text(encoding="utf-8")
        proc, port = start_server(pack)
        status, state = request_json(port, "/api/state")
        check("state persists across restart", status == 200
              and state["counts"]["done"] == 4, str(state["counts"]))
        check("labels.jsonl untouched by restart",
              labels_jsonl.read_text(encoding="utf-8") == before)
        status, payload = request_json(port, f"/api/item?id={hid}")
        check("label survives restart", payload["label"]["verdict"] == "bug")

        stop_server(proc)
        proc = None
        real_import_case(tmp, src)

        print(f"\nimported rows at startup: {state['counts']['imported']}")
        print(f"labels in state: {state['counts']['done']}")
        print(f"checks passed: {len(CHECKS)}")
        print(f"temp pack: {pack}")
        return 0
    finally:
        if proc is not None:
            stop_server(proc)


if __name__ == "__main__":
    raise SystemExit(main())
