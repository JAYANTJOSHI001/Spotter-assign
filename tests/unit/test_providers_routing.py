"""Unit tests for routing orchestration, retries, fallback, and caching."""

from __future__ import annotations

import httpx
import pytest
import respx
from django.core.cache import cache

from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import UpstreamError
from apps.providers.osrm import close_client
from apps.providers.routing import get_route


@pytest.fixture(autouse=True)
def clean_state():
    cache.clear()
    close_client()
    yield
    cache.clear()
    close_client()


@respx.mock
def test_routing_cache_hit_makes_zero_calls(settings) -> None:
    settings.ROUTING_PROVIDER = "osrm"
    settings.OSRM_BASE_URL = "https://test.osrm.org"

    mock_resp = {
        "code": "Ok",
        "routes": [
            {
                "distance": 160934.4,
                "duration": 3600.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.6298, 41.8781], [-88.0, 42.0]],
                },
            }
        ],
    }

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200, json=mock_resp
    )

    budget1 = CallBudget(max_calls=3)
    start = LatLng(lat=41.8781, lng=-87.6298)
    finish = LatLng(lat=42.0, lng=-88.0)

    # First call: cache miss, makes 1 HTTP call
    r1 = get_route(start, finish, budget1)
    assert r1.distance_miles == pytest.approx(100.0, 0.01)
    assert len(budget1.calls) == 1

    # Second call: cache hit, makes 0 HTTP calls
    budget2 = CallBudget(max_calls=3)
    r2 = get_route(start, finish, budget2)
    assert r2.distance_miles == pytest.approx(100.0, 0.01)
    assert len(budget2.calls) == 0  # Zero calls consumed!
    assert r2.provider == "cache"


@respx.mock
def test_routing_retry_once_on_5xx_and_succeeds(settings) -> None:
    settings.ROUTING_PROVIDER = "osrm"
    settings.OSRM_BASE_URL = "https://test.osrm.org"

    mock_resp = {
        "code": "Ok",
        "routes": [
            {
                "distance": 160934.4,
                "duration": 3600.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.6298, 41.8781], [-88.0, 42.0]],
                },
            }
        ],
    }

    route_call = respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").mock(
        side_effect=[
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, json=mock_resp),
        ]
    )

    budget = CallBudget(max_calls=3)
    start = LatLng(lat=41.8781, lng=-87.6298)
    finish = LatLng(lat=42.0, lng=-88.0)

    res = get_route(start, finish, budget, retry_delay_s=0.01)
    assert res.distance_miles == pytest.approx(100.0, 0.01)
    assert route_call.call_count == 2
    assert len(budget.calls) == 2


@respx.mock
def test_routing_fallback_engaged_when_primary_fails(settings) -> None:
    settings.ROUTING_PROVIDER = "osrm"
    settings.OSRM_BASE_URL = "https://test.osrm.org"
    settings.ORS_API_KEY = "test-ors-key"

    # OSRM fails on both attempts
    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=502, text="Bad Gateway"
    )

    # ORS succeeds on fallback
    mock_ors_resp = {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "summary": {
                        "distance": 80467.2,
                        "duration": 1800.0,
                    }
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.6298, 41.8781], [-88.0, 42.0]],
                },
            }
        ],
    }
    respx.post("https://api.openrouteservice.org/v2/directions/driving-car/geojson").respond(
        status_code=200, json=mock_ors_resp
    )

    budget = CallBudget(max_calls=3)
    start = LatLng(lat=41.8781, lng=-87.6298)
    finish = LatLng(lat=42.0, lng=-88.0)

    res = get_route(start, finish, budget, retry_delay_s=0.01)
    assert res.distance_miles == pytest.approx(50.0, 0.01)
    assert res.provider == "ors"
    # 2 calls to OSRM (1 initial + 1 retry) + 1 call to ORS = 3 calls total
    assert len(budget.calls) == 3
    assert budget.calls[0]["provider"] == "osrm"
    assert budget.calls[1]["provider"] == "osrm"
    assert budget.calls[2]["provider"] == "ors"


@respx.mock
def test_routing_budget_exhaustion(settings) -> None:
    settings.ROUTING_PROVIDER = "osrm"
    settings.OSRM_BASE_URL = "https://test.osrm.org"
    settings.ORS_API_KEY = "test-ors-key"

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=500, text="Down"
    )

    # Budget max is 2: primary will try 2 times, then when fallback attempts, budget is exhausted
    budget = CallBudget(max_calls=2)
    start = LatLng(lat=41.8781, lng=-87.6298)
    finish = LatLng(lat=42.0, lng=-88.0)

    with pytest.raises(UpstreamError):
        get_route(start, finish, budget, retry_delay_s=0.01)

    assert len(budget.calls) == 2
