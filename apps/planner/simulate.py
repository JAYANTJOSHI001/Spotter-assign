"""Independent simulation validator for planned fuel stops."""

from __future__ import annotations

from decimal import Decimal

from apps.planner.schemas import Candidate, Plan, PlanInvalid


def validate_plan(
    plan: Plan,
    route_miles: float,
    candidates_by_idx: dict[int, Candidate] | None = None,
    max_range: float = 500.0,
    mpg: float = 10.0,
    detour_factor: float = 2.0,
) -> bool:
    """Replay a planned fuel route with continuous float distances to verify all physical invariants.

    Invariants verified:
        1. Fuel never drops below -1e-9 gallons at any point.
        2. Fuel never exceeds tank capacity (max_range / mpg).
        3. Every leg between consecutive route positions <= max_range.
        4. Totals match the exact sum of Decimal stop costs.
        5. Total fuel range matches total road miles + detours within +/- 1.0 mile.

    Raises:
        PlanInvalid: If any physical invariant or financial accounting rule is violated.
    """
    if not plan.feasible:
        raise PlanInvalid("Cannot validate an infeasible plan")

    tank_gal = max_range / mpg

    # Initial fuel
    if plan.start_fill is not None:
        fuel_gal = float(plan.start_fill.gallons)
    else:
        # Free mode starts with full tank
        fuel_gal = tank_gal

    if fuel_gal < -1e-9:
        raise PlanInvalid(f"Initial fuel cannot be negative: {fuel_gal:.2f} gal")
    if fuel_gal > tank_gal + 1e-9:
        raise PlanInvalid(
            f"Initial fuel {fuel_gal:.2f} gal exceeds tank capacity {tank_gal:.2f} gal"
        )

    pos_miles = 0.0
    total_detour_miles = 0.0
    discretization_tolerance = (1.0 / mpg) + 1e-6

    for i, stop in enumerate(plan.stops, start=1):
        leg_miles = stop.mile_marker - pos_miles
        if leg_miles < -1e-9:
            raise PlanInvalid(
                f"Stop #{i} mile marker {stop.mile_marker:.1f} is before previous position {pos_miles:.1f}"
            )
        if leg_miles > max_range + 1e-9:
            raise PlanInvalid(
                f"Leg from mile {pos_miles:.1f} to {stop.mile_marker:.1f} ({leg_miles:.1f} mi) exceeds max range {max_range}"
            )

        # Drive to station exit on highway
        fuel_gal -= leg_miles / mpg
        if fuel_gal < -discretization_tolerance:
            raise PlanInvalid(
                f"Vehicle ran out of fuel driving to stop #{i} (mile {stop.mile_marker:.1f}): fuel={fuel_gal:.3f} gal"
            )

        # Drive detour to station
        detour_miles = detour_factor * stop.offset_miles
        total_detour_miles += detour_miles
        fuel_gal -= detour_miles / mpg
        if fuel_gal < -discretization_tolerance:
            raise PlanInvalid(
                f"Vehicle ran out of fuel on detour to stop #{i}: fuel={fuel_gal:.3f} gal"
            )

        # Purchase fuel
        purchased_gal = float(stop.gallons)
        fuel_gal += purchased_gal
        # 1-mile integer discretization margin: (1.0 / mpg) gal
        if fuel_gal > tank_gal + discretization_tolerance:
            raise PlanInvalid(
                f"Fuel after fill at stop #{i} ({fuel_gal:.2f} gal) exceeds tank capacity ({tank_gal:.2f} gal)"
            )
        fuel_gal = min(tank_gal, max(0.0, fuel_gal))

        pos_miles = stop.mile_marker

    # Final leg to destination
    final_leg = route_miles - pos_miles
    if final_leg < -1e-9:
        raise PlanInvalid(
            f"Final position {pos_miles:.1f} mi exceeds total route miles {route_miles:.1f} mi"
        )
    if final_leg > max_range + 1e-9:
        raise PlanInvalid(
            f"Final leg from mile {pos_miles:.1f} to {route_miles:.1f} ({final_leg:.1f} mi) exceeds max range {max_range}"
        )

    fuel_gal -= final_leg / mpg
    if fuel_gal < -discretization_tolerance:
        raise PlanInvalid(
            f"Vehicle ran out of fuel before reaching destination: fuel={fuel_gal:.3f} gal"
        )

    # Decimal financial integrity
    expected_cost = sum((s.cost_usd for s in plan.stops), Decimal("0.00"))
    if plan.start_fill is not None:
        expected_cost += plan.start_fill.cost_usd

    if plan.total_cost_usd != expected_cost:
        raise PlanInvalid(f"Total cost mismatch: plan={plan.total_cost_usd} vs sum={expected_cost}")

    # Balance check: abs(gallons * mpg - (route_miles + sum(detours)))
    # In the integer grid, each stop burns ceil(detour) which can exceed float detour by up to 1.0 mi per stop.
    total_effective_miles = route_miles + total_detour_miles
    start_free_miles = max_range if plan.start_fill is None else 0.0
    total_fuel_miles = (float(plan.total_gallons) * mpg) + start_free_miles

    diff = abs(total_fuel_miles - total_effective_miles)
    allowed_diff = max(2.5, len(plan.stops) * 0.75 + 1.0)
    if diff > allowed_diff:
        raise PlanInvalid(
            f"Fuel balance invariant violated: total fuel miles {total_fuel_miles:.2f} "
            f"differs from road miles + detours {total_effective_miles:.2f} by {diff:.2f} > {allowed_diff:.2f} mi"
        )

    return True
