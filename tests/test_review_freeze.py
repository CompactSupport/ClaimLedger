import csv
import json
from pathlib import Path

import pytest

from claimledger.review import freeze_reviews, locate_unique_quote


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
    assert frozen["gold_count"] == 0
    assert frozen["cases"] == []
    assert frozen["gold_benchmark"] is False


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
    assert frozen["gold_count"] == 1
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
    with pytest.raises(ValueError, match="immutable"):
        freeze_reviews(queue, existing=changed)


def test_author_label_is_not_copied_when_review_label_is_missing(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("The sample count is 4.\n", encoding="utf-8")
    queue = tmp_path / "review_queue.csv"
    _write_queue(queue, [_row(human_reviewed="True", reviewer="ada", reviewed_at="2026-10-17")])
    with pytest.raises(ValueError, match="reviewed_label"):
        freeze_reviews(queue)


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
