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
- Every document currently has three rows, and the case-id suffix is the author label: `-1` supported, `-2` contradicted, `-3` insufficient. A model can guess the label from the id or from row order. A formal evaluation has to remove that cue and shuffle the order. The current local scores are not that evaluation.
- AI second-opinion notes cover all 108 rows and match the author label on 107. That match count is not accuracy. The notes are in `benchmark/candidates/ai_second_opinion/`, and they do not fill `human_reviewed` or release a gold set. Human-reviewed rows remain 0.

## Leakage risk

The canonical queue still uses one supported, one contradicted, and one insufficient row per document, in that order. The case-id suffix is the author label. Those files stay unchanged so earlier runs remain auditable.

`benchmark/evaluation/` is a separate export, protocol `claimledger.evaluation_export.v1`, seed `20261017`. It gives each case an opaque evaluation id, shuffles all 108 cases in one list, and writes model-visible inputs that contain only the claim and the source passage. The passage omits the scenario heading because that heading repeats the document number. The id-to-case mapping stays in `benchmark/evaluation/audit/`. That directory is committed in this public repository. It is publicly readable and not access-controlled. It is omitted from the model-visible file list, which is a packaging split, not a confidentiality control. Copying the model view outside the checkout is a file copy, not an operating-system sandbox.

Residual risks remain. The same passage still accompanies every claim about that document, so a reader can group those claims. Someone who also has this repository can join the passage text back to the author label. No blinded model has been scored on the export. The export is not an independent external test set. Human-reviewed rows remain 0. The 30-case calibration packet hides author labels and AI notes. Its response sheets are empty, so there is no paired agreement and no Cohen's kappa. AI identities are not accepted as reviewers. Adjudicated labels are not copied into the canonical queue unless they are tied to two validated human submissions, the approval digest matches that artifact and the dataset version, and a separate write approval is present. A reviewer name does not prove identity or independence. That approval does not release gold.

The semantic-pilot harness sends one isolated record at a time and strips credential environment variables. It is not an operating-system sandbox. Real Codex inference is disabled until subscription authentication and billing are verified, and API-key billing is not a fallback. No real model call has been made.

One conversational Human–AI session on the 30-case packet is recorded in `benchmark/evaluation/human_ai_calibration/`. Its metric is `human_ai_agreement`. The original comparison and the later consensus after feedback are separate. A second conversational label set is stored beside them. Neither is accuracy, a completed two-human review, or a gold result. Reviewer B's formal sheet is still empty.

## Name check

On 2026-10-17, `https://pypi.org/pypi/claimledger/json` returned 404. This repository was not published. Other GitHub projects already use the words ClaimLedger. No trademark search was done. Do not publish to PyPI or buy a domain without a separate decision.
