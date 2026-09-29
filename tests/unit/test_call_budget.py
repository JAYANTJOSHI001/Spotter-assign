"""Unit tests for CallBudget and CallRecord."""

from __future__ import annotations

import pytest

from apps.providers.budget import CallBudget
from apps.providers.errors import BudgetExceeded


def test_call_budget_normal_usage() -> None:
    budget = CallBudget(max_calls=3)
    assert budget.calls_count == 0
    assert len(budget.calls) == 0

    with budget.consume(provider="osrm", purpose="route") as call:
        call.status = "200"

    assert budget.calls_count == 1
    assert len(budget.calls) == 1
    rec = budget.calls[0]
    assert rec["provider"] == "osrm"
    assert rec["purpose"] == "route"
    assert rec["status"] == "200"
    assert rec["ms"] >= 0


def test_call_budget_exhaustion_at_fourth_call() -> None:
    budget = CallBudget(max_calls=3)

    for i in range(3):
        with budget.consume(provider="test", purpose=f"call_{i}") as call:
            call.status = "200"

    assert len(budget.calls) == 3

    with pytest.raises(BudgetExceeded) as exc_info:
        budget.consume(provider="test", purpose="call_4")

    assert "budget of 3 calls exceeded" in str(exc_info.value)
    assert exc_info.value.http_status == 502


def test_call_budget_records_exception_status() -> None:
    budget = CallBudget(max_calls=3)

    with pytest.raises(ValueError):
        with budget.consume(provider="osrm", purpose="route"):
            raise ValueError("simulated network failure")

    assert len(budget.calls) == 1
    assert budget.calls[0]["status"] == "ValueError"
