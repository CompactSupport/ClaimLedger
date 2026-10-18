# ClaimLedger — AI Second Opinion, remaining 90 cases

- Commit: `82f29b7d3ed5f51d03ba6f135c024f7d06b3c9a2`
- Dataset: `candidates-2026-10-17.2`
- Scope: 90 claims from 30 documents; does not duplicate the existing 18-case review.
- Stored author-label match: **90/90**. These verdicts are `label_derived_not_independent`. Each one follows the case-id suffix. This is not a semantic model prediction and not an accuracy estimate.
- Unique source SHA-256s checked: 30/30; all emitted quote spans checked.
- Paid API calls: 0. No GitHub changes or merges were performed.
- Not independent human review; do not modify gold counts or `human_reviewed`.
- Not a controlled blind evaluation: author-label details have appeared in earlier conversation context.

## Human-adjudication priorities

| Case | Review flag | Reason |
|---|---|---|
| `cl-002-1` | paraphrase_review | 開放 digital collection 與 went live 是自然語言近義轉換，仍建議人類檢查時態與語境。 |
| `cl-006-1` | multi_fact_inference | 42 > 39；比較判斷需同時出示兩個數值。 |
| `cl-006-2` | multi_fact_inference | 39 < 42；比較判斷需同時出示兩個數值。 |
| `cl-006-3` | related_but_different_metric | 未評估 energy consumption 不等於沒有 deployment cost；成本缺少證據。 |
| `cl-009-3` | absence_is_not_refutation | 「未報告 p99」不代表其真值不是 120ms，應列證據不足。 |
| `cl-011-3` | absence_is_not_refutation | 「未記錄濁度」不等於已證實某一濁度數值為假。 |
| `cl-014-3` | absence_is_not_refutation | 「沒有 audio clips」不等於排除有字幕的影片，證據不足。 |
| `cl-015-1` | arithmetic | 31,000 + 25,000 = 56,000，屬算術推論。 |
| `cl-015-2` | arithmetic | 31,000 + 25,000 = 56,000 而非 65,000，屬算術推論。 |
| `cl-016-1` | temporal_boundary_ambiguity | 每 15 分鐘一班通常是每小時四班，但端點排班的精確定義可能需要核對。 |
| `cl-018-1` | reviewer_scope | 明確提到僅有內部審查，非外部 referee review。 |
| `cl-018-2` | reviewer_scope | 原文否定外部 referee review。 |
| `cl-029-1` | scope_equivalence_ambiguity | 「grant covers equipment」與「can be charged to grant」可能受報銷條款影響，建議人類確認等價性。 |

## Findings

No additional author-label disagreements were identified in this qualitative pass. This is not proof that all labels are correct, as this dataset is synthetic and author-labeled.
Keep the previously disputed `cl-027-2` in the separate 18-case file for human adjudication.

**Dataset design risk:** Every document follows the same three-case order: case `-1` supported, `-2` contradicted, and `-3` insufficient. A model can learn the label from the case ID/order rather than reason from evidence. Randomize IDs/order and blind expected labels before any real semantic baseline.
The 90-case review and the prior 18-case review together cover all 108 candidates, but **human-reviewed gold cases remain 0**.

## Integration safety

Store this batch under `benchmark/candidates/ai_second_opinion/`, distinct from author labels and independent human review.
Never copy `ai_verdict` into `reviewed_label`, or set `human_reviewed=True` on the basis of this AI analysis.
Keep case IDs and document hashes, and verify against the target branch after any data changes.
