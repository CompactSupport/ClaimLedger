"""Pool candidate-shard evaluations without averaging shard macro-F1 scores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .metrics import classification_metrics, cluster_bootstrap_macro_f1

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


def assert_shard_outputs_match_sources(shard_outputs: list[dict], shard_rows: list[list[dict]],
                                       queue_rows: list[dict], manifest_hashes: dict[str, str],
                                       base: Path) -> None:
    """Reject aggregation when a result disagrees with the queue or document bytes."""
    queue: dict[tuple[str, str], dict] = {}
    for row in queue_rows:
        key = (row["document"], row["claim"])
        if key in queue:
            raise ValueError(f"Duplicate review-queue row for {key}")
        queue[key] = row
    seen_ids: set[str] = set()
    root = base.resolve()
    for output, rows in zip(shard_outputs, shard_rows, strict=True):
        cases = output["cases"]
        if len(cases) != len(rows):
            raise ValueError("Shard result row count does not match the JSONL.")
        for case, row in zip(cases, rows, strict=True):
            if case["claim"] != row["claim"] or case["expected"] != row["expected"]:
                raise ValueError("Shard output does not match the source row.")
            review = queue.get((row["document"], row["claim"]))
            if review is None:
                raise ValueError("Shard row is not in the review queue.")
            if review["expected"] != row["expected"]:
                raise ValueError("Expected label does not match the review queue.")
            case_id = review["id"]
            if row.get("id") not in (None, case_id) or case.get("id") not in (None, case_id):
                raise ValueError(f"Case ID mismatch for {case_id}.")
            if case_id in seen_ids:
                raise ValueError(f"Duplicate case ID {case_id}.")
            seen_ids.add(case_id)
            source = (root / row["document"]).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError(f"Document path is not inside the benchmark directory: {row['document']}")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            filename = Path(row["document"]).name
            if manifest_hashes.get(filename) != digest:
                raise ValueError(f"Document hash mismatch for {filename}.")


def aggregate(shard_outputs: list[dict], shard_rows: list[list[dict]],
              split: dict[str, str]) -> dict:
    """Pool shard cases. ``shard_rows`` supplies the document for each case, in order."""
    if len(shard_outputs) != len(shard_rows):
        raise ValueError("Each shard result needs its source rows.")
    pairs: list[tuple[str, str]] = []
    grouped: dict[str, list[tuple[str, str]]] = {"dev": [], "held_out": []}
    by_document: dict[str, list[tuple[str, str]]] = {}
    failures: list[dict] = []
    valid_quotes = 0
    total_quotes = 0
    cases_with_valid_evidence = 0
    for output, rows in zip(shard_outputs, shard_rows, strict=True):
        cases = output["cases"]
        if len(cases) != len(rows):
            raise ValueError("Shard result row count does not match the JSONL.")
        valid_quotes += output.get("citation_valid_quotes", 0)
        total_quotes += output.get("citation_total_quotes", 0)
        cases_with_valid_evidence += sum(
            1 for case in cases if case.get("has_valid_evidence")
        )
        for case, row in zip(cases, rows, strict=True):
            if case["claim"] != row["claim"] or case["expected"] != row["expected"]:
                raise ValueError("Shard output does not match the source row.")
            if row.get("id") and case.get("id") not in (None, row["id"]):
                raise ValueError("Shard output case ID does not match the source row.")
            pair = (case["expected"], case["actual"])
            pairs.append(pair)
            document_name = Path(row["document"]).name
            grouped[split[document_name]].append(pair)
            by_document.setdefault(document_name, []).append(pair)
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
    abstain_by_document = {
        name: [(expected, "insufficient") for expected, _actual in document_pairs]
        for name, document_pairs in by_document.items()
    }
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
        "independent_documents": len(by_document),
        "local_macro_f1_cluster_bootstrap_95": cluster_bootstrap_macro_f1(by_document),
        "abstain_macro_f1_cluster_bootstrap_95": cluster_bootstrap_macro_f1(abstain_by_document),
        "splits": {
            "dev": classification_metrics(grouped["dev"]),
            "held_out": classification_metrics(grouped["held_out"]),
        },
        "failure_modes": failures,
        "citation_valid_quotes": valid_quotes,
        "citation_total_quotes": total_quotes,
        "citation_validity_rate": valid_quotes / total_quotes if total_quotes else None,
        "citation_validity_scope": "emitted_quotes_only",
        "citation_validity_note": (
            "This rate counts only quotes the baseline emitted. "
            "It is not evidence of citation reliability for cases with no quote."
        ),
        "evidence_coverage_rate": cases_with_valid_evidence / len(pairs),
        "cases_with_valid_evidence": cases_with_valid_evidence,
        "evidence_coverage_note": (
            "Share of cases that received at least one validated quote. "
            "Separate from quote validity among emitted quotes."
        ),
        "held_out_split_note": (
            "The held-out split is an internal partition of the same author-written set. "
            "It is not a blind external test set."
        ),
        "total_tokens": sum(output.get("total_tokens", 0) for output in shard_outputs),
        "latency_seconds": sum(output.get("latency_seconds", 0) for output in shard_outputs),
        "paid_inference": False,
        "notice": (
            "Engineering smoke on synthetic_author_labeled candidates. "
            "Not gold and not human reviewed. "
            "macro-F1 is recomputed from every case pair, not averaged across shards."
        ),
    }
