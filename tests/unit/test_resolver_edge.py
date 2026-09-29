import pytest

from apps.geo.resolver import _try_parse_coordinates, reset_gazetteer_index, resolve_location
from apps.providers.budget import CallBudget
from apps.providers.errors import LocationNotFound


def test_reset_gazetteer_index():
    reset_gazetteer_index()
    # Can still resolve after reset
    budget = CallBudget(max_calls=3)
    loc = resolve_location("Chicago, IL", budget=budget)
    assert loc.source == "gazetteer"
    assert loc.label == "Chicago, IL"


def test_try_parse_coordinates_invalid_dict():
    # Non-numeric dict values
    res = _try_parse_coordinates({"lat": "bad", "lng": "bad"})
    assert res is None


def test_try_parse_coordinates_invalid_str():
    # Looks like coord pattern but fails float parse
    res = _try_parse_coordinates(". , .")
    assert res is None


def test_resolver_empty_or_whitespace():
    budget = CallBudget(max_calls=3)
    with pytest.raises(LocationNotFound):
        resolve_location("   ", budget=budget)
