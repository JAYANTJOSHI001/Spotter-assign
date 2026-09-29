"""Property-based tests for optimizer: baseline dominance, invariants, scaling, determinism."""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from apps.planner.optimizer import optimize
from apps.planner.schemas import Candidate, Plan
from apps.planner.simulate import validate_plan


def make_cands(n: int, max_mile: float, seed: int) -> list[Candidate]:
    rng = random.Random(seed)
    cands: list[Candidate] = []
    for i in range(n):
        mile = round(rng.uniform(10.0, max_mile - 10.0), 1)
        offset = round(rng.uniform(0.0, 5.0), 1)
        price = round(rng.uniform(2.50, 4.50), 3)
        cands.append(
            Candidate(
                station_idx=i + 1,
                opis_id=2000 + i,
                mile_marker=mile,
                offset_miles=offset,
                price=price,
            )
        )
    return sorted(cands, key=lambda c: (c.mile_marker, c.price, c.opis_id))


def fill_at_every_stop_cost(
    candidates: list[Candidate],
    route_miles: float,
    max_range: float = 500.0,
    mpg: float = 10.0,
    start_price: float = 3.50,
) -> float | None:
    """Heuristic baseline: stops at every feasible candidate and fills tank to full."""
    pos = 0.0
    fuel = max_range
    total_cost = (max_range / mpg) * start_price

    for c in candidates:
        leg = c.mile_marker - pos
        detour = 2.0 * c.offset_miles
        needed = leg + detour
        if needed > fuel:
            return None  # Infeasible for this sequential chain
        fuel -= needed
        to_fill = max_range - fuel
        total_cost += (to_fill / mpg) * c.price
        fuel = max_range
        pos = c.mile_marker

    final_leg = route_miles - pos
    if final_leg > fuel:
        return None
    return total_cost


def test_dp_dominates_fill_at_every_stop() -> None:
    """DP optimal cost must always be <= naive fill-at-every-stop heuristic."""
    for seed in range(50):
        cands = make_cands(n=4, max_mile=800.0, seed=seed)
        plan = optimize(
            candidates=cands,
            route_miles=800.0,
            max_range_miles=500.0,
            mpg=10.0,
            start_mode="priced",
            start_price=3.80,
        )

        if isinstance(plan, Plan) and plan.feasible:
            baseline_cost = fill_at_every_stop_cost(
                candidates=plan.stops,  # using visited chain
                route_miles=800.0,
                max_range=500.0,
                mpg=10.0,
                start_price=3.80,
            )
            if baseline_cost is not None:
                assert float(plan.total_cost_usd) <= baseline_cost + 1.0


def test_cheaper_candidate_never_increases_cost() -> None:
    """Adding a cheaper candidate along the route must not increase optimal cost."""
    for seed in range(30):
        cands = make_cands(n=5, max_mile=1000.0, seed=seed)
        plan1 = optimize(
            candidates=cands,
            route_miles=1000.0,
            max_range_miles=500.0,
            mpg=10.0,
            start_mode="priced",
            start_price=4.00,
        )

        if isinstance(plan1, Plan) and plan1.feasible:
            # Add an extra cheap station at mile 450
            cheaper_station = Candidate(
                station_idx=999,
                opis_id=9999,
                mile_marker=450.0,
                offset_miles=0.5,
                price=1.80,
            )
            augmented = sorted(
                cands + [cheaper_station], key=lambda c: (c.mile_marker, c.price, c.opis_id)
            )

            plan2 = optimize(
                candidates=augmented,
                route_miles=1000.0,
                max_range_miles=500.0,
                mpg=10.0,
                start_mode="priced",
                start_price=4.00,
            )
            assert isinstance(plan2, Plan)
            assert plan2.feasible
            assert plan2.total_cost_usd <= plan1.total_cost_usd + Decimal("0.05")


def test_price_scaling_invariance() -> None:
    """Scaling all fuel prices by constant alpha scales the optimal cost by alpha."""
    for seed in range(20):
        cands = make_cands(n=4, max_mile=900.0, seed=seed)
        plan1 = optimize(
            candidates=cands,
            route_miles=900.0,
            max_range_miles=500.0,
            mpg=10.0,
            start_mode="priced",
            start_price=3.50,
        )

        if isinstance(plan1, Plan) and plan1.feasible:
            alpha = 1.5
            scaled_cands = [
                Candidate(
                    station_idx=c.station_idx,
                    opis_id=c.opis_id,
                    mile_marker=c.mile_marker,
                    offset_miles=c.offset_miles,
                    price=round(c.price * alpha, 4),
                )
                for c in cands
            ]

            plan2 = optimize(
                candidates=scaled_cands,
                route_miles=900.0,
                max_range_miles=500.0,
                mpg=10.0,
                start_mode="priced",
                start_price=round(3.50 * alpha, 4),
            )
            assert isinstance(plan2, Plan)
            expected_cost = float(plan1.total_cost_usd) * alpha
            assert pytest.approx(float(plan2.total_cost_usd), abs=0.50) == expected_cost


def test_optimizer_determinism() -> None:
    """Repeated calls with identical inputs must return identical plans."""
    cands = make_cands(n=10, max_mile=800.0, seed=42)
    plan1 = optimize(
        candidates=cands,
        route_miles=800.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.40,
    )
    plan2 = optimize(
        candidates=cands,
        route_miles=800.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.40,
    )

    assert isinstance(plan1, Plan)
    assert isinstance(plan2, Plan)
    assert plan1.total_cost_usd == plan2.total_cost_usd
    assert plan1.total_units == plan2.total_units
    assert len(plan1.stops) == len(plan2.stops)
    for s1, s2 in zip(plan1.stops, plan2.stops, strict=True):
        assert s1.station_idx == s2.station_idx
        assert s1.units_bought == s2.units_bought
        assert s1.cost_usd == s2.cost_usd


def test_plans_pass_simulator_validation() -> None:
    """All generated feasible plans must pass independent continuous simulation."""
    for seed in range(30):
        cands = make_cands(n=5, max_mile=1100.0, seed=seed)
        plan = optimize(
            candidates=cands,
            route_miles=1100.0,
            max_range_miles=500.0,
            mpg=10.0,
            start_mode="priced",
            start_price=3.60,
        )
        if isinstance(plan, Plan) and plan.feasible:
            assert validate_plan(plan, 1100.0)
