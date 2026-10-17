# Candidate benchmark expansion (NOT gold)

This is an **original, fictional, author-labeled candidate set**: 36 documents, 108 claims, and 5 shards, balanced across `supported`, `contradicted`, and `insufficient`. No human review has been completed. No observed model performance on these rows is a reliable accuracy estimate.

The sharding exists because v0.2 `evaluate` limits each dataset to 30 rows. Each shard contains 20 rows with relative `documents/*.md` paths and can run using the current CLI unchanged.

## Offline use

```bash
python -m pip install -e '.[dev]'
python -m claimledger evaluate --dataset benchmark/candidates/shard-01.jsonl --out output/claimledger-shard-01.json
python -m claimledger evaluate --dataset benchmark/candidates/shard-02.jsonl --out output/claimledger-shard-02.json
python -m claimledger evaluate --dataset benchmark/candidates/shard-03.jsonl --out output/claimledger-shard-03.json
python scripts/evaluate_candidate_shards.py --backend local
```

All reported rows are **synthetic_author_labeled**, not manually verified gold. The v0.2 CLI hardcodes `dataset_tier=smoke`; do not relabel that value to gold when reviewing this material. An exact unique quote is required, and it still does not establish that the quote entails the claim. See [SEMANTIC_REVIEW_CHECKLIST.md](../SEMANTIC_REVIEW_CHECKLIST.md).

`reviewed_label` is empty until a person fills it. The author column `expected` is never copied into that field. Freeze accepted reviews with:

```bash
python scripts/freeze_reviewed_labels.py --out output/frozen_reviews.json
```

`gold_count` stays 0 while every `human_reviewed` value is false. Document lists for the internal dev and held-out partition are in `split.json`. That partition is not a blind external test. Do not tune on the held-out documents. See [REVIEW_GUIDE.md](../REVIEW_GUIDE.md).

Each document has three rows, and the case-id suffix is the author label: `-1` supported, `-2` contradicted, `-3` insufficient. Those ids stay here. A semantic-model run uses the shuffled export in [../evaluation/PROTOCOL.md](../evaluation/PROTOCOL.md), which does not include them. AI notes under `ai_second_opinion/` match the author label on 107 of 108 rows. That match is not accuracy, and it does not set `human_reviewed` or release gold. See [ai_second_opinion/README.md](ai_second_opinion/README.md).

## Human review before a gold release

Review `review_queue.csv` line by line: check the exact original document, confirm the label (entire claim, not just a word match), check whether the quote genuinely supports/refutes the label, record a reviewer, time, and comments. For uncertain claims, fix the example instead of forcing a label. Re-review ambiguous arithmetic, temporal statements, negation, and underspecified conditions. Prefer an independent reviewer or adjudication process. Track reviewer agreement when multiple reviewers participate.

Only a reviewed, versioned frozen set should be called a gold benchmark; use separate development and held-out evaluation portions. Do not tune prompts on held-out data. Do not combine evaluations against test labels with training claims. All cases here are invented and do not incorporate employer documents, customer data, or licensed research reports.
