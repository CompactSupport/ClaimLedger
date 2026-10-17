"""Freeze human-reviewed labels without copying author labels into the gold set."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

LABELS = {"supported", "contradicted", "insufficient"}
GOLD_READY_MIN_CASES = 100


def locate_unique_quote(text: str, quote: str) -> tuple[int, int]:
    """Return the only exact span of ``quote`` in ``text``."""
    if not quote:
        raise ValueError("A reviewed supported or contradicted label needs an evidence quote.")
    start = text.find(quote)
    if start < 0:
        raise ValueError("Evidence quote is not an exact substring of the document.")
    if text.find(quote, start + 1) != -1:
        raise ValueError("Evidence quote occurs more than once; the span is ambiguous.")
    end = start + len(quote)
    if text[start:end] != quote:
        raise ValueError("Evidence quote span does not match the document text.")
    return start, end


def _as_bool(value: str) -> bool:
    return value.strip().casefold() == "true"


def _criteria_status(quality_criteria: dict[str, Any] | None,
                     criteria_root: Path | None) -> dict[str, Any]:
    """Check a versioned criteria file. Attestation is not verification."""
    status = {
        "criteria_document_present": False,
        "criteria_version_matches": False,
        "criteria_hash_matches": False,
        "independence_attestation_recorded": False,
        "independence_verified": False,
    }
    if not quality_criteria or criteria_root is None:
        return status
    status["independence_attestation_recorded"] = quality_criteria.get("independence_attested") is True
    relative = quality_criteria.get("criteria_document")
    if not isinstance(relative, str) or not relative.strip():
        return status
    path = (criteria_root / relative).resolve()
    root = criteria_root.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return status
    status["criteria_document_present"] = True
    body = path.read_bytes()
    text = body.decode("utf-8")
    version = quality_criteria.get("criteria_version")
    status["criteria_version_matches"] = isinstance(version, str) and bool(version) and version in text
    status["criteria_hash_matches"] = hashlib.sha256(body).hexdigest() == quality_criteria.get("criteria_sha256")
    return status


def release_status(reviewed_case_count: int, criteria: dict[str, Any], *,
                   dataset_version: str | None,
                   release_approval: dict[str, Any] | None) -> dict[str, Any]:
    """Separate a reviewed subset, approval eligibility, and a formal release.

    One hundred rows do not publish or certify a gold benchmark.
    ``independence_attested`` is recorded as an attestation only.
    """
    subset = reviewed_case_count > 0
    provenance_recorded = isinstance(dataset_version, str) and bool(dataset_version.strip())
    eligible = (
        reviewed_case_count >= GOLD_READY_MIN_CASES
        and provenance_recorded
        and criteria["criteria_document_present"]
        and criteria["criteria_version_matches"]
        and criteria["criteria_hash_matches"]
        and criteria["independence_attestation_recorded"]
    )
    approval = release_approval or {}
    formally_released = (
        eligible
        and approval.get("decision") == "formally_approved"
        and isinstance(approval.get("approval_id"), str)
        and bool(approval.get("approval_id", "").strip())
        and isinstance(approval.get("approver"), str)
        and bool(approval.get("approver", "").strip())
    )
    return {
        "reviewed_subset_available": subset,
        "eligible_for_final_approval": eligible,
        "gold_benchmark_released": formally_released,
    }


def freeze_reviews(queue_path: Path, *, existing: dict[str, Any] | None = None,
                   quality_criteria: dict[str, Any] | None = None,
                   criteria_root: Path | None = None,
                   dataset_version: str | None = None,
                   release_approval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Freeze rows a person has marked reviewed.

    Author ``expected`` values stay in the queue. They are not copied into
    ``reviewed_label``. Unreviewed rows do not increase the reviewed count.
    """
    base = queue_path.parent.resolve()
    with queue_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    frozen_cases = list((existing or {}).get("cases") or [])
    by_id = {case["case_id"]: case for case in frozen_cases}
    if len(by_id) != len(frozen_cases):
        raise ValueError("Existing freeze contains duplicate case IDs.")
    by_pair: dict[tuple[str, str], str] = {}
    for case in frozen_cases:
        pair = (case["document"], case["claim"])
        if pair in by_pair:
            raise ValueError("Existing freeze contains a duplicate document-claim pair.")
        by_pair[pair] = case["case_id"]

    for row in rows:
        if not _as_bool(row.get("human_reviewed", "")):
            continue
        case_id = row["id"].strip()
        reviewer = row.get("reviewer", "").strip()
        reviewed_at = row.get("reviewed_at", "").strip()
        reviewed_label = row.get("reviewed_label", "").strip()
        if not case_id or not reviewer or not reviewed_at:
            raise ValueError(f"Reviewed row {case_id or '<missing id>'} is missing reviewer metadata.")
        if reviewed_label not in LABELS:
            raise ValueError(
                f"Reviewed row {case_id} needs its own reviewed_label. "
                "The author label is not copied."
            )
        document = row["document"].strip()
        pair = (document, row["claim"])
        prior_pair_id = by_pair.get(pair)
        if prior_pair_id is not None and prior_pair_id != case_id:
            raise ValueError(
                "Duplicate document-claim pair. A second case ID cannot increase the reviewed count."
            )
        source = (base / document).resolve()
        if not source.is_relative_to(base):
            raise ValueError(f"Document path escapes the benchmark directory: {document}")
        if not source.is_file():
            raise ValueError(f"Document not found for {case_id}: {document}")
        text = source.read_text(encoding="utf-8")
        evidence: dict[str, Any] | None
        if reviewed_label == "insufficient":
            evidence = None
            if row.get("evidence_quote", "").strip():
                start, end = locate_unique_quote(text, row["evidence_quote"])
                evidence = {"quote": row["evidence_quote"], "start": start, "end": end, "page": 1}
        else:
            start, end = locate_unique_quote(text, row.get("evidence_quote", ""))
            evidence = {"quote": row["evidence_quote"], "start": start, "end": end, "page": 1}
        record = {
            "case_id": case_id,
            "document": document,
            "document_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "claim": row["claim"],
            "author_label": row["expected"],
            "reviewed_label": reviewed_label,
            "author_label_origin": row.get("label_origin", ""),
            "evidence": evidence,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "review_provenance": {
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "document_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "dataset_version": dataset_version,
            },
        }
        previous = by_id.get(case_id)
        if previous is None:
            by_id[case_id] = record
            by_pair[pair] = case_id
            frozen_cases.append(record)
            continue
        if previous != record:
            raise ValueError(f"Frozen case {case_id} would change. Case IDs and evidence are immutable.")
    reviewed_case_count = len({(case["document"], case["claim"]) for case in frozen_cases})
    criteria = _criteria_status(quality_criteria, criteria_root)
    status = release_status(
        reviewed_case_count,
        criteria,
        dataset_version=dataset_version,
        release_approval=release_approval,
    )
    return {
        "schema": "claimledger.reviewed_labels.v2",
        "reviewed_case_count": reviewed_case_count,
        "reviewed_subset_available": status["reviewed_subset_available"],
        "eligible_for_final_approval": status["eligible_for_final_approval"],
        "gold_benchmark_released": status["gold_benchmark_released"],
        "gold_count": reviewed_case_count,
        "independence_attestation_recorded": criteria["independence_attestation_recorded"],
        "independence_verified": False,
        "dataset_version": dataset_version,
        "cases": frozen_cases,
        "note": (
            "reviewed_case_count counts unique document-claim pairs. "
            "independence_attested is an attestation, not a verification. "
            "One hundred rows do not release a gold benchmark."
        ),
    }


def read_freeze(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
