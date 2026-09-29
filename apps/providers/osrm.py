"""OSRM (Open Source Routing Machine) route provider."""

from __future__ import annotations

import httpx
import numpy as np
from django.conf import settings

from apps.providers.base import LatLng, RouteResult
from apps.providers.budget import CallBudget
from apps.providers.errors import NoRouteError, UpstreamError, UpstreamTimeout

_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    """Return a pooled, module-level HTTP client."""
    global _client
    if _client is None:
        read_timeout = float(getattr(settings, "UPSTREAM_TIMEOUT_S", 8.0))
        timeout = httpx.Timeout(read_timeout, connect=3.0)
        _client = httpx.Client(timeout=timeout)
    return _client


def close_client() -> None:
    """Close the pooled HTTP client (useful for testing and teardown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


class OSRMProvider:
    """OSRM route service client implementing RouteProvider."""

    name: str = "osrm"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "OSRM_BASE_URL", "https://router.project-osrm.org")
        ).rstrip("/")

    def route(self, start: LatLng, finish: LatLng, budget: CallBudget) -> RouteResult:
        """Fetch driving route from OSRM."""
        url = f"{self.base_url}/route/v1/driving/{start.lng:.6f},{start.lat:.6f};{finish.lng:.6f},{finish.lat:.6f}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
            "alternatives": "false",
        }

        client = get_client()
        with budget.consume(provider=self.name, purpose="route") as call:
            try:
                resp = client.get(url, params=params)
            except httpx.TimeoutException as exc:
                call.status = "timeout"
                raise UpstreamTimeout(f"OSRM request timed out: {exc}") from exc
            except httpx.RequestError as exc:
                call.status = "error"
                raise UpstreamError(f"OSRM request failed: {exc}") from exc

            call.status = str(resp.status_code)
            if resp.status_code >= 500:
                raise UpstreamError(f"OSRM server error HTTP {resp.status_code}")
            if resp.status_code == 404:
                raise NoRouteError(f"OSRM returned 404: {resp.text}")

            try:
                data = resp.json()
            except Exception as exc:
                raise UpstreamError(f"OSRM response was not valid JSON: {exc}") from exc

            code = data.get("code")
            if code == "NoRoute":
                raise NoRouteError("OSRM found no driving route between endpoints")
            if code != "Ok":
                raise UpstreamError(
                    f"OSRM error: code={code}, message={data.get('message', 'unknown')}"
                )

            routes = data.get("routes")
            if not routes:
                raise NoRouteError("OSRM returned no routes")

            primary = routes[0]
            if "distance" not in primary or "duration" not in primary:
                raise UpstreamError("OSRM response missing distance or duration")

            distance_miles = float(primary["distance"]) / 1609.344
            duration_minutes = float(primary["duration"]) / 60.0

            geometry = primary.get("geometry", {})
            coords_raw = geometry.get("coordinates")
            if not isinstance(coords_raw, list) or len(coords_raw) < 2:
                raise UpstreamError("OSRM returned invalid or empty route geometry")

            try:
                coords = np.asarray(coords_raw, dtype=np.float64)
            except (ValueError, TypeError) as exc:
                raise UpstreamError(f"OSRM geometry coordinates cannot be parsed: {exc}") from exc

            if coords.ndim != 2 or coords.shape[1] != 2:
                raise UpstreamError(f"OSRM geometry shape invalid: {coords.shape}")

            if not np.all(np.isfinite(coords)):
                raise UpstreamError("OSRM geometry contains non-finite coordinates (NaN or Inf)")

            lng_arr = coords[:, 0]
            lat_arr = coords[:, 1]

            if np.any(lat_arr < -90.0) or np.any(lat_arr > 90.0):
                raise UpstreamError("OSRM geometry latitudes out of range [-90, 90]")
            if np.any(lng_arr < -180.0) or np.any(lng_arr > 180.0):
                raise UpstreamError("OSRM geometry longitudes out of range [-180, 180]")

            return RouteResult(
                distance_miles=distance_miles,
                duration_minutes=duration_minutes,
                lat=lat_arr,
                lng=lng_arr,
                provider=self.name,
            )
