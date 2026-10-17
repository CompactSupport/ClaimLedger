import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from claimledger.ingest import load_pages, split_into_units
from claimledger.models import ClaimResult, DocumentPage, EvidenceQuote, EvidenceUnit
from claimledger.pipeline import verify_documents
from claimledger.retrieve import retrieve
from claimledger.verify import (
    MAX_QUOTE_CHARS,
    VERIFICATION_SCHEMA,
    local_verify,
    openai_verify,
    validated_quote,
)

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "aurora.md"


def _page_lookup(pages):
    return {(page.source, page.sha256, page.page): page.text for page in pages}


def _assert_report_quotes(report, pages) -> None:
    lookup = _page_lookup(pages)
    for result in report["results"]:
        if result["verdict"] != "insufficient":
            assert result["evidence"]
        for quote in result["evidence"]:
            text = lookup[(quote["source"], quote["sha256"], quote["page"])]
            assert text[quote["start"]:quote["end"]] == quote["quote"]


def _response(text, *, status="completed", usage=(18, 30, 48), output=None,
              incomplete_reason=None, error=None):
    if output is None:
        output = [SimpleNamespace(
            type="message",
            content=[SimpleNamespace(type="output_text", text=text)],
        )]
    usage_obj = None
    if usage is not None:
        usage_obj = SimpleNamespace(
            input_tokens=usage[0], output_tokens=usage[1], total_tokens=usage[2],
        )
    return SimpleNamespace(
        status=status,
        output_text=text,
        output=output,
        usage=usage_obj,
        incomplete_details=SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None,
        error=SimpleNamespace(message=error) if error else None,
    )


class OpenAIError(Exception):
    pass


class APIConnectionError(OpenAIError):
    pass


class APITimeoutError(APIConnectionError):
    pass


def _install_openai(create_result=None, create_error=None):
    mock_client = MagicMock()
    if create_error is not None:
        mock_client.return_value.responses.create.side_effect = create_error
    else:
        mock_client.return_value.responses.create.return_value = create_result
    module = SimpleNamespace(
        OpenAI=mock_client,
        APITimeoutError=APITimeoutError,
        APIConnectionError=APIConnectionError,
        OpenAIError=OpenAIError,
    )
    return mock_client, module


def test_local_baseline_is_conservative():
    pages = load_pages([SAMPLE])
    claims = ["Project Aurora evaluated 120 samples in March 2026.",
              "The study used synthetic samples.",
              "There were seven laboratories."]
    report = verify_documents([SAMPLE], claims)
    assert [result["verdict"] for result in report["results"]] == [
        "supported", "insufficient", "insufficient"]
    _assert_report_quotes(report, pages)
    assert "does not guarantee" in report["disclaimer"]


def test_local_mode_treats_any_exact_substring_as_supported():
    report = verify_documents([SAMPLE], ["120 samples"])
    assert report["results"][0]["verdict"] == "supported"
    assert report["results"][0]["evidence"][0]["quote"] == "120 samples"


def test_local_exact_match_survives_small_top_k(tmp_path):
    paragraphs = ["zephyr " + " ".join(f"filler{i}" for i in range(30)) for _ in range(8)]
    paragraphs.append("zephyr quota is 17 wafers in the locked cabinet.")
    path = tmp_path / "notes.md"
    path.write_text("\n\n".join(paragraphs), encoding="utf-8")
    pages = load_pages([path])
    report = verify_documents(
        [path],
        ["zephyr quota is 17 wafers in the locked cabinet."],
        top_k=1,
    )
    assert report["results"][0]["verdict"] == "supported"
    _assert_report_quotes(report, pages)


def test_claim_split_across_chunks_is_not_called_supported():
    body = ("甲" * 80) + ("乙" * 80)
    claim = ("甲" * 40) + ("乙" * 40)
    page = DocumentPage("split.md", "b" * 64, 1, body)
    units = split_into_units([page], max_chars=100)
    assert all(claim not in unit.text for unit in units)
    result = local_verify("c1", claim, units)
    assert result.verdict == "insufficient"
    assert result.evidence == []


def test_repeated_quote_uses_the_earliest_exact_span():
    text = "alpha beta. alpha beta."
    unit = EvidenceUnit("u", "notes.md", "c" * 64, 1, 0, len(text), text)
    quote = validated_quote(unit, "alpha beta.")
    assert quote is not None
    assert quote.start == text.find("alpha beta.")
    assert text[quote.start:quote.end] == "alpha beta."


