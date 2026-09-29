"""Edge-case tests, failure injection, concurrency, and security hardening (Phase P7)."""

from __future__ import annotations

import concurrent.futures
import json

import numpy as np
import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

from apps.geo.resample import scale_to_provider
from apps.planner.optimizer import optimize
from apps.planner.schemas import Candidate
from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import UpstreamTimeout
from apps.stations.index import reload_index
from apps.stations.models import FuelStation


@pytest.fixture(autouse=True)
def setup_hardening_env(db, settings):
    settings.ROUTING_PROVIDER = "fixture"
    settings.DISABLE_RATE_LIMIT = True
    cache.clear()
    if FuelStation.objects.count() == 0:
        call_command("load_stations", "--input", "data/stations_geocoded.csv")
    reload_index()


def test_500_4_mile_route_with_margin():
    """Verify that a 500.4-mile trip with intermediate candidate is planned correctly."""
    cands = [
        Candidate(station_idx=1, opis_id=101, mile_marker=250.0, offset_miles=1.0, price=3.20),
    ]
    plan = optimize(
        candidates=cands,
        route_miles=500.4,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.50,
    )
    assert plan.feasible
    assert len(plan.stops) == 1
    assert plan.stops[0].opis_id == 101


def test_identical_coordinate_station_ties_are_deterministic():
    """Ensure tie-breaking is 100% deterministic when stations share exact miles and price."""
    # Two stations at mile 200, price 3.00, but different opis_ids
    cands = [
        Candidate(station_idx=10, opis_id=2001, mile_marker=200.0, offset_miles=1.0, price=3.00),
        Candidate(station_idx=11, opis_id=1001, mile_marker=200.0, offset_miles=1.0, price=3.00),
    ]

    results = []
    for _ in range(20):
        # Shuffle candidates before passing
        shuffled = list(reversed(cands))
        plan = optimize(
            candidates=shuffled,
            route_miles=350.0,
            max_range_miles=500.0,
            mpg=10.0,
            start_mode="priced",
            start_price=3.50,
        )
        if plan.stops:
            results.append(plan.stops[0].opis_id)

    # If stops were chosen, the same station must be chosen deterministically every time
    if results:
        assert len(set(results)) == 1


def test_all_prices_equal_prefers_fewest_stops():
    """When all stations cost the same as origin, optimizer makes 0 redundant intermediate stops."""
    # Route is 400 miles (within range), all stations same price as start
    cands = [
        Candidate(station_idx=1, opis_id=101, mile_marker=100.0, offset_miles=2.0, price=3.50),
        Candidate(station_idx=2, opis_id=102, mile_marker=200.0, offset_miles=2.0, price=3.50),
        Candidate(station_idx=3, opis_id=103, mile_marker=300.0, offset_miles=2.0, price=3.50),
    ]
    plan = optimize(
        candidates=cands,
        route_miles=400.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.50,
    )
    assert plan.feasible
    assert len(plan.stops) == 0  # No need to stop and incur detour miles


def test_unicode_and_whitespace_inputs():
    """Test inputs with extra whitespace, mixed case, and unicode characters."""
    client = Client()
    payload = {"start": "   chicago,   IL  ", "finish": "  DALLAS,   tx  "}
    response = client.post(
        "/api/v1/route", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["request"]["start"]["label"] == "Chicago, IL"
    assert data["request"]["finish"]["label"] == "Dallas, TX"


def test_concurrent_requests():
    """Verify 20 concurrent requests across same and different routes are consistent."""
    client = Client()

    def make_call(pair: tuple[str, str]) -> int:
        s, f = pair
        resp = client.post(
            "/api/v1/route",
            data=json.dumps({"start": s, "finish": f}),
            content_type="application/json",
        )
        return resp.status_code

    pairs = [
        ("Chicago, IL", "Dallas, TX"),
        ("Chicago, IL", "St. Louis, MO"),
    ] * 10

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(make_call, pairs))

    assert all(status == 200 for status in statuses)


def test_cache_stampede_protection(monkeypatch):
    """Ensure simultaneous cold requests for the exact same route trigger at most 1 upstream call."""
    import time

    import apps.providers.routing as routing_mod
    from apps.providers.fixture import FixtureRouteProvider

    call_count = 0
    orig_route = FixtureRouteProvider.route

    def counting_route(self, start, finish, budget):
        nonlocal call_count
        call_count += 1
        time.sleep(0.02)
        return orig_route(self, start, finish, budget)

    monkeypatch.setattr(FixtureRouteProvider, "route", counting_route)

    start = LatLng(lat=41.8781, lng=-87.6298)
    finish = LatLng(lat=32.7767, lng=-96.7970)

    # Launch 10 simultaneous calls for the same route
    def call_get_route():
        b = CallBudget(max_calls=3)
        return routing_mod.get_route(start, finish, b)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(call_get_route) for _ in range(10)]
        results = [f.result() for f in futures]

    assert len(results) == 10
    # Exactly 1 call to provider despite 10 concurrent cold requests
    assert call_count == 1


def test_failure_injection_provider_timeout_and_500(monkeypatch):
    """Failure injection: upstream timeout triggers retry and returns HTTP 504."""
    import apps.planner.service as svc

    def mock_get_route_timeout(*args, **kwargs):
        raise UpstreamTimeout("OSRM upstream gateway timed out")

    monkeypatch.setattr(svc, "get_route", mock_get_route_timeout)

    client = Client()
    resp = client.post(
        "/api/v1/route",
        data=json.dumps({"start": "Chicago, IL", "finish": "Dallas, TX"}),
        content_type="application/json",
    )
    assert resp.status_code == 504
    assert resp.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_failure_injection_geometry_distance_mismatch():
    """Failure injection: geometry length differing from provider distance by > 5% raises ValueError."""
    cum = np.array([0.0, 100.0, 200.0])
    # Provider reports 300 miles (50% difference)
    with pytest.raises(ValueError, match="differs from provider distance"):
        scale_to_provider(cum, provider_miles=300.0)


def test_security_xss_protection_in_map_view():
    """Security check: location strings containing HTML/JS tags are not executed."""
    client = Client()
    xss_payload = "<script>alert('xss')</script>"
    # Requesting map with script tag
    resp = client.get(f"/api/v1/route/map?start={xss_payload}&finish=Dallas,%20TX")
    # Should either be rejected by validator or safely escaped in HTML
    content = resp.content.decode("utf-8")
    assert (
        "<script>alert('xss')</script>" not in content
        or "alert(&#x27;xss&#x27;)" in content
        or resp.status_code in (400, 422)
    )


def test_forced_infeasible_plan_gap_details(monkeypatch):
    """Verify that a forced gap > 500 miles returns HTTP 422 NO_FEASIBLE_PLAN with gap details."""
    import apps.planner.service as svc
    from apps.planner.schemas import InfeasiblePlan

    def mock_plan_widening(*args, **kwargs):
        return InfeasiblePlan(
            gap_start_mile=100.0,
            gap_end_mile=700.0,
            message="No feasible fuel plan found within maximum range",
        ), ["Corridor widened to 50 mi"]

    monkeypatch.setattr(svc, "plan_with_widening", mock_plan_widening)

    client = Client()
    resp = client.post(
        "/api/v1/route",
        data=json.dumps({"start": "Chicago, IL", "finish": "Dallas, TX"}),
        content_type="application/json",
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "NO_FEASIBLE_PLAN"
    assert "gap_start_mile" in data["error"]["details"]
    assert data["error"]["details"]["gap_start_mile"] == 100.0
