"""Unit tests for the exact fuel route optimizer with hand-calculated scenarios."""

from __future__ import annotations

from decimal import Decimal

from apps.planner.optimizer import optimize
from apps.planner.schemas import Candidate, InfeasiblePlan, Plan
from apps.planner.simulate import validate_plan


def make_cand(idx: int, mile: float, offset: float, price: float) -> Candidate:
    """Helper to construct Candidate dataclass."""
    return Candidate(
        station_idx=idx,
        opis_id=1000 + idx,
        mile_marker=mile,
        offset_miles=offset,
        price=price,
    )


def test_scenario_single_cheap_station_mid_route() -> None:
    # Route: 800 miles, range 500 (G=498), mpg 10.
    # Start price: $4.00/gal.
    # Station at mile 400, offset 0, price: $3.00/gal.
    # Reasoning:
    #   Vehicle cannot reach destination (800 > 498) on start fuel alone.
    #   Must stop at mile 400.
    #   Arriving at mile 400 with 0 fuel requires buying 400 units at start ($4.00).
    #   At mile 400, remaining distance is 400 miles. Since station is cheaper ($3.00 vs $4.00),
    #   optimizer should buy minimum needed at start (400 units) and buy 400 units at station.
    #   Start cost: 40 gal * $4.00 = $160.00
    #   Stop cost: 40 gal * $3.00 = $120.00
    #   Total expected: $280.00
    cands = [make_cand(1, 400.0, 0.0, 3.00)]
    plan = optimize(
        candidates=cands,
        route_miles=800.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=4.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 1
    assert plan.stops[0].station_idx == 1
    assert plan.stops[0].units_bought == 400
    assert plan.start_fill is not None
    assert plan.start_fill.units == 400
    assert plan.total_cost_usd == Decimal("280.00")
    assert validate_plan(plan, 800.0)


def test_scenario_cheaper_station_beyond_range() -> None:
    # Route: 900 miles, range 500 (G=498), mpg 10.
    # Station 1: mile 300, price $3.50
    # Station 2: mile 550, price $2.50 (cheaper, but unreachable from start: 550 > 498)
    # Reasoning:
    #   Vehicle must stop at Station 1 to reach Station 2.
    cands = [
        make_cand(1, 300.0, 0.0, 3.50),
        make_cand(2, 550.0, 0.0, 2.50),
    ]
    plan = optimize(
        candidates=cands,
        route_miles=900.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=4.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    # Both stations must be visited
    visited_indices = [s.station_idx for s in plan.stops]
    assert visited_indices == [1, 2]
    assert validate_plan(plan, 900.0)


def test_scenario_equal_prices_prefer_fewest_stops() -> None:
    # Route: 700 miles, range 500 (G=498), mpg 10.
    # Start price $3.00.
    # Station 1 at 200 mi: $3.00
    # Station 2 at 350 mi: $3.00
    # Station 3 at 450 mi: $3.00
    # Reasoning:
    #   Due to EPS per-visit tie-break, optimizer must prefer visiting 1 station (Station 2 or 3)
    #   rather than 2 stations. Mile 350 allows reaching destination (700 - 350 = 350 <= 498).
    cands = [
        make_cand(1, 200.0, 0.0, 3.00),
        make_cand(2, 350.0, 0.0, 3.00),
        make_cand(3, 450.0, 0.0, 3.00),
    ]
    plan = optimize(
        candidates=cands,
        route_miles=700.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 1
    assert validate_plan(plan, 700.0)


def test_scenario_expensive_start_price_cheap_first_station() -> None:
    # Route: 400 miles (within range 500), mpg 10.
    # Start price is very expensive: $5.00/gal.
    # Station at mile 20, price: $2.50/gal.
    # Reasoning:
    #   Even though vehicle COULD complete the entire 400-mile trip on start fuel,
    #   it is much cheaper to buy only 20 units at start ($5.00) and fill 380 units at mile 20 ($2.50).
    #   Start cost: 2 gal * $5.00 = $10.00
    #   Stop cost: 38 gal * $2.50 = $95.00
    #   Total: $105.00 (vs 40 gal * $5.00 = $200.00 without stop)
    cands = [make_cand(1, 20.0, 0.0, 2.50)]
    plan = optimize(
        candidates=cands,
        route_miles=400.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=5.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 1
    assert plan.stops[0].units_bought == 380
    assert plan.start_fill is not None
    assert plan.start_fill.units == 20
    assert plan.total_cost_usd == Decimal("105.00")
    assert validate_plan(plan, 400.0)


def test_scenario_free_start_mode() -> None:
    # Route: 800 miles, range 500 (G=499), mpg 10.
    # Start mode: free (tank starts with 499 units at $0).
    # Station at mile 400, price $3.00/gal.
    # Reasoning:
    #   Arrives at mile 400 with 499 - 400 = 99 units remaining.
    #   Remaining distance to destination is 400 miles.
    #   Needs 400 - 99 = 301 units to reach destination with 0 fuel.
    #   Cost: 30.1 gal * $3.00 = $90.30.
    cands = [make_cand(1, 400.0, 0.0, 3.00)]
    plan = optimize(
        candidates=cands,
        route_miles=800.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="free",
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert plan.start_fill is None
    assert len(plan.stops) == 1
    assert plan.stops[0].units_bought == 301
    assert plan.total_cost_usd == Decimal("90.30")
    assert validate_plan(plan, 800.0)


def test_scenario_trip_shorter_than_range_no_cheaper_station() -> None:
    # Route: 300 miles, range 500, start price $3.00.
    # Station at mile 150 has higher price $3.50.
    # Reasoning:
    #   No stops needed; vehicle buys all 300 units at start ($3.00).
    cands = [make_cand(1, 150.0, 0.0, 3.50)]
    plan = optimize(
        candidates=cands,
        route_miles=300.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 0
    assert plan.start_fill is not None
    assert plan.start_fill.units == 300
    assert plan.total_cost_usd == Decimal("90.00")
    assert validate_plan(plan, 300.0)


def test_scenario_big_detour_not_worth_it() -> None:
    # Route: 400 miles, start price $3.00/gal.
    # Station at mile 200 has price $2.95/gal (only 5 cents cheaper),
    # but detour offset is 30 miles (detour burn = ceil(2 * 30) = 60 miles = 6 gal).
    # Buying 200 miles of fuel at $2.95 saves $1.00, but burns 6 gallons ($17.70+)!
    # Reasoning:
    #   Optimizer must skip the detour station and buy at start.
    cands = [make_cand(1, 200.0, 30.0, 2.95)]
    plan = optimize(
        candidates=cands,
        route_miles=400.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.00,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 0  # Skipped because detour burn outweighs price discount
    assert plan.total_cost_usd == Decimal("120.00")
    assert validate_plan(plan, 400.0)


def test_scenario_leg_exactly_at_limit() -> None:
    # Range 500 (G = 498).
    # Station at mile 498.0 -> leg is exactly 498.
    # Next leg to mile 996 (498 mi) -> destination.
    cands = [make_cand(1, 498.0, 0.0, 3.20)]
    plan = optimize(
        candidates=cands,
        route_miles=996.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.50,
    )

    assert isinstance(plan, Plan)
    assert plan.feasible
    assert len(plan.stops) == 1
    assert validate_plan(plan, 996.0)


def test_scenario_leg_one_mile_over_infeasible() -> None:
    # Range 500 (G = 499).
    # First station at mile 500.0 -> leg is 500 > G (499).
    # Reasoning:
    #   Unreachable from start (exceeds G by 1 mile); must return InfeasiblePlan.
    cands = [make_cand(1, 500.0, 0.0, 3.20)]
    plan = optimize(
        candidates=cands,
        route_miles=800.0,
        max_range_miles=500.0,
        mpg=10.0,
        start_mode="priced",
        start_price=3.50,
    )

    assert isinstance(plan, InfeasiblePlan)
    assert not plan.feasible
    assert plan.gap_start_mile == 0.0
