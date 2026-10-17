"""Integrity tests for ClaimLedger's candidate-only synthetic benchmark expansion."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmark" / "candidates"


def test_manifest_document_hashes_and_counts():
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gold_benchmark"] is False
    assert manifest["label_origin"] == "synthetic_author_labeled"
    assert manifest["dataset_version"] == "candidates-2026-10-17.2"
    assert manifest["original_synthetic_documents"] == 36
    assert manifest["rows"] == 108
    assert manifest["external_evaluation_set"] == "not_available"
    assert len(manifest["document_sha256"]) == 36
    for filename, digest in manifest["document_sha256"].items():
        source = BASE / "documents" / filename
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_review_queue_and_shards_are_aligned():
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    with (BASE / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        reviews = list(csv.DictReader(handle))
    shards = sorted(BASE.glob("shard-*.jsonl"))
    assert len(shards) == manifest["shards"] == 5
    cases = []
    for shard in shards:
        local_cases = [json.loads(line) for line in shard.read_text(encoding="utf-8").splitlines()]
        assert 1 <= len(local_cases) <= 30
        cases += local_cases
    assert len(reviews) == len(cases) == 108
    assert Counter(case["expected"] for case in cases) == {
        "supported": 36,
        "contradicted": 36,
        "insufficient": 36,
    }
    assert len({review["id"] for review in reviews}) == len(reviews)
    for review, case in zip(reviews, cases, strict=True):
        assert review["claim"] == case["claim"]
        assert review["expected"] == case["expected"]
        assert review["document"] == case["document"]
        assert review["label_origin"] == "synthetic_author_labeled"
        assert review["human_reviewed"] == "False"
        assert review["reviewer"] == ""
        source = (BASE / case["document"]).resolve()
        assert source.is_file()
        assert source.is_relative_to(BASE.resolve())
        assert ".." not in Path(case["document"]).parts
        if review["evidence_quote"]:
            text = source.read_text(encoding="utf-8")
            start = text.find(review["evidence_quote"])
            assert start >= 0
            end = start + len(review["evidence_quote"])
            assert text[start:end] == review["evidence_quote"]
            assert text.find(review["evidence_quote"], start + 1) == -1
        assert review["reviewed_label"] == ""
        assert review["human_reviewed"] == "False"


CORRECTED_QUOTES = {
    "cl-009-2": "Median message latency was 42 milliseconds during the benchmark.",
    "cl-010-2": "The museum is closed to visitors on Mondays.",
    "cl-013-2": "The Delta complex consists of three towers.",
    "cl-019-2": "It did not provide a French translation.",
    "cl-020-2": "The authors did not conduct a blinded trial.",
}


def test_pre_review_flags_do_not_mark_rows_reviewed():
    with (BASE / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        reviews = {row["id"]: row for row in csv.DictReader(handle)}
    with (BASE / "pre_review_flags.csv").open(encoding="utf-8", newline="") as handle:
        flags = list(csv.DictReader(handle))
    assert flags
    for flag in flags:
        assert flag["id"] in reviews
        assert flag["human_reviewed"] == "false"
        assert reviews[flag["id"]]["human_reviewed"] == "False"
        assert reviews[flag["id"]]["reviewed_label"] == ""


def test_ai_second_opinion_does_not_become_human_review():
    annotation = json.loads(
        (BASE / "ai_second_opinion" / "semantic_review_18.json").read_text(encoding="utf-8")
    )
    assert annotation["review_type"] == "AI_not_independent_human_review"
    assert annotation["gold_eligible"] is False
    assert annotation["paid_api_calls"] == 0
    with (BASE / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        reviews = {row["id"]: row for row in csv.DictReader(handle)}
    disagreements = []
    for result in annotation["results"]:
        review = reviews[result["case_id"]]
        assert review["expected"] == result["author_label"]
        assert review["reviewed_label"] == ""
        assert review["human_reviewed"] == "False"
        assert review["reviewer"] == ""
        assert review["reviewed_at"] == ""
        assert result["review_type"] == "AI_semantic_second_opinion_not_human"
        text = (BASE / result["document"]).read_text(encoding="utf-8")
        digest = hashlib.sha256((BASE / result["document"]).read_bytes()).hexdigest()
        assert digest == result["document_sha256"]
        for evidence in result["evidence"]:
            assert text[evidence["start"]:evidence["end"]] == evidence["quote"]
        if not result["agrees_with_author"]:
            disagreements.append(result["case_id"])
    assert disagreements == ["cl-027-2"]
    assert reviews["cl-027-2"]["expected"] == "contradicted"


def test_corrected_quotes_name_the_relevant_statement():
    with (BASE / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        reviews = {row["id"]: row for row in csv.DictReader(handle)}
    for case_id, quote in CORRECTED_QUOTES.items():
        review = reviews[case_id]
        text = (BASE / review["document"]).read_text(encoding="utf-8")
        assert review["evidence_quote"] == quote
        assert review["human_reviewed"] == "False"
        start = text.find(quote)
        assert start >= 0
        assert text.find(quote, start + 1) == -1
