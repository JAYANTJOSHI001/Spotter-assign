from decimal import Decimal

import pytest

from apps.stations.pricing import resolve_price


def test_resolve_price_min():
    prices = [Decimal("3.50"), Decimal("3.20"), Decimal("3.80")]
    assert resolve_price(prices, policy="min") == Decimal("3.20")


def test_resolve_price_median_odd():
    prices = [Decimal("3.50"), Decimal("3.20"), Decimal("3.80")]
    assert resolve_price(prices, policy="median") == Decimal("3.50")


def test_resolve_price_median_even():
    prices = [Decimal("3.20"), Decimal("3.40"), Decimal("3.60"), Decimal("3.80")]
    assert resolve_price(prices, policy="median") == Decimal("3.5000")


def test_resolve_price_mean():
    prices = [Decimal("3.00"), Decimal("3.50"), Decimal("4.00")]
    assert resolve_price(prices, policy="mean") == Decimal("3.5000")


def test_resolve_price_single_element():
    prices = [Decimal("3.259")]
    assert resolve_price(prices, policy="min") == Decimal("3.259")
    assert resolve_price(prices, policy="median") == Decimal("3.259")
    assert resolve_price(prices, policy="mean") == Decimal("3.2590")


def test_resolve_price_empty_raises():
    with pytest.raises(ValueError, match="prices list cannot be empty"):
        resolve_price([], policy="min")


def test_resolve_price_invalid_policy_raises():
    with pytest.raises(ValueError, match="Unknown pricing policy"):
        resolve_price([Decimal("3.00")], policy="random")
