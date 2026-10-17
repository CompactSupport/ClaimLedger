"""Pool candidate-shard evaluations without averaging shard macro-F1 scores."""

from __future__ import annotations

import json
from pathlib import Path

from .metrics import bootstrap_macro_f1, classification_metrics

CANDIDATES = Path(__file__).resolve().parents[2] / "benchmark" / "candidates"


def load_split(path: Path | None = None) -> dict[str, str]:
    data = json.loads((path or (CANDIDATES / "split.json")).read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for name in data["dev_documents"]:
        mapping[name] = "dev"
    for name in data["held_out_documents"]:
        if name in mapping:
            raise ValueError(f"Document is in both splits: {name}")
        mapping[name] = "held_out"
    return mapping


def aggregate(shard_outputs: list[dict], shard_rows: list[list[dict]],
              split: dict[str, str]) -> dict:
    """Pool shard cases. ``shard_rows`` supplies the document for each case, in order."""
    if len(shard_outputs) != len(shard_rows):
        raise ValueError("Each shard result needs its source rows.")
    pairs: list[tuple[str, str]] = []
    grouped: dict[str, list[tuple[str, str]]] = {"dev": [], "held_out": []}
    failures: list[dict] = []
    valid_quotes = 0
    total_quotes = 0
    for output, rows in zip(shard_outputs, shard_rows, strict=True):
        cases = output["cases"]
        if len(cases) != len(rows):
            raise ValueError("Shard result row count does not match the JSONL.")
        valid_quotes += output.get("citation_valid_quotes", 0)
        total_quotes += output.get("citation_total_quotes", 0)
        for case, row in zip(cases, rows, strict=True):
            pair = (case["expected"], case["actual"])
            pairs.append(pair)
            document_name = Path(row["document"]).name
            grouped[split[document_name]].append(pair)
            if case["expected"] != case["actual"]:
                failures.append({
                    "document": row["document"],
                    "claim": case["claim"],
                    "expected": case["expected"],
                    "actual": case["actual"],
                })
    if not pairs:
        raise ValueError("No candidate cases to score.")
    metrics = classification_metrics(pairs)
    shard_scores = [output["metrics"]["macro_f1"] for output in shard_outputs]
    shard_mean = sum(shard_scores) / len(shard_scores)
    abstain_pairs = [(expected, "insufficient") for expected, _actual in pairs]
    correct = sum(expected == actual for expected, actual in pairs)
    return {
        "dataset_tier": "unreviewed_candidate_set",
        "gold_benchmark": False,
        "label_origin": "synthetic_author_labeled",
        "human_reviewed": False,
        "examples": len(pairs),
        "correct": correct,
        "accuracy": correct / len(pairs),
        "metrics": metrics,
        "macro_f1_is_pooled_from_cases": True,
        "mean_of_shard_macro_f1": shard_mean,
        "baselines": {
            "local_exact_match": metrics,
            "always_abstain": classification_metrics(abstain_pairs),
        },
        "local_macro_f1_bootstrap_95": bootstrap_macro_f1(pairs),
        "abstain_macro_f1_bootstrap_95": bootstrap_macro_f1(abstain_pairs),
        "splits": {
            "dev": classification_metrics(grouped["dev"]),
            "held_out": classification_metrics(grouped["held_out"]),
        },
        "failure_modes": failures,
        "citation_valid_quotes": valid_quotes,
        "citation_total_quotes": total_quotes,
        "citation_validity_rate": valid_quotes / total_quotes if total_quotes else None,
        "total_tokens": sum(output.get("total_tokens", 0) for output in shard_outputs),
        "latency_seconds": sum(output.get("latency_seconds", 0) for output in shard_outputs),
        "paid_inference": False,
        "notice": (
            "Engineering smoke on synthetic_author_labeled candidates. "
            "Not gold and not human reviewed. "
            "macro-F1 is recomputed from every case pair, not averaged across shards."
        ),
    }
