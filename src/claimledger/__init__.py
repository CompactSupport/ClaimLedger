"""ClaimLedger: auditable verification for AI-generated research claims."""

__version__ = "0.2.0"

from .pipeline import verify_documents
from .providers import verifier_for

__all__ = ["verifier_for", "verify_documents", "__version__"]