def test_forged_quotes_fail_closed():
    units = split_into_units(load_pages([SAMPLE]))
    assert validated_quote(units[0], "The study had a thousand participants.") is None
    assert validated_quote(units[0], "") is None
    assert validated_quote(units[0], "   ") is None
    assert validated_quote(units[0], None) is None
    long_quote = "a" * (MAX_QUOTE_CHARS + 1)
    long_unit = EvidenceUnit("u", "n.md", "d" * 64, 1, 0, len(long_quote), long_quote)
    assert validated_quote(long_unit, long_quote) is None
    accepted = "b" * MAX_QUOTE_CHARS
    ok_unit = EvidenceUnit("u2", "n.md", "d" * 64, 1, 0, len(accepted), accepted)
    assert validated_quote(ok_unit, accepted) is not None


def test_model_quote_rejection_downgrades_claim():
    units = retrieve("Project Aurora evaluated 120 samples in March 2026.",
                     split_into_units(load_pages([SAMPLE])))
    payload = {"verdict": "supported", "reason": "looks fine",
               "evidence": [{"unit_id": "unknown", "quote": "fake citation"}]}
    fake = _response(json.dumps(payload))
    mock_openai, module = _install_openai(fake)
    with patch.dict(sys.modules, {"openai": module}):
        result = openai_verify("c1", "Project Aurora evaluated 120 samples in March 2026.", units)
    assert result.verdict == "insufficient"
    assert result.evidence == []
    assert result.audit_warnings
    assert result.usage["total_tokens"] == 48
    kwargs = mock_openai.return_value.responses.create.call_args.kwargs
    assert kwargs["store"] is False
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["text"]["format"]["type"] == "json_schema"
    assert kwargs["text"]["format"]["strict"] is True
    assert kwargs["text"]["format"]["name"] == "claim_verification"
    assert kwargs["text"]["format"]["schema"] == VERIFICATION_SCHEMA
    assert kwargs["input"][0]["role"] == "system"
    assert mock_openai.call_args.kwargs == {"timeout": 60.0, "max_retries": 2}


def test_model_valid_evidence_keeps_verdict():
    claim = "Project Aurora evaluated 120 samples in March 2026."
    units = retrieve(claim, split_into_units(load_pages([SAMPLE])))
    matching = next(unit for unit in units if claim in unit.text)
    payload = {"verdict": "supported", "reason": "Direct statement",
               "evidence": [{"unit_id": matching.id, "quote": claim}]}
    fake = _response(json.dumps(payload), usage=None)
    _mock, module = _install_openai(fake)
    with patch.dict(sys.modules, {"openai": module}):
        result = openai_verify("c1", claim, units, model="unit-test-model")
    assert result.verdict == "supported"
    assert result.model == "unit-test-model"
    assert result.evidence[0].quote == claim
    assert result.evidence[0].start == matching.start + matching.text.find(claim)
    assert not result.audit_warnings
    assert result.usage == {}


def test_contradicted_verdict_requires_a_real_quote():
    claim = "The study used synthetic samples."
    units = split_into_units(load_pages([SAMPLE]))
    source_quote = "The study did not use synthetic samples."
    matching = next(unit for unit in units if source_quote in unit.text)
    forged = {"verdict": "contradicted", "reason": "negation",
              "evidence": [{"unit_id": "missing", "quote": source_quote}]}
    valid = {"verdict": "contradicted", "reason": "The source states the opposite.",
             "evidence": [{"unit_id": matching.id, "quote": source_quote}]}
    _mock, module = _install_openai(_response(json.dumps(forged)))
    with patch.dict(sys.modules, {"openai": module}):
        rejected = openai_verify("c1", claim, units)
    assert rejected.verdict == "insufficient"
    assert rejected.evidence == []
    module.OpenAI.return_value.responses.create.return_value = _response(json.dumps(valid))
    with patch.dict(sys.modules, {"openai": module}):
        kept = openai_verify("c1", claim, units)
    assert kept.verdict == "contradicted"
    assert kept.evidence[0].quote == source_quote


