"""API telemetry, budget, timing, and rate limiting middleware."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

from apps.api.errors import error_json_response
from apps.providers.budget import CallBudget

logger = logging.getLogger("fuelroute.api")

SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


class RequestIdMiddleware:
    """Assigns or propagates request ID to request and response header."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming_id = request.headers.get("X-Request-ID", "").strip()
        if incoming_id and SAFE_REQUEST_ID_REGEX.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class CallBudgetMiddleware:
    """Initializes request-scoped CallBudget and attaches X-External-Calls header."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        max_calls = getattr(settings, "EXTERNAL_CALL_BUDGET", 3)
        request.budget = CallBudget(max_calls=max_calls)

        response = self.get_response(request)

        if hasattr(request, "budget"):
            response["X-External-Calls"] = str(request.budget.calls_count)
        return response


class ServerTimingMiddleware:
    """Measures overall request time and appends Server-Timing response header."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.server_timings = {}
        t0 = time.perf_counter()

        response = self.get_response(request)

        total_ms = (time.perf_counter() - t0) * 1000.0

        # Build Server-Timing header: total;dur=X, resolve;dur=Y, ...
        timings = [f"total;dur={total_ms:.1f}"]
        for metric, dur in getattr(request, "server_timings", {}).items():
            timings.append(f"{metric};dur={dur:.1f}")

        response["Server-Timing"] = ", ".join(timings)
        return response


class RateLimitMiddleware:
    """Sliding per-minute IP-based rate limiter using Django cache."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        limit = getattr(settings, "RATE_LIMIT_PER_MIN", 60)
        # 0 or negative disables rate limiting
        if limit <= 0:
            return self.get_response(request)

        # Do not rate limit health check
        if request.path.endswith("/health"):
            return self.get_response(request)

        # Allow tests to bypass rate limiting with an explicit test header or setting
        if getattr(settings, "DISABLE_RATE_LIMIT", False):
            return self.get_response(request)

        ip = self._get_client_ip(request)
        # 1-minute bucket
        bucket = int(time.time() // 60)
        cache_key = f"rate_limit:{ip}:{bucket}"

        try:
            current_count = cache.get(cache_key, 0)
            if current_count >= limit:
                req_id = getattr(request, "request_id", "")
                logger.warning("Rate limit exceeded for IP %s: %s req/min", ip, current_count)
                return error_json_response(
                    code="RATE_LIMITED",
                    message=f"Rate limit of {limit} requests per minute exceeded.",
                    status=429,
                    request_id=req_id,
                )

            # Atomic increment or set
            if current_count == 0:
                cache.set(cache_key, 1, timeout=65)
            else:
                try:
                    cache.incr(cache_key)
                except Exception:
                    cache.set(cache_key, current_count + 1, timeout=65)
        except Exception as exc:
            # If cache is temporarily down, fail open but log
            logger.warning("Rate limit cache error: %s", exc)

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")
