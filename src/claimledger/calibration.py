"""Validate label-blind human calibration sheets.

This module does not invent reviews, does not treat an AI note as a human
review, and does not write the canonical review queue.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .label_blind import CLASSES, permitted_passage

REPORT_SCHEMA = "claimledger.calibration_report.v1"
IMPORT_DECISION = "approved_for_queue_import"
AI_REVIEWER_RE = re.compile(
    r"(?i)(?:^|[^a-z])(ai|gpt|codex|claude|gemini|openai|llm|model)(?:[^a-z]|$)"
)


class CalibrationError(ValueError):
    """A calibration sheet or import request failed a check."""


class ImportRefused(CalibrationError):
    """Raised when adjudicated labels are not approved for queue import."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CalibrationError("Timestamp is not ISO-8601.") from exc
    if parsed.tzinfo is None:
        raise CalibrationError("Timestamp needs a timezone.")
    return parsed


def _is_blank(row: dict) -> bool:
    fields = (
        "reviewer_id", "reviewed_at", "reviewed_label",
        "evidence_start", "evidence_end", "evidence_quote", "notes",
    )
    return all(not (row.get(field) or "").strip() for field in fields)


def _check_span(passage: str, row: dict) -> None:
    label = row["reviewed_label"]
    start_text = (row.get("evidence_start") or "").strip()
    end_text = (row.get("evidence_end") or "").strip()
    quote = row.get("evidence_quote") or ""
    if label == "insufficient" and start_text == "" and end_text == "" and quote == "":
        return
    if start_text == "" or end_text == "":
        raise CalibrationError("Evidence span is missing.")
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise CalibrationError("Evidence span is not an integer.") from exc
    if start < 0 or end < start or end > len(passage):
        raise CalibrationError("Evidence span is outside the passage.")
    if passage[start:end] != quote or quote == "":
        raise CalibrationError("Evidence quote does not match the passage span.")


def _validate_row(row: dict, passage: str, slot: str) -> dict:
    if row.get("reviewer_slot") not in {slot, "", None} and row.get("reviewer_slot") != slot:
        raise CalibrationError("Reviewer slot does not match the sheet.")
    reviewer_id = (row.get("reviewer_id") or "").strip()
    if not reviewer_id:
        raise CalibrationError("Reviewer id is missing.")
    if AI_REVIEWER_RE.search(reviewer_id):
        raise CalibrationError("An AI identity is not an independent human review.")
    _parse_timestamp(row.get("reviewed_at") or "")
    label = (row.get("reviewed_label") or "").strip()
    if label not in CLASSES:
        raise CalibrationError("Review label is not one of the three classes.")
    checked = dict(row)
    checked["reviewer_slot"] = slot
    checked["reviewer_id"] = reviewer_id
    checked["reviewed_label"] = label
    _check_span(passage, checked)
    return checked


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    """Return Cohen's kappa, or None when there are no pairs or no variation."""
    if len(labels_a) != len(labels_b) or not labels_a:
        return None
    count = len(labels_a)
    observed = sum(left == right for left, right in zip(labels_a, labels_b, strict=True)) / count
    expected = 0.0
    for label in CLASSES:
        expected += (labels_a.count(label) / count) * (labels_b.count(label) / count)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def _index_sources(packet_rows: list[dict], mapping_cases: list[dict],
                   manifest_hashes: dict[str, str], documents: dict[str, bytes]) -> dict[str, dict]:
    by_hash = {}
    for name, digest in manifest_hashes.items():
        if digest in by_hash:
            raise CalibrationError(f"Document hash is not unique: {name}")
        by_hash[digest] = name
    mapping = {row["packet_id"]: row for row in mapping_cases}
    sources = {}
    for row in packet_rows:
        packet_id = row["packet_id"]
        joined = mapping.get(packet_id)
        if joined is None:
            raise CalibrationError(f"Packet id is not in the audit mapping: {packet_id}")
        digest = joined["document_sha256"]
        filename = by_hash.get(digest)
        if filename is None or filename not in documents:
            raise CalibrationError(f"Source hash is not in the current documents: {packet_id}")
        raw = documents[filename]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise CalibrationError(f"Source hash does not match the file bytes: {filename}")
        passage = permitted_passage(raw.decode("utf-8"))
        if passage != row["passage"]:
            raise CalibrationError(f"Packet passage does not match the source file: {packet_id}")
        sources[packet_id] = {
            "passage": passage,
            "passage_sha256": _sha256(passage),
            "document_sha256": digest,
            "claim": row["claim"],
        }
    return sources