def test_one_valid_quote_keeps_verdict_and_warns_about_the_forged_one():
    claim = "Project Aurora evaluated 120 samples in March 2026."
    units = split_into_units(load_pages([SAMPLE]))
    matching = next(unit for unit in units if claim in unit.text)
    payload = {
        "verdict": "supported",
        "reason": "Direct statement",
        "evidence": [
            {"unit_id": matching.id, "quote": "not in the source"},
            {"unit_id": matching.id, "quote": claim},
        ],
    }
    _mock, module = _install_openai(_response(json.dumps(payload)))
    with patch.dict(sys.modules, {"openai": module}):
        result = openai_verify("c1", claim, units)
    assert result.verdict == "supported"
    assert [quote.quote for quote in result.evidence] == [claim]
    assert result.audit_warnings


def test_incomplete_refusal_and_transport_errors_do_not_invent_verdicts():
    claim = "Project Aurora evaluated 120 samples in March 2026."
    units = split_into_units(load_pages([SAMPLE]))
    matching = next(unit for unit in units if claim in unit.text)
    believable = json.dumps({
        "verdict": "supported",
        "reason": "partial but tempting",
        "evidence": [{"unit_id": matching.id, "quote": claim}],
    })
    cases = [
        _response(believable, status="incomplete", incomplete_reason="max_output_tokens"),
        _response("", output=[SimpleNamespace(
            type="message",
            content=[SimpleNamespace(type="refusal", refusal="I cannot answer this.")],
        )]),
        _response(believable, status="failed", error="server exploded"),
    ]
    for fake in cases:
        _mock, module = _install_openai(fake)
        with patch.dict(sys.modules, {"openai": module}):
            with pytest.raises(RuntimeError, match="no verdict was recorded"):
                openai_verify("c1", claim, units)

    _mock, module = _install_openai(create_error=APITimeoutError("slow"))
    with patch.dict(sys.modules, {"openai": module}):
        with pytest.raises(RuntimeError, match="timed out"):
            openai_verify("c1", claim, units)
    module.OpenAI.return_value.responses.create.side_effect = APIConnectionError("reset")
    with patch.dict(sys.modules, {"openai": module}):
        with pytest.raises(RuntimeError, match="connect"):
            openai_verify("c1", claim, units)
    module.OpenAI.return_value.responses.create.side_effect = OpenAIError("429")
    with patch.dict(sys.modules, {"openai": module}):
        with pytest.raises(RuntimeError, match="failed"):
            openai_verify("c1", claim, units)
    module.OpenAI.return_value.responses.create.side_effect = None
    module.OpenAI.return_value.responses.create.return_value = _response("{not json")
    with patch.dict(sys.modules, {"openai": module}):
        with pytest.raises(RuntimeError, match="invalid JSON"):
            openai_verify("c1", claim, units)


def test_empty_retrieval_does_not_call_the_api():
    result = openai_verify("c1", "nothing retrieved", [])
    assert result.verdict == "insufficient"
    assert result.evidence == []


def test_missing_openai_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    units = split_into_units(load_pages([SAMPLE]))[:1]
    with pytest.raises(RuntimeError, match="OpenAI extra"):
        openai_verify("c1", "Project Aurora", units)


def test_pipeline_rejects_a_non_abstaining_verdict_with_a_bad_span(monkeypatch):
    pages = load_pages([SAMPLE])
    claim = "Project Aurora evaluated 120 samples in March 2026."
    matching = next(unit for unit in split_into_units(pages) if claim in unit.text)

    def forged(_claim_id, _claim, _units, _model):
        quote = validated_quote(matching, claim)
        assert quote is not None
        bad = EvidenceQuote(quote.unit_id, quote.source, quote.sha256, quote.page,
                            0, 4, "nope")
        return ClaimResult("c1", claim, "supported", "forged", [bad], "openai", "test-model")

    monkeypatch.setattr("claimledger.pipeline.openai_verify", forged)
    with pytest.raises(RuntimeError, match="do not match"):
        verify_documents([SAMPLE], [claim], backend="openai")


def test_schema_is_strict_structured_output():
    assert VERIFICATION_SCHEMA["additionalProperties"] is False
    assert set(VERIFICATION_SCHEMA["required"]) == set(VERIFICATION_SCHEMA["properties"])
    item = VERIFICATION_SCHEMA["properties"]["evidence"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    schema_path = SAMPLE.parents[1] / "docs" / "verification.schema.json"
    assert json.loads(schema_path.read_text(encoding="utf-8")) == VERIFICATION_SCHEMA
