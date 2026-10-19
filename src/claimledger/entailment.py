"""Separate quote presence from evidence entailment.

A quote that occurs in the passage proves only that the span exists. Support
or refutation is a second decision. When none of the narrow rules below fire,
the result stays ``unresolved`` instead of treating presence as entailment.
"""

from __future__ import annotations

import re

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
MEASURE = re.compile(r"\b(\d+(?:\.\d+)?)\s+([A-Za-z]+)\b")
NEGATION = re.compile(r"\b(no|not|never|without|excluded|none)\b", re.IGNORECASE)
INCLUSION = re.compile(
    r"\b(include|includes|included|contain|contains|contained|record|records|recorded)\b",
    re.IGNORECASE,
)
LESS_THAN = re.compile(r"^(?P<a>.+?) is less than (?P<b>.+)\.$")
STOPWORDS = {
    "the", "a", "an", "of", "on", "in", "was", "were", "is", "are", "their",
    "its", "for", "and", "or", "to", "by", "with", "from", "that", "this",
    "it", "as", "at", "than", "after", "before", "into", "only",
}


def _audit(quote_present: bool, entailment: str, rule: str) -> dict:
    return {
        "quote_present": quote_present,
        "entailment": entailment,
        "rule": rule,
        "semantics_verified": False,
        "verdict_confirmed": False,
    }


def audit_entailment(claim: str, quote: str, passage: str) -> dict:
    """Return presence and entailment as separate fields.

    Heuristic rules never set ``verdict_confirmed``. They can suggest a
    relation. They do not certify a label.
    """
    if not isinstance(quote, str) or quote == "":
        return _audit(False, "not_applicable", "empty_quote")
    if quote not in passage:
        return _audit(False, "not_applicable", "quote_absent")
    relation, rule = _relation(claim, quote)
    return _audit(True, relation, rule)


def label_assessment(audit: dict, verdict: str) -> dict:
    """Separate format, heuristic suggestion, and semantic confirmation.

    An empty quote on an insufficient verdict matches the format. It does not
    verify that the passage leaves the claim unsettled.
    """
    empty_insufficient = (
        verdict == "insufficient"
        and audit.get("rule") == "empty_quote"
        and audit.get("quote_present") is False
    )
    quote_for_decision = verdict in {"supported", "contradicted"} and audit.get("quote_present") is True
    suggestion = None
    if verdict == "supported" and audit.get("entailment") == "supports":
        suggestion = audit.get("rule")
    elif verdict == "contradicted" and audit.get("entailment") == "refutes":
        suggestion = audit.get("rule")
    elif audit.get("entailment") == "unresolved":
        suggestion = audit.get("rule")
    return {
        "quote_present": audit.get("quote_present"),
        "entailment": audit.get("entailment"),
        "format_ok": empty_insufficient or quote_for_decision,
        "semantics_verified": False,
        "verdict_confirmed": False,
        "heuristic_suggestion": suggestion,
    }


def _relation(claim: str, quote: str) -> tuple[str, str]:
    if claim in quote:
        return "supports", "claim_verbatim_in_quote"
    measure = _measure_conflict(claim, quote)
    if measure == "same_unit_different_number":
        return "refutes", measure
    if measure == "same_number_different_unit":
        return "unresolved", measure
    if _different_period(claim, quote):
        return "unresolved", "different_period_not_exclusive"
    if _exclusion_conflict(claim, quote):
        return "refutes", "exclusion_conflict"
    comparison = _less_than(claim, quote)
    if comparison is not None:
        return comparison
    return "unresolved", "presence_is_not_entailment"


def _measures(text: str) -> list[tuple[str, str]]:
    return [(number, unit.casefold()) for number, unit in MEASURE.findall(text)]


def _measure_conflict(claim: str, quote: str) -> str | None:
    claim_measures = _measures(claim)
    quote_measures = _measures(quote)
    if not claim_measures or not quote_measures:
        return None
    quote_by_unit: dict[str, set[str]] = {}
    quote_by_number: dict[str, set[str]] = {}
    for number, unit in quote_measures:
        quote_by_unit.setdefault(unit, set()).add(number)
        quote_by_number.setdefault(number, set()).add(unit)
    for number, unit in claim_measures:
        numbers = quote_by_unit.get(unit)
        if numbers and number not in numbers:
            return "same_unit_different_number"
        units = quote_by_number.get(number)
        if units and unit not in units:
            return "same_number_different_unit"
    return None


def _different_period(claim: str, quote: str) -> bool:
    """Different months are not mutually exclusive. This only flags them for review."""
    claim_months = [month for month in MONTHS if re.search(rf"\b{month}\b", claim)]
    quote_months = [month for month in MONTHS if re.search(rf"\b{month}\b", quote)]
    if len(claim_months) != 1 or len(quote_months) != 1 or claim_months[0] == quote_months[0]:
        return False
    return bool(_measures(claim)) and _measures(claim) == _measures(quote)


def _content(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text.casefold())
    return {word for word in words if word not in STOPWORDS and not NEGATION.fullmatch(word)}


def _exclusion_conflict(claim: str, quote: str) -> bool:
    if NEGATION.search(claim) or not NEGATION.search(quote):
        return False
    if not INCLUSION.search(claim):
        return False
    return len(_content(claim) & _content(quote)) >= 2


def _less_than(claim: str, quote: str) -> tuple[str, str] | None:
    match = LESS_THAN.fullmatch(claim)
    if match is None:
        return None
    left = _measure_for_name(match.group("a"), quote)
    right = _measure_for_name(match.group("b"), quote)
    if left is None or right is None or left[1] != right[1]:
        return None
    if left[0] < right[0]:
        return "supports", "less_than_measures"
    if left[0] > right[0]:
        return "refutes", "less_than_reversed"
    return "unresolved", "less_than_equal_measures"


def _measure_for_name(name: str, quote: str) -> tuple[float, str] | None:
    found = re.search(
        re.escape(name) + r"\D{0,40}?(\d+(?:\.\d+)?)\s+([A-Za-z]+)",
        quote,
    )
    if found is None:
        return None
    return float(found.group(1)), found.group(2).casefold()
