"""Pick a stratified dev sample for ensemble labelling.

Strata: anaphor kind x whether the anaphor's sentence yields parser structure.
That keeps the sample representative of what the resolver actually faces instead of
being dominated by the (easy, common) pronouns-with-structure cases.
"""
import json, collections, os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import refs, ptree

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
DEV = os.path.join(BASE, "coref_standard.json")
OUT = (sys.argv[2] if len(sys.argv) > 2
       else os.path.join(BASE, ".cache", "strat_sample.json"))
with open(DEV) as fh:
    d = json.load(fh)
buckets = collections.defaultdict(list)
for case in d:
    text = case["text"]
    if not text.strip():
        continue
    recs = ptree.peek(text) or []
    parsed = [r for r in recs if r["node"]]
    sents = refs.sentence_spans(text)
    for a in case["anaphors"]:
        g = a.get("antecedent")
        if g is None or g < 0:
            continue
        sent = next(((x, y) for x, y in sents if x <= a["start"] < y), None)
        has_struct = bool(sent and any(sent[0] <= r["start"] < sent[1] for r in parsed))
        key = (a["kind"], "struct" if has_struct else "no-struct")
        buckets[key].append({
            "card": case["card"], "text": text, "kind": a["kind"],
            "surface": a["surface"], "start": a["start"], "end": a["end"],
            "teacher": case["candidates"][g]["surface"],
        })

total = sum(len(v) for v in buckets.values())
print(f"dev occurrences: {total} across {len(buckets)} strata")
for k in sorted(buckets, key=lambda k: -len(buckets[k])):
    print(f"  {str(k):<28} {len(buckets[k])}")
per = max(1, N // len(buckets))
sample = []
for k in sorted(buckets):
    v = buckets[k]
    stride = max(1, len(v) // per)
    sample.extend(v[::stride][:per])
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w") as fh:
    json.dump(sample, fh)
print(f"\nsampled {len(sample)} (target {N}, {per}/stratum) -> {OUT}")
