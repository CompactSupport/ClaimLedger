"""Plan a paid OpenAI pilot. This module does not call the API.

A request cap is not a dollar ceiling. The preflight uses operator-supplied
prices and conservative token estimates, then still requires the operator to
set a budget on the provider account.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Conservative planning figures, not a measurement of a real request.
DEFAULT_INPUT_TOKENS_PER_CASE = 4000
DEFAULT_OUTPUT_TOKENS_PER_CASE = 800


@dataclass(frozen=True)
class PilotPrices:
    usd_per_million_input_tokens: float
    usd_per_million_output_tokens: float


@dataclass(frozen=True)
class PilotPlan:
    max_cases: int
    max_http_attempts: int
    max_retries: int
    usd_budget: float
    estimated_usd: float
    input_tokens_per_case: int
    output_tokens_per_case: int
    executed: bool = False


class PaidPilotRefused(RuntimeError):
    """Raised when a paid run is not allowed."""


def estimate_usd(cases: int, prices: PilotPrices, *, max_attempts: int,
                 input_tokens: int = DEFAULT_INPUT_TOKENS_PER_CASE,
                 output_tokens: int = DEFAULT_OUTPUT_TOKENS_PER_CASE) -> float:
    """Estimate spend if every allowed HTTP attempt uses the conservative token counts."""
    if cases < 1 or max_attempts < 1:
        raise ValueError("cases and max_attempts must be positive.")
    attempts = cases * max_attempts
    input_cost = attempts * input_tokens / 1_000_000 * prices.usd_per_million_input_tokens
    output_cost = attempts * output_tokens / 1_000_000 * prices.usd_per_million_output_tokens
    return input_cost + output_cost


def preflight(cases: int, *, usd_budget: float, max_cases: int, max_retries: int,
              prices: PilotPrices) -> PilotPlan:
    """Return a plan. This function does not contact a provider."""
    if usd_budget <= 0:
        raise PaidPilotRefused("A numeric USD budget is required.")
    if cases > max_cases:
        raise PaidPilotRefused("The dataset exceeds the logical case cap.")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative.")
    max_attempts = max_retries + 1
    estimated = estimate_usd(cases, prices, max_attempts=max_attempts)
    if estimated > usd_budget:
        raise PaidPilotRefused(
            "Conservative estimate exceeds the USD budget. "
            "A request cap alone does not keep spending under the ceiling."
        )
    return PilotPlan(
        max_cases=max_cases,
        max_http_attempts=cases * max_attempts,
        max_retries=max_retries,
        usd_budget=usd_budget,
        estimated_usd=estimated,
        input_tokens_per_case=DEFAULT_INPUT_TOKENS_PER_CASE,
        output_tokens_per_case=DEFAULT_OUTPUT_TOKENS_PER_CASE,
    )


def execute_pilot(plan: PilotPlan, *, confirmed: bool, results_path: Path) -> None:
    """Refuse to call the API.

    Confirmation is necessary and not sufficient. This revision records no
    network call. Results, when a future runner is approved, append one JSON
    object per completed case so the file can be resumed.
    """
    if not confirmed:
        raise PaidPilotRefused("Paid execution requires explicit confirmation.")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    if not results_path.exists():
        results_path.write_text("", encoding="utf-8")
    raise PaidPilotRefused(
        "Paid execution is disabled in this revision. "
        "Set an account-level budget at the provider before any future run. "
        f"Plan estimate: {plan.estimated_usd:.4f} USD, not a spending ceiling."
    )


def completed_case_ids(results_path: Path) -> set[str]:
    """Read case IDs already written so a future run can resume."""
    if not results_path.is_file():
        return set()
    found: set[str] = set()
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if "case_id" in record:
            found.add(record["case_id"])
    return found
