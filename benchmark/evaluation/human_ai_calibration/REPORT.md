# Human–AI calibration session, 30 cases

This is a Human–AI calibration study. It is not a two-human independent review, not a gold benchmark, and not a controlled blind model evaluation.

## Objective and method

One person recorded a label for each row of `calibration_packet.jsonl` before seeing a comparison with the committed AI second opinions. The join uses that file's order and `packet_id`. It does not use the canonical case-id suffix. The AI labels are read from the two committed annotation files. They were not rerun for this report.

The response origin is a user-provided conversational judgment. The exact original response timestamp and a verified real-world identity are not available, so neither is recorded. The answers are not marked as independently verified human reviews. If the project maintainer is also the dataset author, this person is not an independent external reviewer.

## Dataset

- Dataset version: `candidates-2026-10-17.2`.
- Mapping: `benchmark/evaluation/audit/calibration_mapping.json` (`claimledger.evaluation_export.v1`, seed 20261018, SHA-256 `7b8cc7775caee9084b7356f18e68656d177051d409586907642998c189fd3d6c`).
- AI sources, with the commit recorded inside each file:
  - `benchmark/candidates/ai_second_opinion/semantic_review_18.json` commit `4729842129139cb8ddecb9cdbb05be0ec7754e86`, SHA-256 `2ef71de15078667e34a6f453996a094ffaafd257a1efa9e1f2f7dcb13aa748ac`, paid API calls 0.
  - `benchmark/candidates/ai_second_opinion/semantic_review_remaining_90.json` commit `82f29b7d3ed5f51d03ba6f135c024f7d06b3c9a2`, SHA-256 `ced3f1b34d08749be63e0c0921d19f82436a8bbeca60b27408c92fe505ecc363`, paid API calls 0.

The committed AI annotations predate this comparison. They were not produced under a rigorously independent blind protocol. No encrypted AI-answer artifact was used.

## Original human responses

The 30 original labels, in packet order, are stored in `human_original_responses.json`. That file is the immutable record. The table below is derived from it.

| # | Packet id | Canonical id | Original human label | AI second opinion |
| --- | --- | --- | --- | --- |
| 1 | `hr-bc24e166ae45` | `cl-003-3` | insufficient | insufficient |
| 2 | `hr-ae7f18afeab0` | `cl-005-2` | contradicted | contradicted |
| 3 | `hr-afdae7d2b1a0` | `cl-016-1` | supported | supported |
| 4 | `hr-00167c34dea2` | `cl-031-2` | contradicted | contradicted |
| 5 | `hr-13c8d23f529b` | `cl-007-3` | insufficient | insufficient |
| 6 | `hr-1a328e6dfd71` | `cl-001-2` | contradicted | contradicted |
| 7 | `hr-2bc4b0608fcf` | `cl-009-3` | insufficient | insufficient |
| 8 | `hr-1735c91b192c` | `cl-024-1` | supported | supported |
| 9 | `hr-953ea0228df8` | `cl-003-1` | supported | supported |
| 10 | `hr-0af0ec362abf` | `cl-005-3` | insufficient | insufficient |
| 11 | `hr-d299916ec3ea` | `cl-002-2` | contradicted | contradicted |
| 12 | `hr-5653083efb59` | `cl-002-1` | supported | supported |
| 13 | `hr-f5d18c35e468` | `cl-027-2` | contradicted | insufficient |
| 14 | `hr-1d7bb677be97` | `cl-004-2` | contradicted | contradicted |
| 15 | `hr-4b5fe6fc1c13` | `cl-018-2` | contradicted | contradicted |
| 16 | `hr-908818e96c55` | `cl-011-3` | insufficient | insufficient |
| 17 | `hr-14400ed3160d` | `cl-003-2` | contradicted | contradicted |
| 18 | `hr-c5fab55caecb` | `cl-015-2` | contradicted | contradicted |
| 19 | `hr-849c75addd99` | `cl-006-1` | supported | supported |
| 20 | `hr-e78a3a74eb91` | `cl-015-1` | supported | supported |
| 21 | `hr-bfb1fcc3a242` | `cl-006-3` | insufficient | insufficient |
| 22 | `hr-7db7793a9253` | `cl-001-1` | supported | supported |
| 23 | `hr-d7b5833325e5` | `cl-032-1` | supported | supported |
| 24 | `hr-f541de60a8a9` | `cl-029-1` | supported | supported |
| 25 | `hr-84e66e402ffb` | `cl-006-2` | contradicted | contradicted |
| 26 | `hr-07aa32960410` | `cl-001-3` | insufficient | insufficient |
| 27 | `hr-b796bfb042f2` | `cl-018-1` | supported | supported |
| 28 | `hr-7f20f28a0759` | `cl-014-3` | insufficient | insufficient |
| 29 | `hr-ad629275e82b` | `cl-002-3` | insufficient | insufficient |
| 30 | `hr-3324d375bc4a` | `cl-004-3` | insufficient | insufficient |

