# Benchmark card

## What this is

ClaimLedger v0.2.0 can score a 60-row fictional candidate set. The set is an engineering fixture. It is not a gold benchmark and it has not been human reviewed.

| Item | Value |
| --- | --- |
| Documents | 20 original fictional Markdown files |
| Rows | 60, with 20 supported, 20 contradicted, and 20 insufficient author labels |
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

Macro-F1 is `classification_metrics` on all 60 `(expected, actual)` pairs. The mean of the three shard macro-F1 scores is stored separately and is not the reported score. On the local run used to write this card, those two numbers differed.

## Measured local smoke, 2026-10-17

These numbers come from `python scripts/evaluate_candidate_shards.py --backend local` on this candidate set. They are regression figures for the exact-match baseline.

| Baseline | Correct | Macro-F1 | Insufficient-prediction rate | Document-cluster 95% interval for macro-F1 |
| --- | --- | --- | --- | --- |
| Local exact match | 22 / 60 | 0.2315 | 0.9667 | 0.1667 to 0.3111, 1000 resamples of 20 documents, seed 0 |
| Always abstain | 20 / 60 | 0.1667 | 1.0 | 0.1667 to 0.1667, same document resampling |

The insufficient-prediction rate is the share of rows the baseline labeled `insufficient`. The local baseline has no separate abstention decision. The interval resamples the 20 documents, not the 60 rows, and it does not estimate accuracy beyond this set. The always-abstain interval is a single point because every document has the same three author labels.

Two quotes were emitted and both matched the extracted text. The other 58 rows emitted no quote. A 2/2 match is not evidence of broad citation reliability. Retrieval recall is not defined here because rows do not name a relevant chunk. Token use was 0.

Held-out documents `d015.md`–`d020.md` are an internal partition written and labeled by the same author. They are not a blind external test set. They were not used to choose the baseline. On that slice the local baseline labeled every row `insufficient`, so its macro-F1 matched always-abstain. That is a limit of exact string match, not a tuning result.

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
