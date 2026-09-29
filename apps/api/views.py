"""API views for FuelRoute service: health, route planning, and interactive map."""

from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from apps.api.errors import (
    error_json_response,
    handle_exception,
)
from apps.api.validators import parse_and_validate_route_request
from apps.planner.service import plan_trip
from apps.providers.budget import CallBudget
from apps.stations.index import IndexEmpty, get_index

logger = logging.getLogger("fuelroute.api")


def health(request: HttpRequest) -> JsonResponse:
    """Comprehensive health check reporting db status, station count, and data version."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "error"

    try:
        index = get_index()
        return JsonResponse(
            {
                "status": "ok",
                "db": db_status,
                "stations": len(index),
                "data_version": index.data_version,
            },
            status=200,
        )
    except IndexEmpty:
        return JsonResponse(
            {
                "status": "error",
                "db": db_status,
                "stations": 0,
                "error": "station index is empty",
            },
            status=503,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "status": "error",
                "db": db_status,
                "stations": 0,
                "error": str(exc),
            },
            status=503,
        )


@csrf_exempt
def route_view(request: HttpRequest) -> HttpResponse:
    """Plan an optimal fuel route (JSON endpoint). Supports GET and POST."""
    request_id = getattr(request, "request_id", "")
    budget = getattr(request, "budget", None) or CallBudget(max_calls=3)

    try:
        route_req = parse_and_validate_route_request(request)
        plan = plan_trip(route_req, budget=budget, request_id=request_id)

        if "meta" in plan and "timings_ms" in plan["meta"]:
            request.server_timings = plan["meta"]["timings_ms"]

        return JsonResponse(plan, status=200, json_dumps_params={"separators": (",", ":")})

    except Exception as exc:
        return handle_exception(exc, request_id=request_id)


def route_map_view(request: HttpRequest) -> HttpResponse:
    """Render interactive Leaflet map for a planned route."""
    request_id = getattr(request, "request_id", "")
    budget = getattr(request, "budget", None) or CallBudget(max_calls=3)

    if request.method != "GET":
        return error_json_response(
            code="VALIDATION_ERROR",
            message=f"HTTP method {request.method} not allowed. Use GET.",
            status=405,
            request_id=request_id,
        )

    try:
        raw_data = request.GET.dict()
        # Ensure geometry is simplified or full so coordinates are present for Leaflet
        if not raw_data.get("geometry") or raw_data.get("geometry") == "none":
            raw_data["geometry"] = "simplified"

        route_req = parse_and_validate_route_request(raw_data)
        plan = plan_trip(route_req, budget=budget, request_id=request_id)

        # Record timings for Server-Timing middleware
        if "meta" in plan and "timings_ms" in plan["meta"]:
            request.server_timings = plan["meta"]["timings_ms"]

        return render(request, "api/map.html", {"plan": plan})

    except Exception as exc:
        return handle_exception(exc, request_id=request_id)
