"""Unit tests for LocationResolver: coordinates, offline gazetteer, and Nominatim fallback."""

from __future__ import annotations

import pytest
import respx
from django.core.cache import cache

from apps.geo.resolver import resolve_location
from apps.providers.budget import CallBudget
from apps.providers.errors import LocationNotFound, OutsideUSA


@pytest.fixture(autouse=True)
def clean_state():
    cache.clear()
    yield
    cache.clear()


def test_resolve_coordinate_dict() -> None:
    budget = CallBudget(max_calls=3)
    loc = resolve_location({"lat": 41.8781, "lng": -87.6298}, budget)

    assert loc.source == "coordinates"
    assert pytest.approx(loc.lat, 0.0001) == 41.8781
    assert pytest.approx(loc.lng, 0.0001) == -87.6298
    assert loc.warning is None
    assert len(budget.calls) == 0  # 0 external calls


def test_resolve_coordinate_string() -> None:
    budget = CallBudget(max_calls=3)
    loc = resolve_location("41.8781, -87.6298", budget)

    assert loc.source == "coordinates"
    assert pytest.approx(loc.lat, 0.0001) == 41.8781
    assert pytest.approx(loc.lng, 0.0001) == -87.6298
    assert len(budget.calls) == 0


def test_resolve_swapped_coordinates() -> None:
    budget = CallBudget(max_calls=3)
    # Case 1: Provided as (lng, lat) where |lng| > 90 (Dallas: -96.7970, 32.7767)
    loc1 = resolve_location("-96.7970, 32.7767", budget)
    assert loc1.source == "coordinates"
    assert pytest.approx(loc1.lat, 0.0001) == 32.7767
    assert pytest.approx(loc1.lng, 0.0001) == -96.7970
    assert loc1.warning is not None
    assert "Swapped coordinates detected" in loc1.warning
    assert len(budget.calls) == 0

    # Case 2: Provided as (lng, lat) with negative US longitude (Chicago: -87.6298, 41.8781)
    loc2 = resolve_location("-87.6298, 41.8781", budget)
    assert loc2.source == "coordinates"
    assert pytest.approx(loc2.lat, 0.0001) == 41.8781
    assert pytest.approx(loc2.lng, 0.0001) == -87.6298
    assert loc2.warning is not None
    assert "Swapped coordinates detected" in loc2.warning
    assert len(budget.calls) == 0


def test_resolve_outside_usa_coordinates() -> None:
    budget = CallBudget(max_calls=3)
    # Toronto coords
    with pytest.raises(OutsideUSA):
        resolve_location("43.6532, -79.3832", budget)

    # Tijuana coords
    with pytest.raises(OutsideUSA):
        resolve_location("32.5149, -117.0382", budget)


def test_resolve_city_st_offline_gazetteer() -> None:
    budget = CallBudget(max_calls=3)

    loc1 = resolve_location("Chicago, IL", budget)
    assert loc1.source == "gazetteer"
    assert pytest.approx(loc1.lat, 0.2) == 41.88
    assert pytest.approx(loc1.lng, 0.2) == -87.63
    assert len(budget.calls) == 0

    loc2 = resolve_location("Dallas, TX", budget)
    assert loc2.source == "gazetteer"
    assert pytest.approx(loc2.lat, 0.2) == 32.78
    assert pytest.approx(loc2.lng, 0.2) == -96.80
    assert len(budget.calls) == 0

    loc3 = resolve_location("Fort Wayne, IN", budget)
    assert loc3.source == "gazetteer"
    assert pytest.approx(loc3.lat, 0.2) == 41.08
    assert pytest.approx(loc3.lng, 0.2) == -85.14
    assert len(budget.calls) == 0

    loc4 = resolve_location("St. Louis, MO", budget)
    assert loc4.source == "gazetteer"
    assert pytest.approx(loc4.lat, 0.2) == 38.63
    assert pytest.approx(loc4.lng, 0.2) == -90.20
    assert len(budget.calls) == 0


@respx.mock
def test_resolve_free_text_falls_to_nominatim() -> None:
    budget = CallBudget(max_calls=3)

    # Springfield without state -> not in "City, ST" gazetteer
    respx.get("https://nominatim.openstreetmap.org/search").respond(
        status_code=200,
        json=[
            {
                "lat": "39.7817",
                "lon": "-89.6501",
                "display_name": "Springfield, Illinois, USA",
            }
        ],
    )

    loc = resolve_location("Springfield", budget)
    assert loc.source == "nominatim"
    assert pytest.approx(loc.lat, 0.01) == 39.7817
    assert pytest.approx(loc.lng, 0.01) == -89.6501
    assert len(budget.calls) == 1
    assert budget.calls[0]["provider"] == "nominatim"


@respx.mock
def test_resolve_unresolvable_raises_location_not_found() -> None:
    budget = CallBudget(max_calls=3)

    respx.get("https://nominatim.openstreetmap.org/search").respond(status_code=200, json=[])

    with pytest.raises(LocationNotFound):
        resolve_location("SomeNonExistentPlaceNeverFound12345", budget)

    assert len(budget.calls) == 1
