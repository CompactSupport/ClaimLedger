# Candidate benchmark expansion (NOT gold)

This is an **original, fictional, author-labeled starter set**: 20 documents and 60 candidate claims, balanced across `supported`, `contradicted`, and `insufficient`. No human review has been completed. No observed model performance on these rows is a reliable accuracy estimate.

The sharding exists because v0.2 `evaluate` limits each dataset to 30 rows. Each shard contains 20 rows with relative `documents/*.md` paths and can run using the current CLI unchanged.

## Offline use

```bash
python -m pip install -e '.[dev]'
python -m claimledger evaluate --dataset benchmark/candidates/shard-01.jsonl --out output/claimledger-shard-01.json
python -m claimledger evaluate --dataset benchmark/candidates/shard-02.jsonl --out output/claimledger-shard-02.json
python -m claimledger evaluate --dataset benchmark/candidates/shard-03.jsonl --out output/claimledger-shard-03.json
python scripts/evaluate_candidate_shards.py --backend local
```

All reported rows are **synthetic_author_labeled**, not manually verified gold. The v0.2 CLI hardcodes `dataset_tier=smoke`; do not relabel that value to gold when reviewing this material.

`reviewed_label` is empty until a person fills it. The author column `expected` is never copied into that field. Freeze accepted reviews with:

```bash
python scripts/freeze_reviewed_labels.py --out output/frozen_reviews.json
```

`gold_count` stays 0 while every `human_reviewed` value is false. Development documents are `d001.md` through `d014.md`. Held-out documents are `d015.md` through `d020.md`. Do not tune on the held-out documents. See [REVIEW_GUIDE.md](../REVIEW_GUIDE.md).

## Human review before a gold release

Review `review_queue.csv` line by line: check the exact original document, confirm the label (entire claim, not just a word match), check whether the quote genuinely supports/refutes the label, record a reviewer, time, and comments. For uncertain claims, fix the example instead of forcing a label. Re-review ambiguous arithmetic, temporal statements, negation, and underspecified conditions. Prefer an independent reviewer or adjudication process. Track reviewer agreement when multiple reviewers participate.

Only a reviewed, versioned frozen set should be called a gold benchmark; use separate development and held-out evaluation portions. Do not tune prompts on held-out data. Do not combine evaluations against test labels with training claims. All cases here are invented and do not incorporate employer documents, customer data, or licensed research reports.
