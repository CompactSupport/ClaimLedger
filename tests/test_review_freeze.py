import csv
import json
from pathlib import Path

import pytest

from claimledger.review import GOLD_READY_MIN_CASES, freeze_reviews, locate_unique_quote


def _write_queue(path: Path, rows: list[dict]) -> None:
    fields = [
        "id", "scenario", "category", "document", "claim", "expected", "reviewed_label",
        "evidence_quote", "label_origin", "human_reviewed", "reviewer", "reviewed_at", "review_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _row(**overrides) -> dict:
    row = {
        "id": "cl-901-1",
        "scenario": "901",
        "category": "numeric",
        "document": "note.md",
        "claim": "The sample count is 4.",
        "expected": "supported",
        "reviewed_label": "",
        "evidence_quote": "The sample count is 4.",
        "label_origin": "synthetic_author_labeled",
        "human_reviewed": "False",
        "reviewer": "",
        "reviewed_at": "",
        "review_notes": "",
    }
    row.update(overrides)
    return row


def test_unreviewed_rows_do_not_create_gold(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row()])
    frozen = freeze_reviews(queue)
    assert frozen["reviewed_case_count"] == 0
    assert frozen["reviewed_subset_available"] is False
    assert frozen["eligible_for_final_approval"] is False
    assert frozen["gold_benchmark_released"] is False
    assert frozen["independence_verified"] is False
    assert frozen["cases"] == []


def test_reviewed_label_is_frozen_with_exact_span(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("Prefix. The sample count is 4. Suffix.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row(
        human_reviewed="True",
        reviewed_label="contradicted",
        reviewer="ada",
        reviewed_at="2026-10-17T00:00:00Z",
    )])
    frozen = freeze_reviews(queue)
    assert frozen["reviewed_case_count"] == 1
    assert frozen["reviewed_subset_available"] is True
    assert frozen["eligible_for_final_approval"] is False
    assert frozen["gold_benchmark_released"] is False
    case = frozen["cases"][0]
    assert case["author_label"] == "supported"
    assert case["reviewed_label"] == "contradicted"
    start, end = case["evidence"]["start"], case["evidence"]["end"]
    assert note.read_text(encoding="utf-8")[start:end] == "The sample count is 4."
    again = freeze_reviews(queue, existing=frozen)
    assert again == frozen


def test_frozen_case_cannot_change_its_span(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row(
        human_reviewed="True",
        reviewed_label="supported",
        reviewer="ada",
        reviewed_at="2026-10-17T00:00:00Z",
    )])
    frozen = freeze_reviews(queue)
    changed = json.loads(json.dumps(frozen))
    changed["cases"][0]["evidence"]["end"] += 1
    with pytest.raises(ValueError, match="span"):
        freeze_reviews(queue, existing=changed)


def test_author_label_is_not_copied_when_review_label_is_missing(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row(human_reviewed="True", reviewer="ada", reviewed_at="2026-10-17")])
    with pytest.raises(ValueError, match="reviewed_label"):
        freeze_reviews(queue)


def _criteria(root: Path) -> dict:
    document = root / "QUALITY_CRITERIA.md"
    document.write_text("version: criteria-1\nReviewed cases need a separate approval.\n", encoding="utf-8")
    import hashlib
    return {
        "independence_attested": True,
        "criteria_document": "QUALITY_CRITERIA.md",
        "criteria_version": "criteria-1",
        "criteria_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
    }


def test_counts_do_not_release_a_gold_benchmark(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    criteria = _criteria(tmp_path)
    for count, subset, eligible in (
        (0, False, False),
        (1, True, False),
        (99, True, False),
        (GOLD_READY_MIN_CASES, True, True),
    ):
        rows = [_row(
            id=f"cl-800-{index}",
            claim=f"Claim number {index}.",
            evidence_quote="The sample count is 4.",
            human_reviewed="True",
            reviewed_label="supported",
            reviewer="ada",
            reviewed_at="2026-10-17",
        ) for index in range(count)]
        queue = tmp_path / f"queue-{count}.csv"
        _write_queue(queue, rows)
        frozen = freeze_reviews(
            queue,
            quality_criteria=criteria if count == GOLD_READY_MIN_CASES else None,
            criteria_root=tmp_path,
            dataset_version="candidates-test",
        )
        assert frozen["reviewed_case_count"] == count
        assert frozen["reviewed_subset_available"] is subset
        assert frozen["eligible_for_final_approval"] is eligible
        assert frozen["gold_benchmark_released"] is False
        assert frozen["independence_verified"] is False


def test_duplicate_claims_cannot_inflate_the_reviewed_count(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    rows = [_row(
        id=f"cl-dup-{index}",
        human_reviewed="True",
        reviewed_label="supported",
        reviewer="ada",
        reviewed_at="2026-10-17",
    ) for index in range(100)]
    queue = tmp_path / "duplicates.csv"
    _write_queue(queue, rows)
    with pytest.raises(ValueError, match="Duplicate document-claim"):
        freeze_reviews(queue, dataset_version="candidates-test")


def test_forged_reviewer_metadata_is_not_verification(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "forged.csv"
    _write_queue(queue, [_row(
        human_reviewed="True",
        reviewed_label="supported",
        reviewer="forged-reviewer",
        reviewed_at="2026-10-17",
    )])
    frozen = freeze_reviews(queue, dataset_version="candidates-test")
    assert frozen["independence_attestation_recorded"] is False
    assert frozen["independence_verified"] is False
    assert frozen["eligible_for_final_approval"] is False
    assert frozen["gold_benchmark_released"] is False


def test_missing_criteria_document_blocks_approval(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    rows = [_row(
        id=f"cl-801-{index}",
        claim=f"Distinct claim {index}.",
        human_reviewed="True",
        reviewed_label="supported",
        reviewer="ada",
        reviewed_at="2026-10-17",
    ) for index in range(GOLD_READY_MIN_CASES)]
    queue = tmp_path / "missing-criteria.csv"
    _write_queue(queue, rows)
    frozen = freeze_reviews(
        queue,
        quality_criteria={
            "independence_attested": True,
            "criteria_document": "missing.md",
            "criteria_version": "criteria-1",
            "criteria_sha256": "0" * 64,
        },
        criteria_root=tmp_path,
        dataset_version="candidates-test",
    )
    assert frozen["reviewed_case_count"] == 100
    assert frozen["eligible_for_final_approval"] is False
    assert frozen["gold_benchmark_released"] is False


def test_modified_source_document_cannot_be_refrozen(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row(
        human_reviewed="True",
        reviewed_label="supported",
        reviewer="ada",
        reviewed_at="2026-10-17",
    )])
    frozen = freeze_reviews(queue, dataset_version="candidates-test")
    note.write_text("The sample count is 4.\nEdited after review.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        freeze_reviews(queue, existing=frozen, dataset_version="candidates-test")


def test_quote_span_must_be_unique():
    with pytest.raises(ValueError, match="more than once"):
        locate_unique_quote("alpha alpha", "alpha")


def test_document_path_cannot_escape(tmp_path: Path):
    outside = tmp_path / "secret.md"
    outside.write_text("secret\n", encoding="utf-8")
    queue_dir = tmp_path / "bench"
    queue_dir.mkdir()
    queue = queue_dir / "review_queue.csv"
    _write_queue(queue, [_row(
        document="../secret.md",
        human_reviewed="True",
        reviewed_label="supported",
        evidence_quote="secret",
        reviewer="ada",
        reviewed_at="2026-10-17",
    )])
    with pytest.raises(ValueError, match="escapes"):
        freeze_reviews(queue)