def _sheet_rows(rows: list[dict], slot: str, sources: dict[str, dict]) -> tuple[dict[str, dict], list[dict]]:
    accepted: dict[str, dict] = {}
    errors = []
    seen: set[str] = set()
    for row in rows:
        packet_id = (row.get("packet_id") or "").strip()
        if _is_blank(row):
            continue
        if packet_id in seen:
            errors.append({
                "packet_id": packet_id,
                "reviewer_slot": slot,
                "code": "duplicate_submission",
                "message": "The same packet id appears twice on one sheet.",
            })
            accepted.pop(packet_id, None)
            continue
        seen.add(packet_id)
        source = sources.get(packet_id)
        if source is None:
            errors.append({
                "packet_id": packet_id,
                "reviewer_slot": slot,
                "code": "unknown_packet",
                "message": "Packet id is not in the calibration packet.",
            })
            continue
        try:
            checked = _validate_row(row, source["passage"], slot)
        except CalibrationError as exc:
            code = "not_independent_human" if "AI identity" in str(exc) else "invalid_submission"
            errors.append({
                "packet_id": packet_id,
                "reviewer_slot": slot,
                "code": code,
                "message": str(exc),
            })
            continue
        checked["passage_sha256"] = source["passage_sha256"]
        checked["document_sha256"] = source["document_sha256"]
        accepted[packet_id] = checked
    return accepted, errors


def validate_sheets(packet_rows: list[dict], sheet_a: list[dict], sheet_b: list[dict],
                    mapping_cases: list[dict], manifest_hashes: dict[str, str],
                    documents: dict[str, bytes]) -> dict:
    """Validate reviewer sheets. Author labels are not an input."""
    sources = _index_sources(packet_rows, mapping_cases, manifest_hashes, documents)
    accepted_a, errors_a = _sheet_rows(sheet_a, "A", sources)
    accepted_b, errors_b = _sheet_rows(sheet_b, "B", sources)
    errors = errors_a + errors_b
    pairs = []
    disagreements = []
    for packet_id in sorted(set(accepted_a) & set(accepted_b)):
        left = accepted_a[packet_id]
        right = accepted_b[packet_id]
        if left["reviewer_id"] == right["reviewer_id"]:
            errors.append({
                "packet_id": packet_id,
                "reviewer_slot": "A+B",
                "code": "reviewers_not_independent",
                "message": "The same reviewer id appears on both sheets.",
            })
            continue
        pair = {
            "packet_id": packet_id,
            "reviewer_a": left["reviewer_id"],
            "reviewer_b": right["reviewer_id"],
            "label_a": left["reviewed_label"],
            "label_b": right["reviewed_label"],
            "passage_sha256": left["passage_sha256"],
            "document_sha256": left["document_sha256"],
            "agree": left["reviewed_label"] == right["reviewed_label"],
        }
        pairs.append(pair)
        if not pair["agree"]:
            disagreements.append({
                **pair,
                "adjudicated_label": None,
                "adjudicator": None,
                "adjudicated_at": None,
            })
    labels_a = [pair["label_a"] for pair in pairs]
    labels_b = [pair["label_b"] for pair in pairs]
    observed = None
    if pairs:
        observed = sum(pair["agree"] for pair in pairs) / len(pairs)
    return {
        "schema": REPORT_SCHEMA,
        "submissions": len(accepted_a) + len(accepted_b) + len(errors),
        "valid_submissions": len(accepted_a) + len(accepted_b),
        "paired_cases": len(pairs),
        "raw_agreement": observed,
        "cohen_kappa": cohen_kappa(labels_a, labels_b),
        "disagreements": disagreements,
        "errors": errors,
        "ai_submissions_rejected": sum(row["code"] == "not_independent_human" for row in errors),
        "import_applied": False,
        "queue_updated": False,
        "gold_benchmark_released": False,
        "human_reviewed_rows": 0,
        "uses_ai_annotations_as_human_review": False,
    }


