# Project overview

ClaimLedger is an auditable, reproducible verification layer for AI-generated research claims. Every factual verdict is linked to exact source evidence, independently auditable, and evaluated against transparent benchmarks.

## Measured

- Version 0.2.0 is a local Python package. It is not on PyPI.
- The default backend makes no network call.
- Quotes are checked against extracted page text before a report is written.
- The public smoke fixture has 6 synthetic, author-labeled rows.

## Not measured

- No human-reviewed gold set.
- No downstream adoption.
- No grant has been received. See [FUNDING_HISTORY.md](FUNDING_HISTORY.md).

The name ClaimLedger replaces EvidenceForge in this repository because Cisco Talos already publishes an unrelated project called EvidenceForge.
