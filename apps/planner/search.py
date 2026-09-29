"""Corridor widening search to plan feasible fuel stops."""

from __future__ import annotations

from apps.geo.corridor import match_corridor
from apps.geo.resample import RouteSamples
from apps.planner.optimizer import optimize
from apps.planner.schemas import Candidate, InfeasiblePlan, Plan
from apps.stations.index import StationIndex


def plan_with_widening(
    samples: RouteSamples,
    index: StationIndex,
    max_range_miles: float = 500.0,
    mpg: float = 10.0,
    start_mode: str = "priced",
    start_price: float = 3.50,
    detour_factor: float = 2.0,
    safety_reserve_miles: float = 0.0,
    corridors: tuple[int, ...] = (10, 25, 50),
) -> tuple[Plan | InfeasiblePlan, list[str]]:
    """Search for fuel stops across widening corridor buffers until a feasible plan is found.

    Args:
        samples: Resampled route points with cumulative mile markers.
        index: In-memory FuelStation index.
        max_range_miles: Vehicle maximum range in miles.
        mpg: Miles per gallon.
        start_mode: 'priced' or 'free'.
        start_price: Origin reference price per gallon.
        detour_factor: Detour multiplier.
        safety_reserve_miles: Safety reserve miles.
        corridors: Sequence of corridor buffer widths in miles (default: 10, 25, 50).

    Returns:
        Tuple of (Plan or InfeasiblePlan, list of warning messages).
    """
    warnings: list[str] = []
    last_infeasible: InfeasiblePlan | None = None

    for buffer_miles in corridors:
        matched = match_corridor(samples, index.unit_vectors, buffer_miles=float(buffer_miles))

        cands: list[Candidate] = []
        for i in range(len(matched.station_idx)):
            s_idx = int(matched.station_idx[i])
            cands.append(
                Candidate(
                    station_idx=s_idx,
                    opis_id=int(index.opis_id[s_idx]),
                    mile_marker=float(matched.mile_marker[i]),
                    offset_miles=float(matched.offset_miles[i]),
                    price=float(index.price[s_idx]),
                )
            )

        plan = optimize(
            candidates=cands,
            route_miles=samples.total_miles,
            max_range_miles=max_range_miles,
            mpg=mpg,
            start_mode=start_mode,
            start_price=start_price,
            detour_factor=detour_factor,
            safety_reserve_miles=safety_reserve_miles,
            corridor_used=buffer_miles,
        )

        if plan.feasible:
            if buffer_miles > corridors[0]:
                warnings.append(
                    f"Corridor buffer widened to {buffer_miles} miles to find a feasible fuel plan"
                )
            return plan, warnings

        last_infeasible = plan  # type: ignore[assignment]

    if last_infeasible is not None:
        return last_infeasible, warnings

    return (
        InfeasiblePlan(
            gap_start_mile=0.0,
            gap_end_mile=samples.total_miles,
            corridor_used=corridors[-1] if corridors else 50,
        ),
        warnings,
    )
