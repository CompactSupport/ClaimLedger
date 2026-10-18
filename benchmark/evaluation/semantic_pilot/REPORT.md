# Semantic pilot

This report does not contain a measured semantic-model score. No genuine model process was started, and mock output is not substituted.

## Label-derived annotations

`semantic_review_remaining_90.json` is `label_derived_not_independent`. Every stored verdict matches the canonical case-id suffix. The historical results array was not regenerated. The 90/90 match and the combined 107/108 match are not independent AI accuracy.

## Internal 10-case subset

- Selection seed: `20261018`.
- Case-set SHA-256: `d221389a0ec88a420e1cdd5d966bb1ae2e8cf947db4a95bbe6e2bcfc8235a297`.
- Dataset version: `candidates-2026-10-17.2`.
- Dataset git commit: `24c8c8e5824c98bf0f7cc68c46fcdbbe5164e73f`.
- Opaque evaluation ids are in `subset_public.json`.
- Adjudicated labels for an internal comparison are in `subset_audit.json`.
- Cases that share a document stay together.
- This subset is not an independent external test.

## Inference blocker

The Codex CLI, the Gemini CLI, and the Antigravity CLI (agy) are not on PATH. Subscription authentication and billing were not verified, and no model process was started. API-key billing is not used as a fallback.

No subscription CLI is on PATH, so the original 10-case subset was not executed. Genuine predictions remain 0.

A verified subscription and one record outside the repository can start Codex, Gemini, or Antigravity. `real_model_execution` is true only for that model subprocess. An in-process mock, and any other subprocess, stays false. A directory outside the repository and a stripped environment are not an operating-system sandbox. Any later run that can read this repository, including `subset_audit.json`, is not independently blinded.

## Measured predictions

- Genuine predictions: 0.
- Paid model calls: 0.
- Accuracy, macro-F1, confusion matrix, quote validity, and latency are not reported because there are no genuine predictions.
- `gold_benchmark_released` remains false.
