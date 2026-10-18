# Semantic pilot

This report records one ChatGPT-subscription Codex run on the internal 10-case subset. Mock output is not included in that score.

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

shutil.which does not find codex, gemini, or agy on PATH. The recorded run did not use that PATH lookup. It invoked the Microsoft Store Codex executable directly. That executable is not on PATH.

A verified subscription and one record outside the repository can start Codex, Gemini, or Antigravity. `real_model_execution` is true only for that model subprocess. An in-process mock, and any other subprocess, stays false. A directory outside the repository and a stripped environment are not an operating-system sandbox. Any later run that can read this repository, including `subset_audit.json`, is not independently blinded.

## Subscription run

On 2026-10-18 the Microsoft Store Codex CLI 0.163.0-alpha.10.2, logged in with ChatGPT, answered the frozen 10-case subset. Each process was started with an explicit read-only sandbox and a workspace outside the repository that contained only that case. The adjudication file was not in the workspace. The run is not independently blinded, because that sandbox was not shown to block every other path on the machine. Ten of ten verdicts matched the adjudicated labels, and ten of ten quotes were valid. This is an internal comparison, not an external test and not a released gold benchmark.

- CLI: `codex-cli 0.163.0-alpha.10.2` via the Microsoft Store package, not PATH.
- Login: `Logged in using ChatGPT`.
- Model: `gpt-6.1-sol`. Reasoning effort: `low`.
- Sandbox flag: `read-only`. Config default was not used.
- Cases: 10. Correct against adjudicated labels: 10.
- Macro-F1: 1.0. Insufficient-prediction rate: 0.3.
- Quote validity: 10 of 10.
- `independent_external_test` is false. `independently_blinded` is false. `gold_benchmark_released` remains false.
- Paid API-key calls: 0. The run used the ChatGPT subscription quota.

## Measured predictions

- Genuine predictions: 10.
- Paid model calls: 0.
- The score is an internal comparison with the adjudicated labels. It is not an external-test accuracy.
- `gold_benchmark_released` remains false.
