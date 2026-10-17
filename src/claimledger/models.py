from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Verdict = Literal["supported", "contradicted", "insufficient"]


@dataclass(frozen=True)
class DocumentPage:
    source: str
    sha256: str
    page: int
    text: str


@dataclass(frozen=True)
class EvidenceUnit:
    id: str
    source: str
    sha256: str
    page: int
    start: int  # zero-based offset in extracted page text
    end: int  # exclusive offset in extracted page text
    text: str


@dataclass(frozen=True)
class EvidenceQuote:
    unit_id: str
    source: str
    sha256: str
    page: int
    start: int
    end: int
    quote: str


@dataclass
class ClaimResult:
    id: str
    claim: str
    verdict: Verdict
    reason: str
    evidence: list[EvidenceQuote] = field(default_factory=list)
    backend: str = "local"
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    audit_warnings: list[str] = field(default_factory=list)
