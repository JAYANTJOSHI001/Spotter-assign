import time

import hypothesis.strategies as st
import numpy as np
import pytest
from hypothesis import given, settings

from apps.geo.corridor import match_corridor, widening_schedule
from apps.geo.distance import haversine_miles, to_unit_vectors
from apps.geo.resample import resample


def test_corridor_matcher_known_offsets():
    # Straight west-to-east route along latitude 40.0 from lng -100.0 to -90.0
    lats = [40.0, 40.0]
    lngs = [-100.0, -90.0]
    samples = resample(lats, lngs, step_miles=0.5)

    # 1 degree of latitude ≈ 69.05 miles at this latitude
    # Miles per degree lat: haversine_miles(40.0, -95.0, 41.0, -95.0) ≈ 69.096 miles
    mi_per_deg_lat = haversine_miles(40.0, -95.0, 41.0, -95.0)

    # Place synthetic stations along the route at longitude -95.0 with known offsets:
    # 0 mi, 5 mi, 9.9 mi, 10.1 mi north of route
    offsets_target = [0.0, 5.0, 9.9, 10.1]
    station_lats = [40.0 + (off / mi_per_deg_lat) for off in offsets_target]
    station_lngs = [-95.0 for _ in offsets_target]

    station_uv = to_unit_vectors(np.array(station_lats), np.array(station_lngs))

    # Buffer = 10.0 miles
    candidates = match_corridor(samples, station_uv, buffer_miles=10.0)

    # Only stations with offset <= 10.0 should be included (indices 0, 1, 2)
    assert len(candidates) == 3
    assert set(candidates.station_idx) == {0, 1, 2}

    # Verify offset accuracy within ±0.3 miles (due to discrete 0.5-mi sampling along route)
    for idx, cand_idx in enumerate(candidates.station_idx):
        expected_off = offsets_target[cand_idx]
        actual_off = candidates.offset_miles[idx]
        assert abs(actual_off - expected_off) < 0.35

    # Verify mile marker is near midpoint of route (~264 miles)
    mid_mile = samples.total_miles / 2.0
    for mm in candidates.mile_marker:
        assert abs(mm - mid_mile) < 1.0


@given(
    buffer_miles=st.floats(min_value=1.0, max_value=50.0),
    num_stations=st.integers(min_value=5, max_value=50),
)
@settings(max_examples=25, deadline=None)
def test_corridor_matcher_property_invariants(buffer_miles, num_stations):
    # Route across central US
    samples = resample([35.0, 36.0, 37.0], [-95.0, -90.0, -85.0], step_miles=1.0)

    # Random stations across the region
    rng = np.random.default_rng(42)
    st_lats = rng.uniform(34.0, 38.0, size=num_stations)
    st_lngs = rng.uniform(-96.0, -84.0, size=num_stations)
    station_uv = to_unit_vectors(st_lats, st_lngs)

    candidates = match_corridor(samples, station_uv, buffer_miles=buffer_miles)

    if len(candidates) > 0:
        # Invariant 1: Matched offsets never exceed the buffer (with numerical tolerance)
        assert np.all(candidates.offset_miles <= buffer_miles + 1e-6)

        # Invariant 2: Mile markers within [0, total_miles]
        assert np.all(candidates.mile_marker >= 0.0)
        assert np.all(candidates.mile_marker <= samples.total_miles + 1e-6)

        # Invariant 3: Candidates sorted by (mile_marker, offset_miles)
        for i in range(len(candidates) - 1):
            assert candidates.mile_marker[i] <= candidates.mile_marker[i + 1]


def test_widening_schedule():
    assert widening_schedule("10,25,50") == [10.0, 25.0, 50.0]
    assert widening_schedule("  15 , 30 , 60 ") == [15.0, 30.0, 60.0]
    assert widening_schedule(None) == [10.0, 25.0, 50.0]

    with pytest.raises(ValueError):
        widening_schedule("")

    with pytest.raises(ValueError):
        widening_schedule("10,-5,50")


def test_corridor_benchmark_performance():
    """10k-sample route x 6.6k stations completes in < 50 ms median."""
    # Synthetic long cross-country route (~5,000 miles at 0.5 mi step -> ~10,000 points)
    t = np.linspace(0, 10, 10000)
    route_lats = 35.0 + 3.0 * np.sin(t)
    route_lngs = np.linspace(-120.0, -75.0, 10000)
    samples = resample(route_lats, route_lngs, step_miles=0.5)

    # 6,611 realistic stations across the US
    rng = np.random.default_rng(1234)
    station_lats = rng.uniform(28.0, 48.0, size=6611)
    station_lngs = rng.uniform(-122.0, -72.0, size=6611)
    station_uv = to_unit_vectors(station_lats, station_lngs)

    # Warm-up run
    match_corridor(samples, station_uv, buffer_miles=10.0)

    # Benchmark 5 runs
    timings_ms = []
    for _ in range(5):
        t0 = time.perf_counter()
        match_corridor(samples, station_uv, buffer_miles=10.0)
        timings_ms.append((time.perf_counter() - t0) * 1000.0)

    median_ms = float(np.median(timings_ms))
    print(
        f"\n[BENCHMARK] 10k-sample route x 6.6k stations: {median_ms:.2f} ms median (Target < 50 ms)"
    )
    assert median_ms < 50.0, f"Corridor match median time {median_ms:.2f} ms exceeded 50 ms limit"
