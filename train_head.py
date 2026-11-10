#!/usr/bin/env python3
"""Train a small mention-ranking head on the teacher-labelled dataset.

The encoder is FROZEN (no fine-tuning): we mean-pool span representations from
a chosen hidden layer and feed pairwise features into a tiny MLP. The head is
evaluated on the 72 human-gold cases (held out from training by card).

Usage:
  python train_head.py
  python train_head.py --model roberta-base --layer 6 --epochs 40
"""
import argparse
import json
import os
import random
import sys

import numpy as np
import torch
import torch.nn as nn

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from anaphora import find_anaphors
from rulecoref import gold_clusters
from transformers import AutoModel, AutoTokenizer


def norm(s):
    return s.lower().replace("\u2019s", "").replace("'s", "")


def match(ss, g):
    return g in ss or ss in g


def span_repr(hidden, offs, span):
    s, e = span
    idx = [i for i, (a, b) in enumerate(offs) if a < b and not (b <= s or a >= e)]
    if not idx:
        return None, None
    v = hidden[idx].mean(axis=0)
    center = 0.5 * (s + e)
    return v, center


class Encoder:
    """Frozen encoder with a per-text hidden-state cache (persisted to disk)."""

    def __init__(self, model, layer):
        self.tok = AutoTokenizer.from_pretrained(model)
        self.net = AutoModel.from_pretrained(model).eval()
        self.layer = layer
        self.cache = {}
        tag = model.replace("/", "_")
        os.makedirs(os.path.join(BASE, ".cache"), exist_ok=True)
        self.path = os.path.join(BASE, ".cache", f"enc_{tag}_L{layer}.pkl")
        if os.path.exists(self.path):
            import pickle
            try:
                self.cache = pickle.load(open(self.path, "rb"))
            except Exception:
                self.cache = {}

    @torch.no_grad()
    def encode(self, text):
        if text in self.cache:
            return self.cache[text]
        e = self.tok(text, return_offsets_mapping=True, truncation=True, max_length=512)
        ids = torch.tensor([e["input_ids"]])
        out = self.net(ids, output_hidden_states=True)
        h = out.hidden_states[self.layer][0].numpy()
        offs = e["offset_mapping"]
        self.cache[text] = (h, offs)
        return h, offs

    def save(self):
        import pickle
        if self.cache:
            pickle.dump(self.cache, open(self.path, "wb"))


class Scorer(nn.Module):
    def __init__(self, d, hidden=128, dropout=0.3):
        super().__init__()
        self.norm = nn.LayerNorm(4 * d + 2)
        self.net = nn.Sequential(
            nn.Linear(4 * d + 2, hidden), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )

    def forward(self, x):
        return self.net(self.norm(x)).squeeze(-1)


def pair_features(enc, text, aspan, cspan):
    h, offs = enc.encode(text)
    a, ac = span_repr(h, offs, aspan)
    c, cc = span_repr(h, offs, cspan)
    if a is None or c is None:
        return None
    dist = abs(cc - ac) / max(1.0, h.shape[0])
    na, nc = np.linalg.norm(a), np.linalg.norm(c)
    cos = float(a @ c / (na * nc)) if na and nc else 0.0
    return np.concatenate([a, c, a * c, np.abs(a - c), [dist, cos]]).astype(np.float32)


def pool_for(case, a):
    """Global candidate indices offered for anaphor `a` (exclude its own span)."""
    return [j for j, c in enumerate(case["candidates"])
            if c["end"] <= a["start"] or c["start"] >= a["end"]]


def build_examples(data, enc, holdout_cards, layer):
    """Return (train, test) lists. Each item: (anaphor_feat_pairs, gold_index_in_pool)."""
    train, skipped = [], 0
    for case in data:
        if case["card"] in holdout_cards:
            continue
        text = case["text"]
        for a in case["anaphors"]:
            pool = pool_for(case, a)
            if a.get("antecedent") is None or a["antecedent"] < 0:
                continue
            if a["antecedent"] not in pool:
                skipped += 1
                continue
            feats = [pair_features(enc, text, (a["start"], a["end"]),
                                   (case["candidates"][j]["start"],
                                    case["candidates"][j]["end"])) for j in pool]
            if any(f is None for f in feats):
                continue
            gold = pool.index(a["antecedent"])
            train.append((feats, gold))
    return train, skipped


