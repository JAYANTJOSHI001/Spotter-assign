import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import numpy as np
import pytest

from apps.stations.index import (
    IndexEmpty,
    StationIndex,
    _compute_data_version,
    _compute_unit_vectors,
    get_index,
    reload_index,
)
from apps.stations.models import FuelStation
from apps.stations.pricing import median_price_in_window, national_median_price


@pytest.fixture
def sample_stations(db):
    stations = [
        FuelStation(
            opis_id=100 + i,
            name=f"Station {i}",
            address=f"{i} Main St",
            city=f"City {i}",
            state="IL",
            rack_id=1,
            price=Decimal(f"3.{i}000"),
            price_min=Decimal(f"3.{i}000"),
            price_max=Decimal(f"3.{i}000"),
            n_price_rows=1,
            lat=40.0 + i * 0.1,
            lng=-88.0 - i * 0.1,
            geocode_method="place",
            geocode_confidence=1.0,
        )
        for i in range(5)
    ]
    FuelStation.objects.bulk_create(stations)
    return stations


@pytest.mark.django_db
def test_index_loads_all_db_rows(sample_stations):
    """Verify that get_index loads N rows equal to FuelStation.objects.count()."""
    db_count = FuelStation.objects.count()
    assert db_count == 5
    index = reload_index()
    assert len(index) == db_count
    assert len(index.opis_id) == db_count
    assert len(index.lat) == db_count
    assert len(index.lng) == db_count
    assert len(index.price) == db_count
    assert len(index.unit_vectors) == db_count
    assert len(index.metadata) == db_count


def test_unit_vectors_have_unit_norm():
    """Verify that computed unit vectors have norm 1.0 ± 1e-12."""
    lats = np.array([0.0, 90.0, -90.0, 45.0, -33.8688, 37.7749])
    lngs = np.array([0.0, 0.0, 0.0, 45.0, 151.2093, -122.4194])

    uv = _compute_unit_vectors(lats, lngs)
    norms = np.linalg.norm(uv, axis=1)

    np.testing.assert_allclose(norms, 1.0, atol=1e-12)


def test_data_version_stability_and_sensitivity():
    """Verify data_version is stable across runs and sensitive to price changes."""
    opis = np.array([1, 2, 3], dtype=np.int64)
    prices_a = np.array([3.199, 3.299, 3.399], dtype=np.float64)
    lats = np.array([30.0, 35.0, 40.0], dtype=np.float64)
    lngs = np.array([-80.0, -85.0, -90.0], dtype=np.float64)

    v1 = _compute_data_version(opis, prices_a, lats, lngs)
    v2 = _compute_data_version(opis, prices_a, lats, lngs)
    assert v1 == v2
    assert v1.startswith("sha1:")

    # Change single price -> version must change
    prices_b = np.array([3.199, 3.300, 3.399], dtype=np.float64)
    v3 = _compute_data_version(opis, prices_b, lats, lngs)
    assert v3 != v1


def test_concurrent_access_single_load(monkeypatch):
    """Verify that concurrent access from 16 threads results in exactly one load."""
    import apps.stations.index as idx_module

    # Reset singleton
    idx_module._index = None

    load_call_count = 0
    dummy_index = StationIndex(
        opis_id=np.array([1]),
        lat=np.array([40.0]),
        lng=np.array([-88.0]),
        price=np.array([3.5]),
        unit_vectors=np.zeros((1, 3)),
        metadata=(),
        data_version="sha1:dummy",
    )

    def mock_load():
        nonlocal load_call_count
        load_call_count += 1
        time.sleep(0.01)  # Introduce contention across threads
        return dummy_index

    monkeypatch.setattr(idx_module, "_load_from_db", mock_load)

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(get_index) for _ in range(16)]
        results = [f.result() for f in futures]

    assert len(results) == 16
    assert all(r is dummy_index for r in results)
    assert load_call_count == 1


@pytest.mark.django_db
def test_empty_db_raises_index_empty():
    """Verify that an empty database raises IndexEmpty."""
    FuelStation.objects.all().delete()
    with pytest.raises(IndexEmpty, match="FuelStation table is empty"):
        reload_index()


def test_pricing_helpers():
    """Verify national_median_price and median_price_in_window."""
    mock_index = StationIndex(
        opis_id=np.array([1, 2, 3]),
        lat=np.array([30.0, 31.0, 32.0]),
        lng=np.array([-80.0, -81.0, -82.0]),
        price=np.array([3.10, 3.30, 3.50]),
        unit_vectors=np.zeros((3, 3)),
        metadata=(),
        data_version="sha1:test",
    )

    assert national_median_price(mock_index) == Decimal("3.3000")

    prices = np.array([3.20, 3.40, 3.60, 3.80])
    miles = np.array([10.0, 50.0, 90.0, 150.0])

    med_100 = median_price_in_window(prices, miles, max_mile=100.0)
    assert med_100 == Decimal("3.4000")

    med_empty = median_price_in_window(prices, miles, max_mile=5.0)
    assert med_empty is None
