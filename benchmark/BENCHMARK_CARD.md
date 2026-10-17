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

| Baseline | Correct | Macro-F1 | Abstention | Bootstrap 95% interval for macro-F1 |
| --- | --- | --- | --- | --- |
| Local exact match | 22 / 60 | 0.2315 | 0.9667 | 0.1472 to 0.3231, 1000 resamples, seed 0 |
| Always abstain | 20 / 60 | 0.1667 | 1.0 | 0.1187 to 0.2069, same resampling rule |

The interval only resamples these 60 rows. It is not an estimate for other documents. Two quotes were emitted and both matched the extracted text, so citation validity on emitted quotes was 1.0. Retrieval recall is not defined here because rows do not name a relevant chunk. Token use was 0.

Held-out documents `d015.md`–`d020.md` were scored separately and were not used to choose the baseline. On that slice the local baseline abstained on every row, so its macro-F1 matched always-abstain. That is a known limit of exact string match, not a tuning result.

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
