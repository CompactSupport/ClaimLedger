# Session provenance

This directory records one Human–AI calibration session on the 30-case packet. It is not a two-human independent review, not a gold benchmark, and not a controlled blind model evaluation.

## Human responses

The 30 labels in `human_original_responses.json` are a user-provided conversational judgment, given in `calibration_packet.jsonl` order before the comparative result was shown. The exact original response timestamp is not available. A verified real-world identity is not available. Neither value is invented.

The labels are not marked as independently verified human reviews. They do not fill reviewer B's sheet. They do not meet the formal review-sheet requirements: there is no recorded timezone timestamp and no evidence-span validation. If the project maintainer is also the dataset author, this person is not an independent external reviewer.

`revision.json` records a later change to question 13 after the person saw the AI comparison. The original label stays in the original file.

`second_reviewer_responses.json` records 30 labels supplied later and described by the user as another independent reviewer. No name, timestamp, or evidence span was available, so none is invented. Those labels are not on reviewer B's formal sheet and are not a completed two-human review.

## AI responses

AI labels are read from the committed files:

- `benchmark/candidates/ai_second_opinion/semantic_review_18.json`
- `benchmark/candidates/ai_second_opinion/semantic_review_remaining_90.json`

Those notes predate this comparison. They were not generated under a rigorously independent blind protocol. This session does not rerun the AI. No encrypted AI-answer artifact is used, because no original ciphertext and decryption key were independently available for a hash check.

`benchmark/evaluation/audit/calibration_mapping.json` joins each `packet_id` to a canonical case id. The join is not done by case-id suffix.

## What this session does not change

`review_queue.csv`, author `expected` labels, `reviewed_label`, `human_reviewed`, the empty reviewer B sheet, `gold_set_rows`, and `gold_benchmark_released` stay as they are. No formal calibration import approval is created.
