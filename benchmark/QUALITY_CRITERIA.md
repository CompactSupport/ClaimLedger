# Quality criteria

version: claimledger-quality-criteria-1

This document states the criteria for a future gold release. It does not certify the current candidate rows.

- At least 100 unique document-claim pairs have a human `reviewed_label`.
- Reviewer names are an attestation of who signed the row. They do not prove the reviewer was independent.
- Each frozen row records the reviewer, review time, document SHA-256, and dataset version.
- Supported and contradicted labels use one exact unique evidence span.
- A separate formal approval decision is required before `gold_benchmark_released` is true.
- One hundred rows alone do not publish or certify a gold benchmark.
