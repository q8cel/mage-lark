"""Pick a stratified dev sample for ensemble labelling.

Strata: anaphor kind x whether the anaphor's sentence yields parser structure.
That keeps the sample representative of what the resolver actually faces instead of
being dominated by the (easy, common) pronouns-with-structure cases.
"""
import json, collections, sys
sys.path.insert(0, "/home/q6/Documents/mage-attn")
import refs, ptree

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
d = json.load(open("/home/q6/Documents/mage-attn/coref_standard.json"))
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
json.dump(sample, open("/tmp/opencode/strat_sample.json", "w"))
print(f"\nsampled {len(sample)} (target {N}, {per}/stratum)")
