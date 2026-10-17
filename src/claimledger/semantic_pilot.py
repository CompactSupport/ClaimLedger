"""Controlled one-record semantic pilot harness.

Real model processes are not launched. Codex subscription billing is checked
and then refused for this revision. API-key billing is never a fallback.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .label_blind import CANONICAL_ID_RE, CLASSES, PROMPT, PROMPT_VERSION

RESULT_SCHEMA = "claimledger.semantic_pilot_result.v1"
ENV_ALLOWLIST = {"SYSTEMROOT", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP", "WINDIR"}
SENSITIVE_NAME = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)")


class PilotRefused(RuntimeError):
    """Raised when a pilot run or score is not allowed."""


def restricted_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Keep a tiny environment and drop credentials."""
    current = source if source is not None else dict(os.environ)
    return {
        key: value
        for key, value in current.items()
        if key in ENV_ALLOWLIST and SENSITIVE_NAME.search(key) is None
    }


def prepare_invocation(records: list[dict], workspace: Path, repo_root: Path,
                       environ: dict[str, str] | None = None) -> dict:
    """Write one evaluation record. Refuse the repository and any extra claims."""
    if len(records) != 1:
        raise PilotRefused("Each model invocation receives exactly one evaluation record.")
    record = records[0]
    allowed = {"evaluation_id", "claim", "passage_id", "passage"}
    if set(record) != allowed:
        raise PilotRefused("The invocation record has fields other than the claim and passage.")
    if CANONICAL_ID_RE.search(json.dumps(record)):
        raise PilotRefused("The invocation record contains a canonical case id.")
    dest = workspace.resolve()
    root = repo_root.resolve()
    if dest == root or dest.is_relative_to(root):
        raise PilotRefused("The invocation workspace must be outside the repository.")
    if dest.exists() and any(dest.iterdir()):
        raise PilotRefused("The invocation workspace must start empty.")
    dest.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, ensure_ascii=False) + "\n"
    (dest / "input.json").write_text(payload, encoding="utf-8", newline="\n")
    (dest / "prompt.txt").write_text(PROMPT, encoding="utf-8", newline="\n")
    return {
        "cwd": dest,
        "env": restricted_env(environ),
        "record": record,
        "prompt_version": PROMPT_VERSION,
        "passage_sha256": hashlib.sha256(record["passage"].encode("utf-8")).hexdigest(),
        "os_sandbox": False,
    }


def _read_invocation(cwd: Path) -> dict:
    names = {path.name for path in cwd.iterdir()}
    if names != {"input.json", "prompt.txt"}:
        raise PilotRefused("The invocation workspace is not limited to one record and the prompt.")
    return json.loads((cwd / "input.json").read_text(encoding="utf-8"))


def validate_model_output(raw: str, record: dict) -> dict:
    """Check schema, id, and quote against the passage that was actually written."""
    leakage = CANONICAL_ID_RE.search(raw) is not None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _rejected("rejected_schema", record, raw, "Model output is not JSON.", leakage)
    if not isinstance(payload, dict) or set(payload) != {"evaluation_id", "verdict", "quote"}:
        return _rejected("rejected_schema", record, raw, "Model output schema is not the three allowed fields.", leakage)
    if payload["evaluation_id"] != record["evaluation_id"]:
        return _rejected("rejected_id", record, raw, "Model output evaluation id does not match the invocation.", leakage)
    if payload["verdict"] not in CLASSES:
        return _rejected("rejected_schema", record, raw, "Verdict is not one of the three classes.", leakage)
    quote = payload["quote"]
    if not isinstance(quote, str):
        return _rejected("rejected_schema", record, raw, "Quote is not a string.", leakage)
    passage = record["passage"]
    if payload["verdict"] == "insufficient":
        if quote != "":
            return _rejected("rejected_quote", record, raw, "An insufficient verdict cannot include a quote.", leakage)
    elif quote == "" or quote not in passage:
        return _rejected("rejected_quote", record, raw, "Quote is not an exact substring of the source passage.", leakage)
    if leakage:
        return _rejected("rejected_leakage", record, raw, "Model output contains a canonical case id.", True)
    return {
        "schema": RESULT_SCHEMA,
        "evaluation_id": record["evaluation_id"],
        "status": "completed_valid",
        "verdict": payload["verdict"],
        "quote": quote,
        "raw_response": raw,
        "quote_in_source": True,
        "human_reviewed": False,
        "message": "",
    }


