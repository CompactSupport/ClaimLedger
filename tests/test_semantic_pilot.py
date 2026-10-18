"""Mocked semantic-pilot checks. No model process is a real evaluator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claimledger.semantic_pilot import (
    PilotRefused,
    execute_real_inference,
    execute_restricted,
    launch_subscription_model,
    observe_subscription_billing,
    offline_mock_checks,
    prepare_invocation,
    restricted_env,
    run_codex_subscription,
    score_adjudicated_subset,
    score_subset,
    select_internal_subset,
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
    assert result["real_model_execution"] is False
    assert result["result_is_model_evaluation"] is False
    assert result["execution_kind"] == "subprocess_command"
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
    with pytest.raises(PilotRefused, match="one-record invocation"):
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
    assert scored["result_is_model_evaluation"] is False


def test_check_command_runs_the_offline_mock_gate(tmp_path):
    report = offline_mock_checks(tmp_path / "gate", ROOT)
    assert report["failures"] == []
    assert report["paid_model_calls"] == 0
    assert report["mock_results_are_model_evaluation"] is False
    assert report["human_labels_synthesized"] is False
    script = ROOT / "scripts" / "run_semantic_pilot.py"
    missing = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True)
    assert missing.returncode == 2
    completed = subprocess.run(
        [sys.executable, str(script), "--check"], cwd=ROOT, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "offline_mock_checks=passed" in completed.stdout
    assert "paid_model_calls=0" in completed.stdout
    assert "mock_results_are_model_evaluation=false" in completed.stdout
    assert "os_sandbox=false" in completed.stdout
    assert "macro_f1" not in completed.stdout
    assert "macro-f1" not in completed.stdout.lower()


def test_real_inference_refuses_without_a_verified_subscription_cli():
    record = _record()
    invocation = {
        "cwd": Path("."),
        "record": record,
        "prompt_version": "claimledger.inference_prompt.v1",
        "passage_sha256": "abc",
    }
    with pytest.raises(PilotRefused, match="has not been verified"):
        execute_real_inference(invocation, None, allow_real_inference=True)
    with pytest.raises(PilotRefused, match="not used as a fallback"):
        execute_real_inference(invocation, {
            "authenticated": True,
            "billing_mode": "api_key",
            "api_key_present": False,
        }, allow_real_inference=True)
    with pytest.raises(PilotRefused, match="not on PATH"):
        execute_real_inference(invocation, {
            "authenticated": True,
            "billing_mode": "subscription",
            "api_key_present": False,
        }, allow_real_inference=True)


def test_internal_subset_is_reproducible_and_hides_canonical_ids(tmp_path):
    from scripts.report_semantic_pilot import _load_cases, build_report_files
    first = build_report_files()
    second = build_report_files()
    assert first == second
    public = json.loads(first["subset_public.json"])
    assert len(public["evaluation_ids"]) == 10
    assert public["independent_external_test"] is False
    assert "cl-" not in first["subset_public.json"]
    assert "supported" not in first["subset_public.json"]
    chosen = select_internal_subset(_load_cases())
    assert [row["evaluation_id"] for row in chosen] == public["evaluation_ids"]
    by_document = {}
    for case in _load_cases():
        by_document.setdefault(case["document"], set()).add(case["canonical_id"])
    selected = {case["canonical_id"] for case in chosen}
    for document, ids in by_document.items():
        overlap = ids & selected
        assert overlap == set() or overlap == ids
    scored = score_adjudicated_subset(
        [{
            "evaluation_id": public["evaluation_ids"][0],
            "status": "completed_valid",
            "verdict": "insufficient",
            "quote_in_source": True,
            "real_model_execution": False,
        }],
        subset=[public["evaluation_ids"][0]],
        adjudicated_labels={public["evaluation_ids"][0]: "insufficient"},
    )
    assert scored["independent_external_test"] is False
    assert scored["result_is_model_evaluation"] is False
    assert "genuine model" in first["REPORT.md"].lower() or "no genuine" in first["REPORT.md"].lower()
    assert "not on PATH" in first["REPORT.md"]
    assert "was not executed" in first["REPORT.md"]
    assert "Genuine predictions: 0." in first["REPORT.md"]


def test_in_process_runner_cannot_be_recorded_as_a_model(tmp_path):
    invocation = prepare_invocation([_record()], tmp_path / "work", ROOT, _environ())
    with pytest.raises(PilotRefused, match="in-process"):
        execute_restricted(
            invocation,
            model="mock-model",
            cli_version="mock-0",
            runner=lambda _cwd, _env: "{}",
            real_model_execution=True,
        )


def test_verified_subscription_subprocess_is_recorded_as_real(tmp_path, monkeypatch):
    record = _record()
    invocation = prepare_invocation([record], tmp_path / "work", ROOT, _environ())
    seen = {}

    def fake_which(name):
        return r"C:\tools\agy.cmd" if name == "agy" else None

    def fake_run(argv, cwd, env, capture_output, text, check):
        seen["argv"] = argv
        seen["cwd"] = cwd
        seen["env"] = env
        payload = {
            "evaluation_id": record["evaluation_id"],
            "verdict": "supported",
            "quote": "The sample count was 120",
        }
        envelope = {"status": "SUCCESS", "structured_output": payload}
        return subprocess.CompletedProcess(argv, 0, json.dumps(envelope), "")

    monkeypatch.setattr("claimledger.semantic_pilot.shutil.which", fake_which)
    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", fake_run)
    result = launch_subscription_model(
        "antigravity",
        {"authenticated": True, "billing_mode": "subscription", "api_key_present": False},
        allow_real_inference=True,
        invocation=invocation,
        repo_root=ROOT,
    )
    assert result["real_model_execution"] is True
    assert result["result_is_model_evaluation"] is True
    assert result["status"] == "completed_valid"
    assert result["verdict"] == "supported"
    assert result["independently_blinded"] is False
    assert result["os_sandbox"] is False
    assert result["adjudication_file_mounted"] is False
    assert "--sandbox" in seen["argv"]
    assert str(ROOT.resolve()) not in " ".join(str(arg) for arg in seen["argv"])
    assert seen["cwd"] == invocation["cwd"]
    assert "GEMINI_API_KEY" not in seen["env"]
    assert "OPENAI_API_KEY" not in seen["env"]
    scored = score_adjudicated_subset(
        [result],
        subset=[record["evaluation_id"]],
        adjudicated_labels={record["evaluation_id"]: "supported"},
    )
    assert scored["real_inference"] is True
    assert scored["result_is_model_evaluation"] is True
    assert scored["independent_external_test"] is False
    assert scored["paid_model_calls"] == 0


def test_failed_model_subprocess_is_still_recorded(tmp_path, monkeypatch):
    invocation = prepare_invocation([_record()], tmp_path / "work", ROOT, _environ())

    def fake_run(argv, cwd, env, capture_output, text, check):
        return subprocess.CompletedProcess(argv, 1, "", "authentication required")

    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", fake_run)
    result = execute_restricted(
        invocation,
        model="antigravity",
        cli_version="agy",
        runner_argv=[r"C:\tools\agy.cmd", "-p", "prompt"],
        repo_root=ROOT,
        real_model_execution=True,
        provider="antigravity",
    )
    assert result["real_model_execution"] is True
    assert result["result_is_model_evaluation"] is False
    assert result["status"] == "rejected_process"


def test_billing_observation_never_invents_a_subscription(monkeypatch):
    def fake_which(name):
        return r"C:\tools\agy.cmd" if name == "agy" else None

    monkeypatch.setattr("claimledger.semantic_pilot.shutil.which", fake_which)
    with pytest.raises(PilotRefused, match="not been verified"):
        observe_subscription_billing(
            "antigravity",
            environ={"PATH": r"C:\tools"},
            settings={"security": {"auth": {"selectedType": "oauth-personal"}}},
        )
    observed = observe_subscription_billing(
        "antigravity",
        environ={"GEMINI_API_KEY": "present"},
        settings=None,
    )
    assert observed["billing_mode"] == "api_key"
    assert observed["api_key_present"] is True
    with pytest.raises(PilotRefused, match="not on PATH"):
        observe_subscription_billing("gemini", environ={})


def test_api_key_billing_does_not_start_antigravity(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("a process was started")

    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", boom)
    monkeypatch.setattr("claimledger.semantic_pilot.shutil.which", lambda _name: r"C:\tools\agy.cmd")
    with pytest.raises(PilotRefused, match="API key"):
        launch_subscription_model(
            "antigravity",
            {"authenticated": True, "billing_mode": "subscription", "api_key_present": True},
            allow_real_inference=True,
            invocation={"cwd": Path("."), "env": {}, "record": {}},
            repo_root=ROOT,
        )


def test_adjudicated_subset_check_does_not_run_a_model():
    script = ROOT / "scripts" / "run_adjudicated_subset.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--check"], cwd=ROOT, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "processes_started=0" in completed.stdout
    assert "adjudication_file_opened=false" in completed.stdout
    assert "macro_f1" not in completed.stdout.lower()
    blocked = subprocess.run(
        [sys.executable, str(script), "--run"], cwd=ROOT, capture_output=True, text=True,
    )
    assert blocked.returncode == 2
    assert "processes_started=0" in blocked.stdout
    assert "genuine_predictions=0" in blocked.stdout
    assert "not on PATH" in blocked.stderr
    assert "macro_f1" not in blocked.stdout.lower()
    assert "macro-f1" not in blocked.stderr.lower()
