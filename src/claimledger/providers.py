"""Provider-agnostic verifier interface.

Local and OpenAI are the only implementations. Another provider can be added by
implementing ``ClaimVerifier`` and teaching ``verifier_for`` about its name.
ClaimLedger does not require a hosted service.
"""

from __future__ import annotations

from typing import Protocol

from .models import ClaimResult, EvidenceUnit
from .verify import local_verify, openai_verify


class ClaimVerifier(Protocol):
    def verify(self, claim_id: str, claim: str, units: list[EvidenceUnit]) -> ClaimResult:
        """Return one verdict. Do not invent a verdict when the provider fails."""


class LocalVerifier:
    """Exact-substring baseline. It does not call a model."""

    name = "local"

    def verify(self, claim_id: str, claim: str, units: list[EvidenceUnit]) -> ClaimResult:
        return local_verify(claim_id, claim, units)


class OpenAIVerifier:
    """Optional OpenAI Responses backend. The model name stays configurable."""

    name = "openai"

    def __init__(self, model: str) -> None:
        self.model = model

    def verify(self, claim_id: str, claim: str, units: list[EvidenceUnit]) -> ClaimResult:
        return openai_verify(claim_id, claim, units, model=self.model)


def verifier_for(backend: str, model: str = "gpt-5-mini") -> ClaimVerifier:
    """Return a verifier. Unknown names fail closed instead of selecting a default provider."""
    if backend == "local":
        return LocalVerifier()
    if backend == "openai":
        return OpenAIVerifier(model)
    raise ValueError("backend must be local or openai")
