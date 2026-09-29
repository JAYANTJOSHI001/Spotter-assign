"""OpenRouteService (ORS) route provider (fallback)."""

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
    """Close the pooled HTTP client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


class ORSProvider:
    """OpenRouteService driving-car directions provider."""

    name: str = "ors"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else getattr(settings, "ORS_API_KEY", "")
        self.base_url = (
            base_url
            if base_url is not None
            else "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        )

    @property
    def is_configured(self) -> bool:
        """Check if ORS has a non-empty API key."""
        return bool(self.api_key and self.api_key.strip())

    def route(self, start: LatLng, finish: LatLng, budget: CallBudget) -> RouteResult:
        """Fetch driving route from OpenRouteService."""
        if not self.is_configured:
            raise UpstreamError("ORS is not configured: ORS_API_KEY is missing or empty")

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, application/geo+json",
        }
        body = {
            "coordinates": [
                [round(start.lng, 6), round(start.lat, 6)],
                [round(finish.lng, 6), round(finish.lat, 6)],
            ]
        }

        client = get_client()
        with budget.consume(provider=self.name, purpose="route") as call:
            try:
                resp = client.post(self.base_url, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                call.status = "timeout"
                raise UpstreamTimeout(f"ORS request timed out: {exc}") from exc
            except httpx.RequestError as exc:
                call.status = "error"
                raise UpstreamError(f"ORS request failed: {exc}") from exc

            call.status = str(resp.status_code)

            if resp.status_code in (401, 403, 429):
                # Auth error, quota limit, or rate limit: do not retry
                raise UpstreamError(
                    f"ORS API authorization or quota error (HTTP {resp.status_code}): {resp.text}"
                )

            if resp.status_code >= 500:
                raise UpstreamError(f"ORS server error HTTP {resp.status_code}")

            try:
                data = resp.json()
            except Exception as exc:
                raise UpstreamError(f"ORS response was not valid JSON: {exc}") from exc

            if resp.status_code in (400, 404):
                error_msg = str(data.get("error", {}).get("message", resp.text))
                if "could not be found" in error_msg.lower() or "no route" in error_msg.lower():
                    raise NoRouteError(f"ORS found no route: {error_msg}")
                raise UpstreamError(f"ORS request error HTTP {resp.status_code}: {error_msg}")

            features = data.get("features", [])
            if not features:
                raise NoRouteError("ORS returned empty features list")

            feat = features[0]
            summary = feat.get("properties", {}).get("summary", {})
            if "distance" not in summary or "duration" not in summary:
                raise UpstreamError(
                    "ORS response missing distance or duration in properties.summary"
                )

            distance_miles = float(summary["distance"]) / 1609.344
            duration_minutes = float(summary["duration"]) / 60.0

            geometry = feat.get("geometry", {})
            coords_raw = geometry.get("coordinates")
            if not isinstance(coords_raw, list) or len(coords_raw) < 2:
                raise UpstreamError("ORS returned invalid or empty route geometry")

            try:
                coords = np.asarray(coords_raw, dtype=np.float64)
            except (ValueError, TypeError) as exc:
                raise UpstreamError(f"ORS geometry coordinates cannot be parsed: {exc}") from exc

            if coords.ndim != 2 or coords.shape[1] != 2:
                raise UpstreamError(f"ORS geometry shape invalid: {coords.shape}")

            if not np.all(np.isfinite(coords)):
                raise UpstreamError("ORS geometry contains non-finite coordinates (NaN or Inf)")

            lng_arr = coords[:, 0]
            lat_arr = coords[:, 1]

            if np.any(lat_arr < -90.0) or np.any(lat_arr > 90.0):
                raise UpstreamError("ORS geometry latitudes out of range [-90, 90]")
            if np.any(lng_arr < -180.0) or np.any(lng_arr > 180.0):
                raise UpstreamError("ORS geometry longitudes out of range [-180, 180]")

            return RouteResult(
                distance_miles=distance_miles,
                duration_minutes=duration_minutes,
                lat=lat_arr,
                lng=lng_arr,
                provider=self.name,
            )
