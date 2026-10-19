"""The fresh held-out freeze is closed to models and separate from the old corpus."""

from __future__ import annotations

import json
from pathlib import Path

from claimledger.heldout import (
    catalog_dir,
    generated_files,
    iter_cases,
    load_catalog,
    model_contact_decision,
    read_human_rows,
)

ROOT = Path(__file__).resolve().parents[1]


def test_generated_heldout_files_match_the_catalog():
    base = catalog_dir(ROOT)
    for name, text in generated_files(ROOT).items():
        assert (base / name).read_text(encoding="utf-8") == text


def test_model_view_hides_labels_and_the_old_corpus():
    base = catalog_dir(ROOT)
    visible = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (base / "model_view").rglob("*")
        if path.is_file()
    )
    for word in ("supported", "contradicted", "insufficient", "author_label", "author_quote"):
        assert word not in visible
    old = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "benchmark" / "candidates" / "documents").glob("*.md")
    )
    catalog = load_catalog(ROOT)
    for item in catalog["documents"]:
        assert item["text"].strip() not in old
        assert item["document_id"].startswith("h")
    for claim in catalog["claims"]:
        assert claim["claim"] not in old


def test_human_sheet_is_blank_and_model_contact_stays_closed():
    base = catalog_dir(ROOT)
    rows = read_human_rows((base / "human" / "adjudication_sheet.csv").read_text(encoding="utf-8"))
    freeze = json.loads((base / "freeze.json").read_text(encoding="utf-8"))
    cases = iter_cases(load_catalog(ROOT))
    assert len(rows) == len(cases) == 16
    assert all(row["adjudicated_label"] == "" and row["reviewer"] == "" for row in rows)
    decision = model_contact_decision(freeze, rows)
    assert decision["allowed"] is False
    assert freeze["model_contact_count"] == 0
    assert freeze["human_adjudication_complete"] is False
    assert freeze["author_labels_are_human_review"] is False
    assert freeze["gold_benchmark_released"] is False
    assert any("Human adjudication" in reason for reason in decision["reasons"])


def test_entailment_audit_does_not_treat_every_present_quote_as_proof():
    audit = json.loads(
        (catalog_dir(ROOT) / "entailment_audit.json").read_text(encoding="utf-8")
    )
    assert audit["model_contact_count"] == 0
    by_rule = {}
    for row in audit["rows"]:
        by_rule.setdefault(row["rule"], []).append(row)
    assert "presence_is_not_entailment" in by_rule
    unresolved = by_rule["presence_is_not_entailment"]
    assert any(row["quote_present"] is True and row["entailment_confirms_author_label"] is False for row in unresolved)
    assert any(row["entailment"] == "supports" for row in audit["rows"])
    assert any(row["entailment"] == "refutes" for row in audit["rows"])
    assert any(row["entailment"] == "not_applicable" for row in audit["rows"])
