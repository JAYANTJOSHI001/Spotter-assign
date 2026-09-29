"""Unit tests for ORSProvider using respx mocks (no network)."""

from __future__ import annotations

import pytest
import respx

from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import UpstreamError
from apps.providers.ors import ORSProvider, close_client


@pytest.fixture(autouse=True)
def clean_client():
    close_client()
    yield
    close_client()


def test_ors_unconfigured_raises() -> None:
    provider = ORSProvider(api_key="")
    budget = CallBudget(max_calls=3)

    with pytest.raises(UpstreamError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert "ORS is not configured" in str(exc_info.value)


@respx.mock
def test_ors_success() -> None:
    provider = ORSProvider(api_key="test-key", base_url="https://api.openrouteservice.org/test")
    budget = CallBudget(max_calls=3)

    mock_resp = {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "summary": {
                        "distance": 80467.2,  # 50 miles
                        "duration": 1800.0,  # 30 min
                    }
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.6298, 41.8781], [-88.0, 42.0]],
                },
            }
        ],
    }

    respx.post("https://api.openrouteservice.org/test").respond(status_code=200, json=mock_resp)

    res = provider.route(
        start=LatLng(lat=41.8781, lng=-87.6298),
        finish=LatLng(lat=42.0, lng=-88.0),
        budget=budget,
    )

    assert pytest.approx(res.distance_miles, 0.01) == 50.0
    assert pytest.approx(res.duration_minutes, 0.01) == 30.0
    assert res.provider == "ors"
    assert len(budget.calls) == 1


@respx.mock
def test_ors_auth_or_quota_error_403() -> None:
    provider = ORSProvider(api_key="bad-key", base_url="https://api.openrouteservice.org/test")
    budget = CallBudget(max_calls=3)

    respx.post("https://api.openrouteservice.org/test").respond(
        status_code=403, text="Quota exceeded or invalid key"
    )

    with pytest.raises(UpstreamError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert "quota error" in str(exc_info.value)
    assert exc_info.value.http_status == 502
