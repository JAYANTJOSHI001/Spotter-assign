"""Unit tests for NominatimGeocoder with caching (no network)."""

from __future__ import annotations

import pytest
import respx
from django.core.cache import cache

from apps.providers.budget import CallBudget
from apps.providers.errors import LocationNotFound, UpstreamError
from apps.providers.nominatim import NominatimGeocoder, close_client


@pytest.fixture(autouse=True)
def clean_env():
    cache.clear()
    close_client()
    yield
    cache.clear()
    close_client()


@respx.mock
def test_nominatim_success_and_cache() -> None:
    geocoder = NominatimGeocoder(
        base_url="https://test.nominatim.org",
        user_agent="fuelroute-test/1.0",
    )
    budget = CallBudget(max_calls=3)

    mock_resp = [
        {
            "lat": "39.7817",
            "lon": "-89.6501",
            "display_name": "Springfield, Sangamon County, Illinois, United States",
        }
    ]

    respx.get("https://test.nominatim.org/search").respond(status_code=200, json=mock_resp)

    # First call: cache miss, consumes 1 budget call
    res1 = geocoder.geocode("Springfield", budget)
    assert res1.lat == 39.7817
    assert res1.lng == -89.6501
    assert res1.source == "nominatim"
    assert len(budget.calls) == 1

    # Second call: cache hit, makes 0 HTTP calls and consumes 0 budget
    res2 = geocoder.geocode("Springfield", budget)
    assert res2.lat == 39.7817
    assert res2.lng == -89.6501
    assert len(budget.calls) == 1  # Still 1 call


@respx.mock
def test_nominatim_not_found_negative_cache() -> None:
    geocoder = NominatimGeocoder(
        base_url="https://test.nominatim.org",
        user_agent="fuelroute-test/1.0",
    )
    budget = CallBudget(max_calls=3)

    respx.get("https://test.nominatim.org/search").respond(status_code=200, json=[])

    with pytest.raises(LocationNotFound):
        geocoder.geocode("NonExistentPlaceXYZ123", budget)

    assert len(budget.calls) == 1

    # Second call uses negative cache: raises LocationNotFound with 0 extra calls
    with pytest.raises(LocationNotFound):
        geocoder.geocode("NonExistentPlaceXYZ123", budget)

    assert len(budget.calls) == 1


@respx.mock
def test_nominatim_403_user_agent() -> None:
    geocoder = NominatimGeocoder(
        base_url="https://test.nominatim.org",
        user_agent="",
    )
    budget = CallBudget(max_calls=3)

    respx.get("https://test.nominatim.org/search").respond(status_code=403, text="Forbidden")

    with pytest.raises(UpstreamError) as exc_info:
        geocoder.geocode("Anywhere", budget)

    assert "HTTP 403" in str(exc_info.value)
