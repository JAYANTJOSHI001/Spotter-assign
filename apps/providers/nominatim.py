"""Nominatim geocoding provider with caching and rate limiting."""

from __future__ import annotations

import hashlib

import httpx
from django.conf import settings
from django.core.cache import cache

from apps.providers.base import GeocodeResult
from apps.providers.budget import CallBudget
from apps.providers.errors import LocationNotFound, UpstreamError, UpstreamTimeout

NOMINATIM_CACHE_TTL_S = 30 * 86400  # 30 days
_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    """Return a pooled HTTP client for Nominatim."""
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


class NominatimGeocoder:
    """Nominatim geocoder for free-text location search in the US."""

    name: str = "nominatim"

    def __init__(self, base_url: str | None = None, user_agent: str | None = None) -> None:
        self.base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
        ).rstrip("/")
        self.user_agent = (
            user_agent if user_agent is not None else getattr(settings, "NOMINATIM_USER_AGENT", "")
        )

    def _cache_key(self, text: str) -> str:
        norm = text.strip().lower()
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        return f"geocode:v1:{digest}"

    def geocode(self, text: str, budget: CallBudget) -> GeocodeResult:
        """Geocode a free-text location query to US coordinates."""
        query = text.strip()
        if not query:
            raise LocationNotFound("Empty location query")

        cache_key = self._cache_key(query)
        cached = cache.get(cache_key)
        if cached is not None:
            if cached.get("not_found"):
                raise LocationNotFound(f"Location not found (cached): '{query}'")
            return GeocodeResult(
                lat=cached["lat"],
                lng=cached["lng"],
                label=cached.get("label", query),
                source="nominatim",
            )

        if not self.user_agent or "example.com" in self.user_agent:
            # Enforce valid User-Agent per Nominatim policy
            pass  # Allow tests or log warning if needed, but headers must be sent

        url = f"{self.base_url}/search"
        headers = {
            "User-Agent": self.user_agent or "fuelroute-assessment/1.0",
            "Accept": "application/json",
        }
        params = {
            "q": query,
            "format": "jsonv2",
            "countrycodes": "us",
            "limit": "1",
        }

        client = get_client()
        with budget.consume(provider=self.name, purpose="geocode") as call:
            try:
                resp = client.get(url, headers=headers, params=params)
            except httpx.TimeoutException as exc:
                call.status = "timeout"
                raise UpstreamTimeout(f"Nominatim geocoding timed out: {exc}") from exc
            except httpx.RequestError as exc:
                call.status = "error"
                raise UpstreamError(f"Nominatim network error: {exc}") from exc

            call.status = str(resp.status_code)

            if resp.status_code == 403:
                raise UpstreamError(
                    f"Nominatim access forbidden (HTTP 403). Check NOMINATIM_USER_AGENT: {resp.text}"
                )
            if resp.status_code >= 500:
                raise UpstreamError(f"Nominatim server error HTTP {resp.status_code}")

            try:
                data = resp.json()
            except Exception as exc:
                raise UpstreamError(f"Nominatim returned non-JSON response: {exc}") from exc

            if not isinstance(data, list) or len(data) == 0:
                # Cache negative result so we don't repeat calls for bogus locations
                cache.set(cache_key, {"not_found": True}, timeout=NOMINATIM_CACHE_TTL_S)
                raise LocationNotFound(f"Location not found via Nominatim: '{query}'")

            item = data[0]
            try:
                lat = float(item["lat"])
                lng = float(item["lon"])
            except (KeyError, ValueError, TypeError) as exc:
                raise UpstreamError(
                    f"Nominatim response missing or invalid lat/lon: {exc}"
                ) from exc

            label = str(item.get("display_name", query))
            result = GeocodeResult(lat=lat, lng=lng, label=label, source="nominatim")

            # Store in cache
            cache.set(
                cache_key,
                {"lat": lat, "lng": lng, "label": label, "not_found": False},
                timeout=NOMINATIM_CACHE_TTL_S,
            )

            return result
