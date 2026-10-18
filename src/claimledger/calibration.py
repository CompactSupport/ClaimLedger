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
PLAN_SCHEMA = "claimledger.calibration_import_plan.v1"
IMPORT_DECISION = "approved_for_queue_import"
WRITE_DECISION = "approved_queue_write"
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
            "canonical_id": joined["canonical_id"],
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
        checked["claim"] = source["claim"]
        checked["canonical_id"] = source["canonical_id"]
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
            "canonical_id": left["canonical_id"],
            "claim": left["claim"],
            "reviewer_a": left["reviewer_id"],
            "reviewer_b": right["reviewer_id"],
            "label_a": left["reviewed_label"],
            "label_b": right["reviewed_label"],
            "reviewed_at_a": left["reviewed_at"],
            "reviewed_at_b": right["reviewed_at"],
            "evidence_quote_a": left.get("evidence_quote") or "",
            "evidence_quote_b": right.get("evidence_quote") or "",
            "evidence_start_a": left.get("evidence_start") or "",
            "evidence_end_a": left.get("evidence_end") or "",
            "evidence_start_b": left.get("evidence_start") or "",
            "evidence_end_b": left.get("evidence_end") or "",
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
        "reviewer_name_proves_identity": False,
        "independence_verified": False,
        "validated_pairs": pairs,
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


