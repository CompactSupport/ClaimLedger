# EvidenceForge

**A local-first prototype that checks claims against documents you already have.**

EvidenceForge records whether a cited quote really occurs in an ingested file, and where. It is a research prototype for auditable claim checks. It is not an automatic fact checker, and a quote that matches the file does not prove the verdict is semantically correct.

```text
your .md / .txt / .pdf
  -> pages, SHA-256, character offsets in the extracted text
  -> paragraph chunks
  -> lexical retrieval (top-k, used by the OpenAI backend)
  -> local exact match, or an optional OpenAI semantic verdict
  -> reject any quote that is not a verbatim slice of that page
  -> JSON + Markdown report
```

## Install

Python 3.11 or newer. From the repository root:

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

`python` works in place of `py -3.11` when that command already points at Python 3.11+. PowerShell does not continue a command with a trailing backslash. Put each command on one line, or use a backtick.

Packaging is in `pyproject.toml`. The `dev` extra installs pytest and ruff. The `openai` extra is optional and is not installed by CI.

## Offline demo

No network access and no API key:

```bash
python -m evidenceforge verify --doc examples/aurora.md --claims examples/claims.json --out output/report.json --markdown output/report.md
python -m evidenceforge evaluate --dataset examples/eval.jsonl --out output/eval.json
python -m pytest -q
```

`examples/aurora.md` is a short synthetic note. The local verifier marks a claim `supported` only when the claim text occurs as a substring. On this demo that is 2 of 4 claims. The other two are `insufficient`, including "The study used synthetic samples.", because the note says the study did **not** use them. Local mode does not understand negation.

`examples/eval.jsonl` is a 6-row smoke test, not a benchmark. The local backend gets **4 of 6** correct. The two misses are the rows labeled `contradicted`: local mode abstains instead of detecting the contradiction. Do not quote 4/6 as a production accuracy number.

A rendered Markdown report is in [docs/sample-report.md](docs/sample-report.md). One offline JSON report is in [docs/sample-report.json](docs/sample-report.json). `created_utc` in a fresh run will differ.

## Optional OpenAI mode

This sends the **claim and the retrieved excerpts** to the OpenAI Responses API. It is off unless you select it.

```bash
python -m pip install -e ".[openai,dev]"
```

```bash
export OPENAI_API_KEY="YOUR_KEY"
python -m evidenceforge verify --doc examples/aurora.md --claims examples/claims.json --backend openai --model gpt-5-mini --out output/report-openai.json --markdown output/report-openai.md
```

PowerShell:

```powershell
$env:OPENAI_API_KEY = "YOUR_KEY"
python -m evidenceforge verify --doc examples/aurora.md --claims examples/claims.json --backend openai --model gpt-5-mini --out output/report-openai.json --markdown output/report-openai.md
```

`gpt-5-mini` is only the default string. Pass a model your account can call and that supports [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). The request uses `responses.create` with `text.format.type=json_schema`, `strict=true`, and `store=false`. Tests mock this call. CI does not install the OpenAI extra and does not set `OPENAI_API_KEY`.

If the request times out, cannot connect, is refused, or the response is incomplete or not valid JSON, the command exits with status 2 and **does not write a verdict**. A `supported` or `contradicted` answer that has no verbatim quote is saved as `insufficient`, with an audit warning.

## Claims file

```json
{"claims": ["Project Aurora evaluated 120 samples in March 2026.", "The study used synthetic samples."]}
```

A bare JSON array of strings is also accepted. Each run allows 1 to 30 claims, and each claim must be 1 to 600 characters.

## Report shape

The JSON report includes the tool version, UTC timestamp, document SHA-256, page count, per-claim verdict, quote, page number, and half-open character span `[start, end)` into the **extracted** page text. For every quote, `page_text[start:end] == quote`. PDF spans are not visual coordinates. Scanned pages without a text layer are rejected (there is no OCR).

```json
{
  "verdict": "supported",
  "evidence": [
    {
      "source": "aurora.md",
      "page": 1,
      "start": 51,
      "end": 102,
      "quote": "Project Aurora evaluated 120 samples in March 2026."
    }
  ]
}
```

The OpenAI response itself must match [docs/verification.schema.json](docs/verification.schema.json):

```json
{
  "verdict": "supported | contradicted | insufficient",
  "reason": "short explanation",
  "evidence": [{"unit_id": "id from the prompt", "quote": "verbatim substring"}]
}
```

## What the checks do and do not mean

- **Provenance check:** the quote is copied from a known chunk, and the reported span reproduces it. This can pass while the verdict is still the wrong label for the claim.
- **Local verdict:** substring search over every chunk. "120 samples" is `supported` because those characters occur in the demo, even though that fragment is not the whole sentence. Paraphrases, negation, and a sentence split across two chunks are `insufficient`.
- **OpenAI verdict:** a model judgment over the top-k retrieved chunks. Retrieval can miss a relevant passage. The model can also choose the wrong label for a passage it did see. The quote check does not repair that.
- **Neither mode** decides whether the supplied document is true, current, or complete.

## Retrieval

Retrieval is an inspectable overlap score, not an embedding index:

`score = shared_tokens / (claim_tokens + 0.05 * chunk_tokens)`, plus 1 when the claim is an exact casefolded substring of the chunk.

Tokens are Latin words and digits, plus individual CJK, kana, and Hangul characters. There is no stemming. These misses are expected:

- a paraphrase with no shared tokens (`revenue doubled` vs `sales by 100 percent`)
- different word forms (`remain` vs `remained`) and different number formats (`1200` vs `1,200`)
- a relevant chunk that shares only common words and falls outside `--top-k`
- a sentence cut in half by the chunker (the default chunk size is 1,400 characters)

`--top-k` (1 to 10, default 5) limits what the OpenAI backend can read. The local backend still scans every chunk, so an exact quote is not dropped just because it ranked below k. Tests cover these cases; they are not a retrieval benchmark.

## Limits and privacy

| Limit | Default |
| --- | --- |
| File size | 8 MB |
| PDF pages | 30 |
| Extracted text per run | 200,000 characters |
| Claims or eval rows | 30 |
| Claim length | 600 characters |
| Quote accepted from a model | 1,400 characters |

- Default `local` mode makes no API call.
- `output/` is gitignored. Do not commit private documents, licensed reports, or generated reports about them.
- Demo files in `examples/` are synthetic.
- Two files with the same filename are labeled with parent folders (`left/notes.md`). The same path cannot be ingested twice.
- Blank PDF pages are skipped. Page numbers stay the original PDF page numbers.
- OpenAI mode can cost money. This tool does not estimate dollars, because prices change. Check the provider's current rates. `store=false` asks the API not to store the response; read the provider terms anyway.

## Tests

GitHub Actions runs, on Python 3.11 and 3.12, without credentials:

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q
python -m evidenceforge verify --doc examples/aurora.md --claims examples/claims.json --out output/report.json --markdown output/report.md
python -m evidenceforge evaluate --dataset examples/eval.jsonl --out output/eval.json
```

## Roadmap

1. **v0.1 (this release):** exact quote provenance, a conservative local baseline, an optional OpenAI semantic verifier, and offline smoke tests.
2. **v0.2:** a larger permissively licensed set with adversarial claims, plus reported macro-F1 and citation-validity numbers. Those numbers are not measured here.
3. **Later, only if v0.1 stays small:** numeric and date checks that abstain on ambiguous units, optional cost logging from rates you supply, and a thin local UI.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