def train_model(examples, d, epochs, lr, seed=0, hidden=128, dropout=0.3, wd=1e-4):
    torch.manual_seed(seed)
    model = Scorer(d, hidden, dropout)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    lossf = nn.BCEWithLogitsLoss()
    rng = random.Random(seed)
    for ep in range(epochs):
        model.train()
        rng.shuffle(examples)
        tot = 0.0
        for feats, gold in examples:
            pos = torch.tensor(feats[gold])
            negs = [torch.tensor(f) for i, f in enumerate(feats) if i != gold]
            if not negs:
                continue
            sp = model(pos.unsqueeze(0))
            sn = model(torch.stack(negs))
            loss = lossf(sp - sn, torch.ones_like(sn))
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss.detach())
        if (ep + 1) % 20 == 0:
            print(f"  epoch {ep+1:3d}  loss={tot/max(1,len(examples)):.4f}")
    model.eval()
    return model


@torch.no_grad()
def eval_gold(model, enc, data, bench):
    by_card = {c["card"]: c for c in data}
    n = ok = base = 0
    for card, ana, occ, gold in bench:
        rec = by_card.get(card)
        if not rec:
            continue
        anas = find_anaphors(rec["text"])
        idxs = [i for i, a in enumerate(anas) if norm(a["surface"]) == norm(ana)]
        if len(idxs) <= occ:
            continue
        a = anas[idxs[occ]]
        pool = [j for j in pool_for(rec, a)]
        if not pool:
            continue
        gi = None
        for j in pool:  # prefer a preceding mention (coreference-consistent)
            ss = rec["candidates"][j]["surface"].lower()
            if match(ss, gold.lower()) and rec["candidates"][j]["end"] <= a["start"]:
                gi = pool.index(j)
                break
        if gi is None:
            for j in pool:
                if match(rec["candidates"][j]["surface"].lower(), gold.lower()):
                    gi = pool.index(j)
                    break
        if gi is None:
            continue
        feats = [pair_features(enc, rec["text"], (a["start"], a["end"]),
                               (rec["candidates"][j]["start"],
                                rec["candidates"][j]["end"])) for j in pool]
        if any(f is None for f in feats):
            continue
        scores = model(torch.tensor(np.stack(feats))).numpy()
        pick = int(np.argmax(scores))
        # entity-aware: any mention of the same gold cluster counts as correct
        uf = gold_clusters(rec["candidates"], rec["anaphors"])
        ok += int(uf.find(pool[pick]) == uf.find(pool[gi]))
        # nearest-mention baseline: greatest end <= anaphor start, else first
        before = [k for k, j in enumerate(pool) if rec["candidates"][j]["end"] <= a["start"]]
        bpick = max(before, key=lambda k: rec["candidates"][pool[k]]["end"]) if before else 0
        base += int(bpick == gi)
        n += 1
    return n, ok, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(BASE, "coref_dataset.json")
                    + "," + os.path.join(BASE, "coref_standard.json"))
    ap.add_argument("--bench", default=os.path.join(BASE, "coref_benchmark.json"))
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    ap.add_argument("--layer", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    data = []
    for p in args.data.split(","):
        data.extend(json.load(open(p)))
    seen = set()
    data = [d for d in data if not (d["card"] in seen or seen.add(d["card"]))]
    bench = json.load(open(args.bench))
    holdout = {b[0] for b in bench}

    enc = Encoder(args.model, args.layer)
    d = None
    for case in data:  # discover hidden size lazily
        h, _ = enc.encode(case["text"])
        d = h.shape[1]
        break

    train_ex, skipped = build_examples(data, enc, holdout, args.layer)
    enc.save()
    print(f"train pools={len(train_ex)}  (skipped {skipped})  dim={d}  layer={args.layer}")

    model = train_model(train_ex, d, args.epochs, args.lr, args.seed,
                        args.hidden, args.dropout, args.wd)
    n, ok, base = eval_gold(model, enc, data, bench)
    print(f"\nGOLD eval: n={n}  head={ok}/{n}={100*ok/max(n,1):.0f}%  "
          f"nearest-mention={base}/{n}={100*base/max(n,1):.0f}%")


if __name__ == "__main__":
    main()
