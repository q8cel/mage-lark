# Review state
`ledger.csv` is generated from a snapshot by `tools/review.py seed`; never hand-edit it.
`claims/<owner>.txt` and `batches/` are scratch state and are git-ignored.
`verdicts/<owner>.csv` is appended by reviewers and IS committed: it is the accumulated judgment.
`loop_inspected.txt` lists sids already read by the audit loops.
Cycle: `tools/snapshot.py build --data {FDN,classic,Standard}.json` → `tools/review.py carry --root review/<c>N --out /tmp/carry.csv` → `seed --root review/<c>N+1 --carry ... --exempt review/loop_inspected.txt` → `batch`; `.cache/trees/trees_<grammar16>.pkl.gz` caches parse trees, so interpreter-only rebuilds take seconds.
