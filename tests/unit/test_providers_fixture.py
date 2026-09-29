"""Unit tests for FixtureRouteProvider using recorded test artifacts."""

from __future__ import annotations

import pytest

from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import NoRouteError
from apps.providers.fixture import FixtureRouteProvider


def test_fixture_chicago_to_dallas() -> None:
    provider = FixtureRouteProvider()
    budget = CallBudget(max_calls=3)

    res = provider.route(
        start=LatLng(lat=41.8781, lng=-87.6298),
        finish=LatLng(lat=32.7767, lng=-96.7970),
        budget=budget,
    )

    assert pytest.approx(res.distance_miles, 5.0) == 967.0
    assert res.duration_minutes > 0
    assert len(res.lat) > 100
    assert len(res.lng) == len(res.lat)
    assert res.provider == "fixture"
    assert len(budget.calls) == 1
    assert budget.calls[0]["status"] == "200"


def test_fixture_new_york_to_honolulu_no_route() -> None:
    provider = FixtureRouteProvider()
    budget = CallBudget(max_calls=3)

    with pytest.raises(NoRouteError):
        provider.route(
            start=LatLng(lat=40.7128, lng=-74.0060),
            finish=LatLng(lat=21.3069, lng=-157.8583),
            budget=budget,
        )

    assert len(budget.calls) == 1


def test_fixture_missing_raises_file_not_found() -> None:
    provider = FixtureRouteProvider()
    budget = CallBudget(max_calls=3)

    with pytest.raises(FileNotFoundError) as exc_info:
        provider.route(
            start=LatLng(lat=10.0, lng=-10.0),
            finish=LatLng(lat=12.0, lng=-12.0),
            budget=budget,
        )

    assert "Route fixture not found" in str(exc_info.value)
