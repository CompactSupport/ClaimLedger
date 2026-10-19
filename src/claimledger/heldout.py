"""Fresh held-out freeze for the v0.5 milestone.

Layer 1 is the immutable snapshot: documents, claims, author labels, the
initial blank sheet, and their hashes. Layer 2 is the research ledger:
reviewer submissions, human adjudications, approval, and model contact.
The ledger is not regenerated from the catalog. A model process may start
only when layer 2 carries one valid release bound to the layer 1 hash.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from .calibration import AI_REVIEWER_RE, adjudication_digest
from .entailment import audit_entailment, label_assessment
from .label_blind import CLASSES

CATALOG_NAME = "catalog.json"
MODEL_INPUTS = "model_view/inputs.jsonl"
BLANK_SHEET = "human/initial_blank_sheet.csv"
ENTAILMENT_AUDIT = "entailment_audit.json"
FREEZE_NAME = "freeze.json"
LEDGER_NAME = "research/ledger.json"
DATASET_VERSION = "heldout-2026-10-18.1"
RELEASE_DECISION = "allow_first_model_contact"
ROOT = Path(__file__).resolve().parents[2]


def catalog_dir(root: Path | None = None) -> Path:
    return (root or ROOT) / "benchmark" / "heldout_v05"


def load_catalog(root: Path | None = None) -> dict:
    return json.loads((catalog_dir(root) / CATALOG_NAME).read_text(encoding="utf-8"))


def case_id(document_id: str, claim: str) -> str:
    digest = hashlib.sha256(f"{document_id}\n{claim}".encode("utf-8")).hexdigest()
    return f"hf-{digest[:12]}"


def iter_cases(catalog: dict) -> list[dict]:
    documents = {item["document_id"]: item for item in catalog["documents"]}
    cases = []
    for claim in catalog["claims"]:
        document = documents[claim["document_id"]]
        passage = document["text"] if document["text"].endswith("\n") else document["text"] + "\n"
        cases.append({
            "id": case_id(claim["document_id"], claim["claim"]),
            "document_id": claim["document_id"],
            "claim": claim["claim"],
            "passage": passage,
            "author_label": claim["author_label"],
            "author_quote": claim["author_quote"],
            "author_label_under_review": claim.get("author_label_under_review") is True,
        })
    cases.sort(key=lambda item: item["id"])
    return cases


def model_inputs(cases: list[dict]) -> str:
    lines = [
        json.dumps({
            "id": case["id"],
            "document_id": case["document_id"],
            "claim": case["claim"],
            "passage": case["passage"],
        }, ensure_ascii=False)
        for case in cases
    ]
    return "\n".join(lines) + "\n"


def initial_blank_sheet(cases: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["heldout_id", "adjudicated_label", "evidence_quote", "reviewer", "reviewed_at"],
        lineterminator="\n",
    )
    writer.writeheader()
    for case in cases:
        writer.writerow({
            "heldout_id": case["id"],
            "adjudicated_label": "",
            "evidence_quote": "",
            "reviewer": "",
            "reviewed_at": "",
        })
    return buffer.getvalue()


def read_human_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def entailment_audit(cases: list[dict]) -> dict:
    rows = []
    for case in cases:
        audit = audit_entailment(case["claim"], case["author_quote"], case["passage"])
        assessment = label_assessment(audit, case["author_label"])
        rows.append({
            "id": case["id"],
            "author_label": case["author_label"],
            "author_label_under_review": case["author_label_under_review"],
            "quote_present": audit["quote_present"],
            "entailment": audit["entailment"],
            "rule": audit["rule"],
            "format_ok": assessment["format_ok"],
            "semantics_verified": False,
            "verdict_confirmed": False,
            "heuristic_suggestion": assessment["heuristic_suggestion"],
        })
    return {
        "schema": "claimledger.heldout_v05_entailment_audit.v1",
        "auditor": "claimledger.entailment",
        "heuristics_certify_labels": False,
        "rows": rows,
    }


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def freeze_sha256(freeze: dict) -> str:
    body = {key: value for key, value in freeze.items() if key != "freeze_sha256"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def build_freeze(root: Path | None = None) -> dict:
    root = root or ROOT
    catalog = load_catalog(root)
    cases = iter_cases(catalog)
    base = catalog_dir(root)
    inputs = model_inputs(cases)
    sheet = initial_blank_sheet(cases)
    audit = entailment_audit(cases)
    body = {
        "schema": "claimledger.heldout_v05_freeze.v1",
        "dataset_version": DATASET_VERSION,
        "milestone": "v0.5-fresh-heldout-entailment",
        "author_label_origin": "dataset_author",
        "author_labels_are_human_review": False,
        "gold_benchmark_released": False,
        "document_count": len(catalog["documents"]),
        "claim_count": len(cases),
        "case_ids": [case["id"] for case in cases],
        "author_label_under_review": [
            case["id"] for case in cases if case["author_label_under_review"]
        ],
        "document_sha256": {
            item["document_id"]: hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
            for item in catalog["documents"]
        },
        "catalog_sha256": hashlib.sha256((base / CATALOG_NAME).read_bytes()).hexdigest(),
        "model_inputs_sha256": hashlib.sha256(inputs.encode("utf-8")).hexdigest(),
        "initial_blank_sheet_sha256": hashlib.sha256(sheet.encode("utf-8")).hexdigest(),
        "entailment_audit_sha256": hashlib.sha256(
            (json.dumps(audit, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        ).hexdigest(),
    }
    body["freeze_sha256"] = freeze_sha256(body)
    return body


def empty_ledger(freeze_digest: str) -> dict:
    return {
        "schema": "claimledger.heldout_v05_research_ledger.v1",
        "dataset_version": DATASET_VERSION,
        "freeze_sha256": freeze_digest,
        "reviewer_submissions": [],
        "human_adjudications": [],
        "approvals": [],
        "model_contacts": [],
    }


def generated_files(root: Path | None = None) -> dict[str, str]:
    """Regenerate the immutable snapshot only. The research ledger is not included."""
    root = root or ROOT
    catalog = load_catalog(root)
    cases = iter_cases(catalog)
    files = {
        MODEL_INPUTS: model_inputs(cases),
        BLANK_SHEET: initial_blank_sheet(cases),
        ENTAILMENT_AUDIT: json.dumps(entailment_audit(cases), indent=2, ensure_ascii=False) + "\n",
        FREEZE_NAME: json.dumps(build_freeze(root), indent=2) + "\n",
    }
    for item in catalog["documents"]:
        text = item["text"] if item["text"].endswith("\n") else item["text"] + "\n"
        files[f"model_view/documents/{item['document_id']}.md"] = text
    return files


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def assess_heldout_release(freeze: dict, ledger: dict, cases: list[dict], *, now: datetime) -> dict:
    """Validate a research ledger against one frozen snapshot. Default is closed."""
    reasons: list[str] = []
    expected_hash = freeze.get("freeze_sha256")
    if not expected_hash or freeze_sha256(freeze) != expected_hash:
        reasons.append("The freeze hash does not match the snapshot.")
    if ledger.get("freeze_sha256") != expected_hash:
        reasons.append("The research ledger is not bound to this freeze hash.")
    if ledger.get("dataset_version") != freeze.get("dataset_version"):
        reasons.append("The research ledger names a different dataset version.")
    passages = {case["id"]: case["passage"] for case in cases}
    expected_ids = set(freeze.get("case_ids") or [])
    adjudications = list(ledger.get("human_adjudications") or [])
    found_ids = [row.get("id") for row in adjudications if isinstance(row, dict)]
    if not adjudications:
        reasons.append("Human adjudication is unreviewed.")
    elif set(found_ids) != expected_ids or len(found_ids) != len(expected_ids):
        reasons.append("Human adjudication is partial or contains an unknown id.")
    reviewed_at = []
    for row in adjudications:
        if not isinstance(row, dict):
            reasons.append("A human adjudication row is not an object.")
            continue
        label = row.get("adjudicated_label")
        if label not in CLASSES:
            reasons.append("A human adjudication uses an illegal label.")
        reviewer = str(row.get("reviewer") or "")
        if not reviewer or AI_REVIEWER_RE.search(reviewer):
            reasons.append("A reviewer id is missing or is not a human reviewer id.")
        parsed = _parse_time(row.get("reviewed_at"))
        if parsed is None or parsed > now:
            reasons.append("A review timestamp is not credible.")
        elif parsed is not None:
            reviewed_at.append(parsed)
        quote = row.get("evidence_quote")
        passage = passages.get(row.get("id"), "")
        if label in {"supported", "contradicted"}:
            if not isinstance(quote, str) or quote == "" or quote not in passage:
                reasons.append("A supported or contradicted adjudication has invalid evidence.")
        elif label == "insufficient" and isinstance(quote, str) and quote and quote not in passage:
            reasons.append("An insufficient adjudication quotes text that is not in the passage.")
    approvals = list(ledger.get("approvals") or [])
    if len(approvals) != 1 or not isinstance(approvals[0], dict):
        reasons.append("A single release approval is required.")
        approval = {}
    else:
        approval = approvals[0]
    if approval:
        if approval.get("decision") != RELEASE_DECISION:
            reasons.append("The approval does not allow the first model contact.")
        if approval.get("freeze_sha256") != expected_hash:
            reasons.append("The approval is not bound to this freeze hash.")
        digest = adjudication_digest(sorted(
            [row for row in adjudications if isinstance(row, dict)],
            key=lambda row: str(row.get("id")),
        ))
        if approval.get("adjudication_digest") != digest:
            reasons.append("The approval digest is forged or does not match the adjudications.")
        approver = str(approval.get("approver") or "")
        if not approver or AI_REVIEWER_RE.search(approver):
            reasons.append("The approver id is missing or is not a human approver id.")
        approved_at = _parse_time(approval.get("approved_at"))
        if approved_at is None or approved_at > now or any(item > approved_at for item in reviewed_at):
            reasons.append("The approval timestamp is not credible.")
    contacts = [row for row in ledger.get("model_contacts") or [] if isinstance(row, dict)]
    if any(row.get("freeze_sha256") == expected_hash for row in contacts):
        reasons.append("This freeze already has a model contact.")
    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return {"allowed": not unique, "reasons": unique}


def release_decision_for_record(record: dict, *, root: Path | None = None,
                                ledger: dict | None = None, now: datetime | None = None) -> dict | None:
    """Return a decision when the record is one of the frozen claims. Otherwise None."""
    root = root or ROOT
    catalog_path = catalog_dir(root) / CATALOG_NAME
    if not catalog_path.is_file():
        return None
    cases = iter_cases(load_catalog(root))
    if not any(case["claim"] == record.get("claim") for case in cases):
        return None
    freeze_path = catalog_dir(root) / FREEZE_NAME
    freeze = json.loads(freeze_path.read_text(encoding="utf-8")) if freeze_path.is_file() else {}
    if ledger is None:
        ledger_path = catalog_dir(root) / LEDGER_NAME
        ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
    return assess_heldout_release(freeze, ledger, cases, now=now or datetime.now().astimezone())
