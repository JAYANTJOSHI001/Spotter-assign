"""Exact dynamic programming fuel stop optimizer (pure Python/numpy)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from apps.planner.schemas import Candidate, InfeasiblePlan, Plan, PlanStop, StartFill

INF = np.inf
EPS = 1e-4  # Per-visit tie-break: prefer fewer stops when costs are equal


def shift_down(f: np.ndarray, shift: int) -> np.ndarray:
    """Shift cost array down by integer distance, filling dropped capacity with INF."""
    if shift == 0:
        return f.copy()
    n = len(f)
    if shift >= n:
        return np.full_like(f, INF)
    out = np.empty_like(f)
    out[: n - shift] = f[shift:]
    out[n - shift :] = INF
    return out


def find_largest_gap(
    candidates: list[Candidate], route_miles: float, max_range_miles: float
) -> tuple[float, float]:
    """Identify the largest route gap exceeding the range limit."""
    mile_markers = sorted({0.0} | {c.mile_marker for c in candidates} | {route_miles})
    largest_gap = (0.0, route_miles)
    max_gap_len = 0.0

    for i in range(len(mile_markers) - 1):
        gap_len = mile_markers[i + 1] - mile_markers[i]
        if gap_len > max_gap_len:
            max_gap_len = gap_len
            largest_gap = (mile_markers[i], mile_markers[i + 1])

    return largest_gap


def _solve_dp(
    cands: list[tuple[int, int, float]],
    M_D: int,
    G: int,
    mpg: float,
    p0: float,
    mode: str,
) -> tuple[float, int, list[tuple[int, int]]] | None:
    """Core DP algorithm solving the fuel-grid cost minimization.

    Args:
        cands: List of (M, k, price) tuples.
        M_D: Integer route length in miles.
        G: Usable integer tank capacity.
        mpg: Miles per gallon.
        p0: Starting reference price per gallon.
        mode: 'priced' or 'free'.

    Returns:
        (optimal_cost_with_eps, initial_units, list_of_(cand_idx, units_bought)) or None if infeasible.
    """
    idx = np.arange(G + 1)
    if mode == "priced":
        f = idx * (p0 / mpg)
    else:  # free
        f = np.full(G + 1, INF, dtype=np.float64)
        f[G] = 0.0

    pos = 0
    hist: list[tuple[np.ndarray, np.ndarray, int, int]] = []

    for M, k, price in cands:
        L = M - pos
        f = shift_down(f, L)
        pos = M

        fd = shift_down(f, k)
        unit_cost = price / mpg
        A = fd - idx * unit_cost
        pm = np.minimum.accumulate(A)
        arg = np.maximum.accumulate(np.where(A == pm, idx, 0))
        h = idx * unit_cost + pm + EPS
        visit = h < f
        f = np.minimum(h, f)
        hist.append((visit, arg, k, L))

    L_final = M_D - pos
    f = shift_down(f, L_final)
    g_end = int(np.argmin(f))
    cost = f[g_end]

    if not np.isfinite(cost):
        return None

    g = g_end + L_final
    buys: list[tuple[int, int]] = []

    for i in range(len(cands) - 1, -1, -1):
        visit, arg, k, L_i = hist[i]
        if visit[g]:
            g_detour = int(arg[g])
            buys.append((i, int(g - g_detour)))
            g = g_detour + k
        g += L_i

    return float(cost), int(g), buys[::-1]


def optimize(
    candidates: list[Candidate],
    route_miles: float,
    max_range_miles: float = 500.0,
    mpg: float = 10.0,
    start_mode: str = "priced",
    start_price: float = 3.50,
    detour_factor: float = 2.0,
    safety_reserve_miles: float = 0.0,
    corridor_used: int = 10,
) -> Plan | InfeasiblePlan:
    """Find exact cost-minimizing fuel stops along a route using DP on an integer fuel grid.

    Args:
        candidates: Candidate fuel stations along the route.
        route_miles: Total road distance of the route in miles.
        max_range_miles: Vehicle maximum range in miles (default 500).
        mpg: Vehicle fuel efficiency in miles per gallon (default 10).
        start_mode: "priced" (fill at start_price) or "free" (start full at $0).
        start_price: Reference price per gallon at the origin.
        detour_factor: Multiplier for detour distance burned leaving/joining route.
        safety_reserve_miles: Reserve range margin (default 0).
        corridor_used: Buffer width used for candidate search.

    Returns:
        Plan if a feasible route exists, otherwise InfeasiblePlan.
    """
    G = int(np.floor(max_range_miles - 1.0 - safety_reserve_miles))
    M_D = int(round(route_miles))

    if G <= 0:
        return InfeasiblePlan(
            gap_start_mile=0.0,
            gap_end_mile=route_miles,
            message=f"Effective tank range {G} miles is too small",
            corridor_used=corridor_used,
        )

    # 1. Sort and filter candidates in one pass
    sorted_cands = sorted(candidates, key=lambda s: (round(s.mile_marker), s.price, s.opis_id))
    valid_cands: list[Candidate] = []
    cand_tuples: list[tuple[int, int, float]] = []

    for c in sorted_cands:
        M = int(round(c.mile_marker))
        k = int(np.ceil(detour_factor * c.offset_miles))
        if k > G or M < 0 or M > M_D:
            continue
        valid_cands.append(c)
        cand_tuples.append((M, k, float(c.price)))

    # 2. Check zero candidates edge-case
    if not valid_cands:
        if M_D <= G:
            if start_mode == "priced":
                start_units = M_D
                start_gal = Decimal(start_units) / Decimal(str(mpg))
                price_dec = Decimal(str(round(start_price, 4)))
                start_cost = (start_gal * price_dec).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                start_fill = StartFill(
                    units=start_units,
                    gallons=start_gal,
                    price=start_price,
                    cost_usd=start_cost,
                )
                return Plan(
                    stops=[],
                    start_fill=start_fill,
                    total_cost_usd=start_cost,
                    total_gallons=start_gal,
                    total_units=start_units,
                    feasible=True,
                    corridor_used=corridor_used,
                )
            else:  # free
                return Plan(
                    stops=[],
                    start_fill=None,
                    total_cost_usd=Decimal("0.00"),
                    total_gallons=Decimal("0.00"),
                    total_units=0,
                    feasible=True,
                    corridor_used=corridor_used,
                )
        else:
            return InfeasiblePlan(
                gap_start_mile=0.0,
                gap_end_mile=route_miles,
                message=f"Trip distance {route_miles:.1f} mi exceeds vehicle range {max_range_miles:.1f} mi with 0 stations",
                corridor_used=corridor_used,
            )

    # 3. Solve via core DP
    dp_result = _solve_dp(
        cands=cand_tuples,
        M_D=M_D,
        G=G,
        mpg=mpg,
        p0=start_price,
        mode=start_mode,
    )

    if dp_result is None:
        gap_start, gap_end = find_largest_gap(valid_cands, route_miles, max_range_miles)
        return InfeasiblePlan(
            gap_start_mile=gap_start,
            gap_end_mile=gap_end,
            message=f"Uncovered gap between mile {gap_start:.1f} and {gap_end:.1f} exceeds tank range",
            corridor_used=corridor_used,
        )

    _, initial_units, buys = dp_result

    # 4. Forward replay to determine fuel on arrival and fuel after for each stop
    # In priced mode, initial fuel is initial_units; in free mode, initial fuel is G
    current_fuel = float(initial_units if start_mode == "priced" else G)
    current_pos = 0.0
    buys_dict = dict(buys)

    plan_stops: list[PlanStop] = []
    mpg_dec = Decimal(str(mpg))
    seq = 1

    for i, cand in enumerate(valid_cands):
        if i not in buys_dict:
            continue

        units_bought = buys_dict[i]
        leg_dist = cand.mile_marker - current_pos
        detour_dist = detour_factor * cand.offset_miles

        fuel_arrival = max(0.0, (current_fuel - leg_dist - detour_dist) / mpg)
        fuel_after = min(float(G) / mpg, fuel_arrival + (units_bought / mpg))

        gallons = Decimal(units_bought) / mpg_dec
        price_dec = Decimal(str(round(cand.price, 4)))
        cost_usd = (gallons * price_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        plan_stops.append(
            PlanStop(
                sequence=seq,
                station_idx=cand.station_idx,
                opis_id=cand.opis_id,
                mile_marker=cand.mile_marker,
                offset_miles=cand.offset_miles,
                detour_miles=float(detour_dist),
                price=cand.price,
                units_bought=units_bought,
                gallons=gallons,
                cost_usd=cost_usd,
                fuel_on_arrival_gal=round(fuel_arrival, 2),
                fuel_after_gal=round(fuel_after, 2),
            )
        )
        seq += 1

        current_fuel = (current_fuel - leg_dist - detour_dist) + units_bought
        current_pos = cand.mile_marker

    start_fill: StartFill | None = None
    if start_mode == "priced" and initial_units > 0:
        start_gal = Decimal(initial_units) / mpg_dec
        start_price_dec = Decimal(str(round(start_price, 4)))
        start_cost = (start_gal * start_price_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        start_fill = StartFill(
            units=initial_units,
            gallons=start_gal,
            price=start_price,
            cost_usd=start_cost,
        )

    total_cost_usd = sum((s.cost_usd for s in plan_stops), Decimal("0.00"))
    if start_fill is not None:
        total_cost_usd += start_fill.cost_usd

    total_units = sum(s.units_bought for s in plan_stops) + (start_fill.units if start_fill else 0)
    total_gallons = Decimal(total_units) / mpg_dec

    return Plan(
        stops=plan_stops,
        start_fill=start_fill,
        total_cost_usd=total_cost_usd,
        total_gallons=total_gallons,
        total_units=total_units,
        feasible=True,
        corridor_used=corridor_used,
    )
