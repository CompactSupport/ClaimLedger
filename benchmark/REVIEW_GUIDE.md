# Human review guide

The 108 candidate rows are fictional and `synthetic_author_labeled`. None are gold. The case-id suffix currently encodes the author label (`-1` supported, `-2` contradicted, `-3` insufficient). Do not treat that pattern as evidence, and do not use it in a formal evaluation. AI notes in `benchmark/candidates/ai_second_opinion/` are not a review: do not copy `ai_verdict` into `reviewed_label` or set `human_reviewed` from them. Their agreement with the author is not an accuracy estimate. A frozen subset is not a gold benchmark until it has at least 100 valid reviewed cases and a separate quality-criteria record. Reviewer names do not prove independence. Use [SEMANTIC_REVIEW_CHECKLIST.md](SEMANTIC_REVIEW_CHECKLIST.md) before marking a row reviewed. `funding/status.json` keeps `gold_set_rows` at 0 until that bar is met.

## Acceptance policy for a future 100+ gold set

A row becomes gold only when all of the following are true:

1. The source is original or carries a permission that allows redistribution. Do not add proprietary PDFs, employer files, customer data, or licensed research reports.
2. The case ID already exists, or a new ID is assigned once and then never reused or edited.
3. A person other than the label's author records `reviewed_label`. The author column `expected` is not copied forward.
4. `reviewer` and `reviewed_at` are filled. `human_reviewed` is `True`.
5. For `supported` and `contradicted`, the evidence quote is an exact, unique span of the extracted document. The freeze command records that span and rejects missing or ambiguous quotes.
6. Numeric units, dates, negation, and comparisons that a reviewer cannot settle are labeled `insufficient` instead of forced into another class.
7. The document stays inside `benchmark/candidates/`.
8. At least 100 rows meet these rules before anyone calls the set a gold benchmark.
9. Development and held-out documents stay separated as listed in `benchmark/candidates/split.json`. Do not tune prompts, thresholds, or model choice on held-out labels.
10. When two people review the same row, keep both decisions and record agreement. Do not silently keep only the matching one.

## Freeze command

```bash
python scripts/freeze_reviewed_labels.py --queue benchmark/candidates/review_queue.csv --out output/frozen_reviews.json
```

Running it on the current queue reports `reviewed_case_count=0`, `reviewed_subset_available=False`, `eligible_for_final_approval=False`, and `gold_benchmark_released=False`. Repeating a freeze is safe. Changing a frozen case ID, label, or evidence span is rejected.

## Reviewer checklist

- Read the whole document, not only the quoted sentence.
- Compare the claim with the entire document, including negation and units.
- Confirm the quote characters match the file, including punctuation.
- Leave `reviewed_label` blank if you are unsure.
- Do not mark `human_reviewed` until the label is your own decision.
- Do not report the local macro-F1 on these rows as the project's accuracy.
- For a semantic-model run, use one isolated record from [evaluation/PROTOCOL.md](evaluation/PROTOCOL.md). Do not give the model this queue, the case ids, the audit mapping, or the AI notes. A copied workspace is not an operating-system sandbox.
- Calibration responses stay on the reviewer sheets until two validated human submissions exist for the case and someone writes an import approval bound to that adjudication's digest and the dataset version. A separate write approval is required before the queue can change. A reviewer name does not prove identity or independence. Do not sign a sheet with an AI identity. Do not copy the author label or an AI verdict into `reviewed_label`.
