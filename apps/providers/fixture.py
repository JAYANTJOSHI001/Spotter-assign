"""Fixture-based route provider for offline tests and predictable demos."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np

from apps.providers.base import LatLng, RouteResult
from apps.providers.budget import CallBudget
from apps.providers.errors import NoRouteError, UpstreamError


def get_fixtures_dir() -> Path:
    try:
        from django.conf import settings

        if getattr(settings, "configured", False) and hasattr(settings, "BASE_DIR"):
            return Path(settings.BASE_DIR) / "tests" / "fixtures" / "routes"
    except Exception:
        pass
    return Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "routes"


FIXTURES_DIR = get_fixtures_dir()


def coordinate_slug(start: LatLng, finish: LatLng) -> str:
    """Generate a deterministic filename slug from rounded endpoints."""
    s_lat = f"{round(start.lat, 2):.2f}".replace("-", "m").replace(".", "p")
    s_lng = f"{round(start.lng, 2):.2f}".replace("-", "m").replace(".", "p")
    f_lat = f"{round(finish.lat, 2):.2f}".replace("-", "m").replace(".", "p")
    f_lng = f"{round(finish.lng, 2):.2f}".replace("-", "m").replace(".", "p")
    return f"{s_lat}_{s_lng}_to_{f_lat}_{f_lng}"


KNOWN_ALIASES: list[tuple[tuple[float, float], tuple[float, float], str]] = [
    # ((start_lat, start_lng), (finish_lat, finish_lng), alias)
    ((41.88, -87.63), (32.78, -96.80), "chicago_il_to_dallas_tx"),
    ((40.71, -74.01), (34.05, -118.24), "new_york_ny_to_los_angeles_ca"),
    ((41.88, -87.63), (38.63, -90.20), "chicago_il_to_st_louis_mo"),
    ((47.61, -122.33), (25.76, -80.19), "seattle_wa_to_miami_fl"),
    ((40.71, -74.01), (21.31, -157.86), "new_york_ny_to_honolulu_hi"),
]


def resolve_fixture_path(start: LatLng, finish: LatLng, fixtures_dir: Path = FIXTURES_DIR) -> Path:
    """Resolve fixture file path by coordinate match or exact slug."""
    # 1. Check known city aliases within 0.3 degrees tolerance
    for (s_lat, s_lng), (f_lat, f_lng), alias in KNOWN_ALIASES:
        if (
            abs(start.lat - s_lat) < 0.3
            and abs(start.lng - s_lng) < 0.3
            and abs(finish.lat - f_lat) < 0.3
            and abs(finish.lng - f_lng) < 0.3
        ):
            json_path = fixtures_dir / f"{alias}.json"
            if json_path.exists():
                return json_path
            gz_path = fixtures_dir / f"{alias}.json.gz"
            if gz_path.exists():
                return gz_path

    # 2. Check coordinate slug
    slug = coordinate_slug(start, finish)
    json_path = fixtures_dir / f"{slug}.json"
    if json_path.exists():
        return json_path
    gz_path = fixtures_dir / f"{slug}.json.gz"
    if gz_path.exists():
        return gz_path

    # Raise clear error if no matching fixture is found
    raise FileNotFoundError(
        f"Route fixture not found for start=({start.lat:.2f}, {start.lng:.2f}) "
        f"finish=({finish.lat:.2f}, {finish.lng:.2f}). Tried slug '{slug}' and aliases in {fixtures_dir}."
    )


class FixtureRouteProvider:
    """Route provider that serves recorded OSRM JSON responses without network access."""

    name: str = "fixture"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR

    def route(self, start: LatLng, finish: LatLng, budget: CallBudget) -> RouteResult:
        """Load route from recorded JSON fixture, recording 1 external call in budget."""
        fixture_path = resolve_fixture_path(start, finish, self.fixtures_dir)

        with budget.consume(provider=self.name, purpose="route") as call:
            try:
                if fixture_path.suffix == ".gz":
                    with gzip.open(fixture_path, "rt", encoding="utf-8") as f:
                        data: dict[str, Any] = json.load(f)
                else:
                    with open(fixture_path, encoding="utf-8") as f:
                        data = json.load(f)
            except Exception as exc:
                call.status = "error"
                raise UpstreamError(
                    f"Failed to read route fixture {fixture_path.name}: {exc}"
                ) from exc

            call.status = "200"

            code = data.get("code")
            if code == "NoRoute":
                raise NoRouteError("Route fixture indicates NoRoute between endpoints")
            if code != "Ok":
                raise UpstreamError(f"Fixture returned error code: {code}")

            routes = data.get("routes", [])
            if not routes:
                raise NoRouteError("Fixture has empty routes list")

            primary = routes[0]
            distance_miles = float(primary["distance"]) / 1609.344
            duration_minutes = float(primary["duration"]) / 60.0

            coords = np.asarray(primary["geometry"]["coordinates"], dtype=np.float64)
            lng_arr = coords[:, 0]
            lat_arr = coords[:, 1]

            return RouteResult(
                distance_miles=distance_miles,
                duration_minutes=duration_minutes,
                lat=lat_arr,
                lng=lng_arr,
                provider=self.name,
            )