## Original agreement

Metric name: `human_ai_agreement`. This is not accuracy and not independent human inter-annotator agreement.

- Cases: 30.
- Agreements: 29.
- Disagreements: 1.
- Observed agreement: 29/30.
- Cohen's kappa: 0.95.

Confusion matrix, human labels by row and AI labels by column:

| Human \ AI | supported | contradicted | insufficient |
| --- | --- | --- | --- |
| supported | 10 | 0 | 0 |
| contradicted | 0 | 9 | 1 |
| insufficient | 0 | 0 | 10 |

Per-class agreement counts (both sides chose that label): supported 10, contradicted 9, insufficient 10.

## Question 13

Position 13, packet `hr-f5d18c35e468`, canonical `cl-027-2`.

Claim: The recipe includes nuts.

Source passage: The recipe uses oats and honey. It does not mention nuts.

Original human label: `contradicted`.
Committed AI second opinion: `insufficient`.
Canonical author `expected` at the time of this report: `contradicted`. That author label was not changed.

The AI note in `semantic_review_18.json` says that not mentioning nuts is not an explicit exclusion. The original human judgment treated the omission as a contradiction.

## Correction after feedback

After the comparison, the same person acknowledged a reasoning error and revised question 13 from `contradicted` to `insufficient`. The stated reason is that the source says the recipe uses oats and honey and does not mention nuts, and that not mentioning nuts does not establish their absence.

- Event: `human_error_corrected_after_ai_feedback`.
- `original_human_label`: `contradicted`.
- `ai_second_opinion`: `insufficient`.
- `revised_human_label`: `insufficient`.
- `revision_trigger`: `AI_feedback_and_user_reconsideration`.
- `revision_reason`: `absence_of_evidence_is_not_evidence_of_absence`.
- `revision_confirmed_by_user`: true.

The original response file is unchanged. There is no independent adjudicator. No evidence quote or timestamp was invented for a formal review sheet.

## Agreement after feedback

These figures are separate from the original result. They do not replace 29/30.

- Agreements: 30/30.
- Remaining disagreements: 0.
- Cohen's kappa: 1.00.

30/30 is consensus after feedback. It is not independent accuracy, and it is not evidence that the AI judgments are all correct.

## Second reviewer

A later set of 30 labels was supplied as another reviewer's answers. The user described that person as independent. The formal sheets name Steven and David. Those names, and the adjudicator account id, do not prove a real-world identity. The completed sheets and the queue import are in `benchmark/evaluation/formal_review/`. The label-blind template for reviewer B stays empty. The import does not release gold. The original 29/30 comparison is unchanged.

- Agreements with the original human labels: 29/30.
- Cohen's kappa against the original human labels: 0.95.
- Agreements with the AI second opinions: 30/30.
- Agreements with the first person's revised labels: 30/30.

Positions that differ from the original human label:

- 13. `hr-f5d18c35e468` / `cl-027-2`: original human `contradicted`, second reviewer `insufficient`, AI `insufficient`.

Confusion matrix, second reviewer by row and original human label by column:

| Second reviewer \ Original human | supported | contradicted | insufficient |
| --- | --- | --- | --- |
| supported | 10 | 0 | 0 |
| contradicted | 0 | 9 | 0 |
| insufficient | 0 | 1 | 10 |

These comparisons are `human_ai_agreement` or conversational label agreement. They are not accuracy.

## Threats to validity

- The candidate set is synthetic and author-labeled.
- The AI notes were not produced under a rigorously independent blind protocol. Earlier discussion had already exposed dataset information.
- The person who labeled these 30 rows may overlap with the dataset author or project maintainer. Identity was not verified.
- The revised label depends on seeing the AI comparison.
- The 30 rows are a small, intentionally class-balanced calibration subset, not a random sample of a broader population.
- Reviewer B's formal sheet is still empty. The additional 30 labels are a conversational record. Identity, independence, and evidence spans were not verified.

## Next steps

Keep this session out of the gold queue. The additional conversational labels still need a timestamped sheet and evidence spans before they can enter the review queue. Do not import these conversational labels through the calibration approval gate.
