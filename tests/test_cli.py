import json
from pathlib import Path

import pytest

from evidenceforge.cli import evaluate_dataset, main, read_claims
from evidenceforge.pipeline import verify_documents

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples"


def test_claims_loader():
    claims = read_claims(SAMPLES / "claims.json")
    assert len(claims) == 4


def test_cli_creates_reports(tmp_path):
    json_path = tmp_path / "run.json"
    md_path = tmp_path / "run.md"
    rc = main(["verify", "--doc", str(SAMPLES / "aurora.md"),
               "--claims", str(SAMPLES / "claims.json"),
               "--out", str(json_path), "--markdown", str(md_path)])
    assert rc == 0
    report = json.loads(json_path.read_text())
    assert report["verdict_counts"]["supported"] >= 2
    assert "extracted-text chars" in md_path.read_text()
    assert "Important" in md_path.read_text()


def test_offline_evaluation():
    result = evaluate_dataset(SAMPLES / "eval.jsonl", "local", "gpt-5-mini")
    assert result["total"] == 6
    assert result["correct"] == 4
    assert result["confusion"]["contradicted"]["insufficient"] == 2


def test_dataset_cannot_escape_root(tmp_path):
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text('{"document":"../private.txt","claim":"hi","expected":"supported"}\n')
    with pytest.raises(ValueError, match="inside"):
        evaluate_dataset(dataset, "local", "gpt-5-mini")


def test_sample_markdown_matches_the_docs(tmp_path):
    md_path = tmp_path / "run.md"
    rc = main(["verify", "--doc", str(SAMPLES / "aurora.md"),
               "--claims", str(SAMPLES / "claims.json"),
               "--out", str(tmp_path / "run.json"), "--markdown", str(md_path)])
    assert rc == 0
    expected = (ROOT / "docs" / "sample-report.md").read_text(encoding="utf-8")
    assert md_path.read_text(encoding="utf-8").replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def test_openai_timeout_does_not_write_a_verdict(tmp_path, monkeypatch, capsys):
    def explode(*_args, **_kwargs):
        raise RuntimeError("OpenAI request timed out; no verdict was recorded.")

    monkeypatch.setattr("evidenceforge.pipeline.openai_verify", explode)
    out = tmp_path / "out.json"
    rc = main(["verify", "--doc", str(SAMPLES / "aurora.md"),
               "--claims", str(SAMPLES / "claims.json"),
               "--backend", "openai", "--out", str(out)])
    assert rc == 2
    assert not out.exists()
    assert "no verdict was recorded" in capsys.readouterr().err


def test_missing_document_returns_error(tmp_path, capsys):
    rc = main(["verify", "--doc", str(tmp_path / "missing.md"),
               "--claims", str(SAMPLES / "claims.json")])
    assert rc == 2
    assert "Error:" in capsys.readouterr().err


def test_sample_json_matches_the_offline_demo():
    sample = json.loads((ROOT / "docs" / "sample-report.json").read_text(encoding="utf-8"))
    live = verify_documents([SAMPLES / "aurora.md"], read_claims(SAMPLES / "claims.json"))
    sample["created_utc"] = live["created_utc"]
    assert sample == live


def test_ci_does_not_require_api_credentials():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "openai_api_key" not in lowered
    assert "--backend openai" not in lowered
    assert "ruff check" in lowered
    assert "pytest" in lowered
    assert "evidenceforge verify" in lowered
    assert "evidenceforge evaluate" in lowered
