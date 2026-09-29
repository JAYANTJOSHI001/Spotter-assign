import numpy as np
import pytest

from apps.geo.resample import (
    cumulative_miles,
    resample,
    scale_to_provider,
    simplify_for_response,
)


def test_cumulative_miles():
    lats = np.array([40.0, 40.0, 40.0])
    lngs = np.array([-100.0, -95.0, -90.0])

    cum = cumulative_miles(lats, lngs)
    assert len(cum) == 3
    assert cum[0] == 0.0
    assert cum[1] > 0.0
    assert cum[2] > cum[1]


def test_scale_to_provider_within_tolerance():
    cum = np.array([0.0, 100.0, 200.0])
    provider_miles = 205.0  # 2.5% diff -> within 5% tolerance

    scaled = scale_to_provider(cum, provider_miles)
    assert scaled[0] == 0.0
    assert scaled[-1] == 205.0
    np.testing.assert_allclose(scaled, np.array([0.0, 102.5, 205.0]))


def test_scale_to_provider_exceeds_tolerance_raises():
    cum = np.array([0.0, 100.0, 200.0])
    # 220.0 vs 200.0 is 10% diff -> exceeds 5% threshold
    with pytest.raises(ValueError, match="differs from provider distance .* by more than 5%"):
        scale_to_provider(cum, 220.0)


def test_resample_properties():
    # Route from Chicago (41.8781, -87.6298) to St. Louis (38.6270, -90.1994)
    lats = [41.8781, 40.5, 38.6270]
    lngs = [-87.6298, -89.0, -90.1994]

    samples = resample(lats, lngs, step_miles=0.5)

    # 1. Monotonically increasing mile markers
    diffs = np.diff(samples.mile)
    assert np.all(diffs > 0.0)

    # 2. Step spacing <= step_miles (0.5 + 1e-9)
    assert np.all(diffs <= 0.5 + 1e-9)

    # 3. Exact endpoint preserved
    assert samples.mile[0] == 0.0
    assert samples.mile[-1] == samples.total_miles
    assert abs(samples.lat[0] - lats[0]) < 1e-6
    assert abs(samples.lng[0] - lngs[0]) < 1e-6
    assert abs(samples.lat[-1] - lats[-1]) < 1e-6
    assert abs(samples.lng[-1] - lngs[-1]) < 1e-6


def test_resample_degenerate_raises():
    with pytest.raises(ValueError, match="Route coordinates must contain at least 2 points"):
        resample([40.0], [-90.0])

    with pytest.raises(ValueError, match="Route has zero total distance"):
        resample([40.0, 40.0], [-90.0, -90.0])


def test_simplify_for_response():
    # Generate synthetic curve with 3,000 points
    t = np.linspace(0, 10, 3000)
    lats = 35.0 + 0.1 * np.sin(t)
    lngs = -90.0 + t

    coords = list(zip(lats, lngs, strict=True))
    simplified = simplify_for_response(coords, max_points=1500)

    assert len(simplified) <= 1500
    assert len(simplified) >= 2

    # Endpoints preserved
    np.testing.assert_allclose(simplified[0], coords[0], atol=1e-9)
    np.testing.assert_allclose(simplified[-1], coords[-1], atol=1e-9)

    # If input is already <= max_points, returned unchanged
    small_coords = coords[:500]
    assert len(simplify_for_response(small_coords, max_points=1500)) == 500
