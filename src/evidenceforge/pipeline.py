from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .ingest import load_pages, split_into_units
from .models import ClaimResult, DocumentPage
from .retrieve import retrieve
from .verify import local_verify, openai_verify

DISCLAIMER = (
    "Exact citation spans are mechanically checked against extracted source text. "
    "A validated quote does not guarantee that the semantic verdict is correct."
)


def verify_documents(documents: list[str | Path], claims: list[str], *,
                     backend: str = "local", model: str = "gpt-5-mini", top_k: int = 5,
                     max_claims: int = 30) -> dict[str, Any]:
    if backend not in {"local", "openai"}:
        raise ValueError("backend must be local or openai")
    if not (1 <= len(claims) <= max_claims):
        raise ValueError(f"Supply 1..{max_claims} claims per run; explicit limit prevents surprise spend.")
    if top_k < 1 or top_k > 10:
        raise ValueError("top_k must be between 1 and 10")
    if any(not isinstance(c, str) or not 1 <= len(c.strip()) <= 600 for c in claims):
        raise ValueError("Each claim must contain 1..600 characters.")
    pages = load_pages(documents)
    if sum(len(p.text) for p in pages) > 200_000:
        raise ValueError("Total extracted text exceeds 200,000 character limit.")
    units = split_into_units(pages)
    if not units:
        raise ValueError("Document text did not produce any evidence units.")
    results = []
    for i, claim in enumerate(claims, start=1):
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("Every claim must be a nonempty string.")
        selected = retrieve(claim, units, top_k=top_k)
        if backend == "openai":
            result = openai_verify(f"c{i}", claim, selected, model)
        else:
            # Local mode searches every chunk. top_k only limits text sent to OpenAI.
            result = local_verify(f"c{i}", claim, units)
        results.append(result)
    _require_quote_provenance(pages, results)
    serialized = [asdict(result) for result in results]
    total_usage = {key: sum(r["usage"].get(key, 0) for r in serialized)
                   for key in ("input_tokens", "output_tokens", "total_tokens")}
    counts = {label: sum(r["verdict"] == label for r in serialized)
              for label in ("supported", "contradicted", "insufficient")}
    return {
        "tool": "EvidenceForge",
        "version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "model": model if backend == "openai" else None,
        "documents": list({(p.source, p.sha256): {"source": p.source, "sha256": p.sha256}
                           for p in pages}.values()),
        "page_count": len(pages),
        "evidence_unit_count": len(units),
        "results": serialized,
        "verdict_counts": counts,
        "token_usage": total_usage,
        "disclaimer": DISCLAIMER,
    }


def _require_quote_provenance(pages: list[DocumentPage], results: list[ClaimResult]) -> None:
    """Refuse to emit a report whose quotes are not exact slices of extracted page text."""
    lookup = {(page.source, page.sha256, page.page): page.text for page in pages}
    for result in results:
        if result.verdict != "insufficient" and not result.evidence:
            raise RuntimeError(
                "Refusing to record a supported or contradicted verdict without a validated quote."
            )
        for quote in result.evidence:
            text = lookup.get((quote.source, quote.sha256, quote.page))
            if text is None or text[quote.start:quote.end] != quote.quote:
                raise RuntimeError(
                    "Citation offsets do not match the extracted page text; no report was emitted."
                )
