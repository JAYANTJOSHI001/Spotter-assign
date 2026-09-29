import numpy as np

from apps.geo.distance import (
    chord_to_miles,
    haversine_miles,
    miles_to_chord,
    to_unit_vectors,
)


def test_haversine_known_pairs():
    # NYC (40.7128° N, 74.0060° W) to LA (34.0522° N, 118.2437° W)
    # Great circle distance is ~2,445 statute miles (±10 miles tolerance)
    nyc_la = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
    assert 2435.0 <= nyc_la <= 2455.0

    # Equator 1 degree longitude: (0.0, 0.0) to (0.0, 1.0)
    # 2 * pi * 3958.7613 / 360 ≈ 69.096 miles
    eq_1deg = haversine_miles(0.0, 0.0, 0.0, 1.0)
    assert abs(eq_1deg - 69.1) < 0.2

    # Zero distance between identical points
    assert haversine_miles(35.0, -90.0, 35.0, -90.0) == 0.0


def test_haversine_vectorized():
    lat1 = np.array([40.7128, 0.0])
    lng1 = np.array([-74.0060, 0.0])
    lat2 = np.array([34.0522, 0.0])
    lng2 = np.array([-118.2437, 1.0])

    dists = haversine_miles(lat1, lng1, lat2, lng2)
    assert len(dists) == 2
    assert 2435.0 <= dists[0] <= 2455.0
    assert abs(dists[1] - 69.1) < 0.2


def test_chord_miles_roundtrip():
    test_distances = [0.0, 0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 2500.0, 5000.0]
    for d in test_distances:
        chord = miles_to_chord(d)
        recovered = chord_to_miles(chord)
        assert abs(recovered - d) < 1e-9

    arr = np.array(test_distances)
    np.testing.assert_allclose(chord_to_miles(miles_to_chord(arr)), arr, atol=1e-9)


def test_to_unit_vectors():
    lats = np.array([0.0, 90.0, -90.0, 45.0, -25.0])
    lngs = np.array([0.0, 0.0, 0.0, 45.0, 120.0])

    uv = to_unit_vectors(lats, lngs)
    assert uv.shape == (5, 3)

    norms = np.linalg.norm(uv, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)

    # North Pole: (0, 0, 1)
    np.testing.assert_allclose(to_unit_vectors(90.0, 0.0), [0.0, 0.0, 1.0], atol=1e-12)

    # Equator / Prime Meridian: (1, 0, 0)
    np.testing.assert_allclose(to_unit_vectors(0.0, 0.0), [1.0, 0.0, 0.0], atol=1e-12)
