"""Classification metrics for labeled claim checks.

A class with gold examples but no predictions has recall 0, precision null, and F1 0.
That class stays in the macro average so a missed contradiction is not dropped from the score.
Precision is null, not zero, when the denominator would be zero.
"""

from __future__ import annotations

import random
from typing import Any

from .models import DocumentPage

LABELS = ("supported", "contradicted", "insufficient")


def classification_metrics(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Score ``(expected, actual)`` pairs. ``macro_f1`` is the unweighted mean of class F1."""
    per_class: dict[str, dict[str, Any]] = {}
    f1_values: list[float] = []
    for label in LABELS:
        true_positive = sum(expected == label and actual == label for expected, actual in pairs)
        false_positive = sum(expected != label and actual == label for expected, actual in pairs)
        false_negative = sum(expected == label and actual != label for expected, actual in pairs)
        predicted = true_positive + false_positive
        support = true_positive + false_negative
        precision = true_positive / predicted if predicted else None
        recall = true_positive / support if support else None
        if precision is None or recall is None or precision + recall == 0:
            f1 = 0.0 if support or predicted else None
        else:
            f1 = 2 * precision * recall / (precision + recall)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        if f1 is not None:
            f1_values.append(f1)
    count = len(pairs)
    insufficient_prediction_rate = (
        sum(actual == "insufficient" for _, actual in pairs) / count if count else None
    )
    return {
        "per_class": per_class,
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
        "insufficient_prediction_rate": insufficient_prediction_rate,
        "n": count,
        "insufficient_prediction_note": (
            "Share of predictions labeled insufficient. "
            "This is not a separate system-abstention decision."
        ),
    }


def bootstrap_macro_f1(pairs: list[tuple[str, str]], *, iterations: int = 1000,
                       seed: int = 0) -> dict[str, Any]:
    """Percentile interval from resampling this finite set.

    The interval does not estimate accuracy on a larger population.
    """
    if not pairs:
        return {"method": "bootstrap_percentile", "iterations": 0, "seed": seed,
                "low": None, "high": None}
    rng = random.Random(seed)
    scores: list[float] = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        score = classification_metrics(sample)["macro_f1"]
        scores.append(0.0 if score is None else score)
    scores.sort()

    def percentile(fraction: float) -> float:
        index = round((len(scores) - 1) * fraction)
        return scores[index]

    return {
        "method": "bootstrap_percentile",
        "iterations": iterations,
        "seed": seed,
        "low": percentile(0.025),
        "high": percentile(0.975),
        "note": "Resampling interval for this finite set, not a population accuracy claim.",
    }


def cluster_bootstrap_macro_f1(pairs_by_document: dict[str, list[tuple[str, str]]], *,
                               iterations: int = 1000, seed: int = 0) -> dict[str, Any]:
    """Resample documents, keeping every row from each drawn document together."""
    documents = list(pairs_by_document)
    if not documents:
        return {
            "method": "document_cluster_bootstrap_percentile",
            "iterations": 0,
            "seed": seed,
            "independent_documents": 0,
            "low": None,
            "high": None,
        }
    rng = random.Random(seed)
    scores: list[float] = []
    for _ in range(iterations):
        chosen = [documents[rng.randrange(len(documents))] for _ in documents]
        sample: list[tuple[str, str]] = []
        for name in chosen:
            sample.extend(pairs_by_document[name])
        score = classification_metrics(sample)["macro_f1"]
        scores.append(0.0 if score is None else score)
    scores.sort()

    def percentile(fraction: float) -> float:
        index = round((len(scores) - 1) * fraction)
        return scores[index]

    return {
        "method": "document_cluster_bootstrap_percentile",
        "iterations": iterations,
        "seed": seed,
        "independent_documents": len(documents),
        "low": percentile(0.025),
        "high": percentile(0.975),
        "note": (
            "Documents are the resampling unit. Rows from the same document are not "
            "treated as independent observations."
        ),
    }


def citation_counts(pages: list[DocumentPage], results: list[dict[str, Any]]) -> tuple[int, int]:
    """Return ``(valid_quotes, total_quotes)`` using extracted page text."""
    lookup = {(page.source, page.sha256, page.page): page.text for page in pages}
    valid = 0
    total = 0
    for result in results:
        for quote in result["evidence"]:
            total += 1
            text = lookup.get((quote["source"], quote["sha256"], quote["page"]))
            if text is not None and text[quote["start"]:quote["end"]] == quote["quote"]:
                valid += 1
    return valid, total
