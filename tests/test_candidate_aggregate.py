import json
from pathlib import Path

import pytest

from claimledger.candidates import aggregate, load_split
from claimledger.metrics import classification_metrics


def _shard(pairs: list[tuple[str, str]], document: str) -> tuple[dict, list[dict]]:
    cases = [
        {"claim": f"claim-{index}", "expected": expected, "actual": actual, "pass": expected == actual}
        for index, (expected, actual) in enumerate(pairs)
    ]
    rows = [{"document": f"documents/{document}", "claim": case["claim"], "expected": case["expected"]}
            for case in cases]
    output = {
        "cases": cases,
        "metrics": classification_metrics(pairs),
        "citation_valid_quotes": 1,
        "citation_total_quotes": 2,
        "total_tokens": 0,
        "latency_seconds": 0.1,
    }
    return output, rows


def test_pooled_macro_f1_is_not_the_mean_of_shard_scores():
    left, left_rows = _shard(
        [("supported", "supported")] * 4 + [("contradicted", "insufficient")],
        "d001.md",
    )
    right, right_rows = _shard(
        [("contradicted", "contradicted"), ("insufficient", "supported")],
        "d015.md",
    )
    split = {"d001.md": "dev", "d015.md": "held_out"}
    summary = aggregate([left, right], [left_rows, right_rows], split)
    pooled = summary["metrics"]["macro_f1"]
    mean = summary["mean_of_shard_macro_f1"]
    assert pooled == classification_metrics(
        [("supported", "supported")] * 4
        + [("contradicted", "insufficient"), ("contradicted", "contradicted"), ("insufficient", "supported")]
    )["macro_f1"]
    assert pooled != pytest.approx(mean)
    assert summary["gold_benchmark"] is False
    assert summary["label_origin"] == "synthetic_author_labeled"
    assert summary["citation_validity_rate"] == pytest.approx(2 / 4)
    assert summary["splits"]["dev"]["n"] == 5
    assert summary["splits"]["held_out"]["n"] == 2
    assert summary["baselines"]["always_abstain"]["abstention_rate"] == 1.0


def test_split_file_has_no_document_overlap():
    mapping = load_split()
    assert len(mapping) == 20
    assert set(mapping.values()) == {"dev", "held_out"}


def test_candidate_directory_rejects_parent_paths(tmp_path: Path):
    from claimledger.cli import evaluate_dataset

    dataset = tmp_path / "shard.jsonl"
    dataset.write_text(
        json.dumps({"document": "../secret.md", "claim": "hidden", "expected": "supported"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inside"):
        evaluate_dataset(dataset, "local", "gpt-5-mini")