def adjudication_digest(adjudications: list[dict]) -> str:
    """Hash the adjudication records exactly as submitted."""
    payload = json.dumps(adjudications, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _field(row: dict, key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _require_complete(row: dict) -> None:
    required = (
        "packet_id", "canonical_id", "claim", "dataset_version", "document_sha256",
        "passage_sha256", "adjudicated_label", "adjudicator", "adjudicated_at",
        "reviewer_a_id", "reviewer_b_id", "reviewer_a_label", "reviewer_b_label",
        "reviewer_a_reviewed_at", "reviewer_b_reviewed_at",
    )
    missing = [key for key in required if not _field(row, key)]
    if missing or "evidence_quote" not in row or "evidence_start" not in row or "evidence_end" not in row:
        raise ImportRefused("Adjudication record is incomplete.")


def plan_queue_import(adjudications: list[dict], approval: dict | None, *,
                      validated_pairs: list[dict], queue_rows: list[dict],
                      dataset_version: str, documents: dict[str, bytes],
                      manifest_hashes: dict[str, str]) -> dict:
    """Plan an import only when each decision is tied to two validated human submissions.

    A reviewer name in this plan does not prove a real-world identity or independence.
    This function does not write the queue.
    """
    if not approval or approval.get("decision") != IMPORT_DECISION:
        raise ImportRefused(
            "Adjudicated labels stay out of the canonical queue without an explicit import approval."
        )
    for field in ("approver", "approved_at", "approval_id", "dataset_version", "adjudication_sha256"):
        if not _field(approval, field):
            raise ImportRefused("Import approval is missing approver, time, id, dataset version, or digest.")
    _parse_timestamp(approval["approved_at"])
    if AI_REVIEWER_RE.search(approval["approver"]):
        raise ImportRefused("An AI identity cannot approve a human-label import.")
    if approval["dataset_version"] != dataset_version:
        raise ImportRefused("Import approval is not bound to this dataset version.")
    digest = adjudication_digest(adjudications)
    if approval["adjudication_sha256"] != digest:
        raise ImportRefused("Import approval is not bound to this adjudication artifact.")
    by_hash = {}
    for name, file_hash in manifest_hashes.items():
        if file_hash in by_hash:
            raise ImportRefused(f"Document hash is not unique: {name}")
        by_hash[file_hash] = name
    pairs = {row["packet_id"]: row for row in validated_pairs}
    queue = {row["id"]: row for row in queue_rows}
    seen: set[str] = set()
    planned = []
    for row in adjudications:
        _require_complete(row)
        packet_id = _field(row, "packet_id")
        if packet_id in seen:
            raise ImportRefused("Adjudication packet id is duplicated.")
        seen.add(packet_id)
        pair = pairs.get(packet_id)
        if pair is None:
            raise ImportRefused(
                "Adjudication requires two distinct validated human submissions for this case."
            )
        if _field(row, "dataset_version") != dataset_version:
            raise ImportRefused("Adjudication dataset version is stale.")
        if _field(row, "canonical_id") != pair["canonical_id"]:
            raise ImportRefused("Adjudication canonical id does not match the validated submissions.")
        canonical = queue.get(pair["canonical_id"])
        if canonical is None or canonical["claim"] != _field(row, "claim") or pair["claim"] != canonical["claim"]:
            raise ImportRefused("Claim identity does not match the canonical queue.")
        if pair["reviewer_a"] == pair["reviewer_b"]:
            raise ImportRefused("The two human submissions are not distinct.")
        if (
            _field(row, "reviewer_a_id") != pair["reviewer_a"]
            or _field(row, "reviewer_b_id") != pair["reviewer_b"]
            or _field(row, "reviewer_a_label") != pair["label_a"]
            or _field(row, "reviewer_b_label") != pair["label_b"]
            or _field(row, "reviewer_a_reviewed_at") != pair["reviewed_at_a"].strip()
            or _field(row, "reviewer_b_reviewed_at") != pair["reviewed_at_b"].strip()
        ):
            raise ImportRefused("Adjudication reviewer metadata does not match the validated submissions.")
        if _field(row, "document_sha256") != pair["document_sha256"]:
            raise ImportRefused("Adjudication document hash does not match the validated submissions.")
        if _field(row, "passage_sha256") != pair["passage_sha256"]:
            raise ImportRefused("Adjudication passage hash does not match the validated submissions.")
        filename = by_hash.get(pair["document_sha256"])
        raw = documents.get(filename or "")
        if filename is None or raw is None or hashlib.sha256(raw).hexdigest() != pair["document_sha256"]:
            raise ImportRefused("Source document hash is stale or unknown.")
        passage = permitted_passage(raw.decode("utf-8"))
        if _sha256(passage) != pair["passage_sha256"]:
            raise ImportRefused("Passage hash is stale.")
        label = _field(row, "adjudicated_label")
        if label not in CLASSES:
            raise ImportRefused("Adjudicated label is not one of the three classes.")
        if pair["agree"] and label != pair["label_a"]:
            raise ImportRefused("The adjudicated label does not match the agreeing human submissions.")
        adjudicator = _field(row, "adjudicator")
        if AI_REVIEWER_RE.search(adjudicator):
            raise ImportRefused("An AI identity cannot adjudicate a human review.")
        adjudicated_at = _parse_timestamp(_field(row, "adjudicated_at"))
        if (
            adjudicated_at <= _parse_timestamp(pair["reviewed_at_a"])
            or adjudicated_at <= _parse_timestamp(pair["reviewed_at_b"])
        ):
            raise ImportRefused("Adjudication timestamp is not after both human submissions.")
        _check_span(passage, {
            "reviewed_label": label,
            "evidence_start": _field(row, "evidence_start"),
            "evidence_end": _field(row, "evidence_end"),
            "evidence_quote": row.get("evidence_quote") or "",
        })
        planned.append({
            "packet_id": packet_id,
            "canonical_id": pair["canonical_id"],
            "adjudicated_label": label,
            "adjudicator": adjudicator,
            "adjudicated_at": _field(row, "adjudicated_at"),
            "tied_to_validated_submissions": True,
            "evidence_quote": row.get("evidence_quote") or "",
            "review_notes": row.get("review_notes") or "",
        })
    return {
        "schema": PLAN_SCHEMA,
        "approved": True,
        "provenance_verified": True,
        "approval_id": approval["approval_id"],
        "dataset_version": dataset_version,
        "adjudication_sha256": digest,
        "queue_write": False,
        "gold_benchmark_released": False,
        "reviewer_name_proves_identity": False,
        "independence_verified": False,
        "rows": planned,
    }


def apply_plan(queue_rows: list[dict], plan: dict, *, write_action: dict | None = None) -> list[dict]:
    """Return a new queue list only after a separate write approval.

    The returned list is not written to disk. The author label in ``expected`` is copied through.
    """
    if plan.get("schema") != PLAN_SCHEMA or plan.get("provenance_verified") is not True:
        raise ImportRefused("A fabricated plan cannot mark a queue row human-reviewed.")
    if not write_action or write_action.get("decision") != WRITE_DECISION:
        raise ImportRefused("Queue writes stay disabled until a separate write action is approved.")
    if write_action.get("adjudication_sha256") != plan.get("adjudication_sha256"):
        raise ImportRefused("The write action is not bound to this adjudication artifact.")
    if write_action.get("dataset_version") != plan.get("dataset_version"):
        raise ImportRefused("The write action is not bound to this dataset version.")
    updates = {}
    for row in plan.get("rows") or []:
        if row.get("tied_to_validated_submissions") is not True:
            raise ImportRefused("A plan row is not tied to validated human submissions.")
        canonical_id = row.get("canonical_id")
        if canonical_id in updates:
            raise ImportRefused("Adjudication canonical id is duplicated.")
        updates[canonical_id] = row
    known = {row["id"] for row in queue_rows}
    if not set(updates).issubset(known):
        raise ImportRefused("Adjudication canonical id is not in the queue.")
    updated = []
    for row in queue_rows:
        copied = dict(row)
        change = updates.get(row["id"])
        if change is not None:
            copied["reviewed_label"] = change["adjudicated_label"]
            copied["human_reviewed"] = "True"
            copied["reviewer"] = change["adjudicator"]
            copied["reviewed_at"] = change["adjudicated_at"]
            if "evidence_quote" in change:
                copied["evidence_quote"] = change["evidence_quote"]
            if change.get("review_notes"):
                copied["review_notes"] = change["review_notes"]
        if copied.get("expected") != row.get("expected"):
            raise ImportRefused("The author label was not preserved.")
        updated.append(copied)
    return updated
