"""Tests validating the OpenAPI 3.1 schema and error code completeness."""

from __future__ import annotations

from pathlib import Path

import yaml

from apps.api.errors import (
    ApiError,
    NoFeasiblePlanError,
    RateLimitedError,
    ValidationFailed,
)
from apps.providers.errors import (
    BudgetExceeded,
    LocationNotFound,
    NoRouteError,
    OutsideUSA,
    ProviderError,
    SameLocation,
    UpstreamError,
    UpstreamTimeout,
)

OPENAPI_PATH = Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "openapi.yaml"


def test_openapi_file_exists_and_parses() -> None:
    assert OPENAPI_PATH.is_file(), f"Missing openapi.yaml at {OPENAPI_PATH}"
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    assert spec.get("openapi", "").startswith("3.1"), (
        f"Expected OpenAPI 3.1, got {spec.get('openapi')}"
    )
    assert "paths" in spec
    assert "/api/v1/health" in spec["paths"]
    assert "/api/v1/route" in spec["paths"]
    assert "/api/v1/route/map" in spec["paths"]

    # Verify methods
    assert "get" in spec["paths"]["/api/v1/health"]
    assert "get" in spec["paths"]["/api/v1/route"]
    assert "post" in spec["paths"]["/api/v1/route"]
    assert "get" in spec["paths"]["/api/v1/route/map"]


def test_error_codes_consistency_between_code_and_openapi() -> None:
    """Assert that every error code in code has a schema in openapi.yaml and vice-versa."""
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 1. Error codes from OpenAPI schema
    error_code_schema = spec["components"]["schemas"]["ErrorCode"]
    openapi_codes = set(error_code_schema.get("enum", []))
    assert openapi_codes, "ErrorCode enum is empty in openapi.yaml"

    # 2. Error codes defined in Python exception classes
    python_exception_classes = [
        ValidationFailed,
        LocationNotFound,
        OutsideUSA,
        SameLocation,
        NoRouteError,
        NoFeasiblePlanError,
        RateLimitedError,
        UpstreamError,
        UpstreamTimeout,
        BudgetExceeded,
        ProviderError,
        ApiError,
    ]
    code_codes = {cls.code for cls in python_exception_classes}

    # Verify both sets are non-empty and exactly equal
    missing_in_spec = code_codes - openapi_codes
    missing_in_code = openapi_codes - code_codes

    assert not missing_in_spec, (
        f"Error codes in Python code but missing in OpenAPI: {missing_in_spec}"
    )
    assert not missing_in_code, (
        f"Error codes in OpenAPI but missing in Python code: {missing_in_code}"
    )
    assert openapi_codes == code_codes
