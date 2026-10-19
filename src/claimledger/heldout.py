"""Fresh held-out freeze for the v0.5 milestone.

Documents and claims are frozen before any evaluation model sees them.
Author reference labels are not human adjudications. The human sheet stays
blank in this revision, and model contact stays closed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from .entailment import audit_entailment, entailment_confirms

CATALOG_NAME = "catalog.json"
MODEL_INPUTS = "model_view/inputs.jsonl"
HUMAN_SHEET = "human/adjudication_sheet.csv"
ENTAILMENT_AUDIT = "entailment_audit.json"
FREEZE_NAME = "freeze.json"
LABEL_WORDS = ("supported", "contradicted", "insufficient")


def catalog_dir(root: Path) -> Path:
    return root / "benchmark" / "heldout_v05"


def load_catalog(root: Path) -> dict:
    return json.loads((catalog_dir(root) / CATALOG_NAME).read_text(encoding="utf-8"))


def case_id(document_id: str, claim: str) -> str:
    digest = hashlib.sha256(f"{document_id}\n{claim}".encode("utf-8")).hexdigest()
    return f"hf-{digest[:12]}"


def iter_cases(catalog: dict) -> list[dict]:
    documents = {item["document_id"]: item for item in catalog["documents"]}
    cases = []
    for claim in catalog["claims"]:
        document = documents[claim["document_id"]]
        heldout_id = case_id(claim["document_id"], claim["claim"])
        passage = document["text"] if document["text"].endswith("\n") else document["text"] + "\n"
        cases.append({
            "id": heldout_id,
            "document_id": claim["document_id"],
            "claim": claim["claim"],
            "passage": passage,
            "author_label": claim["author_label"],
            "author_quote": claim["author_quote"],
        })
    cases.sort(key=lambda item: item["id"])
    return cases


def model_inputs(cases: list[dict]) -> str:
    lines = []
    for case in cases:
        lines.append(json.dumps({
            "id": case["id"],
            "document_id": case["document_id"],
            "claim": case["claim"],
            "passage": case["passage"],
        }, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def human_sheet(cases: list[dict]) -> str:
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
        rows.append({
            "id": case["id"],
            "author_label": case["author_label"],
            "quote_present": audit["quote_present"],
            "entailment": audit["entailment"],
            "rule": audit["rule"],
            "entailment_confirms_author_label": entailment_confirms(audit, case["author_label"]),
        })
    return {
        "schema": "claimledger.heldout_v05_entailment_audit.v1",
        "auditor": "claimledger.entailment",
        "model_contact_count": 0,
        "rows": rows,
    }


def build_freeze(root: Path) -> dict:
    catalog = load_catalog(root)
    cases = iter_cases(catalog)
    base = catalog_dir(root)
    document_hashes = {
        item["document_id"]: hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
        for item in catalog["documents"]
    }
    inputs = model_inputs(cases)
    sheet = human_sheet(cases)
    audit = entailment_audit(cases)
    return {
        "schema": "claimledger.heldout_v05_freeze.v1",
        "milestone": "v0.5-fresh-heldout-entailment",
        "model_contact_count": 0,
        "first_model_contact_at": None,
        "human_adjudication_complete": False,
        "model_release": None,
        "author_label_origin": "dataset_author",
        "author_labels_are_human_review": False,
        "gold_benchmark_released": False,
        "document_count": len(catalog["documents"]),
        "claim_count": len(cases),
        "document_sha256": document_hashes,
        "catalog_sha256": hashlib.sha256((base / CATALOG_NAME).read_bytes()).hexdigest(),
        "model_inputs_sha256": hashlib.sha256(inputs.encode("utf-8")).hexdigest(),
        "human_sheet_sha256": hashlib.sha256(sheet.encode("utf-8")).hexdigest(),
        "entailment_audit_sha256": hashlib.sha256(
            (json.dumps(audit, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        ).hexdigest(),
    }


def model_contact_decision(freeze: dict, rows: list[dict]) -> dict:
    """Decide whether an evaluation model may see this freeze. Default is no."""
    reasons = []
    if freeze.get("model_contact_count") != 0:
        reasons.append("A model has already contacted this freeze.")
    if any(not (row.get("adjudicated_label") or "").strip() for row in rows):
        reasons.append("Human adjudication is not complete.")
    if freeze.get("human_adjudication_complete") is not True:
        reasons.append("The freeze does not record a complete human adjudication.")
    if freeze.get("model_release") != "allow_first_model_contact":
        reasons.append("No separate model-release record allows the first contact.")
    return {"allowed": not reasons, "reasons": reasons}


def generated_files(root: Path) -> dict[str, str]:
    catalog = load_catalog(root)
    cases = iter_cases(catalog)
    audit = entailment_audit(cases)
    freeze = build_freeze(root)
    files = {
        MODEL_INPUTS: model_inputs(cases),
        HUMAN_SHEET: human_sheet(cases),
        ENTAILMENT_AUDIT: json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        FREEZE_NAME: json.dumps(freeze, indent=2) + "\n",
    }
    for item in catalog["documents"]:
        text = item["text"] if item["text"].endswith("\n") else item["text"] + "\n"
        files[f"model_view/documents/{item['document_id']}.md"] = text
    return files
