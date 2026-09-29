"""Integration tests for FuelRoute API endpoints, middleware, and error handling."""

from __future__ import annotations

import json

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

from apps.stations.index import reload_index
from apps.stations.models import FuelStation


@pytest.fixture(autouse=True)
def setup_api_environment(db, settings):
    """Ensure fixture provider, rate limit bypass by default, and loaded stations."""
    settings.ROUTING_PROVIDER = "fixture"
    settings.DISABLE_RATE_LIMIT = True
    cache.clear()

    if FuelStation.objects.count() == 0:
        call_command("load_stations", "--input", "data/stations_geocoded.csv")
    reload_index()


def test_route_chicago_to_dallas_post_success():
    client = Client()
    payload = {"start": "Chicago, IL", "finish": "Dallas, TX"}
    response = client.post(
        "/api/v1/route",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers.get("X-External-Calls") == "1"
    assert "Server-Timing" in response.headers

    data = response.json()
    assert data["request"]["start"]["label"] == "Chicago, IL"
    assert data["request"]["finish"]["label"] == "Dallas, TX"
    assert data["route"]["distance_miles"] > 800
    assert len(data["fuel_plan"]["stops"]) >= 1
    assert data["fuel_plan"]["totals"]["total_fuel_cost_usd"] > 0
    assert data["meta"]["external_calls"] == 1
    assert data["meta"]["cache"] == "miss"
    assert "map" in data and "html_url" in data["map"]
    assert "geojson" in data["map"]


def test_route_cache_hit_behavior():
    client = Client()
    payload = {"start": "Chicago, IL", "finish": "Dallas, TX"}

    # First call (miss)
    resp1 = client.post("/api/v1/route", data=json.dumps(payload), content_type="application/json")
    assert resp1.status_code == 200
    assert resp1.headers.get("X-External-Calls") == "1"
    assert resp1.json()["meta"]["cache"] == "miss"

    # Second call (hit: 0 external calls)
    resp2 = client.post("/api/v1/route", data=json.dumps(payload), content_type="application/json")
    assert resp2.status_code == 200
    assert resp2.headers.get("X-External-Calls") == "0"
    assert resp2.json()["meta"]["cache"] == "hit"
    assert resp2.json()["meta"]["external_calls"] == 0


def test_route_nyc_to_la_cross_country():
    client = Client()
    payload = {"start": "New York, NY", "finish": "Los Angeles, CA"}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["route"]["distance_miles"] > 2700
    # Cross-country requires at least 5 stops at 500-mi range
    stops = data["fuel_plan"]["stops"]
    assert len(stops) >= 5
    assert data["fuel_plan"]["totals"]["stops"] == len(stops)
    assert data["fuel_plan"]["totals"]["total_fuel_cost_usd"] > 0

    # Verify no leg exceeds 500 miles
    current_mile = 0.0
    for s in stops:
        assert s["mile_marker"] - current_mile <= 500.0 + 1e-4
        current_mile = s["mile_marker"]
    assert data["route"]["distance_miles"] - current_mile <= 500.0 + 1e-4


def test_route_chicago_to_st_louis_short():
    client = Client()
    payload = {"start": "Chicago, IL", "finish": "St. Louis, MO"}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["route"]["distance_miles"] < 500
    assert len(data["fuel_plan"]["stops"]) <= 1


def test_route_get_endpoint_parity():
    client = Client()
    response = client.get("/api/v1/route?start=Chicago,%20IL&finish=Dallas,%20TX")

    assert response.status_code == 200
    data = response.json()
    assert data["request"]["start"]["label"] == "Chicago, IL"
    assert data["request"]["finish"]["label"] == "Dallas, TX"
    assert data["route"]["distance_miles"] > 800


def test_route_map_view():
    client = Client()
    response = client.get("/api/v1/route/map?start=Chicago,%20IL&finish=Dallas,%20TX")

    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    content = response.content.decode("utf-8")
    assert "FuelRoute" in content
    assert "leaflet.js" in content
    assert 'id="plan-data"' in content
    assert "Chicago, IL" in content


def test_request_id_preservation():
    client = Client()
    custom_id = "test-custom-request-id-12345"
    response = client.post(
        "/api/v1/route",
        data=json.dumps({"start": "Chicago, IL", "finish": "Dallas, TX"}),
        content_type="application/json",
        headers={"X-Request-ID": custom_id},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
    assert response.json()["meta"]["request_id"] == custom_id


def test_validation_errors():
    client = Client()

    # Missing start
    r1 = client.post(
        "/api/v1/route", data=json.dumps({"finish": "Dallas, TX"}), content_type="application/json"
    )
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "VALIDATION_ERROR"

    # String > 200 chars
    long_str = "A" * 201
    r2 = client.post(
        "/api/v1/route",
        data=json.dumps({"start": long_str, "finish": "Dallas, TX"}),
        content_type="application/json",
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "VALIDATION_ERROR"

    # Invalid JSON
    r3 = client.post("/api/v1/route", data="{not-valid-json", content_type="application/json")
    assert r3.status_code == 400
    assert r3.json()["error"]["code"] == "VALIDATION_ERROR"

    # Oversized payload (> 4 KB)
    huge_data = json.dumps({"start": "Chicago, IL", "finish": "Dallas, TX", "extra": "x" * 5000})
    r4 = client.post("/api/v1/route", data=huge_data, content_type="application/json")
    assert r4.status_code == 400
    assert r4.json()["error"]["code"] == "VALIDATION_ERROR"

    # Invalid MPG
    r5 = client.post(
        "/api/v1/route",
        data=json.dumps({"start": "Chicago, IL", "finish": "Dallas, TX", "mpg": -5}),
        content_type="application/json",
    )
    assert r5.status_code == 400
    assert r5.json()["error"]["code"] == "VALIDATION_ERROR"

    # Method not allowed
    r6 = client.delete("/api/v1/route")
    assert r6.status_code == 405
    assert r6.json()["error"]["code"] == "VALIDATION_ERROR"


def test_domain_outside_usa():
    client = Client()
    # Toronto is outside contiguous USA bounds
    payload = {"start": "43.6532,-79.3832", "finish": "Dallas, TX"}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "OUTSIDE_USA"


def test_domain_same_location():
    client = Client()
    payload = {"start": "Chicago, IL", "finish": "Chicago, IL"}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SAME_LOCATION"


def test_domain_no_route(monkeypatch):
    from apps.providers.errors import NoRouteError

    def mock_get_route(*args, **kwargs):
        raise NoRouteError("Route provider indicates NoRoute between endpoints")

    monkeypatch.setattr("apps.planner.service.get_route", mock_get_route)
    client = Client()
    payload = {"start": "Chicago, IL", "finish": "Dallas, TX"}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_ROUTE"


def test_rate_limiting_middleware(settings):
    settings.RATE_LIMIT_PER_MIN = 2
    settings.DISABLE_RATE_LIMIT = False

    client = Client()
    payload = {"start": "Chicago, IL", "finish": "Dallas, TX"}

    r1 = client.post("/api/v1/route", data=json.dumps(payload), content_type="application/json")
    assert r1.status_code == 200

    r2 = client.post("/api/v1/route", data=json.dumps(payload), content_type="application/json")
    assert r2.status_code == 200

    # 3rd request in same minute exceeds limit
    r3 = client.post("/api/v1/route", data=json.dumps(payload), content_type="application/json")
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "RATE_LIMITED"
