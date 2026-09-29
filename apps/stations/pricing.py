from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np


def resolve_price(prices: list[Decimal], policy: str = "min") -> Decimal:
    """Resolve a single representative price from multiple price observations.

    Args:
        prices: List of observed prices as Decimals.
        policy: Pricing aggregation policy, one of 'min', 'median', 'mean'.

    Returns:
        Decimal resolved price rounded to 4 decimal places (ROUND_HALF_UP).
    """
    if not prices:
        raise ValueError("prices list cannot be empty")

    policy_clean = policy.strip().lower()

    if policy_clean == "min":
        return min(prices)

    if policy_clean == "median":
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        if n % 2 == 1:
            return sorted_prices[n // 2]
        mid1 = sorted_prices[n // 2 - 1]
        mid2 = sorted_prices[n // 2]
        return ((mid1 + mid2) / Decimal(2)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if policy_clean == "mean":
        total = sum(prices)
        return (total / Decimal(len(prices))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    raise ValueError(f"Unknown pricing policy '{policy}'. Must be one of ('min', 'median', 'mean')")


def national_median_price(index: Any) -> Decimal:
    """Compute the overall national median price of all stations in the StationIndex."""
    prices = getattr(index, "price", None)
    if prices is None or len(prices) == 0:
        raise ValueError("StationIndex has no prices to compute national median")

    median_val = float(np.median(prices))
    return Decimal(str(round(median_val, 4))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def median_price_in_window(
    prices: np.ndarray,
    mile_markers: np.ndarray,
    max_mile: float,
) -> Decimal | None:
    """Compute the median price of candidate stations within [0, max_mile].

    Args:
        prices: 1D array of station prices.
        mile_markers: 1D array of mile markers matching prices.
        max_mile: Maximum mile threshold (e.g. 100.0).

    Returns:
        Decimal median price or None if no candidate stations exist within max_mile.
    """
    if len(prices) == 0 or len(mile_markers) == 0:
        return None

    mask = (mile_markers >= 0.0) & (mile_markers <= max_mile)
    window_prices = prices[mask]

    if len(window_prices) == 0:
        return None

    med = float(np.median(window_prices))
    return Decimal(str(round(med, 4))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
