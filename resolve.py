import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import torch
from transformers import AutoModel, AutoTokenizer

from preprocess import normalize_names, strip_reminders
from mentions import candidate_mentions
from anaphora import find_anaphors

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


_FDN = None


def _load_fdn():
    global _FDN
    if _FDN is None:
        from setdata import load
        _FDN = load(os.path.join(BASE, "FDN.json"))
    return _FDN


def card_text(name):
    items, types, names, sets = _load_fdn()
    for n, text, code in items:
        if n == name or n.lower() == name.lower():
            t = " ".join(normalize_names(strip_reminders(text), names).split())
            return t
    return None


def anaphora(text):
    return find_anaphors(text)


def nearest_baseline(cands, aspan):
    before = [c for c in cands if c["end"] <= aspan[0]]
    if not before:
        return None
    return max(before, key=lambda c: c["end"])


class AttentionResolver:
    def __init__(self, model=DEFAULT_MODEL, layer=2, head="max"):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.enc = AutoModel.from_pretrained(model, attn_implementation="eager").eval()
        self.layer = layer
        self.head = head

    @staticmethod
    def _tokens_in(offs, span):
        s, e = span
        return [i for i, (a, b) in enumerate(offs) if a < b and not (b <= s or a >= e)]

    @torch.no_grad()
    def score(self, text, aspan, cspans):
        e = self.tok(text, return_offsets_mapping=True)
        ids = torch.tensor([e["input_ids"]])
        offs = e["offset_mapping"]
        out = self.enc(ids, output_attentions=True)
        attn = torch.stack(out.attentions)[self.layer, 0]
        attn = attn.max(dim=0).values if self.head == "max" else attn.mean(dim=0)
        ai = self._tokens_in(offs, aspan)
        if not ai:
            return [0.0] * len(cspans)
        row = attn[ai].mean(dim=0)
        scores = []
        for sp in cspans:
            ti = self._tokens_in(offs, sp)
            scores.append(float(row[ti].sum()) if ti else 0.0)
        return scores

    def resolve(self, text):
        cands = candidate_mentions(text, parser=True)
        result = []
        for a in anaphora(text):
            if a.get("kind") == "pronoun":
                pool = cands
            else:
                pool = [c for c in cands if c["end"] <= a["start"]]
            if not pool:
                result.append({"anaphor": a, "antecedent": None, "scores": []})
                continue
            sc = self.score(text, (a["start"], a["end"]), [(c["start"], c["end"]) for c in pool])
            ranked = sorted(zip(pool, sc), key=lambda x: x[1], reverse=True)
            result.append({"anaphor": a, "antecedent": ranked[0][0], "scores": ranked})
        return result


def eval_benchmark(resolver, bench_path=None):
    bench_path = bench_path or os.path.join(BASE, "coref_benchmark.json")
    with open(bench_path) as fh:
        labels = json.load(fh)
    cases = []
    for card, ana, occ, gold in labels:
        text = card_text(card)
        if not text:
            continue
        ms = [m for m in re.finditer(r"(?<![A-Za-z])" + re.escape(ana) + r"(?![A-Za-z])", text, re.I)]
        if len(ms) <= occ:
            continue
        aspan = (ms[occ].start(), ms[occ].end())
        cands = [c for c in candidate_mentions(text, parser=True) if not (c["start"] == aspan[0] and c["end"] == aspan[1])]
        g = gold.lower()
        gi = None
        for i, c in enumerate(cands):
            ss = c["surface"].lower()
            if (g in ss or ss in g) and c["end"] <= aspan[0]:
                gi = i
                break
        if gi is None:
            for i, c in enumerate(cands):
                ss = c["surface"].lower()
                if g in ss or ss in g:
                    gi = i
                    break
        if gi is None:
            continue
        cases.append((text, aspan, cands, gi))
    ok = 0
    bl = 0
    for text, aspan, cands, gi in cases:
        sc = resolver.score(text, aspan, [(c["start"], c["end"]) for c in cands])
        if max(range(len(cands)), key=lambda i: sc[i]) == gi:
            ok += 1
        nb = nearest_baseline(cands, aspan)
        if nb is not None and nb["surface"] == cands[gi]["surface"]:
            bl += 1
    n = len(cases)
    print(f"cases={n}  attention={ok}/{n}={100*ok/max(n,1):.0f}%  baseline={bl}/{n}={100*bl/max(n,1):.0f}%")
    return ok, bl, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="?")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--layer", type=int, default=2)
    ap.add_argument("--head", default="max")
    args = ap.parse_args()
    r = AttentionResolver(args.model, args.layer, args.head)
    if args.eval:
        eval_benchmark(r)
        return
    if not args.card:
        ap.error("provide a card name or --eval")
    text = card_text(args.card)
    if not text:
        print("card not found")
        return
    print(text)
    for res in r.resolve(text):
        a = res["anaphor"]["surface"]
        ant = res["antecedent"]["surface"] if res["antecedent"] else None
        print(f"  {a!r:22} -> {ant!r}")


if __name__ == "__main__":
    main()
