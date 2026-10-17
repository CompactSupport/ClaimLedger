"""Mocked semantic-pilot checks. No model process is a real evaluator."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from claimledger.semantic_pilot import (
    PilotRefused,
    execute_restricted,
    prepare_invocation,
    restricted_env,
    run_codex_subscription,
    score_subset,
    validate_model_output,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(evaluation_id: str = "ev-001122334455") -> dict:
    return {
        "evaluation_id": evaluation_id,
        "claim": "The sample count was 120.",
        "passage_id": "p-001122334455",
        "passage": "The sample count was 120 in April.\n",
    }


def _environ() -> dict[str, str]:
    return {
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "PATH": os.environ.get("PATH", ""),
        "PATHEXT": os.environ.get("PATHEXT", ".EXE"),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "OPENAI_API_KEY": "blocked",
        "GH_TOKEN": "blocked",
    }


def test_environment_drops_credentials_and_workspace_has_one_record(tmp_path):
    env = restricted_env(_environ())
    assert "OPENAI_API_KEY" not in env
    assert "GH_TOKEN" not in env
    assert "PATH" in env
    with pytest.raises(PilotRefused, match="exactly one"):
        prepare_invocation([_record(), _record("ev-aabbccddeeff")], tmp_path / "many", ROOT, _environ())
    leaked = _record()
    leaked["author_label"] = "supported"
    with pytest.raises(PilotRefused, match="other than the claim"):
        prepare_invocation([leaked], tmp_path / "leaked", ROOT, _environ())
    with pytest.raises(PilotRefused, match="outside the repository"):
        prepare_invocation([_record()], ROOT / "output" / "pilot", ROOT, _environ())
    invocation = prepare_invocation([_record()], tmp_path / "one", ROOT, _environ())
    names = {path.name for path in invocation["cwd"].iterdir()}
    assert names == {"input.json", "prompt.txt"}
    assert invocation["os_sandbox"] is False
    assert "OPENAI_API_KEY" not in invocation["env"]
    stored = json.loads((invocation["cwd"] / "input.json").read_text(encoding="utf-8"))
    assert stored == _record()


def test_output_schema_quote_and_leakage_are_checked():
    record = _record()
    valid = validate_model_output(
        json.dumps({
            "evaluation_id": record["evaluation_id"],
            "verdict": "supported",
            "quote": "The sample count was 120",
        }),
        record,
    )
    assert valid["status"] == "completed_valid"
    assert valid["human_reviewed"] is False
    bad_quote = validate_model_output(
        json.dumps({
            "evaluation_id": record["evaluation_id"],
            "verdict": "supported",
            "quote": "a sentence that was not written",
        }),
        record,
    )
    assert bad_quote["status"] == "rejected_quote"
    leaked = validate_model_output(
        json.dumps({
            "evaluation_id": record["evaluation_id"],
            "verdict": "insufficient",
            "quote": "cl-001-1",
        }),
        record,
    )
    assert leaked["status"] == "rejected_leakage"
    mismatched = validate_model_output(
        json.dumps({"evaluation_id": "ev-ffffffffffff", "verdict": "insufficient", "quote": ""}),
        record,
    )
    assert mismatched["status"] == "rejected_id"


def test_subprocess_mock_sees_only_the_invocation(tmp_path):
    invocation = prepare_invocation([_record()], tmp_path / "work", ROOT, _environ())
    script = tmp_path / "mock_model.py"
    script.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "names = sorted(path.name for path in Path('.').iterdir())\n"
        "assert names == ['input.json', 'prompt.txt']\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "record = json.loads(Path('input.json').read_text(encoding='utf-8'))\n"
        "print(json.dumps({'evaluation_id': record['evaluation_id'], "
        "'verdict': 'insufficient', 'quote': ''}))\n",
        encoding="utf-8",
    )
    result = execute_restricted(
        invocation,
        model="mock-model",
        cli_version="mock-0",
        runner_argv=[sys.executable, str(script)],
        repo_root=ROOT,
    )
    assert result["status"] == "completed_valid"
    assert result["model"] == "mock-model"
    assert result["cli_version"] == "mock-0"
    assert result["prompt_version"] == "claimledger.inference_prompt.v1"
    assert result["human_reviewed"] is False
    assert result["passage_sha256"] == invocation["passage_sha256"]
    with pytest.raises(PilotRefused, match="repository path"):
        execute_restricted(
            invocation,
            model="mock-model",
            cli_version="mock-0",
            runner_argv=[sys.executable, str(ROOT / "scripts" / "run_semantic_pilot.py")],
            repo_root=ROOT,
        )


def test_codex_subscription_gate_never_starts_a_process(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("a process was started")

    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", boom)
    with pytest.raises(PilotRefused, match="has not been verified"):
        run_codex_subscription(None)
    with pytest.raises(PilotRefused, match="not used as a fallback"):
        run_codex_subscription({"authenticated": True, "billing_mode": "api_key"})
    with pytest.raises(PilotRefused, match="API key"):
        run_codex_subscription({
            "authenticated": True,
            "billing_mode": "subscription",
            "api_key_present": True,
        })
    verified = {"authenticated": True, "billing_mode": "subscription", "api_key_present": False}
    with pytest.raises(PilotRefused, match="disabled"):
        run_codex_subscription(verified)
    with pytest.raises(PilotRefused, match="disabled"):
        run_codex_subscription(verified, allow_real_inference=True)


def test_scoring_requires_a_subset_and_stays_apart_from_human_labels():
    known = {"ev-1", "ev-2"}
    labels = {"ev-1": "supported", "ev-2": "contradicted"}
    valid = {
        "evaluation_id": "ev-1",
        "status": "completed_valid",
        "verdict": "supported",
        "human_reviewed": False,
    }
    with pytest.raises(PilotRefused, match="declared evaluation subset"):
        score_subset([valid], subset=[], known_ids=known, author_labels=labels)
    with pytest.raises(PilotRefused, match="unknown"):
        score_subset([valid], subset=["ev-nope"], known_ids=known, author_labels=labels)
    with pytest.raises(PilotRefused, match="duplicated"):
        score_subset([valid, dict(valid)], subset=["ev-1"], known_ids=known, author_labels=labels)
    with pytest.raises(PilotRefused, match="no valid prediction"):
        score_subset([valid], subset=["ev-1", "ev-2"], known_ids=known, author_labels=labels)
    scored = score_subset(
        [valid, {**valid, "evaluation_id": "ev-2", "verdict": "supported"}],
        subset=["ev-1", "ev-2"],
        known_ids=known,
        author_labels=labels,
    )
    assert scored["correct"] == 1
    assert scored["human_reviewed"] is False
    assert scored["result_class"] == "internal_label_blinded_test"
    assert scored["real_inference"] is False
