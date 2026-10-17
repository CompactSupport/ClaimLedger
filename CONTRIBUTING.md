# Contributing to EvidenceForge

Thanks for helping. Keep changes small enough for one person to review.

## Setup

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The OpenAI extra is optional and is not required to run tests:

```bash
python -m pip install -e ".[openai,dev]"
```

## Checks

```bash
python -m ruff check .
python -m pytest -q
python -m evidenceforge verify --doc examples/aurora.md --claims examples/claims.json --out output/report.json --markdown output/report.md
python -m evidenceforge evaluate --dataset examples/eval.jsonl --out output/eval.json
```

These commands must pass without `OPENAI_API_KEY` and without calling the network.

## Ground rules

1. Fork the repository and use one branch per change.
2. Verdict changes need a positive case, a negative case, and an abstention case.
3. A `supported` or `contradicted` result must include a quote that is an exact slice of the extracted page text. If the quote cannot be checked, abstain or fail the run. Do not invent a verdict when the API times out, refuses, or returns incomplete JSON.
4. Fixtures must be original, synthetic, or clearly permissively licensed. Do not commit confidential documents, licensed analyst reports, or API keys.
5. Describe what changed, which commands you ran, and any limitation you did not fix.

Open an issue before changing the report JSON shape or the verdict meanings.
