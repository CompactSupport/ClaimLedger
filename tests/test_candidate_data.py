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
    assert manifest["original_synthetic_documents"] == 20
    assert manifest["rows"] == 60
    assert len(manifest["document_sha256"]) == 20
    for filename, digest in manifest["document_sha256"].items():
        source = BASE / "documents" / filename
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_review_queue_and_shards_are_aligned():
    with (BASE / "review_queue.csv").open(encoding="utf-8", newline="") as handle:
        reviews = list(csv.DictReader(handle))
    shards = sorted(BASE.glob("shard-*.jsonl"))
    assert len(shards) == 3
    cases = []
    for shard in shards:
        local_cases = [json.loads(line) for line in shard.read_text(encoding="utf-8").splitlines()]
        assert len(local_cases) == 20
        cases += local_cases
    assert len(reviews) == len(cases) == 60
    assert Counter(case["expected"] for case in cases) == {
        "supported": 20,
        "contradicted": 20,
        "insufficient": 20,
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
