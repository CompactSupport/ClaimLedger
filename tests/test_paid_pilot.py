from pathlib import Path

import pytest

from claimledger.paid_pilot import PaidPilotRefused, PilotPrices, execute_pilot, preflight


def test_preflight_uses_operator_prices_and_refuses_over_budget():
    prices = PilotPrices(usd_per_million_input_tokens=5, usd_per_million_output_tokens=15)
    plan = preflight(2, usd_budget=100, max_cases=108, max_retries=2, prices=prices)
    assert plan.executed is False
    assert plan.max_http_attempts == 6
    with pytest.raises(PaidPilotRefused, match="request cap"):
        preflight(108, usd_budget=0.01, max_cases=108, max_retries=2, prices=prices)


def test_execute_requires_confirmation_and_still_does_not_call_the_api(tmp_path: Path):
    prices = PilotPrices(usd_per_million_input_tokens=1, usd_per_million_output_tokens=1)
    plan = preflight(1, usd_budget=100, max_cases=1, max_retries=0, prices=prices)
    results = tmp_path / "results.jsonl"
    with pytest.raises(PaidPilotRefused, match="confirmation"):
        execute_pilot(plan, confirmed=False, results_path=results)
    with pytest.raises(PaidPilotRefused, match="disabled"):
        execute_pilot(plan, confirmed=True, results_path=results)
    assert results.read_text(encoding="utf-8") == ""
