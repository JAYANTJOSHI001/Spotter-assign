from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, JsonResponse

from apps.stations.index import IndexEmpty, get_index


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
