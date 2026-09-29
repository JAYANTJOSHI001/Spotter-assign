"""Data structures and schemas for the fuel route optimization engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Candidate:
    """A fuel station candidate matched within a route corridor."""

    station_idx: int
    opis_id: int
    mile_marker: float
    offset_miles: float
    price: float


@dataclass(frozen=True, slots=True)
class PlanStop:
    """An individual planned fuel stop along the route."""

    sequence: int
    station_idx: int
    opis_id: int
    mile_marker: float
    offset_miles: float
    detour_miles: float
    price: float
    units_bought: int
    gallons: Decimal
    cost_usd: Decimal
    fuel_on_arrival_gal: float
    fuel_after_gal: float


@dataclass(frozen=True, slots=True)
class StartFill:
    """Initial fuel fill at the start location (in priced mode)."""

    units: int
    gallons: Decimal
    price: float
    cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class Plan:
    """A complete, optimal fuel purchase plan for a route."""

    stops: list[PlanStop]
    start_fill: StartFill | None
    total_cost_usd: Decimal
    total_gallons: Decimal
    total_units: int
    feasible: bool = True
    corridor_used: int = 10


@dataclass(frozen=True, slots=True)
class InfeasiblePlan:
    """Representation of an infeasible trip with gap details."""

    gap_start_mile: float
    gap_end_mile: float
    message: str = "No feasible fuel plan found within maximum range"
    feasible: bool = False
    corridor_used: int = 50


class PlanInvalid(Exception):
    """Raised when an independent simulation of a fuel plan detects an invariant violation."""

    pass
