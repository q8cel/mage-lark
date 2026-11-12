#!/usr/bin/env python3
"""Tests for tools/snapshot.py and tools/review.py.

Deterministic and corpus-free: snapshots are built from a tiny fixed sentence
file, review state lives in a temporary directory.  Run with
``python tests/test_review.py`` from anywhere.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
SNAPSHOT = os.path.join(ROOT, "tools", "snapshot.py")
REVIEW = os.path.join(ROOT, "tools", "review.py")

SENTENCES = [
    "Draw a card",
    "Draw two cards",
    "Draw three cards",
    "You gain 3 life",
    "You gain 2 life",
    "Target creature gets +1/+1 until end of turn",
]


def run(script, *args, cwd=None):
    return subprocess.run([PY, script] + list(args), capture_output=True,
                          text=True, cwd=cwd or ROOT)


def build_snapshot(texts, out, extra=(), fixture=None):
    if fixture is None:
        fixture = out + ".txt"
        with open(fixture, "w") as fh:
            fh.write("\n".join(texts) + "\n")
    res = run(SNAPSHOT, "build", "--sentences", fixture, "--out", out, *extra)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def write(doc, path):
    with open(path, "w") as fh:
        json.dump(doc, fh, sort_keys=True, separators=(",", ":"))


def test_snapshot_deterministic(tmp):
    a = os.path.join(tmp, "snap_a.json")
    b = os.path.join(tmp, "snap_b.json")
    fixture = os.path.join(tmp, "fixed.txt")
    with open(fixture, "w") as fh:
        fh.write("\n".join(SENTENCES) + "\n")
    build_snapshot(SENTENCES, a, fixture=fixture)
    build_snapshot(SENTENCES, b, fixture=fixture)
    assert open(a, "rb").read() == open(b, "rb").read(), "snapshot builds differ"
    doc = json.load(open(a))
    assert doc["meta"]["count"] == len(doc["sentences"])
    assert set(doc["sentences"]) == set(SENTENCES)
    assert "stale" not in doc["meta"]
    for rec in doc["sentences"].values():
        assert len(rec["cluster"]) > 0
        assert len(rec["out_sha1"]) == 40 and len(rec["shape_sha1"]) == 40
    res = run(SNAPSHOT, "diff", a, a, "--json")
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["changed"] == 0


def test_diff_classes(tmp):
    base = os.path.join(tmp, "base.json")
    build_snapshot(SENTENCES, base)
    doc = json.load(open(base))
    sentences = [t for t in SENTENCES if t in doc["sentences"]]
    assert len(sentences) >= 5
    other = dict(doc)
    other["sentences"] = {k: dict(v) for k, v in doc["sentences"].items()}

    added = "Flying"
    removed = sentences[0]
    changed_cluster = sentences[1]
    changed_shape = sentences[2]
    changed_output = sentences[3]
    _unchanged = sentences[4]

    other["sentences"][added] = {"out_sha1": "0" * 40,
                                 "shape_sha1": "1" * 40,
                                 "cluster": "start(sentence($@))"}
    del other["sentences"][removed]
    other["sentences"][changed_cluster]["cluster"] += "(x)"
    other["sentences"][changed_shape]["shape_sha1"] = "2" * 40
    other["sentences"][changed_output]["out_sha1"] = "3" * 40

    b = os.path.join(tmp, "changed.json")
    write(other, b)
    res = run(SNAPSHOT, "diff", base, b, "--json")
    assert res.returncode == 1, "diff must exit 1 when something changed"
    data = json.loads(res.stdout)
    counts = data["counts"]
    assert counts["added"] == 1 and counts["removed"] == 1
    assert counts["cluster"] == 1 and counts["shape"] == 1 and counts["output"] == 1
    classes = {row["sentence"]: cls for cls, rows in data["details"].items()
               for row in rows}
    assert classes[added] == "added" and classes[removed] == "removed"
    assert classes[changed_cluster] == "cluster"
    assert classes[changed_shape] == "shape"
    assert classes[changed_output] == "output"
    assert classes[_unchanged] == "unchanged"


def test_review_flow(tmp):
    snap = os.path.join(tmp, "snap.json")
    build_snapshot(SENTENCES, snap)
    root = os.path.join(tmp, "review")
    res = run(REVIEW, "seed", "--snapshot", snap, "--out",
              os.path.join(root, "ledger.csv"))
    assert res.returncode == 0, res.stderr
    seeded = json.loads(res.stdout)
    ledger_rows = list(__import__("csv").DictReader(open(os.path.join(root, "ledger.csv"))))
    assert len(ledger_rows) == seeded["rows"]
    assert len({r["sid"] for r in ledger_rows}) == len(ledger_rows)

    b1 = os.path.join(tmp, "b1.json")
    b2 = os.path.join(tmp, "b2.json")
    r1 = run(REVIEW, "batch", "--owner", "a1", "--n", "2", "--out", b1, "--root", root)
    r2 = run(REVIEW, "batch", "--owner", "a2", "--n", "2", "--out", b2, "--root", root)
    assert r1.returncode == 0 and r2.returncode == 0, r1.stderr + r2.stderr
    s1 = set(json.load(open(b1))["sids"])
    s2 = set(json.load(open(b2))["sids"])
    assert s1 and s2 and not (s1 & s2), "claims overlap across owners"
    assert run(REVIEW, "status", "--root", root).returncode == 0

    sid = sorted(s1)[0]
    res = run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
              "--verdict", "ok", "--root", root)
    assert res.returncode == 0, res.stderr
    # appending again is allowed; the last row wins (reopen path)
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
               "--verdict", "ok", "--root", root).returncode == 0
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
               "--verdict", "bug", "--root", root).returncode == 0
    # unclaimed sid rejected
    other_sid = sorted(s2 - s1)[0]
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", other_sid,
               "--verdict", "ok", "--root", root).returncode != 0
    # unknown sid rejected
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", "0" * 12,
               "--verdict", "ok", "--root", root).returncode != 0

    # check fails until every claimed sid has a verdict
    assert run(REVIEW, "check", "--owner", "a1", "--root", root).returncode != 0
    for sid in sorted(s1):
        run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
            "--verdict", "legit", "--root", root)
    # but a sid the owner never claimed is still rejected
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", other_sid,
               "--verdict", "ok", "--root", root).returncode != 0
    assert run(REVIEW, "check", "--owner", "a1", "--root", root).returncode == 0

    # tampered overlap must be detected loudly
    claim_b = os.path.join(root, "claims", "a2.txt")
    original = open(claim_b).read()
    with open(claim_b, "a") as fh:
        fh.write(sorted(s1)[0] + "\n")
    assert run(REVIEW, "status", "--root", root).returncode == 1
    open(claim_b, "w").write(original)


def test_unparsed_priority(tmp):
    texts = SENTENCES + ["@@@"]
    snap = os.path.join(tmp, "snap_unparsed.json")
    build_snapshot(texts, snap, extra=("--unparsed",))
    doc = json.load(open(snap))
    assert doc["unparsed"] == ["@@@"]
    root = os.path.join(tmp, "review_unparsed")
    out = os.path.join(root, "ledger.csv")
    res = run(REVIEW, "seed", "--snapshot", snap, "--out", out)
    assert res.returncode == 0, res.stderr
    b = os.path.join(tmp, "b_unparsed.json")
    res = run(REVIEW, "batch", "--owner", "u1", "--n", "1", "--out", b, "--root", root)
    assert res.returncode == 0, res.stderr
    item = json.load(open(b))["items"][0]
    assert item["role"] == "unparsed" and item["sentence"] == "@@@"
    for key in ("sid", "sentence", "corpus", "occurrences", "cid", "role",
                "output", "siblings"):
        assert key in item, "missing batch field %s" % key


def test_minority_priority(tmp):
    # the copy/copies pair shares a cluster key but keeps two output shapes
    texts = ["Draw a card",
             "You may choose new targets for the copy",
             "You may choose new targets for the copies"]
    snap = os.path.join(tmp, "snap_minority.json")
    build_snapshot(texts, snap)
    doc = json.load(open(snap))
    shapes = {text: rec["shape_sha1"] for text, rec in doc["sentences"].items()}
    assert len(set(shapes.values())) >= 2, "fixture must contain two output shapes"
    root = os.path.join(tmp, "review_minority")
    out = os.path.join(root, "ledger.csv")
    assert run(REVIEW, "seed", "--snapshot", snap, "--out", out).returncode == 0
    rows = list(__import__("csv").DictReader(open(out)))
    assert any(r["role"] == "minority" for r in rows)
    b = os.path.join(tmp, "b_minority.json")
    res = run(REVIEW, "batch", "--owner", "m1", "--n", "1", "--out", b, "--root", root)
    assert res.returncode == 0, res.stderr
    assert json.load(open(b))["items"][0]["role"] == "minority"


def test_exempt(tmp):
    import hashlib
    texts = ["Draw a card", "Draw two cards", "You gain 3 life"]
    snap = os.path.join(tmp, "snap_exempt.json")
    build_snapshot(texts, snap)
    exempt_sentence = texts[0]
    exempt_sid = hashlib.sha1(exempt_sentence.encode()).hexdigest()[:12]
    exempt_path = os.path.join(tmp, "loop_inspected.txt")
    with open(exempt_path, "w") as fh:
        fh.write("%s\tStandard\n" % exempt_sid)
    root = os.path.join(tmp, "review_exempt")
    out = os.path.join(root, "ledger.csv")
    res = run(REVIEW, "seed", "--snapshot", snap, "--out", out,
              "--exempt", exempt_path)
    assert res.returncode == 0, res.stderr
    rows = {r["sid"]: r for r in __import__("csv").DictReader(open(out))}
    assert rows[exempt_sid]["verdict"] == "inspected"
    assert sum(1 for r in rows.values() if r["verdict"] == "inspected") == 1
    status = run(REVIEW, "status", "--root", root)
    assert status.returncode == 0
    assert "inspected" in status.stdout

    b1 = os.path.join(tmp, "b_ex1.json")
    res = run(REVIEW, "batch", "--owner", "e1", "--n", "10", "--out", b1,
              "--root", root, "--exempt", exempt_path)
    assert res.returncode == 0, res.stderr
    assert exempt_sid not in json.load(open(b1))["sids"]

    b2 = os.path.join(tmp, "b_ex2.json")
    res = run(REVIEW, "batch", "--owner", "e2", "--n", "10", "--out", b2,
              "--root", root, "--exempt", exempt_path, "--include-exempt")
    assert res.returncode == 0, res.stderr
    assert exempt_sid in json.load(open(b2))["sids"]


def test_last_verdict_wins(tmp):
    import csv as _csv
    texts = ["Draw a card", "You gain 3 life"]
    snap = os.path.join(tmp, "snap_last.json")
    build_snapshot(texts, snap)
    root = os.path.join(tmp, "last_r")
    ledger = os.path.join(root, "ledger.csv")
    assert run(REVIEW, "seed", "--snapshot", snap, "--out", ledger).returncode == 0
    b = os.path.join(tmp, "last_batch.json")
    assert run(REVIEW, "batch", "--owner", "a1", "--n", "1",
               "--out", b, "--root", root).returncode == 0
    sid = json.load(open(b))["sids"][0]
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
               "--verdict", "ok", "--root", root).returncode == 0
    assert run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
               "--verdict", "bug", "--root", root).returncode == 0
    log = list(_csv.DictReader(open(os.path.join(root, "verdicts", "a1.csv"))))
    assert [r["verdict"] for r in log if r["sid"] == sid] == ["ok", "bug"]
    carry_csv = os.path.join(tmp, "last_carry.csv")
    assert run(REVIEW, "carry", "--root", root, "--out", carry_csv).returncode == 0
    carried = {r["sid"]: r["verdict"] for r in _csv.DictReader(open(carry_csv))}
    assert carried[sid] == "bug"
    assert run(REVIEW, "check", "--owner", "a1", "--root", root).returncode == 0
    status = run(REVIEW, "status", "--root", root)
    assert status.returncode == 0


def test_carry(tmp):
    import csv as _csv
    import hashlib
    texts = ["Draw a card", "Draw two cards", "You gain 3 life"]
    snap = os.path.join(tmp, "snap_carry.json")
    build_snapshot(texts, snap)

    root1 = os.path.join(tmp, "carry_r1")
    ledger1 = os.path.join(root1, "ledger.csv")
    assert run(REVIEW, "seed", "--snapshot", snap, "--out", ledger1).returncode == 0
    claims = os.path.join(tmp, "carry_batch.json")
    res = run(REVIEW, "batch", "--owner", "a1", "--n", "10",
              "--out", claims, "--root", root1)
    assert res.returncode == 0, res.stderr
    sids = json.load(open(claims))["sids"]
    assert len(sids) >= 3
    for sid in sids:
        assert run(REVIEW, "verdict", "--owner", "a1", "--sid", sid,
                   "--verdict", "ok", "--root", root1).returncode == 0

    carry_csv = os.path.join(tmp, "carry.csv")
    res = run(REVIEW, "carry", "--root", root1, "--out", carry_csv)
    assert res.returncode == 0, res.stderr
    carried = list(_csv.DictReader(open(carry_csv)))
    assert {r["sid"] for r in carried} == set(sids)
    assert all(r["out_sha1"] for r in carried)

    # mutate one output hash and add a new sentence
    doc = json.load(open(snap))
    changed_text = texts[0]
    changed_sid = hashlib.sha1(changed_text.encode()).hexdigest()[:12]
    unchanged_text = texts[1]
    unchanged_sid = hashlib.sha1(unchanged_text.encode()).hexdigest()[:12]
    doc["sentences"][changed_text]["out_sha1"] = "f" * 40
    doc["sentences"]["Flying"] = {"out_sha1": "a" * 40, "shape_sha1": "b" * 40,
                                  "cluster": "start(sentence($@))"}
    doc["outputs"]["Flying"] = [{"type": "static_keyword"}]
    snap2 = os.path.join(tmp, "snap_carry2.json")
    write(doc, snap2)

    root2 = os.path.join(tmp, "carry_r2")
    ledger2 = os.path.join(root2, "ledger.csv")
    res = run(REVIEW, "seed", "--snapshot", snap2, "--out", ledger2,
              "--carry", carry_csv)
    assert res.returncode == 0, res.stderr
    summary = json.loads(res.stdout)["carry"]
    assert summary["reopened"] == 1 and summary["kept"] >= 2 and summary["new"] == 1
    rows = {r["sid"]: r for r in _csv.DictReader(open(ledger2))}
    assert rows[changed_sid]["verdict"] == "todo"
    assert rows[changed_sid]["note"].startswith("reopened: output changed (was ok)")
    assert rows[unchanged_sid]["verdict"] == "ok"
    new_sid = hashlib.sha1(b"Flying").hexdigest()[:12]
    assert rows[new_sid]["verdict"] == "todo" and rows[new_sid]["note"] == ""

    status = run(REVIEW, "status", "--root", root2)
    assert status.returncode == 0
    assert "reopened" in status.stdout
    assert any(line.split()[-1] == "1" for line in status.stdout.splitlines()
               if line.startswith("reopened "))

    # conflicting duplicate verdicts make carry fail
    root3 = os.path.join(tmp, "carry_r3")
    ledger3 = os.path.join(root3, "ledger.csv")
    run(REVIEW, "seed", "--snapshot", snap, "--out", ledger3)
    sid0 = sorted(sids)[0]
    os.makedirs(os.path.join(root3, "verdicts"), exist_ok=True)
    for owner, verdict in (("x", "ok"), ("y", "bug")):
        with open(os.path.join(root3, "verdicts", owner + ".csv"), "w") as fh:
            fh.write("sid,verdict,note\n%s,%s,-\n" % (sid0, verdict))
    res = run(REVIEW, "carry", "--root", root3, "--out",
              os.path.join(tmp, "carry_conflict.csv"))
    assert res.returncode != 0

    # a partially written trailing row (no newline) must not break carry
    root4 = os.path.join(tmp, "carry_r4")
    run(REVIEW, "seed", "--snapshot", snap, "--out",
        os.path.join(root4, "ledger.csv"))
    os.makedirs(os.path.join(root4, "verdicts"), exist_ok=True)
    with open(os.path.join(root4, "verdicts", "partial.csv"), "w") as fh:
        fh.write("sid,verdict,note\n%s,ok,-\n%s,ok" % (sid0, sorted(sids)[1]))
    res = run(REVIEW, "carry", "--root", root4, "--out",
              os.path.join(tmp, "carry_partial.csv"))
    assert res.returncode == 0, res.stderr
    assert len(list(_csv.DictReader(open(os.path.join(tmp, "carry_partial.csv"))))) == 1


def test_stale_snapshot(tmp):
    import importlib.util
    spec = importlib.util.spec_from_file_location("snapshot_tool", SNAPSHOT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # an empty sentence list exercises the provenance check without a parse
    fixture = os.path.join(tmp, "stale.txt")
    open(fixture, "w").close()
    out = os.path.join(tmp, "stale.json")
    before = {"grammar_sha1": "a" * 16, "interp_sha1": "b" * 16,
              "preprocess_sha1": "c" * 16, "setdata_sha1": "d" * 16}
    after = dict(before)
    after["interp_sha1"] = "e" * 16
    calls = [before, after]
    original = mod.source_hashes
    mod.source_hashes = lambda: calls.pop(0)
    try:
        rc = mod.main(["build", "--sentences", fixture, "--out", out])
    finally:
        mod.source_hashes = original
    assert rc != 0, "a source change during build must fail loudly"
    doc = json.load(open(out))
    assert doc["meta"]["stale"] is True
    assert doc["meta"]["sources_at_start"] == before
    assert doc["meta"]["sources_at_end"] == after
    assert doc["meta"]["interp_sha1"] == before["interp_sha1"]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for fn in (test_snapshot_deterministic, test_diff_classes,
                   test_review_flow, test_unparsed_priority,
                   test_minority_priority, test_exempt, test_last_verdict_wins,
                   test_carry, test_stale_snapshot):
            with tempfile.TemporaryDirectory() as sub:
                fn(sub)
            print("PASS", fn.__name__)
    print("all tests passed")


if __name__ == "__main__":
    main()
