#!/usr/bin/env python3
"""Smoke test for tools/review_ui.py.

Starts the review server on an ephemeral port against a temporary copy of the
Standard v5 pack, exercises the HTTP API (import, per-item payload, claim
decision, label, undo, export), checks that ``labels.jsonl`` and the exported
``labels.tsv`` round-trip, and confirms ``swarm/scripts/human_audit_eval.py``
accepts the exported file.

Run with ``./myenv/bin/python tests/test_review_ui.py`` from the repo root.
"""

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
SRC_PACK = ROOT.parent / "swarm" / "work" / "human_review_v5"
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


def build_pack(tmp):
    pack = tmp / "pack"
    pack.mkdir()
    for name in ("key.json", "meta.json", "sheet_01.md", "sheet_02.md"):
        shutil.copy2(SRC_PACK / name, pack / name)
    key = json.loads((pack / "key.json").read_text(encoding="utf-8"))
    ids = sorted(key)
    rows = ["id\tverdict\tnote"]
    for hid in ids:
        if hid == "Y001":
            rows.append('Y001\tbug "zone": destination says library but it should be exile')
        elif hid == "Y002":
            rows.append("Y002\tok")
        else:
            rows.append(f"{hid}\t\t")
    (pack / "labels.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return pack, ids


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


def leaf_paths(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaf_paths(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from leaf_paths(value, f"{path}[{i}]")
    else:
        yield path


def main():
    if not SRC_PACK.is_dir():
        raise SystemExit(f"missing review pack: {SRC_PACK}")
    if not ARTIFACT.exists():
        raise SystemExit(f"missing artifact: {ARTIFACT}")

    tmp = Path(tempfile.mkdtemp(prefix="review-ui-test-"))
    pack, ids = build_pack(tmp)
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
        lanes = json.loads((pack / "review_state.json").read_text())["lanes"]
        check("state file records the lane split",
              len(lanes) == 100 and set(lanes) == set(ids))

        # ---- static assets -----------------------------------------
        for name, needle in (("/", "review-ui"), ("/app.js", "commit"),
                             ("/style.css", "--bg")):
            code, body = request(port, name)
            check(f"static {name}", code == 200 and needle.encode() in body)
        page = request(port, "/")[1].decode() + request(port, "/app.js")[1].decode()
        check("no external requests in static assets",
              "http://" not in page and "https://" not in page)

        # ---- imported label shape ----------------------------------
        status, item = request_json(port, "/api/item?id=Y001")
        check("GET /api/item", status == 200 and item["id"] == "Y001")
        label = item.get("label") or {}
        check("imported verdict/note preserved",
              label.get("verdict") == "bug"
              and label.get("note", "").startswith('"zone": destination says library'),
              str(label))
        check("imported axis inferred from the loose note",
              label.get("axis") == "zone", str(label.get("axis")))
        check("imported path resolved against the output",
              label.get("path", "").startswith("$") and label.get("source") == "import",
              str(label.get("path")))
        check("resolved text and card context present",
              item.get("resolved_text") and len(item.get("cards", [])) >= 1)
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
            "id": "Y003", "verdict": "ok", "axis": "", "path": "", "note": ""})
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
              by_id["Y001"][0].startswith("Y001\tbug \"zone\":") and
              by_id["Y002"][0].startswith("Y002\tok"))
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
