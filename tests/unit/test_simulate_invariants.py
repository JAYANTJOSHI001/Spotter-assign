from decimal import Decimal

import pytest

from apps.planner.schemas import InfeasiblePlan, Plan, PlanStop, StartFill
from apps.planner.simulate import PlanInvalid, validate_plan


def test_simulate_infeasible_plan_raises():
    plan = InfeasiblePlan(gap_start_mile=100.0, gap_end_mile=700.0, corridor_used=10)
    with pytest.raises(PlanInvalid, match="Cannot validate an infeasible plan"):
        validate_plan(plan, route_miles=800.0)


def test_simulate_negative_initial_fuel():
    plan = Plan(
        stops=[],
        total_cost_usd=Decimal("0.00"),
        total_gallons=Decimal("0.00"),
        total_units=0,
        start_fill=StartFill(
            units=-50,
            gallons=Decimal("-5.00"),
            price=3.50,
            cost_usd=Decimal("-17.50"),
        ),
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="Initial fuel cannot be negative"):
        validate_plan(plan, route_miles=200.0)


def test_simulate_initial_fuel_exceeds_tank():
    plan = Plan(
        stops=[],
        total_cost_usd=Decimal("0.00"),
        total_gallons=Decimal("0.00"),
        total_units=0,
        start_fill=StartFill(
            units=600,
            gallons=Decimal("60.00"),  # Tank is 50.0 gal for 500 mi / 10 mpg
            price=3.50,
            cost_usd=Decimal("210.00"),
        ),
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="exceeds tank capacity"):
        validate_plan(plan, route_miles=200.0)


def test_simulate_stop_before_previous_position():
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=300.0,
        offset_miles=1.0,
        detour_miles=2.0,
        price=3.00,
        units_bought=300,
        gallons=Decimal("30.00"),
        cost_usd=Decimal("90.00"),
        fuel_on_arrival_gal=20.0,
        fuel_after_gal=50.0,
    )
    stop2 = PlanStop(
        sequence=2,
        station_idx=2,
        opis_id=2,
        mile_marker=200.0,  # Before stop 1!
        offset_miles=1.0,
        detour_miles=2.0,
        price=3.00,
        units_bought=200,
        gallons=Decimal("20.00"),
        cost_usd=Decimal("60.00"),
        fuel_on_arrival_gal=10.0,
        fuel_after_gal=30.0,
    )
    plan = Plan(
        stops=[stop1, stop2],
        total_cost_usd=Decimal("150.00"),
        total_gallons=Decimal("50.00"),
        total_units=500,
        start_fill=None,
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="is before previous position"):
        validate_plan(plan, route_miles=500.0)


def test_simulate_leg_exceeds_max_range():
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=550.0,  # 550 > 500
        offset_miles=0.0,
        detour_miles=0.0,
        price=3.00,
        units_bought=500,
        gallons=Decimal("50.00"),
        cost_usd=Decimal("150.00"),
        fuel_on_arrival_gal=0.0,
        fuel_after_gal=50.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("150.00"),
        total_gallons=Decimal("50.00"),
        total_units=500,
        start_fill=None,
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="exceeds max range"):
        validate_plan(plan, route_miles=600.0)


def test_simulate_runs_out_of_fuel_to_stop():
    # Start with only 10 gal (100 mi range), stop is at mile 300
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=300.0,
        offset_miles=0.0,
        detour_miles=0.0,
        price=3.00,
        units_bought=300,
        gallons=Decimal("30.00"),
        cost_usd=Decimal("90.00"),
        fuel_on_arrival_gal=0.0,
        fuel_after_gal=30.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("125.00"),
        total_gallons=Decimal("40.00"),
        total_units=400,
        start_fill=StartFill(
            units=100,
            gallons=Decimal("10.00"),
            price=3.50,
            cost_usd=Decimal("35.00"),
        ),
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="Vehicle ran out of fuel driving to stop"):
        validate_plan(plan, route_miles=400.0)


def test_simulate_runs_out_of_fuel_on_detour():
    # Detour factor 2.0 * 25 miles = 50 miles detour.
    # Start fill gives 48 gallons = 480 miles. Stop is at 470 miles.
    # Driving to mile 470 leaves 10 miles (1 gal). Detour requires 50 miles (5 gal).
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=470.0,
        offset_miles=25.0,  # detour = 50 mi = 5 gal
        detour_miles=50.0,
        price=3.00,
        units_bought=200,
        gallons=Decimal("20.00"),
        cost_usd=Decimal("60.00"),
        fuel_on_arrival_gal=1.0,
        fuel_after_gal=21.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("228.00"),
        total_gallons=Decimal("68.00"),
        total_units=680,
        start_fill=StartFill(
            units=480,
            gallons=Decimal("48.00"),
            price=3.50,
            cost_usd=Decimal("168.00"),
        ),
        corridor_used=25,
    )
    with pytest.raises(PlanInvalid, match="Vehicle ran out of fuel on detour"):
        validate_plan(plan, route_miles=550.0)


def test_simulate_fill_exceeds_tank():
    # At mile 100, vehicle has 40 gal left. Adds 25 gal -> 65 gal > 50 gal.
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=100.0,
        offset_miles=0.0,
        detour_miles=0.0,
        price=3.00,
        units_bought=250,
        gallons=Decimal("25.00"),
        cost_usd=Decimal("75.00"),
        fuel_on_arrival_gal=40.0,
        fuel_after_gal=65.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("250.00"),
        total_gallons=Decimal("75.00"),
        total_units=750,
        start_fill=StartFill(
            units=500,
            gallons=Decimal("50.00"),
            price=3.50,
            cost_usd=Decimal("175.00"),
        ),
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="exceeds tank capacity"):
        validate_plan(plan, route_miles=200.0)


def test_simulate_final_leg_exceeds_max_range():
    # Stop at 100, route total 700 miles. Final leg is 600 > 500 miles.
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=100.0,
        offset_miles=0.0,
        detour_miles=0.0,
        price=3.00,
        units_bought=100,
        gallons=Decimal("10.00"),
        cost_usd=Decimal("30.00"),
        fuel_on_arrival_gal=40.0,
        fuel_after_gal=50.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("30.00"),
        total_gallons=Decimal("10.00"),
        total_units=100,
        start_fill=None,
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="Final leg .* exceeds max range"):
        validate_plan(plan, route_miles=700.0)


def test_simulate_cost_mismatch():
    stop1 = PlanStop(
        sequence=1,
        station_idx=1,
        opis_id=1,
        mile_marker=200.0,
        offset_miles=0.0,
        detour_miles=0.0,
        price=3.00,
        units_bought=200,
        gallons=Decimal("20.00"),
        cost_usd=Decimal("60.00"),
        fuel_on_arrival_gal=30.0,
        fuel_after_gal=50.0,
    )
    plan = Plan(
        stops=[stop1],
        total_cost_usd=Decimal("999.00"),  # Bad total cost!
        total_gallons=Decimal("20.00"),
        total_units=200,
        start_fill=None,
        corridor_used=10,
    )
    with pytest.raises(PlanInvalid, match="Total cost mismatch"):
        validate_plan(plan, route_miles=400.0)
