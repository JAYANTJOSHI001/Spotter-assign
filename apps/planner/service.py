"""Service orchestration: coordinate resolution, caching, routing, optimization, and response assembly."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

import numpy as np
from django.conf import settings
from django.core.cache import cache

from apps.api.errors import NoFeasiblePlanError
from apps.api.validators import RouteRequestParams
from apps.geo.corridor import match_corridor
from apps.geo.distance import haversine_miles
from apps.geo.resample import resample, simplify_for_response
from apps.geo.resolver import resolve_location
from apps.planner.schemas import Plan
from apps.planner.search import plan_with_widening
from apps.planner.simulate import validate_plan
from apps.providers.base import LatLng
from apps.providers.budget import CallBudget
from apps.providers.errors import SameLocation
from apps.providers.routing import get_route
from apps.stations.index import get_index
from apps.stations.pricing import median_price_in_window, national_median_price


def plan_trip(
    params: RouteRequestParams,
    budget: CallBudget,
    request_id: str = "",
) -> dict[str, Any]:
    """Execute end-to-end trip planning workflow and construct full response payload."""
    t_start = time.perf_counter()
    timings: dict[str, int] = {}
    warnings: list[str] = []

    # 1. Resolve start and finish locations
    t0 = time.perf_counter()
    start_loc = resolve_location(params.start, budget)
    finish_loc = resolve_location(params.finish, budget)
    timings["resolve"] = int((time.perf_counter() - t0) * 1000)

    if start_loc.warning:
        warnings.append(start_loc.warning)
    if finish_loc.warning:
        warnings.append(finish_loc.warning)

    # 2. Check same-location guard
    dist_direct = haversine_miles(start_loc.lat, start_loc.lng, finish_loc.lat, finish_loc.lng)
    if dist_direct < 0.5:
        raise SameLocation("Start and finish resolve to virtually the same location (< 0.5 mi)")

    # 3. Check plan result cache
    index = get_index()
    start_mode = getattr(settings, "START_MODE", "priced").lower()
    detour_factor = float(getattr(settings, "DETOUR_FACTOR", 2.0))
    cache_ttl = int(getattr(settings, "CACHE_TTL_S", 86400))

    plan_cache_key = (
        f"plan:v1:{start_loc.lat:.4f},{start_loc.lng:.4f}:"
        f"{finish_loc.lat:.4f},{finish_loc.lng:.4f}:"
        f"{params.max_range_miles:.1f}:{params.mpg:.1f}:{start_mode}:{params.geometry}:{index.data_version}"
    )

    cached_payload = cache.get(plan_cache_key)
    if cached_payload is not None:
        total_ms = int((time.perf_counter() - t_start) * 1000)
        cached_payload["meta"]["request_id"] = request_id
        cached_payload["meta"]["cache"] = "hit"
        cached_payload["meta"]["external_calls"] = len(budget.calls)
        cached_payload["meta"]["external_calls_detail"] = budget.calls
        cached_payload["meta"]["timings_ms"]["total"] = total_ms
        return cached_payload

    # 4. Route retrieval
    t0 = time.perf_counter()
    start_pt = LatLng(lat=start_loc.lat, lng=start_loc.lng)
    finish_pt = LatLng(lat=finish_loc.lat, lng=finish_loc.lng)
    route_res = get_route(start_pt, finish_pt, budget)
    timings["route"] = int((time.perf_counter() - t0) * 1000)

    cache_status = "route-hit" if route_res.provider == "cache" else "miss"

    # 5. Route resampling and candidate matching
    t0 = time.perf_counter()
    samples = resample(
        route_res.lat,
        route_res.lng,
        step_miles=0.5,
        provider_miles=route_res.distance_miles,
    )

    # Determine start fuel price for priced mode
    if start_mode == "priced":
        # Look for stations in initial 100 miles
        corridor_10 = match_corridor(samples, index.unit_vectors, buffer_miles=10.0)
        cand_prices = index.price[corridor_10.station_idx]
        cand_miles = corridor_10.mile_marker
        med_start = median_price_in_window(cand_prices, cand_miles, max_mile=100.0)
        if med_start is not None:
            start_price = float(med_start)
        else:
            start_price = float(national_median_price(index))
    else:
        start_price = float(national_median_price(index))

    timings["match"] = int((time.perf_counter() - t0) * 1000)

    # 6. Optimization across widening corridor
    t0 = time.perf_counter()
    corridor_schedule = (10, 25, 50)
    plan_result, widening_warnings = plan_with_widening(
        samples=samples,
        index=index,
        max_range_miles=params.max_range_miles,
        mpg=params.mpg,
        start_mode=start_mode,
        start_price=start_price,
        detour_factor=detour_factor,
        safety_reserve_miles=float(getattr(settings, "SAFETY_RESERVE_MILES", 0.0)),
        corridors=corridor_schedule,
    )
    timings["optimize"] = int((time.perf_counter() - t0) * 1000)
    warnings.extend(widening_warnings)

    if not plan_result.feasible:
        raise NoFeasiblePlanError(
            plan_result.message,
            details={
                "gap_start_mile": round(plan_result.gap_start_mile, 1),
                "gap_end_mile": round(plan_result.gap_end_mile, 1),
                "max_range_miles": params.max_range_miles,
            },
        )

    assert isinstance(plan_result, Plan)

    # 7. Independent continuous simulation validation
    validate_plan(
        plan=plan_result,
        route_miles=route_res.distance_miles,
        max_range=params.max_range_miles,
        mpg=params.mpg,
        detour_factor=detour_factor,
    )

    # 8. Geometry processing
    coords_stacked = np.column_stack([route_res.lat, route_res.lng])
    if params.geometry == "simplified":
        simplified_pts = simplify_for_response(coords_stacked, max_points=1500)
        route_coords = [[round(pt[1], 5), round(pt[0], 5)] for pt in simplified_pts]
    elif params.geometry == "full":
        route_coords = [
            [round(lng, 5), round(lat, 5)]
            for lat, lng in zip(route_res.lat, route_res.lng, strict=True)
        ]
    else:
        route_coords = []

    # 9. Assemble response payload
    # Calculate bounding box [min_lng, min_lat, max_lng, max_lat]
    bbox = [
        round(float(np.min(route_res.lng)), 4),
        round(float(np.min(route_res.lat)), 4),
        round(float(np.max(route_res.lng)), 4),
        round(float(np.max(route_res.lat)), 4),
    ]

    # Map GeoJSON features
    features: list[dict[str, Any]] = []
    if route_coords:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": route_coords},
                "properties": {
                    "type": "route",
                    "distance_miles": round(route_res.distance_miles, 1),
                    "duration_minutes": round(route_res.duration_minutes),
                },
            }
        )

    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(start_loc.lng, 5), round(start_loc.lat, 5)],
            },
            "properties": {"type": "start", "label": start_loc.label},
        }
    )

    stops_data: list[dict[str, Any]] = []
    total_detour_miles = 0.0

    for s in plan_result.stops:
        meta = index.metadata[s.station_idx]
        total_detour_miles += s.detour_miles
        stop_dict = {
            "sequence": s.sequence,
            "opis_id": s.opis_id,
            "name": meta.get("name", ""),
            "address": meta.get("address", ""),
            "city": meta.get("city", ""),
            "state": meta.get("state", ""),
            "lat": round(float(index.lat[s.station_idx]), 5),
            "lng": round(float(index.lng[s.station_idx]), 5),
            "price_per_gallon": round(s.price, 4),
            "mile_marker": round(s.mile_marker, 1),
            "offset_miles": round(s.offset_miles, 1),
            "detour_miles": round(s.detour_miles, 1),
            "gallons_purchased": round(float(s.gallons), 2),
            "cost_usd": round(float(s.cost_usd), 2),
            "fuel_on_arrival_gallons": s.fuel_on_arrival_gal,
            "fuel_after_gallons": s.fuel_after_gal,
        }
        stops_data.append(stop_dict)

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [stop_dict["lng"], stop_dict["lat"]]},
                "properties": {
                    "type": "stop",
                    "sequence": s.sequence,
                    "name": stop_dict["name"],
                    "city": stop_dict["city"],
                    "state": stop_dict["state"],
                    "price": stop_dict["price_per_gallon"],
                    "gallons": stop_dict["gallons_purchased"],
                    "cost": stop_dict["cost_usd"],
                    "mile_marker": stop_dict["mile_marker"],
                },
            }
        )

    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(finish_loc.lng, 5), round(finish_loc.lat, 5)],
            },
            "properties": {"type": "finish", "label": finish_loc.label},
        }
    )

    # Start fill data
    start_fill_data = None
    if plan_result.start_fill is not None:
        start_fill_data = {
            "gallons": round(float(plan_result.start_fill.gallons), 2),
            "price_per_gallon": round(plan_result.start_fill.price, 4),
            "cost_usd": round(float(plan_result.start_fill.cost_usd), 2),
        }

    total_cost_usd = round(float(plan_result.total_cost_usd), 2)
    total_gallons = round(float(plan_result.total_gallons), 2)
    avg_price = (
        round(total_cost_usd / total_gallons, 3) if total_gallons > 0 else round(start_price, 3)
    )

    # Construct map HTML URL
    map_query = urllib.parse.urlencode({"start": start_loc.query, "finish": finish_loc.query})
    map_url = f"/api/v1/route/map?{map_query}"

    total_ms = int((time.perf_counter() - t_start) * 1000)
    timings["total"] = total_ms

    payload = {
        "request": {
            "start": {
                "query": start_loc.query,
                "lat": round(start_loc.lat, 5),
                "lng": round(start_loc.lng, 5),
                "label": start_loc.label,
                "source": start_loc.source,
            },
            "finish": {
                "query": finish_loc.query,
                "lat": round(finish_loc.lat, 5),
                "lng": round(finish_loc.lng, 5),
                "label": finish_loc.label,
                "source": finish_loc.source,
            },
        },
        "route": {
            "distance_miles": round(route_res.distance_miles, 1),
            "duration_minutes": round(route_res.duration_minutes),
            "provider": route_res.provider,
            "bbox": bbox,
            "geometry": {"type": "LineString", "coordinates": route_coords}
            if route_coords
            else None,
        },
        "fuel_plan": {
            "assumptions": {
                "max_range_miles": round(params.max_range_miles),
                "mpg": round(params.mpg),
                "tank_gallons": round(params.max_range_miles / params.mpg, 1),
                "start_mode": start_mode,
                "start_price_per_gallon": round(start_price, 3),
                "corridor_miles_used": plan_result.corridor_used,
                "detour_factor": detour_factor,
            },
            "start_fill": start_fill_data,
            "stops": stops_data,
            "totals": {
                "total_fuel_cost_usd": total_cost_usd,
                "total_gallons": total_gallons,
                "avg_price_per_gallon": avg_price,
                "stops": len(stops_data),
                "route_miles": round(route_res.distance_miles, 1),
                "detour_miles": round(total_detour_miles, 1),
            },
        },
        "map": {
            "html_url": map_url,
            "geojson": {
                "type": "FeatureCollection",
                "features": features,
            },
        },
        "meta": {
            "request_id": request_id,
            "external_calls": len(budget.calls),
            "external_calls_detail": budget.calls,
            "cache": cache_status,
            "timings_ms": timings,
            "data_version": index.data_version,
            "warnings": warnings,
        },
    }

    # Store assembled payload in cache
    cache.set(plan_cache_key, payload, timeout=cache_ttl)
    return payload
