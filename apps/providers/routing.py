"""Route orchestration: primary provider, retry, fallback, and caching."""

from __future__ import annotations

import io
import time
from typing import Any

import numpy as np
from django.conf import settings
from django.core.cache import cache

from apps.providers.base import LatLng, RouteProvider, RouteResult
from apps.providers.budget import CallBudget
from apps.providers.errors import ProviderError, UpstreamError, UpstreamTimeout
from apps.providers.fixture import FixtureRouteProvider
from apps.providers.ors import ORSProvider
from apps.providers.osrm import OSRMProvider


def make_route_cache_key(start: LatLng, finish: LatLng) -> str:
    """Generate cache key from 4-decimal rounded coordinates."""
    return f"route:v1:{start.lat:.4f},{start.lng:.4f}:{finish.lat:.4f},{finish.lng:.4f}"


def serialize_route(route: RouteResult) -> dict[str, Any]:
    """Serialize RouteResult into compact compressed bytes."""
    buf = io.BytesIO()
    np.savez_compressed(buf, lat=route.lat, lng=route.lng)
    return {
        "distance_miles": route.distance_miles,
        "duration_minutes": route.duration_minutes,
        "coords_npz": buf.getvalue(),
        "provider": route.provider,
    }


def deserialize_route(data: dict[str, Any], provider_override: str = "cache") -> RouteResult:
    """Deserialize compact dictionary back to RouteResult."""
    buf = io.BytesIO(data["coords_npz"])
    npz = np.load(buf)
    return RouteResult(
        distance_miles=float(data["distance_miles"]),
        duration_minutes=float(data["duration_minutes"]),
        lat=npz["lat"],
        lng=npz["lng"],
        provider=provider_override or data.get("provider", "cache"),
    )


def get_primary_provider() -> RouteProvider:
    """Instantiate primary route provider based on settings."""
    provider_name = getattr(settings, "ROUTING_PROVIDER", "osrm").lower()
    if provider_name == "fixture":
        return FixtureRouteProvider()
    if provider_name == "ors":
        return ORSProvider()
    return OSRMProvider()


def get_fallback_provider() -> RouteProvider | None:
    """Return fallback provider if configured and distinct from primary."""
    provider_name = getattr(settings, "ROUTING_PROVIDER", "osrm").lower()
    ors_key = getattr(settings, "ORS_API_KEY", "")
    if provider_name != "ors" and ors_key and ors_key.strip():
        return ORSProvider()
    return None


def get_route(
    start: LatLng,
    finish: LatLng,
    budget: CallBudget,
    retry_delay_s: float = 0.2,
) -> RouteResult:
    """Retrieve driving route with caching, 1 retry on timeout/5xx, and fallback."""
    cache_key = make_route_cache_key(start, finish)
    ttl = int(getattr(settings, "CACHE_TTL_S", 86400))

    # 1. Cache lookup
    cached = cache.get(cache_key)
    if cached is not None:
        return deserialize_route(cached, provider_override="cache")

    primary = get_primary_provider()
    fallback = get_fallback_provider()

    last_error: ProviderError | None = None

    # 2. Try primary provider
    try:
        result = primary.route(start, finish, budget)
        cache.set(cache_key, serialize_route(result), timeout=ttl)
        return result
    except (UpstreamTimeout, UpstreamError) as exc:
        last_error = exc
        # Retry once only on timeout or 5xx if budget remains
        can_retry = budget.max_calls - len(budget.records) > 0
        if can_retry and "quota" not in str(exc).lower() and "forbidden" not in str(exc).lower():
            if retry_delay_s > 0:
                time.sleep(retry_delay_s)
            try:
                result = primary.route(start, finish, budget)
                cache.set(cache_key, serialize_route(result), timeout=ttl)
                return result
            except (UpstreamTimeout, UpstreamError) as retry_exc:
                last_error = retry_exc

    # 3. Fallback provider if configured and budget remains
    if fallback is not None and (budget.max_calls - len(budget.records) > 0):
        try:
            result = fallback.route(start, finish, budget)
            cache.set(cache_key, serialize_route(result), timeout=ttl)
            return result
        except ProviderError as fb_exc:
            last_error = fb_exc

    # 4. If we reached here, raise the last encountered error
    if last_error is not None:
        raise last_error

    raise UpstreamError("Failed to calculate route with available providers")
