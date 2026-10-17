# AI second opinion

`semantic_review_18.json` and `semantic_review_18.csv` are AI annotations for 18 candidate rows. They are not independent human review and they are not gold.

The import does not change `expected`, `reviewed_label`, `human_reviewed`, `reviewer`, or `reviewed_at` in `review_queue.csv`. Agreement with the author label is 17 of 18 annotations. `cl-027-2` disagrees. That disagreement is only a flag for a person to adjudicate.

Suggested quote expansions in the AI file were not written back into the author `evidence_quote` column. The recorded spans were checked against the current document bytes before this import.
