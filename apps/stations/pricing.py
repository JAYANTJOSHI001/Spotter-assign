from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


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
