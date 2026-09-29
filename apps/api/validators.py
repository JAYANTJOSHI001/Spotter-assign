"""Input validation and parsing for Route API requests."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest

from apps.api.errors import ValidationFailed

ALLOWED_FIELDS = {"start", "finish", "max_range_miles", "mpg", "geometry"}
ALLOWED_GEOMETRIES = {"full", "simplified", "none"}
MAX_BODY_BYTES = 4096
MAX_STRING_LENGTH = 200


@dataclass(frozen=True, slots=True)
class RouteRequestParams:
    """Parsed and validated request parameters."""

    start: str | dict[str, Any]
    finish: str | dict[str, Any]
    max_range_miles: float = 500.0
    mpg: float = 10.0
    geometry: str = "simplified"


def _clean_string(val: str, field_name: str, details: dict[str, Any]) -> str:
    """Trim, NFC-normalize, and validate length of string inputs."""
    normalized = unicodedata.normalize("NFC", val).strip()
    if not normalized:
        details[field_name] = f"'{field_name}' cannot be empty"
    elif len(normalized) > MAX_STRING_LENGTH:
        details[field_name] = (
            f"'{field_name}' exceeds maximum length of {MAX_STRING_LENGTH} characters"
        )
    return normalized


def _validate_location_input(
    val: Any, field_name: str, details: dict[str, Any]
) -> str | dict[str, Any]:
    """Validate that location is either a clean string or a coordinate dict."""
    if isinstance(val, str):
        return _clean_string(val, field_name, details)
    elif isinstance(val, dict):
        lat = val.get("lat", val.get("latitude"))
        lng = val.get("lng", val.get("lon", val.get("longitude")))
        if lat is None or lng is None:
            details[field_name] = (
                f"'{field_name}' coordinate object must contain 'lat' and 'lng' keys"
            )
            return val
        try:
            float(lat)
            float(lng)
        except (ValueError, TypeError):
            details[field_name] = f"'{field_name}' coordinates must be valid numeric values"
        return val
    else:
        details[field_name] = f"'{field_name}' must be a string or a coordinate object"
        return val


def parse_and_validate_route_request(
    request_or_data: HttpRequest | dict[str, Any],
) -> RouteRequestParams:
    """Parse HttpRequest (GET/POST) or raw dictionary into validated RouteRequestParams."""
    data: dict[str, Any] = {}
    details: dict[str, Any] = {}

    if isinstance(request_or_data, HttpRequest):
        request = request_or_data
        if request.method == "POST":
            if len(request.body) > MAX_BODY_BYTES:
                raise ValidationFailed(
                    f"Request payload exceeds {MAX_BODY_BYTES} byte limit",
                    details={
                        "body": f"Payload size {len(request.body)} bytes exceeds {MAX_BODY_BYTES}"
                    },
                )
            if not request.body.strip():
                raise ValidationFailed(
                    "Empty request body",
                    details={"body": "Expected JSON payload with 'start' and 'finish'"},
                )
            try:
                parsed = json.loads(request.body)
                if not isinstance(parsed, dict):
                    raise ValidationFailed(
                        "Request body must be a JSON object",
                        details={"body": "Top-level JSON value must be an object"},
                    )
                data = parsed
            except json.JSONDecodeError as exc:
                raise ValidationFailed(
                    f"Malformed JSON: {exc.msg}",
                    details={"body": f"Line {exc.lineno}, column {exc.colno}: {exc.msg}"},
                ) from exc
        elif request.method == "GET":
            data = request.GET.dict()
        else:
            raise ValidationFailed(
                f"Method {request.method} not allowed",
                details={"method": "Allowed methods: GET, POST"},
                http_status=405,
            )
    elif isinstance(request_or_data, dict):
        data = request_or_data
    else:
        raise ValidationFailed(
            "Invalid request type",
            details={"type": f"Expected HttpRequest or dict, got {type(request_or_data).__name__}"},
        )

    # 1. Reject unknown fields
    unknown_fields = set(data.keys()) - ALLOWED_FIELDS
    if unknown_fields:
        unknown_sorted = sorted(unknown_fields)
        allowed_sorted = sorted(ALLOWED_FIELDS)
        raise ValidationFailed(
            f"Unknown parameter(s): {', '.join(unknown_sorted)}. Allowed parameters: {', '.join(allowed_sorted)}",
            details={"unknown_fields": unknown_sorted, "allowed_fields": allowed_sorted},
        )

    # 2. Check required fields
    if "start" not in data or data["start"] is None:
        details["start"] = "Missing required parameter 'start'"
    if "finish" not in data or data["finish"] is None:
        details["finish"] = "Missing required parameter 'finish'"

    if details:
        raise ValidationFailed("Validation failed for route request", details=details)

    # 3. Clean and validate location inputs
    clean_start = _validate_location_input(data["start"], "start", details)
    clean_finish = _validate_location_input(data["finish"], "finish", details)

    # 4. Optional numeric overrides
    max_range = 500.0
    if "max_range_miles" in data:
        try:
            max_range = float(data["max_range_miles"])
            if not (50.0 <= max_range <= 1000.0):
                details["max_range_miles"] = "max_range_miles must be between 50 and 1000"
        except (ValueError, TypeError):
            details["max_range_miles"] = "max_range_miles must be a valid number"

    mpg = 10.0
    if "mpg" in data:
        try:
            mpg = float(data["mpg"])
            if not (1.0 <= mpg <= 100.0):
                details["mpg"] = "mpg must be between 1 and 100"
        except (ValueError, TypeError):
            details["mpg"] = "mpg must be a valid number"

    geometry = "simplified"
    if "geometry" in data:
        geom_val = str(data["geometry"]).strip().lower()
        if geom_val not in ALLOWED_GEOMETRIES:
            details["geometry"] = (
                f"geometry must be one of: {', '.join(sorted(ALLOWED_GEOMETRIES))}"
            )
        else:
            geometry = geom_val

    if details:
        raise ValidationFailed("Validation failed for route request", details=details)

    return RouteRequestParams(
        start=clean_start,
        finish=clean_finish,
        max_range_miles=max_range,
        mpg=mpg,
        geometry=geometry,
    )
