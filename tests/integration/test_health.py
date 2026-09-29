import pytest
from django.test import Client

from apps.stations.index import reload_index
from apps.stations.models import FuelStation


@pytest.mark.django_db
def test_health_endpoint_with_stations():
    # Ensure index is populated
    FuelStation.objects.create(
        opis_id=9999,
        name="Test Station",
        address="123 Test Rd",
        city="Testville",
        state="IL",
        rack_id=1,
        price="3.2500",
        price_min="3.2500",
        price_max="3.2500",
        n_price_rows=1,
        lat=40.0,
        lng=-88.0,
        geocode_method="place",
        geocode_confidence=1.0,
    )
    reload_index()

    client = Client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["stations"] >= 1
    assert "data_version" in data
    assert data["data_version"].startswith("sha1:")


@pytest.mark.django_db
def test_health_endpoint_with_empty_db():
    import apps.stations.index as idx_mod

    idx_mod._index = None
    FuelStation.objects.all().delete()

    client = Client()
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["stations"] == 0
    assert data["error"] == "station index is empty"
