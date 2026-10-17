import pytest

from claimledger.metrics import classification_metrics
from claimledger.providers import LocalVerifier, verifier_for


def test_macro_f1_keeps_a_missed_class_in_the_average():
    pairs = (
        [("supported", "supported")] * 3
        + [("contradicted", "insufficient")] * 2
        + [("insufficient", "insufficient")]
    )
    metrics = classification_metrics(pairs)
    assert metrics["per_class"]["supported"]["f1"] == 1.0
    assert metrics["per_class"]["contradicted"]["precision"] is None
    assert metrics["per_class"]["contradicted"]["recall"] == 0.0
    assert metrics["per_class"]["contradicted"]["f1"] == 0.0
    assert metrics["per_class"]["insufficient"]["precision"] == pytest.approx(1 / 3)
    assert metrics["per_class"]["insufficient"]["f1"] == 0.5
    assert metrics["macro_f1"] == 0.5
    assert metrics["abstention_rate"] == 0.5


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="local or openai"):
        verifier_for("some-hosted-vendor")


def test_local_provider_matches_the_substring_baseline():
    from claimledger.models import EvidenceUnit

    unit = EvidenceUnit("u", "notes.md", "a" * 64, 1, 0, 10, "alpha beta")
    result = LocalVerifier().verify("c1", "alpha", [unit])
    assert result.verdict == "supported"
    assert result.evidence[0].quote == "alpha"
