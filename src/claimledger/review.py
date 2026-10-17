"""Freeze human-reviewed labels without copying author labels into the gold set."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

LABELS = {"supported", "contradicted", "insufficient"}


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


def freeze_reviews(queue_path: Path, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a gold freeze from rows a person has actually reviewed.

    Author ``expected`` values stay in the queue. They are not copied into
    ``reviewed_label``. Rows that are still unreviewed do not increase ``gold_count``.
    """
    base = queue_path.parent.resolve()
    with queue_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    frozen_cases = list((existing or {}).get("cases") or [])
    by_id = {case["case_id"]: case for case in frozen_cases}
    if len(by_id) != len(frozen_cases):
        raise ValueError("Existing freeze contains duplicate case IDs.")

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
        }
        previous = by_id.get(case_id)
        if previous is None:
            by_id[case_id] = record
            frozen_cases.append(record)
            continue
        if previous != record:
            raise ValueError(f"Frozen case {case_id} would change. Case IDs and evidence are immutable.")
    return {
        "schema": "claimledger.reviewed_labels.v1",
        "gold_benchmark": bool(frozen_cases),
        "gold_count": len(frozen_cases),
        "cases": frozen_cases,
        "note": "gold_count counts frozen human reviews only. Author labels are not included.",
    }


def read_freeze(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
