# AI second opinion

These files are AI annotations. They are not independent human review, and they are not gold.

| Batch | Files | Rows | Author-label matches |
| --- | --- | --- | --- |
| First | `semantic_review_18.json`, `semantic_review_18.csv` | 18 | 17 |
| Second | `semantic_review_remaining_90.json`, `semantic_review_remaining_90.csv`, `review_summary.md` | 90 | 90 suffix-derived records, not model predictions |

Together the two batches name all 108 candidate rows once. The only disagreement is `cl-027-2`: the AI annotation says `insufficient`, and the author label `contradicted` was left unchanged. `review_summary.md` describes the second batch only.

**107 of 108 is not an accuracy estimate.** Ninety of those stored verdicts are `label_derived_not_independent`: each one copies the case-id suffix rule, so the 90/90 match is by construction. The other batch has 17 of 18 stored matches and was not a blinded model run. Do not quote either figure as independent AI accuracy. `baseline_metrics_valid` in the 90-row file is false.

The import does not change `expected`, `evidence_quote`, `reviewed_label`, `human_reviewed`, `reviewer`, or `reviewed_at` in `review_queue.csv`. It does not change `gold_set_rows`, `human_reviewed_rows`, or `gold_benchmark_released`. Suggested quote expansions in the first file were not written back into the author `evidence_quote` column. Recorded spans were checked against the current document bytes before each import.

## Label shortcut

Every document has three rows, and the case-id suffix is the author label: `-1` is `supported`, `-2` is `contradicted`, and `-3` is `insufficient`. A model can guess the label from the case id or from row order without reading the document. A formal evaluation has to remove that cue and shuffle the order before any semantic baseline is reported. This import does not renumber the rows.

## Human adjudication, still open

Priority checks from the second batch, with the author label left as it is:

- `cl-016-1`: every 15 minutes is not automatically four arrivals in each operating hour once the 06:00 and 18:00 endpoints are counted.
- `cl-029-1`: "the grant covers equipment" is not automatically the same statement as "the equipment can be charged to the grant."
- Comparison, arithmetic, and missing-evidence rows listed in `human_adjudication_flags` inside `semantic_review_remaining_90.json`, including `cl-006-1`, `cl-006-2`, `cl-006-3`, `cl-009-3`, `cl-011-3`, `cl-014-3`, `cl-015-1`, and `cl-015-2`.

`cl-027-2` remains the only author-label disagreement and still needs a person. Flags in `pre_review_flags.csv` do not set `human_reviewed`.