def report_for_repository(root: Path) -> dict:
    """Validate the committed empty sheets. This does not write the review queue."""
    candidates = root / "benchmark" / "candidates"
    evaluation = root / "benchmark" / "evaluation"
    packet = [
        json.loads(line)
        for line in (evaluation / "human_review" / "calibration_packet.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mapping = json.loads((evaluation / "audit" / "calibration_mapping.json").read_text(encoding="utf-8"))
    manifest = json.loads((candidates / "manifest.json").read_text(encoding="utf-8"))
    documents = {
        name: (candidates / "documents" / name).read_bytes()
        for name in manifest["document_sha256"]
    }

    def rows(path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    return validate_sheets(
        packet,
        rows(evaluation / "human_review" / "response_sheet_A.csv"),
        rows(evaluation / "human_review" / "response_sheet_B.csv"),
        mapping["cases"],
        manifest["document_sha256"],
        documents,
    )


def plan_queue_import(adjudications: list[dict], approval: dict | None,
                      mapping_cases: list[dict]) -> dict:
    """Return an import plan. This function does not write a file."""
    if not approval or approval.get("decision") != IMPORT_DECISION:
        raise ImportRefused(
            "Adjudicated labels stay out of the canonical queue without an explicit import approval."
        )
    for field in ("approver", "approved_at", "approval_id"):
        if not (approval.get(field) or "").strip():
            raise ImportRefused("Import approval is missing approver, approved_at, or approval_id.")
    _parse_timestamp(approval["approved_at"])
    if AI_REVIEWER_RE.search(approval["approver"]):
        raise ImportRefused("An AI identity cannot approve a human-label import.")
    by_packet = {row["packet_id"]: row for row in mapping_cases}
    planned = []
    for row in adjudications:
        packet_id = row.get("packet_id")
        joined = by_packet.get(packet_id)
        if joined is None:
            raise ImportRefused(f"Adjudication packet id is unknown: {packet_id}")
        label = (row.get("adjudicated_label") or "").strip()
        adjudicator = (row.get("adjudicator") or "").strip()
        adjudicated_at = (row.get("adjudicated_at") or "").strip()
        if label not in CLASSES or not adjudicator or not adjudicated_at:
            raise ImportRefused("An adjudicated row needs a label, adjudicator, and timestamp.")
        if AI_REVIEWER_RE.search(adjudicator):
            raise ImportRefused("An AI identity cannot adjudicate a human review.")
        _parse_timestamp(adjudicated_at)
        planned.append({
            "packet_id": packet_id,
            "canonical_id": joined["canonical_id"],
            "adjudicated_label": label,
            "adjudicator": adjudicator,
            "adjudicated_at": adjudicated_at,
        })
    return {
        "approved": True,
        "approval_id": approval["approval_id"],
        "queue_write": False,
        "gold_benchmark_released": False,
        "rows": planned,
    }


def apply_plan(queue_rows: list[dict], plan: dict) -> list[dict]:
    """Return a new queue list. The caller has to write it; this does not."""
    if not plan.get("approved") or plan.get("queue_write") is not False:
        raise ImportRefused("Refusing a plan that was not created by the approval gate.")
    updates = {row["canonical_id"]: row for row in plan["rows"]}
    updated = []
    for row in queue_rows:
        copied = dict(row)
        change = updates.get(row["id"])
        if change is not None:
            copied["reviewed_label"] = change["adjudicated_label"]
            copied["human_reviewed"] = "True"
            copied["reviewer"] = change["adjudicator"]
            copied["reviewed_at"] = change["adjudicated_at"]
        updated.append(copied)
    return updated