def _rejected(status: str, record: dict, raw: str, message: str, leakage: bool) -> dict:
    return {
        "schema": RESULT_SCHEMA,
        "evaluation_id": record["evaluation_id"],
        "status": "rejected_leakage" if leakage and status != "rejected_id" else status,
        "verdict": None,
        "quote": None,
        "raw_response": raw,
        "quote_in_source": False,
        "human_reviewed": False,
        "message": message if not leakage else "Model output contains a canonical case id.",
    }


def execute_restricted(invocation: dict, *, model: str, cli_version: str,
                       runner=None, runner_argv: list[str] | None = None,
                       repo_root: Path | None = None) -> dict:
    """Run one mock in the workspace. A subprocess gets that cwd and the stripped env.

    This is not an operating-system sandbox. It does not mount the repository
    or pass credential variables. A hostile program can still open other paths.
    """
    if not model or not cli_version:
        raise PilotRefused("Model name and CLI version are required.")
    if runner is not None and runner_argv is not None:
        raise PilotRefused("Pass either an in-process runner or a subprocess command.")
    record = _read_invocation(invocation["cwd"])
    if record != invocation["record"]:
        raise PilotRefused("Invocation file does not match the prepared record.")
    if runner_argv is not None:
        if repo_root is not None and any(str(repo_root.resolve()) in str(arg) for arg in runner_argv):
            raise PilotRefused("The runner command must not include the repository path.")
        completed = subprocess.run(
            runner_argv,
            cwd=invocation["cwd"],
            env=invocation["env"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise PilotRefused(detail or "The restricted runner failed.")
        raw = completed.stdout
    elif runner is not None:
        raw = runner(invocation["cwd"], invocation["env"])
    else:
        raise PilotRefused("Real model execution is disabled.")
    result = validate_model_output(raw, record)
    result.update({
        "model": model,
        "cli_version": cli_version,
        "prompt_version": invocation["prompt_version"],
        "passage_sha256": invocation["passage_sha256"],
        "execution_status": result["status"],
    })
    return result


def assert_codex_subscription(billing: dict | None) -> None:
    """Refuse unless authentication and subscription billing were both verified."""
    if not billing or billing.get("authenticated") is not True:
        raise PilotRefused("Codex authentication has not been verified.")
    if billing.get("billing_mode") != "subscription":
        raise PilotRefused(
            "Codex billing mode is not a verified subscription. API-key billing is not used as a fallback."
        )
    if billing.get("api_key_present") is True:
        raise PilotRefused("An API key is present. Refusing to bill the pilot to an API key.")


def run_codex_subscription(billing: dict | None, *, allow_real_inference: bool = False) -> None:
    """Subscription gate. Real Codex execution is disabled in this revision."""
    assert_codex_subscription(billing)
    if not allow_real_inference:
        raise PilotRefused("Real Codex inference is disabled in this revision.")
    raise PilotRefused("Real Codex inference is disabled in this revision.")


def score_subset(results: list[dict], *, subset: list[str], known_ids: set[str],
                 author_labels: dict[str, str]) -> dict:
    """Score one declared subset. Author labels are passed in; the queue is not read."""
    if not subset:
        raise PilotRefused("A declared evaluation subset is required before scoring.")
    unknown = [item for item in subset if item not in known_ids or item not in author_labels]
    if unknown:
        raise PilotRefused("The declared subset contains an unknown evaluation id.")
    seen: set[str] = set()
    by_id = {}
    for result in results:
        evaluation_id = result.get("evaluation_id")
        if evaluation_id not in known_ids or evaluation_id not in set(subset):
            raise PilotRefused("A prediction uses an unknown evaluation id.")
        if evaluation_id in seen:
            raise PilotRefused("A prediction evaluation id is duplicated.")
        seen.add(evaluation_id)
        if result.get("status") != "completed_valid":
            raise PilotRefused("A subset prediction is missing or invalid.")
        by_id[evaluation_id] = result
    missing = [item for item in subset if item not in by_id]
    if missing:
        raise PilotRefused("A declared subset id has no valid prediction.")
    pairs = [(author_labels[item], by_id[item]["verdict"]) for item in subset]
    correct = sum(expected == actual for expected, actual in pairs)
    return {
        "schema": "claimledger.semantic_pilot_score.v1",
        "result_class": "internal_label_blinded_test",
        "subset_size": len(subset),
        "correct": correct,
        "human_reviewed": False,
        "label_source": "author_labels_from_the_audit_mapping",
        "real_inference": False,
    }
