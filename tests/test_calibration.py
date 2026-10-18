"""Human calibration validation. Fixtures stay in temporary files."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from claimledger.calibration import (
    ImportRefused,
    adjudication_digest,
    apply_plan,
    plan_queue_import,
    report_for_repository,
    validate_sheets,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "benchmark" / "candidates"
EVALUATION = ROOT / "benchmark" / "evaluation"
QUEUE = CANDIDATES / "review_queue.csv"


def _packet() -> list[dict]:
    return [
        json.loads(line)
        for line in (EVALUATION / "human_review" / "calibration_packet.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sources():
    manifest = json.loads((CANDIDATES / "manifest.json").read_text(encoding="utf-8"))
    mapping = json.loads((EVALUATION / "audit" / "calibration_mapping.json").read_text(encoding="utf-8"))
    documents = {
        name: (CANDIDATES / "documents" / name).read_bytes()
        for name in manifest["document_sha256"]
    }
    return manifest["document_sha256"], mapping["cases"], documents


def _sheet(rows: list[dict]) -> list[dict]:
    return rows


def _review(packet_row: dict, slot: str, reviewer: str, label: str, *, quote: bool) -> dict:
    passage = packet_row["passage"]
    if quote:
        start, end = 0, min(12, len(passage.strip()))
        snippet = passage[start:end]
    else:
        start, end, snippet = "", "", ""
    return {
        "packet_id": packet_row["packet_id"],
        "reviewer_slot": slot,
        "reviewer_id": reviewer,
        "reviewed_at": "2026-10-17T18:00:00+00:00",
        "reviewed_label": label,
        "evidence_start": str(start) if quote else "",
        "evidence_end": str(end) if quote else "",
        "evidence_quote": snippet,
        "notes": "",
    }


def test_empty_sheets_have_no_agreement_and_do_not_touch_the_queue():
    before = QUEUE.read_bytes()
    report = report_for_repository(ROOT)
    assert report["paired_cases"] == 0
    assert report["cohen_kappa"] is None
    assert report["disagreements"] == []
    assert report["queue_updated"] is False
    assert report["gold_benchmark_released"] is False
    assert report["human_reviewed_rows"] == 0
    assert report["uses_ai_annotations_as_human_review"] is False
    assert QUEUE.read_bytes() == before


def test_paired_reviews_report_kappa_and_keep_disagreements():
    packet = _packet()[:4]
    hashes, mapping, documents = _sources()
    labels_a = ["supported", "supported", "contradicted", "insufficient"]
    labels_b = ["supported", "contradicted", "contradicted", "insufficient"]
    sheet_a = [
        _review(row, "A", "ada-lane", label, quote=label != "insufficient")
        for row, label in zip(packet, labels_a, strict=True)
    ]
    sheet_b = [
        _review(row, "B", "bea-lane", label, quote=label != "insufficient")
        for row, label in zip(packet, labels_b, strict=True)
    ]
    report = validate_sheets(packet, sheet_a, sheet_b, mapping, hashes, documents)
    assert report["paired_cases"] == 4
    assert report["raw_agreement"] == 0.75
    assert report["cohen_kappa"] == pytest.approx(0.6363636363636364)
    assert len(report["disagreements"]) == 1
    assert report["disagreements"][0]["adjudicated_label"] is None
    assert report["import_applied"] is False
    assert "author_label" not in json.dumps(report)


def test_invalid_reviews_are_rejected_and_not_counted_as_human():
    packet = _packet()
    hashes, mapping, documents = _sources()
    first = packet[0]
    ai_row = _review(first, "A", "gpt-reviewer", "supported", quote=True)
    duplicate = _review(first, "A", "ada-lane", "supported", quote=True)
    bad_span = _review(packet[1], "A", "ada-lane", "supported", quote=True)
    bad_span["evidence_quote"] = "not in the passage"
    missing_zone = _review(packet[2], "A", "ada-lane", "insufficient", quote=False)
    missing_zone["reviewed_at"] = "2026-10-17T18:00:00"
    unknown = _review(packet[3], "A", "ada-lane", "insufficient", quote=False)
    unknown["packet_id"] = "hr-not-a-real-packet"
    same_person_a = _review(packet[4], "A", "ada-lane", "insufficient", quote=False)
    same_person_b = _review(packet[4], "B", "ada-lane", "insufficient", quote=False)
    report = validate_sheets(
        packet,
        [ai_row, duplicate, duplicate, bad_span, missing_zone, unknown, same_person_a],
        [same_person_b],
        mapping,
        hashes,
        documents,
    )
    codes = {row["code"] for row in report["errors"]}
    assert "not_independent_human" in codes
    assert "duplicate_submission" in codes
    assert "invalid_submission" in codes
    assert "unknown_packet" in codes
    assert "reviewers_not_independent" in codes
    assert report["ai_submissions_rejected"] == 1
    assert report["cohen_kappa"] is None
    assert report["human_reviewed_rows"] == 0


def _queue_rows() -> list[dict]:
    with QUEUE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _dataset_version() -> str:
    return json.loads((CANDIDATES / "manifest.json").read_text(encoding="utf-8"))["dataset_version"]


def _approval(adjudications: list[dict], version: str, **overrides) -> dict:
    approval = {
        "decision": "approved_for_queue_import",
        "approver": "cy-lane",
        "approved_at": "2026-10-17T20:00:00+00:00",
        "approval_id": "import-1",
        "dataset_version": version,
        "adjudication_sha256": adjudication_digest(adjudications),
    }
    approval.update(overrides)
    return approval


def _import_kwargs(documents=None):
    hashes, _mapping, loaded = _sources()
    return {
        "validated_pairs": [],
        "queue_rows": _queue_rows(),
        "dataset_version": _dataset_version(),
        "documents": loaded if documents is None else documents,
        "manifest_hashes": hashes,
    }


def test_fabricated_adjudication_cannot_become_human_reviewed():
    before = QUEUE.read_bytes()
    rows = _queue_rows()
    version = _dataset_version()
    fake = [{
        "packet_id": "hr-fabricated",
        "canonical_id": rows[0]["id"],
        "claim": rows[0]["claim"],
        "dataset_version": version,
        "document_sha256": "abc",
        "passage_sha256": "def",
        "adjudicated_label": "supported",
        "evidence_quote": "x",
        "evidence_start": "0",
        "evidence_end": "1",
        "adjudicator": "cy-lane",
        "adjudicated_at": "2026-10-17T19:00:00+00:00",
        "reviewer_a_id": "ada-lane",
        "reviewer_b_id": "bea-lane",
        "reviewer_a_label": "supported",
        "reviewer_b_label": "supported",
        "reviewer_a_reviewed_at": "2026-10-17T18:00:00+00:00",
        "reviewer_b_reviewed_at": "2026-10-17T18:00:00+00:00",
    }]
    with pytest.raises(ImportRefused, match="two distinct validated human submissions"):
        plan_queue_import(fake, _approval(fake, version), **_import_kwargs())
    forged_plan = {
        "approved": True,
        "provenance_verified": False,
        "rows": [{
            "canonical_id": rows[0]["id"],
            "adjudicated_label": "supported",
            "adjudicator": "cy-lane",
            "adjudicated_at": "2026-10-17T19:00:00+00:00",
            "tied_to_validated_submissions": True,
        }],
        "adjudication_sha256": "0" * 64,
        "dataset_version": version,
        "queue_write": False,
    }
    with pytest.raises(ImportRefused, match="fabricated"):
        apply_plan(rows, forged_plan, write_action={
            "decision": "approved_queue_write",
            "adjudication_sha256": "0" * 64,
            "dataset_version": version,
        })
    assert all(row["human_reviewed"] == "False" for row in rows)
    assert QUEUE.read_bytes() == before


def test_proven_import_preserves_the_author_label_and_stays_unwritten():
    before = QUEUE.read_bytes()
    packet = _packet()[:1]
    hashes, mapping, documents = _sources()
    version = _dataset_version()
    sheet_a = [_review(packet[0], "A", "ada-lane", "supported", quote=True)]
    sheet_b = [_review(packet[0], "B", "bea-lane", "supported", quote=True)]
    report = validate_sheets(packet, sheet_a, sheet_b, mapping, hashes, documents)
    pair = report["validated_pairs"][0]
    passage = packet[0]["passage"]
    end = min(12, len(passage.strip()))
    adjudication = [{
        "packet_id": pair["packet_id"],
        "canonical_id": pair["canonical_id"],
        "claim": pair["claim"],
        "dataset_version": version,
        "document_sha256": pair["document_sha256"],
        "passage_sha256": pair["passage_sha256"],
        "adjudicated_label": "supported",
        "evidence_quote": passage[:end],
        "evidence_start": "0",
        "evidence_end": str(end),
        "adjudicator": "cy-lane",
        "adjudicated_at": "2026-10-17T19:00:00+00:00",
        "reviewer_a_id": pair["reviewer_a"],
        "reviewer_b_id": pair["reviewer_b"],
        "reviewer_a_label": pair["label_a"],
        "reviewer_b_label": pair["label_b"],
        "reviewer_a_reviewed_at": pair["reviewed_at_a"],
        "reviewer_b_reviewed_at": pair["reviewed_at_b"],
    }]
    kwargs = {
        "validated_pairs": report["validated_pairs"],
        "queue_rows": _queue_rows(),
        "dataset_version": version,
        "documents": documents,
        "manifest_hashes": hashes,
    }
    plan = plan_queue_import(adjudication, _approval(adjudication, version), **kwargs)
    assert plan["provenance_verified"] is True
    assert plan["queue_write"] is False
    assert plan["reviewer_name_proves_identity"] is False
    assert plan["independence_verified"] is False
    assert plan["gold_benchmark_released"] is False
    with pytest.raises(ImportRefused, match="separate write"):
        apply_plan(kwargs["queue_rows"], plan)
    updated = apply_plan(kwargs["queue_rows"], plan, write_action={
        "decision": "approved_queue_write",
        "adjudication_sha256": plan["adjudication_sha256"],
        "dataset_version": version,
    })
    changed = next(row for row in updated if row["id"] == pair["canonical_id"])
    original = next(row for row in kwargs["queue_rows"] if row["id"] == pair["canonical_id"])
    assert changed["expected"] == original["expected"]
    assert changed["reviewed_label"] == "supported"
    assert changed["human_reviewed"] == "True"
    assert QUEUE.read_bytes() == before
    forged = [dict(adjudication[0], reviewer_a_id="forged-person")]
    with pytest.raises(ImportRefused, match="reviewer metadata"):
        plan_queue_import(forged, _approval(forged, version), **kwargs)
    stale = {name: (b"\x00" + blob[1:] if blob else b"\x00") for name, blob in documents.items()}
    with pytest.raises(ImportRefused, match="hash"):
        plan_queue_import(adjudication, _approval(adjudication, version), **{**kwargs, "documents": stale})
    mismatched = _approval(adjudication, version, adjudication_sha256="0" * 64)
    with pytest.raises(ImportRefused, match="adjudication artifact"):
        plan_queue_import(adjudication, mismatched, **kwargs)
    incomplete = [dict(adjudication[0])]
    del incomplete[0]["evidence_end"]
    with pytest.raises(ImportRefused, match="incomplete"):
        plan_queue_import(incomplete, _approval(incomplete, version), **kwargs)
