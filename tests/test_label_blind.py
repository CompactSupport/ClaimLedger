"""Leakage checks for the internal label-blind export."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from claimledger.label_blind import (
    CLASSES,
    HUMAN_PACKET_SEED,
    SEED,
    assert_human_tree,
    assert_isolated_tree,
    build_bundle,
    committed_files_match,
    inter_annotator_agreement,
    prepare_agent_view,
    reconcile,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "benchmark" / "candidates"
CANONICAL_ID_RE = re.compile(r"cl-\d{3}-\d")
LABEL_CYCLE = ("supported", "contradicted", "insufficient")


def _queue():
    with (CANDIDATES / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bundle():
    return build_bundle(CANDIDATES)


def _suffix_label(case_id: str) -> str | None:
    if case_id.endswith("-1"):
        return "supported"
    if case_id.endswith("-2"):
        return "contradicted"
    if case_id.endswith("-3"):
        return "insufficient"
    return None


def test_canonical_labels_stay_in_the_queue():
    bundle = _bundle()
    reviews = _queue()
    assert [row["expected"] for row in reviews] == [LABEL_CYCLE[i % 3] for i in range(len(reviews))]
    assert all(row["human_reviewed"] == "False" and row["reviewed_label"] == "" for row in reviews)
    assert bundle["protocol"]["review_queue_sha256"]
    status = json.loads((ROOT / "funding" / "status.json").read_text(encoding="utf-8"))
    assert status["benchmark"]["gold_benchmark_released"] is False
    assert status["benchmark"]["human_reviewed_rows"] == 0
    assert status["benchmark"]["label_blind_is_external_test"] is False
    assert status["benchmark"]["label_blind_model_runs"] == 0
    assert status["benchmark"]["human_calibration_decisions"] == 0


def test_model_view_hides_labels_and_canonical_ids(tmp_path):
    bundle = _bundle()
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    for name, text in bundle["isolated"].items():
        (isolated / name).write_text(text, encoding="utf-8")
    assert_isolated_tree(isolated)
    visible = "\n".join(bundle["isolated"].values())
    for row in bundle["mapping"]["cases"]:
        assert row["canonical_id"] not in visible
        assert row["document"] not in visible
        assert row["author_label"] not in bundle["isolated"]["inputs.jsonl"]
    records = [json.loads(line) for line in bundle["isolated"]["inputs.jsonl"].splitlines()]
    assert [set(record) for record in records] == [
        {"evaluation_id", "claim", "passage_id", "passage"}
    ] * len(records)
    assert "author_label" not in bundle["isolated"]["prompt.txt"]
    assert CANONICAL_ID_RE.search(bundle["isolated"]["prompt.txt"]) is None


def test_evaluation_ids_do_not_encode_the_class_label():
    bundle = _bundle()
    labels = {row["evaluation_id"]: row["author_label"] for row in bundle["mapping"]["cases"]}
    assert set(labels.values()) == set(CLASSES)
    for evaluation_id, label in labels.items():
        assert re.fullmatch(r"ev-[0-9a-f]{12}", evaluation_id)
        assert _suffix_label(evaluation_id) is None
        assert label not in evaluation_id
    groups = defaultdict(list)
    for evaluation_id, label in labels.items():
        groups[evaluation_id[-1]].append(label)
    correct = 0
    for evaluation_id, label in labels.items():
        majority = Counter(groups[evaluation_id[-1]]).most_common(1)[0][0]
        correct += majority == label
    assert correct < len(labels)


def test_order_does_not_reconstruct_the_three_case_pattern():
    bundle = _bundle()
    rows = bundle["public_rows"]
    labels = [row["author_label"] for row in rows]
    documents = [row["document"] for row in rows]
    assert labels != [LABEL_CYCLE[i % 3] for i in range(len(labels))]
    assert not any(documents[i] == documents[i + 1] == documents[i + 2] for i in range(len(documents) - 2))
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["document"], []).append(row["canonical_id"])
    assert all(len(ids) == 3 and ids != sorted(ids) for ids in grouped.values())
    order_hits = sum(label == LABEL_CYCLE[i % 3] for i, label in enumerate(labels))
    assert order_hits / len(labels) < 0.5


def test_shuffle_preserves_the_claim_set():
    bundle = _bundle()
    reviews = _queue()
    exported = [json.loads(line)["claim"] for line in bundle["isolated"]["inputs.jsonl"].splitlines()]
    assert exported != [row["claim"] for row in reviews]
    assert sorted(exported) == sorted(row["claim"] for row in reviews)
    assert len(exported) == len(set(exported)) == 108


def test_prompts_and_paths_omit_ai_answers():
    bundle = _bundle()
    visible = "\n".join(bundle["isolated"].values()) + "\n" + "\n".join(bundle["human"].values())
    annotation_dir = CANDIDATES / "ai_second_opinion"
    reasons = []
    for path in annotation_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for result in payload.get("results", []):
            reasons.append(result["reason_zh"])
            assert result["case_id"] not in visible
    assert reasons
    for reason in reasons:
        assert reason not in visible
    for name in bundle["isolated"]:
        assert CANONICAL_ID_RE.search(name) is None
        assert "d0" not in name
    assert_human_tree_from_bundle(bundle)


def assert_human_tree_from_bundle(bundle):
    assert "ai_verdict" not in "\n".join(bundle["human"].values())
    assert "author_label" not in "\n".join(bundle["human"].values())


def test_suffix_baseline_fails_on_evaluation_ids():
    bundle = _bundle()
    canonical_hits = [
        _suffix_label(row["canonical_id"]) == row["author_label"] for row in bundle["mapping"]["cases"]
    ]
    assert all(canonical_hits)
    blinded_predictions = [_suffix_label(row["evaluation_id"]) for row in bundle["mapping"]["cases"]]
    assert blinded_predictions == [None] * len(blinded_predictions)
    scored = [prediction == row["author_label"] for prediction, row in zip(
        blinded_predictions, bundle["mapping"]["cases"], strict=True,
    )]
    assert not any(scored)


def test_reconciliation_requires_the_audit_mapping():
    bundle = _bundle()
    visible_ids = [json.loads(line)["evaluation_id"] for line in bundle["isolated"]["inputs.jsonl"].splitlines()]
    assert "canonical_id" not in bundle["isolated"]["inputs.jsonl"]
    with pytest.raises(ValueError, match="audit mapping"):
        reconcile([{"evaluation_id": visible_ids[0], "verdict": "supported"}], {})
    predictions = [
        {"evaluation_id": row["evaluation_id"], "verdict": "insufficient"}
        for row in bundle["mapping"]["cases"][:2]
    ]
    resolved = reconcile(predictions, bundle["mapping"])
    assert [row["canonical_id"] for row in resolved] == [
        bundle["mapping"]["cases"][0]["canonical_id"],
        bundle["mapping"]["cases"][1]["canonical_id"],
    ]
    with pytest.raises(ValueError, match="answer-key"):
        reconcile([{
            "evaluation_id": visible_ids[0],
            "verdict": "supported",
            "author_label": "supported",
        }], bundle["mapping"])


def test_human_packet_hides_answers_and_records_no_decisions(tmp_path):
    bundle = _bundle()
    human_dir = tmp_path / "human"
    human_dir.mkdir()
    for name, text in bundle["human"].items():
        (human_dir / name).write_text(text, encoding="utf-8")
    assert_human_tree(human_dir)
    packet = [json.loads(line) for line in bundle["human"]["calibration_packet.jsonl"].splitlines()]
    assert len(packet) == 30
    assert [set(row) for row in packet] == [{"packet_id", "claim", "passage_id", "passage"}] * 30
    mapping = bundle["calibration_mapping"]["cases"]
    assert sorted(row["author_label"] for row in mapping) == ["contradicted"] * 10 + ["insufficient"] * 10 + ["supported"] * 10
    categories = {row["category"] for row in mapping}
    assert {"temporal_boundary", "scope_equivalence", "comparison", "arithmetic", "absence"} <= categories
    priority = {row["canonical_id"] for row in mapping}
    assert {"cl-016-1", "cl-029-1"} <= priority
    sheets = []
    for name in ("response_sheet_A.csv", "response_sheet_B.csv"):
        rows = list(csv.DictReader(bundle["human"][name].splitlines()))
        assert len(rows) == 30
        assert [row["packet_id"] for row in rows] == [row["packet_id"] for row in packet]
        assert all(row["reviewed_label"] == "" and row["reviewer_id"] == "" for row in rows)
        sheets.extend(rows)
    assert {row["reviewer_slot"] for row in sheets} == {"A", "B"}
    summary = inter_annotator_agreement(sheets)
    assert summary["paired_cases"] == 0
    assert summary["raw_agreement"] is None
    assert summary["disagreements"] == []
    assert summary["human_reviewed_rows"] == 0
    filled = [dict(row) for row in sheets if row["reviewer_slot"] == "A"][:1]
    filled[0]["reviewed_label"] = "supported"
    other = [dict(row) for row in sheets if row["reviewer_slot"] == "B" and row["packet_id"] == filled[0]["packet_id"]]
    other[0]["reviewed_label"] = "insufficient"
    scored = inter_annotator_agreement(filled + other)
    assert scored["disagreements"]
    assert scored["human_reviewed_rows"] == 0
    assert bundle["human"]["adjudication_log.csv"].count("\n") == 1


def test_protocol_versions_the_export_and_refuses_an_in_repo_agent_dir(tmp_path):
    bundle = _bundle()
    protocol = bundle["protocol"]
    prose = (ROOT / "benchmark" / "evaluation" / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "claimledger.evaluation_export.v1" in prose
    assert "does not create an independent external test set" in prose
    assert "publicly readable" in prose
    assert "not an operating-system sandbox" in prose
    assert protocol["audit_mapping_is_access_controlled"] is False
    assert protocol["agent_directory_is_os_sandbox"] is False
    assert protocol["audit_mapping_access"] == "committed_in_the_public_repository"
    assert "private_mapping" not in protocol
    assert "sandbox" in bundle["isolated"]["BOUNDARY.txt"].lower()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "benchmark/evaluation/audit" not in gitignore
    assert protocol["protocol_version"] == "claimledger.evaluation_export.v1"
    assert protocol["prompt_version"] == "claimledger.inference_prompt.v1"
    assert protocol["randomization_seed"] == SEED
    assert protocol["human_packet_seed"] == HUMAN_PACKET_SEED
    assert protocol["creates_external_blind_test"] is False
    assert protocol["evaluator"]["paid_inference"] is False
    assert protocol["evaluator"]["runs_completed"] == 0
    assert set(protocol["result_classes"]) == {
        "synthetic_author_label_smoke",
        "ai_second_opinion",
        "human_reviewed_development",
        "internal_label_blinded_test",
        "independent_external_test",
    }
    assert "not" in protocol["result_classes"]["independent_external_test"].lower() or \
        "Not available" in protocol["result_classes"]["independent_external_test"]
    prepare_agent_view(tmp_path / "agent", ROOT, bundle)
    assert_isolated_tree(tmp_path / "agent")
    with pytest.raises(ValueError, match="outside the repository"):
        prepare_agent_view(ROOT / "output" / "agent-view", ROOT, bundle)


def test_committed_export_matches_the_generator():
    assert committed_files_match(ROOT, _bundle())
    assert_isolated_tree(ROOT / "benchmark" / "evaluation" / "isolated")
    assert_human_tree(ROOT / "benchmark" / "evaluation" / "human_review")


def test_same_seed_is_deterministic():
    first = _bundle()["isolated"]["inputs.jsonl"]
    second = _bundle()["isolated"]["inputs.jsonl"]
    assert first == second
