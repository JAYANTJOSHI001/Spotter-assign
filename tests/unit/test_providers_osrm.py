"""Unit tests for OSRMProvider using respx mocks (no network)."""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import NoRouteError, UpstreamError, UpstreamTimeout
from apps.providers.osrm import OSRMProvider, close_client


@pytest.fixture(autouse=True)
def clean_client():
    close_client()
    yield
    close_client()


@respx.mock
def test_osrm_success() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    mock_resp = {
        "code": "Ok",
        "routes": [
            {
                "distance": 160934.4,  # 100.0 miles
                "duration": 3600.0,  # 60.0 minutes
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-87.6298, 41.8781], [-88.0, 42.0]],
                },
            }
        ],
    }

    respx.get(
        "https://test.osrm.org/route/v1/driving/-87.629800,41.878100;-88.000000,42.000000"
    ).respond(status_code=200, json=mock_resp)

    res = provider.route(
        start=LatLng(lat=41.8781, lng=-87.6298),
        finish=LatLng(lat=42.0, lng=-88.0),
        budget=budget,
    )

    assert pytest.approx(res.distance_miles, 0.01) == 100.0
    assert pytest.approx(res.duration_minutes, 0.01) == 60.0
    assert len(res.lat) == 2
    assert len(res.lng) == 2
    assert res.lat[0] == 41.8781
    assert res.lng[0] == -87.6298
    assert res.provider == "osrm"
    assert len(budget.calls) == 1
    assert budget.calls[0]["status"] == "200"


@respx.mock
def test_osrm_no_route() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(
        "https://test.osrm.org/route/v1/driving/-74.006000,40.712800;-157.858300,21.306900"
    ).respond(status_code=200, json={"code": "NoRoute", "message": "No route found"})

    with pytest.raises(NoRouteError) as exc_info:
        provider.route(
            start=LatLng(lat=40.7128, lng=-74.0060),
            finish=LatLng(lat=21.3069, lng=-157.8583),
            budget=budget,
        )

    assert exc_info.value.code == "NO_ROUTE"
    assert exc_info.value.http_status == 422


@respx.mock
def test_osrm_5xx_server_error() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=503, text="Service Unavailable"
    )

    with pytest.raises(UpstreamError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert exc_info.value.code == "UPSTREAM_ERROR"
    assert exc_info.value.http_status == 502


@respx.mock
def test_osrm_timeout() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )

    with pytest.raises(UpstreamTimeout) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert exc_info.value.code == "UPSTREAM_TIMEOUT"
    assert exc_info.value.http_status == 504


@respx.mock
def test_osrm_malformed_json() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200, text="not valid json <html"
    )

    with pytest.raises(UpstreamError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert "valid JSON" in str(exc_info.value)


@respx.mock
def test_osrm_other_error_code() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200, json={"code": "InvalidQuery", "message": "Query parameter invalid"}
    )

    with pytest.raises(UpstreamError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert "InvalidQuery" in str(exc_info.value)


@respx.mock
def test_osrm_empty_routes_list() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200, json={"code": "Ok", "routes": []}
    )

    with pytest.raises(NoRouteError) as exc_info:
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )

    assert "no routes" in str(exc_info.value)


@respx.mock
def test_osrm_invalid_coordinates_shape() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000.0,
                    "duration": 100.0,
                    "geometry": {"type": "LineString", "coordinates": [[1.0]]},  # Not length 2
                }
            ],
        },
    )

    with pytest.raises(UpstreamError):
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )


@respx.mock
def test_osrm_missing_distance_or_duration() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200,
        json={
            "code": "Ok",
            "routes": [{"geometry": {"coordinates": [[-87.0, 41.0], [-88.0, 42.0]]}}],
        },
    )

    with pytest.raises(UpstreamError, match="missing distance or duration"):
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )


@respx.mock
def test_osrm_coords_out_of_bounds() -> None:
    provider = OSRMProvider(base_url="https://test.osrm.org")
    budget = CallBudget(max_calls=3)

    respx.get(url__startswith="https://test.osrm.org/route/v1/driving/").respond(
        status_code=200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000.0,
                    "duration": 100.0,
                    "geometry": {
                        "coordinates": [[-87.0, 95.0], [-88.0, 42.0]]  # lat 95 > 90
                    },
                }
            ],
        },
    )

    with pytest.raises(UpstreamError, match="latitudes out of range"):
        provider.route(
            start=LatLng(lat=41.8781, lng=-87.6298),
            finish=LatLng(lat=42.0, lng=-88.0),
            budget=budget,
        )
