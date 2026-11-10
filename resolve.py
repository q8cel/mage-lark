import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import torch
from transformers import AutoModel, AutoTokenizer

from mentions import candidate_mentions
from anaphora import find_anaphors

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DATA = os.path.join(BASE, "FDN.json")


def card_text(name, data_path=None):
    """Normalized text from the same loader the deterministic path uses."""
    from setdata import card_text as _card_text
    return _card_text(name, data_path or DEFAULT_DATA)


def anaphora(text):
    return find_anaphors(text)


def nearest_baseline(cands, aspan):
    before = [c for c in cands if c["end"] <= aspan[0]]
    if not before:
        return None
    return max(before, key=lambda c: c["end"])


class AttentionResolver:
    def __init__(self, model=DEFAULT_MODEL, layer=2, head="max", max_length=512):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.enc = AutoModel.from_pretrained(model, attn_implementation="eager").eval()
        self.layer = layer
        self.head = head
        self.max_length = max_length

    @staticmethod
    def _tokens_in(offs, span):
        s, e = span
        return [i for i, (a, b) in enumerate(offs) if a < b and not (b <= s or a >= e)]

    @torch.no_grad()
    def score(self, text, aspan, cspans):
        e = self.tok(text, return_offsets_mapping=True,
                     truncation=True, max_length=self.max_length)
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


def eval_benchmark(resolver, bench_path=None, data_path=None):
    """Unified benchmark scoring for the attention baseline.

    Delegates to coref_eval so the attention path and the deterministic rules
    use the same fixed candidate pool and entity-aware metrics.
    """
    from coref_eval import load_bench_cases, evaluate_cases, attention_predictions

    cases, extra = load_bench_cases(bench_path, data_path=data_path,
                                    mentions="parser")
    stats = evaluate_cases(
        cases, lambda case: attention_predictions(case, resolver),
        resolver="attention", verbose=8)
    print(f"  skipped={extra['skipped']}  duplicate_cases={extra['duplicate_cases']}")
    return stats["entity"], stats["exact"], stats["total"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="?")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--layer", type=int, default=2)
    ap.add_argument("--head", default="max")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--max-length", type=int, default=512)
    args = ap.parse_args()
    r = AttentionResolver(args.model, args.layer, args.head, args.max_length)
    if args.eval:
        eval_benchmark(r, data_path=args.data)
        return
    if not args.card:
        ap.error("provide a card name or --eval")
    text = card_text(args.card, args.data)
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
