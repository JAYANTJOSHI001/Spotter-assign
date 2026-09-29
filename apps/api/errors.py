"""Uniform error responses and exception mappings for the FuelRoute API."""

from __future__ import annotations

import logging
from typing import Any

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base exception for API errors with uniform envelope codes."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if http_status is not None:
            self.http_status = http_status


class ValidationFailed(ApiError):
    code: str = "VALIDATION_ERROR"
    http_status: int = 400


class NoFeasiblePlanError(ApiError):
    code: str = "NO_FEASIBLE_PLAN"
    http_status: int = 422


class RateLimitedError(ApiError):
    code: str = "RATE_LIMITED"
    http_status: int = 429


def make_error_payload(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Construct uniform JSON error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def error_json_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status: int = 400,
    request_id: str = "",
) -> JsonResponse:
    """Return JsonResponse containing uniform error envelope."""
    payload = make_error_payload(code, message, details, request_id)
    return JsonResponse(payload, status=status, json_dumps_params={"separators": (",", ":")})


def handle_exception(exc: Exception, request_id: str = "") -> JsonResponse:
    """Map any domain, provider, or unexpected exception to a uniform JsonResponse."""
    from apps.providers.errors import ProviderError

    if isinstance(exc, ApiError):
        return error_json_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status=exc.http_status,
            request_id=request_id,
        )
    if isinstance(exc, ProviderError):
        return error_json_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status=exc.http_status,
            request_id=request_id,
        )

    # Unexpected internal error
    logger.exception("Unexpected error handling request %s: %s", request_id, exc)
    return error_json_response(
        code="INTERNAL_ERROR",
        message="An internal error occurred processing the route.",
        details={},
        status=500,
        request_id=request_id,
    )
