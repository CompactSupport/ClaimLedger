"""The 30-case Human–AI session is computed from stored inputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from claimledger.human_ai_calibration import assemble_formal_review, build_study, render_report_json

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "benchmark" / "candidates" / "review_queue.csv"
STUDY = ROOT / "benchmark" / "evaluation" / "human_ai_calibration"


def test_original_session_is_immutable_and_not_gold():
    before = QUEUE.read_bytes()
    first = build_study(ROOT)
    second = build_study(ROOT)
    assert render_report_json(first) == render_report_json(second)
    assert len(first["cases"]) == 30
    assert len({row["packet_id"] for row in first["cases"]}) == 30
    original = json.loads((STUDY / "human_original_responses.json").read_text(encoding="utf-8"))
    assert original["original_codes_in_packet_order"][12] == "C"
    assert first["cases"][12]["original_human_label"] == "contradicted"
    assert first["original"]["metric"] == "human_ai_agreement"
    assert first["original"]["agreements"] == 29
    assert first["original"]["disagreements"] == 1
    assert first["original"]["observed_agreement"] == pytest.approx(29 / 30)
    assert first["original"]["cohen_kappa"] == pytest.approx(0.95)
    assert first["original"]["is_accuracy"] is False
    assert first["original"]["is_independent_inter_annotator_agreement"] is False
    assert len(first["disagreements"]) == 1
    only = first["disagreements"][0]
    assert only["position"] == 13
    assert only["packet_id"] == "hr-f5d18c35e468"
    assert only["canonical_id"] == "cl-027-2"
    assert only["claim"] == "The recipe includes nuts."
    assert only["original_human_label"] == "contradicted"
    assert only["ai_second_opinion"] == "insufficient"
    revision = first["revision"]
    assert revision["revised_human_label"] == "insufficient"
    assert revision["event"] == "human_error_corrected_after_ai_feedback"
    assert revision["revision_trigger"] == "AI_feedback_and_user_reconsideration"
    assert revision["revision_reason"] == "absence_of_evidence_is_not_evidence_of_absence"
    assert revision["revision_confirmed_by_user"] is True
    assert revision["independent_adjudicator"] is False
    assert revision["original_response_overwritten"] is False
    assert first["cases"][12]["original_human_label"] == "contradicted"
    assert first["after_feedback"]["agreements"] == 30
    assert first["after_feedback"]["disagreements"] == 0
    assert first["after_feedback"]["replaces_original_result"] is False
    assert first["after_feedback"]["is_evidence_of_ai_correctness"] is False
    assert first["not_two_human_independent_review"] is True
    assert first["integrity"]["gold_set_rows"] == 0
    assert first["integrity"]["gold_benchmark_released"] is False
    assert first["integrity"]["calibration_import_applied"] is False
    assert first["integrity"]["formal_import_approval_generated"] is False
    assert first["integrity"]["question_13_author_expected"] == "contradicted"
    assert first["encrypted_ai_answer_artifact_used"] is False
    with QUEUE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    reviewed = [row for row in rows if row["human_reviewed"] == "True"]
    assert len(reviewed) == 30
    question_13 = next(row for row in rows if row["id"] == "cl-027-2")
    assert question_13["expected"] == "contradicted"
    assert question_13["reviewed_label"] == "insufficient"
    assert question_13["reviewer"] == "117230865"
    sheet_b = ROOT / "benchmark" / "evaluation" / "human_review" / "response_sheet_B.csv"
    with sheet_b.open(encoding="utf-8", newline="") as handle:
        assert all(not (row.get("reviewed_label") or "").strip() for row in csv.DictReader(handle))
    assert QUEUE.read_bytes() == before
    status = json.loads((ROOT / "funding" / "status.json").read_text(encoding="utf-8"))["benchmark"]
    assert status["human_ai_original_agreements"] == first["original"]["agreements"]
    assert status["human_ai_post_feedback_agreements"] == first["after_feedback"]["agreements"]
    assert status["human_ai_original_agreement_is_accuracy"] is False
    assert status["human_reviewed_rows"] == 30
    assert status["gold_benchmark_released"] is False
    formal = assemble_formal_review(ROOT)
    assert formal["queue_csv"] == QUEUE.read_text(encoding="utf-8")
    assert formal["paired_cases"] == 30
    assert len(formal["sheet_disagreements"]) == 1
    assert formal["gold_benchmark_released"] is False
    assert formal["independence_verified"] is False
    original_codes = original["original_codes_in_packet_order"]
    second_doc = json.loads((STUDY / "second_reviewer_responses.json").read_text(encoding="utf-8"))
    second_codes = second_doc["original_codes_in_packet_order"]
    assert second_doc["reviewer_identity_verified"] is False
    assert second_doc["formal_review_sheet"] is False
    assert len(second_codes) == 30
    assert [index for index, (left, right) in enumerate(zip(original_codes, second_codes, strict=True), start=1) if left != right] == [13]
    assert first["cases"][12]["second_reviewer_label"] == "insufficient"
    assert first["cases"][12]["original_human_label"] == "contradicted"
    second = first["second_reviewer"]
    assert second["formal_review_sheet"] is False
    assert second["formal_queue_import_recorded"] is True
    assert second["versus_original_human"]["agreements"] == 29
    assert second["versus_revised_human"]["agreements"] == 30
    assert second["versus_ai"]["agreements"] == 30
    assert second["versus_ai"]["is_accuracy"] is False
    assert second["versus_original_human"]["is_independent_inter_annotator_agreement"] is False
