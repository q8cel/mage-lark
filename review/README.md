# Review state
`ledger.csv` is generated from a snapshot by `tools/review.py seed`; never hand-edit it.
`claims/<owner>.txt` and `batches/` are scratch state and are git-ignored.
`verdicts/<owner>.csv` is appended by reviewers and IS committed: it is the accumulated judgment.
`loop_inspected.txt` lists sids already read by the audit loops.
