"""Base types, data structures, and protocols for route and geocode providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from apps.providers.budget import CallBudget


@dataclass(frozen=True, slots=True)
class LatLng:
    """Geographic coordinate pair in decimal degrees."""

    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"Latitude {self.lat} outside valid range [-90, 90]")
        if not (-180.0 <= self.lng <= 180.0):
            raise ValueError(f"Longitude {self.lng} outside valid range [-180, 180]")


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Result of a routing provider query."""

    distance_miles: float
    duration_minutes: float
    lat: np.ndarray  # float64 1-D array
    lng: np.ndarray  # float64 1-D array
    provider: str


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    """Result of a geocoding query."""

    lat: float
    lng: float
    label: str
    source: str  # "coordinates" | "gazetteer" | "nominatim"


class RouteProvider(Protocol):
    """Protocol for upstream driving route providers."""

    name: str

    def route(self, start: LatLng, finish: LatLng, budget: CallBudget) -> RouteResult:
        """Calculate a driving route between two points within the given budget."""
        ...


class Geocoder(Protocol):
    """Protocol for geocoding services."""

    def geocode(self, text: str, budget: CallBudget) -> GeocodeResult:
        """Geocode a text query to coordinates within the given budget."""
        ...
