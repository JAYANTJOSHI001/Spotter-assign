"""Provider and routing exceptions for the FuelRoute service."""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider-related errors."""

    code: str = "UPSTREAM_ERROR"
    http_status: int = 502

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NoRouteError(ProviderError):
    """Raised when no driving route can be found between endpoints."""

    code: str = "NO_ROUTE"
    http_status: int = 422


class UpstreamError(ProviderError):
    """Raised when an upstream provider returns 5xx or invalid payload."""

    code: str = "UPSTREAM_ERROR"
    http_status: int = 502


class UpstreamTimeout(ProviderError):
    """Raised when an upstream provider call times out after retries."""

    code: str = "UPSTREAM_TIMEOUT"
    http_status: int = 504


class BudgetExceeded(ProviderError):
    """Raised when the request-scoped external call budget is exhausted."""

    code: str = "UPSTREAM_ERROR"
    http_status: int = 502


class LocationNotFound(ProviderError):
    """Raised when a location query cannot be resolved to coordinates."""

    code: str = "LOCATION_NOT_FOUND"
    http_status: int = 422


class OutsideUSA(ProviderError):
    """Raised when a resolved location is outside supported contiguous US bounds."""

    code: str = "OUTSIDE_USA"
    http_status: int = 422


class SameLocation(ProviderError):
    """Raised when start and finish resolve to virtually the same point (< 0.5 mi)."""

    code: str = "SAME_LOCATION"
    http_status: int = 422
