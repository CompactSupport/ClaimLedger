# Governance

ClaimLedger is maintained by the GitHub account CompactSupport. That account is the only maintainer with commit access today.

## Decisions

Changes that alter a verdict, a citation offset, or the report JSON need a reviewable commit, tests for the success case and the failure case, and a changelog entry. The maintainer merges those changes on `main`.

A proposal that adds a model provider must keep the local backend as the default and must not require an API key in CI.

## Maintainer policy

- Do not commit credentials, private documents, employer code, or licensed research reports.
- Do not publish to PyPI, rename the repository, or rewrite Git history without an explicit maintainer decision recorded in the issue or pull request.
- Do not present smoke-test metrics as a gold-benchmark result.
- Grant applications and confidential correspondence stay outside this repository, in a private directory that is not pushed.

## Participation

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report security problems through [SECURITY.md](SECURITY.md), not through a public issue.

There is no paid support commitment and no service-level agreement.
