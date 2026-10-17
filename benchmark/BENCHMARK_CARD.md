# Benchmark card

## What this is

ClaimLedger can score a 108-row fictional candidate set. The set is an engineering fixture. It is not a gold benchmark and it has not been human reviewed.

| Item | Value |
| --- | --- |
| Documents | 36 original fictional Markdown files |
| Rows | 108, with 36 supported, 36 contradicted, and 36 insufficient author labels |
| Label origin | `synthetic_author_labeled` |
| Human-reviewed rows | 0 |
| Gold rows | 0 |
| License of the texts | Written for this repository; not copied from a proprietary report |
| Paid model calls | None |

## How to reproduce

```bash
python -m pip install -e '.[dev]'
python scripts/evaluate_candidate_shards.py --backend local
```

The command refuses `--backend openai` unless `--allow-paid` is also present. CI does not pass that flag.

Macro-F1 is `classification_metrics` on all 108 `(expected, actual)` pairs across 5 shards. The mean of the shard macro-F1 scores is stored separately and is not the reported score. On the local run used to write this card, those two numbers differed.

## Measured local smoke, 2026-10-17

These numbers come from `python scripts/evaluate_candidate_shards.py --backend local` on this candidate set. They are regression figures for the exact-match baseline.

| Baseline | Correct | Macro-F1 | Insufficient-prediction rate | Document-cluster 95% interval for macro-F1 |
| --- | --- | --- | --- | --- |
| Local exact match | 43 / 108 | 0.2837 | 0.9352 | 0.2215 to 0.3485, 1000 resamples of 36 documents, seed 0 |
| Always abstain | 36 / 108 | 0.1667 | 1.0 | Same document resampling; the point estimate is 0.1667 |

The insufficient-prediction rate is the share of rows the baseline labeled `insufficient`. The local baseline has no separate abstention decision. The interval resamples the 36 documents, not the 108 rows, and it does not estimate accuracy beyond this set.

Seven cases received a validated quote. All 7 emitted quotes matched the extracted text. Evidence coverage is 7/108. Quote validity among those 7 is not a reliability rate for the other 101 rows. Retrieval recall is not defined here because rows do not name a relevant chunk. Token use was 0.

Held-out documents are `d015.md`–`d020.md` and `d029.md`–`d036.md`. The original `d001`–`d020` assignment was not moved when the later documents were added. This split was written by the same author as the labels. It is not a blind external test set, and no independent external evaluation set is available. The split was not used to choose the baseline.

Evidence quotes for `cl-009-2`, `cl-010-2`, `cl-013-2`, `cl-019-2`, and `cl-020-2` were corrected so they cite the statement about the claim, not a different true sentence in the same document. Exact quote matching still does not establish semantic entailment. See [SEMANTIC_REVIEW_CHECKLIST.md](SEMANTIC_REVIEW_CHECKLIST.md).

## Known errors

The local baseline misses paraphrases, negation, unit changes, and comparisons. It predicted `contradicted` zero times. Thirty-eight author labels therefore disagree with the local verdict. The disagreements are listed when the command runs. Do not treat those author labels as settled facts; nobody has reviewed them.

## Leakage precautions

- Author labels and reviewed labels are different columns.
- `gold_count` stays 0 until a reviewer freezes a row.
- Held-out document names are listed in `benchmark/candidates/split.json` before any gold labels exist.
- Dataset paths must stay inside the candidate directory.
- No employer, customer, or licensed research PDF is in this set.

## Name check

On 2026-10-17, `https://pypi.org/pypi/claimledger/json` returned 404. This repository was not published. Other GitHub projects already use the words ClaimLedger. No trademark search was done. Do not publish to PyPI or buy a domain without a separate decision.
