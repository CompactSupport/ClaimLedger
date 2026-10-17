# Changelog

All notable changes to ClaimLedger are documented here. The project uses semantic versions. It is still 0.x, so minor versions may change the import name or the report JSON.

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
