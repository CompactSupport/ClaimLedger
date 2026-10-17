# Cursor Agent Prompt — EvidenceForge v0.1 review and GitHub polish

You are a senior open-source Python engineer and a rigorous LLM evaluation researcher.
You are working in this EvidenceForge repository (initial scaffold already exists).

## Objective
Turn it into a credible, runnable, minimal public GitHub release that demonstrates:

`document -> provenance-preserving chunks -> claim retrieval -> source-grounded verdict -> deterministic quote audit -> JSON + Markdown report`

Do NOT replace it with an ambitious framework, UI, vector database, LangChain, crew of agents, custom training, or hosted service. Preserve a local-only default and an explicit optional OpenAI mode.

## P0 tasks — must finish before publishing
1. Read `README.md`, source, tests and examples. Run `python -m pip install -e '.[openai,dev]'`, `python -m pytest -q`, a local CLI sample and `evaluate` sample. Fix any real failures.
2. Audit `ingest.py` document/page provenance and text offset invariants. Every quote `[start:end]` must exactly equal the quoted substring in its extracted PDF page / text document. Add tests for multi-page PDF, blank chunks, unicode/CJK, duplicate source names, and long paragraphs.
3. Audit `verify.py` for fail-closed citation validation. Invalid unit IDs/quotes must never produce supported/contradicted results without a valid source quote. Explicitly document that exact provenance does not guarantee semantic correctness.
4. Ensure OpenAI `responses.create` Structured Outputs follows the **current official SDK documentation** (keep model configurable, `store=False`, and no live API calls in CI). Handle refusals, timeouts, and incomplete responses without inventing verdicts. Mock API in tests.
5. Review retrieval for false negatives. Keep a simple transparent baseline, add top-K recall tests, and make it clear that semantic errors and missed chunks are expected limitations.
6. Make docs newbie-friendly, include Windows instructions, example JSON schema and output sample, Python packaging, MIT license, CONTRIBUTING.md, SECURITY.md, GitHub Actions CI, no committed tokens or licensed reports.
7. Run full tests, CLI smoke test, and basic style checks. Report actual test results, not invented metrics. Commit with a clear message. If GitHub push is not configured, give exact `gh repo create`/`git push` commands without claiming they ran.

## P1 tasks — only after P0 is green
- A minimal `evidenceforge extract` command to propose atomic claims from documents, preserving quote-based provenance and requiring human approval before verification.
- Add an honest `benchmark/` dataset of 50+ **original or permissively licensed** examples, with supported/contradicted/insufficient and adversarial negatives, plus a report of macro-F1 and citation validity rate.
- Add deterministic checks for percentages, numerical comparisons and date contradictions, with explicit abstention on ambiguous units.
- Add optional API usage logging: input/output tokens and estimated dollar cost using rates provided by the user, never silently assume current pricing.
- Build a thin local web UI only if the CLI and correctness tests are stable.

## Product quality bar
- One-command reproducible offline demo and tests.
- OpenAI semantic mode optional; API secrets never committed.
- Clean deterministic provenance even if the model hallucinates a quote.
- Fail closed on semantic verification API errors rather than fabricate success.
- README is candid about what is tested versus what is planned.
- Scope is small enough to be maintained by one open-source developer.

Start by testing the current project. Implement P0 before proposing larger refactors.
