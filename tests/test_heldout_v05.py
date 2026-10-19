"""The fresh held-out freeze is closed to models and separate from the old corpus."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claimledger.calibration import adjudication_digest
from claimledger.heldout import (
    LEDGER_NAME,
    assess_heldout_release,
    catalog_dir,
    generated_files,
    iter_cases,
    load_catalog,
)
from claimledger.semantic_pilot import PilotRefused, launch_subscription_model, prepare_invocation

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 18, 18, 0, tzinfo=timezone(timedelta(hours=-7)))
REVIEWED_AT = "2026-10-18T12:00:00-07:00"
APPROVED_AT = "2026-10-18T13:00:00-07:00"


def _cases():
    return iter_cases(load_catalog(ROOT))


def _freeze():
    return json.loads((catalog_dir(ROOT) / "freeze.json").read_text(encoding="utf-8"))


def _adjudications(cases, *, drop=None, label=None, quote=None, reviewer="fixture-reviewer"):
    rows = []
    for case in cases:
        if drop and case["id"] in drop:
            continue
        chosen = label if label is not None else ("insufficient" if not case["author_quote"] else case["author_label"])
        evidence = "" if chosen == "insufficient" else (quote if quote is not None else case["author_quote"])
        rows.append({
            "id": case["id"],
            "adjudicated_label": chosen,
            "evidence_quote": evidence,
            "reviewer": reviewer,
            "reviewed_at": REVIEWED_AT,
        })
    return sorted(rows, key=lambda row: row["id"])


def _ledger(freeze, rows, *, digest=None, freeze_hash=None, contacts=None, approver="fixture-approver"):
    return {
        "schema": "claimledger.heldout_v05_research_ledger.v1",
        "dataset_version": freeze["dataset_version"],
        "freeze_sha256": freeze["freeze_sha256"] if freeze_hash is None else freeze_hash,
        "reviewer_submissions": [],
        "human_adjudications": rows,
        "approvals": [{
            "decision": "allow_first_model_contact",
            "freeze_sha256": freeze["freeze_sha256"] if freeze_hash is None else freeze_hash,
            "adjudication_digest": adjudication_digest(rows) if digest is None else digest,
            "approver": approver,
            "approved_at": APPROVED_AT,
        }],
        "model_contacts": contacts or [],
    }


def test_generated_heldout_files_match_the_catalog_and_leave_the_ledger_alone():
    base = catalog_dir(ROOT)
    files = generated_files(ROOT)
    assert LEDGER_NAME not in files
    for name, text in files.items():
        assert (base / name).read_text(encoding="utf-8") == text


def test_model_view_hides_labels_and_the_old_corpus():
    base = catalog_dir(ROOT)
    visible = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (base / "model_view").rglob("*")
        if path.is_file()
    )
    for word in ("supported", "contradicted", "insufficient", "author_label", "author_quote"):
        assert word not in visible
    old = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "benchmark" / "candidates" / "documents").glob("*.md")
    )
    catalog = load_catalog(ROOT)
    for item in catalog["documents"]:
        assert item["text"].strip() not in old
    for claim in catalog["claims"]:
        assert claim["claim"] not in old


def test_kiln_month_label_stays_contradicted_and_is_marked_for_review():
    cases = _cases()
    kiln = next(case for case in cases if case["claim"] == "Kiln North fired 18 batches in June 2026.")
    assert kiln["author_label"] == "contradicted"
    assert kiln["author_label_under_review"] is True
    audit = json.loads((catalog_dir(ROOT) / "entailment_audit.json").read_text(encoding="utf-8"))
    row = next(item for item in audit["rows"] if item["id"] == kiln["id"])
    assert row["author_label"] == "contradicted"
    assert row["author_label_under_review"] is True
    assert row["entailment"] == "unresolved"
    assert row["rule"] == "different_period_not_exclusive"
    assert row["verdict_confirmed"] is False
    assert audit["heuristics_certify_labels"] is False


def test_committed_ledger_is_bound_and_has_no_model_contact():
    freeze = _freeze()
    ledger = json.loads((catalog_dir(ROOT) / LEDGER_NAME).read_text(encoding="utf-8"))
    assert ledger["freeze_sha256"] == freeze["freeze_sha256"]
    assert ledger["human_adjudications"] == []
    assert ledger["approvals"] == []
    assert ledger["model_contacts"] == []
    assert freeze["gold_benchmark_released"] is False
    decision = assess_heldout_release(freeze, ledger, _cases(), now=NOW)
    assert decision["allowed"] is False
    assert any("unreviewed" in reason for reason in decision["reasons"])


def test_release_refuses_partial_review_forged_approval_wrong_hash_and_duplicate_contact():
    freeze = _freeze()
    cases = _cases()
    partial = assess_heldout_release(
        freeze, _ledger(freeze, _adjudications(cases, drop={cases[0]["id"]})), cases, now=NOW,
    )
    assert partial["allowed"] is False
    assert any("partial" in reason for reason in partial["reasons"])
    forged = assess_heldout_release(
        freeze, _ledger(freeze, _adjudications(cases), digest="0" * 64), cases, now=NOW,
    )
    assert forged["allowed"] is False
    assert any("forged" in reason for reason in forged["reasons"])
    wrong_hash = assess_heldout_release(
        freeze, _ledger(freeze, _adjudications(cases), freeze_hash="1" * 64), cases, now=NOW,
    )
    assert wrong_hash["allowed"] is False
    assert any("freeze hash" in reason for reason in wrong_hash["reasons"])
    duplicate = assess_heldout_release(
        freeze,
        _ledger(freeze, _adjudications(cases), contacts=[{"freeze_sha256": freeze["freeze_sha256"]}]),
        cases,
        now=NOW,
    )
    assert duplicate["allowed"] is False
    assert any("already has a model contact" in reason for reason in duplicate["reasons"])
    illegal_rows = _adjudications(cases)
    illegal_rows[0]["adjudicated_label"] = "maybe"
    illegal = assess_heldout_release(freeze, _ledger(freeze, illegal_rows), cases, now=NOW)
    assert illegal["allowed"] is False
    assert any("illegal label" in reason for reason in illegal["reasons"])
    bad_evidence = _adjudications(cases)
    for row in bad_evidence:
        if row["adjudicated_label"] == "supported":
            row["evidence_quote"] = ""
            break
    invalid = assess_heldout_release(freeze, _ledger(freeze, bad_evidence), cases, now=NOW)
    assert invalid["allowed"] is False
    assert any("invalid evidence" in reason for reason in invalid["reasons"])
    machine = assess_heldout_release(
        freeze, _ledger(freeze, _adjudications(cases, reviewer="gpt-reviewer")), cases, now=NOW,
    )
    assert machine["allowed"] is False
    assert any("not a human reviewer" in reason for reason in machine["reasons"])


def test_a_complete_release_opens_the_gate_without_certifying_the_labels():
    freeze = _freeze()
    cases = _cases()
    decision = assess_heldout_release(freeze, _ledger(freeze, _adjudications(cases)), cases, now=NOW)
    assert decision == {"allowed": True, "reasons": []}


def test_the_inference_entry_refuses_a_heldout_claim_until_the_release_is_valid(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("a model process was started")

    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", boom)
    monkeypatch.setattr("claimledger.semantic_pilot.shutil.which", lambda _name: r"C:\tools\codex.exe")
    case = next(item for item in _cases() if item["author_label_under_review"])
    invocation = prepare_invocation(
        [{
            "evaluation_id": "ev-heldout-gate",
            "claim": case["claim"],
            "passage_id": "p-heldout-gate",
            "passage": case["passage"],
        }],
        tmp_path / "work",
        ROOT,
        {"SYSTEMROOT": r"C:\Windows", "PATH": r"C:\Windows"},
    )
    billing = {"authenticated": True, "billing_mode": "subscription", "api_key_present": False}
    with pytest.raises(PilotRefused, match="unreviewed"):
        launch_subscription_model(
            "codex", billing, allow_real_inference=True, invocation=invocation, repo_root=ROOT,
        )
    called = {}

    def fake_run(argv, cwd, env, capture_output, text, check, input=None):
        called["ok"] = True
        return __import__("subprocess").CompletedProcess(argv, 0, json.dumps({
            "evaluation_id": "ev-heldout-gate",
            "verdict": "insufficient",
            "quote": "",
        }), "")

    monkeypatch.setattr("claimledger.semantic_pilot.subprocess.run", fake_run)
    result = launch_subscription_model(
        "codex",
        billing,
        allow_real_inference=True,
        invocation=invocation,
        repo_root=ROOT,
        heldout_ledger=_ledger(_freeze(), _adjudications(_cases())),
    )
    assert called["ok"] is True
    assert result["real_model_execution"] is True
    committed = json.loads((catalog_dir(ROOT) / LEDGER_NAME).read_text(encoding="utf-8"))
    assert committed["model_contacts"] == []
