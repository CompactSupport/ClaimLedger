## What changed

## Tests

- [ ] `python -m ruff check .`
- [ ] `python -m pytest -q --cov=claimledger --cov-report=term-missing`
- [ ] Offline `claimledger verify` and `claimledger evaluate` if behavior changed

## Boundaries

- [ ] No API keys, private documents, employer code, or licensed research reports
- [ ] Local mode still runs without credentials
- [ ] Smoke metrics are not described as a gold-benchmark result
