# Changelog

All notable changes to ClaimLedger are documented here. The project uses semantic versions. It is still 0.x, so minor versions may change the import name or the report JSON.

## Unreleased

- Reclassify the 90 stored annotations as label-derived from the case-id suffix. They are not semantic model predictions, and the 90/90 or 107/108 match is not independent accuracy.
- Add a reproducible 10-case internal pilot subset and a real-inference gate. No genuine model process was started, so no model score is reported.
- Import the Steven and David calibration labels into the review queue after an explicit write approval. Thirty rows are human-reviewed, author labels stay in `expected`, and the set is not a released gold benchmark.
- Record a second conversational 30-label set beside the original Human–AI session. It does not replace the original answers or become a formal human review.
- Record one 30-case Human–AI calibration session. Original agreement stays separate from the post-feedback consensus, and neither is accuracy or a gold label.
- Refuse a human-reviewed queue row unless the adjudication is tied to two validated human submissions, the approval digest, and the dataset version. A reviewer name does not prove identity. Queue writes stay off without a separate write approval.
- Make `scripts/run_semantic_pilot.py --check` run the offline mock gate and exit nonzero on failure. Mock output is not a semantic-model score, and real Codex execution stays disabled.
- Validate the empty 30-case calibration sheets, keep disagreements for adjudication, and require an explicit approval before any adjudicated label can be planned for the canonical queue.
- Add a one-record semantic-pilot harness with mocked tests. Real Codex inference stays disabled, and API-key billing is not a fallback.
- State that the committed audit mapping is publicly readable and that copying the model view outside the repository is not an operating-system sandbox.
- Add a seeded label-blind export for future semantic evaluations. Canonical case IDs and author labels stay in the candidate set. Model-visible inputs omit them, and the 30-case human packet has no recorded decisions. The export is not an external test set.
- Import the remaining 90 AI second-opinion annotations beside the first 18. Combined author-label agreement is 107 of 108 and is not an accuracy estimate. The case-id suffix still encodes the author label.
- Import 18 AI second-opinion annotations beside the candidate queue. They do not change author labels or human-review fields.
- Fix the freeze CLI so it reports the four release-state fields instead of the removed `gold_benchmark_ready` key.
- Require the evaluated shards to match the manifest and review queue exactly, and revalidate frozen rows against current document bytes.
- Add an unexecuted OpenAI pilot planner with an explicit USD preflight. A request cap is not a spending ceiling.
- Stop duplicate document-claim pairs from inflating the reviewed count.
- Separate a reviewed subset, eligibility for final approval, and a formally approved gold release. One hundred rows do not certify a benchmark, and an independence attestation is not a verification.
- Add 48 fictional candidate rows in 16 new documents, a pre-review flag list, and an empty adjudication log.
- Report evidence coverage separately from quote validity.
- Correct five candidate evidence quotes that cited a true but irrelevant sentence: `cl-009-2`, `cl-010-2`, `cl-013-2`, `cl-019-2`, and `cl-020-2`.
- Keep author labels separate from reviewed labels. Reviewer metadata is not treated as independence.
- Rename the insufficient-prediction share so it is not called system abstention, and add a document-level cluster bootstrap.
- Add 20 fictional documents and 60 author-labeled candidate claims. They are not gold and have not been human reviewed.
- Pool candidate macro-F1 from every case pair, and keep an always-abstain baseline beside the local exact-match baseline.
- Add a review freeze that records a human `reviewed_label` and an exact evidence span without copying the author label. `gold_count` stays 0 until that happens.
- Record the dev and held-out document split before any gold labels exist.

## 0.2.0

- Renamed the project and Python package from EvidenceForge to ClaimLedger. The old name collides with an unrelated Cisco Talos project. The command is now `claimledger`.
- Recorded deterministic provenance as the implemented prototype, and stated that multi-model verification, a human-reviewed gold set, and additional providers are not implemented.
- Added smoke-evaluation metrics: macro-F1, per-class precision and recall, abstention rate, citation validity, latency, and token use. Retrieval recall is reported as null when the fixture does not name a relevant passage.
- Added an abstain baseline beside the local exact-match baseline. Neither baseline calls an API.
- Added a small `ClaimVerifier` interface for local and OpenAI backends.
- Removed the deprecated MIT license classifier. The SPDX field `license = "MIT"` remains.
- Stopped publishing the internal Cursor brief. A local copy stays outside Git.
- Added coverage, Gitleaks, pip-audit, Dependabot, governance documents, and a manual PyPI Trusted Publishing workflow. No package has been uploaded.

## 0.1.0

- Initial public prototype: local exact quotes, optional OpenAI structured outputs, and offline smoke tests.
