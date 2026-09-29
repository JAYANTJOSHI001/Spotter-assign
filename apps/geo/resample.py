"""Route resampling, scaling to upstream provider distance, and polyline simplification.

All coordinates are in decimal degrees.
All distances are in statute miles.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from apps.geo.distance import haversine_miles

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RouteSamples:
    """Evenly spaced route samples with cumulative mile markers."""

    lat: np.ndarray  # float64
    lng: np.ndarray  # float64
    mile: np.ndarray  # float64
    total_miles: float

    def __len__(self) -> int:
        return len(self.lat)


def cumulative_miles(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    """Compute cumulative great-circle miles along a sequence of coordinates.

    Args:
        lat: 1D array of latitudes in degrees.
        lng: 1D array of longitudes in degrees.

    Returns:
        1D array of cumulative distances starting at 0.0 with same length as input.
    """
    if len(lat) < 2:
        return np.zeros(len(lat), dtype=np.float64)

    dists = haversine_miles(lat[:-1], lng[:-1], lat[1:], lng[1:])
    return np.insert(np.cumsum(dists), 0, 0.0)


def scale_to_provider(cum: np.ndarray, provider_miles: float) -> np.ndarray:
    """Scale cumulative geometry distances so the final point matches provider road distance.

    Args:
        cum: Cumulative distance array from geometry.
        provider_miles: Total driving road miles returned by upstream provider.

    Returns:
        Scaled cumulative distance array where scaled[-1] == provider_miles.

    Raises:
        ValueError: If provider_miles is invalid (<=0, NaN) or discrepancy > 5%.
    """
    if np.isnan(provider_miles) or provider_miles <= 0:
        raise ValueError(f"Invalid provider distance: {provider_miles}")
    if len(cum) < 2:
        raise ValueError("Cumulative distance array must contain at least 2 points")
    if np.isnan(cum).any() or cum[-1] <= 0:
        raise ValueError("Cumulative distance geometry length must be positive and non-NaN")

    geom_length = float(cum[-1])
    diff_pct = abs(geom_length - provider_miles) / provider_miles

    if diff_pct > 0.05:
        raise ValueError(
            f"Geometry length ({geom_length:.2f} mi) differs from provider distance "
            f"({provider_miles:.2f} mi) by more than 5% ({diff_pct * 100.0:.1f}%)"
        )

    if diff_pct > 0.01:
        logger.warning(
            "Geometry length (%.2f mi) differs from provider distance (%.2f mi) by %.1f%%",
            geom_length,
            provider_miles,
            diff_pct * 100.0,
        )

    scaled = cum * (provider_miles / geom_length)
    scaled[-1] = provider_miles  # Ensure exact match
    return scaled


def resample(
    lat: np.ndarray | Sequence[float],
    lng: np.ndarray | Sequence[float],
    step_miles: float = 0.5,
    provider_miles: float | None = None,
) -> RouteSamples:
    """Resample route coordinates into evenly spaced mile-marked points.

    Args:
        lat: Latitude array or sequence in degrees.
        lng: Longitude array or sequence in degrees.
        step_miles: Uniform resampling step in miles (default 0.5 mi).
        provider_miles: Optional provider road distance to scale geometry distances to.

    Returns:
        RouteSamples with interpolated lat, lng, mile markers, and total_miles.
    """
    lat_arr = np.asarray(lat, dtype=np.float64)
    lng_arr = np.asarray(lng, dtype=np.float64)

    if len(lat_arr) < 2 or len(lng_arr) < 2:
        raise ValueError("Route coordinates must contain at least 2 points")
    if len(lat_arr) != len(lng_arr):
        raise ValueError(f"lat and lng lengths must match ({len(lat_arr)} != {len(lng_arr)})")

    cum = cumulative_miles(lat_arr, lng_arr)
    total_raw = float(cum[-1])
    if total_raw <= 0:
        raise ValueError("Route has zero total distance (all coordinates are identical)")

    if provider_miles is not None:
        cum = scale_to_provider(cum, provider_miles)

    total_miles = float(cum[-1])

    # Sample mile markers at step_miles intervals, always including exact endpoint
    sample_miles = np.arange(0.0, total_miles, step_miles, dtype=np.float64)
    if len(sample_miles) == 0 or sample_miles[-1] < total_miles:
        sample_miles = np.append(sample_miles, total_miles)
    else:
        sample_miles[-1] = total_miles

    interp_lat = np.interp(sample_miles, cum, lat_arr)
    interp_lng = np.interp(sample_miles, cum, lng_arr)

    return RouteSamples(
        lat=interp_lat,
        lng=interp_lng,
        mile=sample_miles,
        total_miles=total_miles,
    )


def _perpendicular_distance_sq(
    pt: np.ndarray,
    line_start: np.ndarray,
    line_end: np.ndarray,
) -> float:
    """Compute squared perpendicular distance from point to line segment in equirectangular projection."""
    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]
    denom = dx * dx + dy * dy
    if denom == 0:
        return float((pt[0] - line_start[0]) ** 2 + (pt[1] - line_start[1]) ** 2)

    # Cross product magnitude
    num = (
        (line_end[1] - line_start[1]) * pt[0]
        - (line_end[0] - line_start[0]) * pt[1]
        + line_end[0] * line_start[1]
        - line_end[1] * line_start[0]
    )
    return float((num * num) / denom)


def _douglas_peucker_indices(coords: np.ndarray, epsilon_sq: float) -> np.ndarray:
    """Iterative (non-recursive) Douglas-Peucker returning boolean mask of kept points."""
    n = len(coords)
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[-1] = True

    stack = [(0, n - 1)]

    while stack:
        start_idx, end_idx = stack.pop()
        if end_idx <= start_idx + 1:
            continue

        p_start = coords[start_idx]
        p_end = coords[end_idx]
        d = p_end - p_start
        denom = float(d[0] * d[0] + d[1] * d[1])

        pts = coords[start_idx + 1 : end_idx]
        if denom < 1e-14:
            d_sq = np.sum((pts - p_start) ** 2, axis=1)
        else:
            num = (
                pts[:, 0] * d[1] - pts[:, 1] * d[0] + p_end[0] * p_start[1] - p_end[1] * p_start[0]
            )
            d_sq = (num * num) / denom

        max_offset = int(np.argmax(d_sq))
        max_d_sq = float(d_sq[max_offset])
        max_idx = start_idx + 1 + max_offset

        if max_d_sq > epsilon_sq:
            keep[max_idx] = True
            stack.append((start_idx, max_idx))
            stack.append((max_idx, end_idx))

    return keep


def simplify_for_response(
    coords: Sequence[Sequence[float]] | np.ndarray,
    max_points: int = 1500,
) -> list[list[float]] | np.ndarray:
    """Simplify polyline coordinates to at most max_points using iterative Douglas-Peucker.

    Preserves exact start and finish endpoints.

    Args:
        coords: Sequence of [lng, lat] or [lat, lng] pairs.
        max_points: Maximum allowed number of points in simplified response.

    Returns:
        Simplified coordinates in same format with length <= max_points.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    n = len(coords_arr)

    if n <= max_points:
        return coords

    # If coordinate count is massive (> 3000), pre-subsample uniformly to 3000 points
    # to keep Douglas-Peucker blazing fast while preserving all macro curves and endpoints
    if n > 3000:
        pre_idx = np.linspace(0, n - 1, 3000, dtype=int)
        coords_eval = coords_arr[pre_idx]
    else:
        coords_eval = coords_arr

    # Binary search for epsilon that achieves len(result) <= max_points
    low_eps_sq = 1e-12
    high_eps_sq = 1e-2
    best_mask = np.ones(len(coords_eval), dtype=bool)

    for _ in range(12):
        mid_eps_sq = (low_eps_sq + high_eps_sq) / 2.0
        mask = _douglas_peucker_indices(coords_eval, mid_eps_sq)
        count = int(np.sum(mask))

        if count <= max_points:
            best_mask = mask
            high_eps_sq = mid_eps_sq
        else:
            low_eps_sq = mid_eps_sq

    simplified = coords_eval[best_mask]

    # If still > max_points (edge case), take uniform subsample retaining endpoints
    if len(simplified) > max_points:
        indices = np.linspace(0, len(simplified) - 1, max_points, dtype=int)
        simplified = simplified[indices]

    if isinstance(coords, list):
        return [list(pt) for pt in simplified]
    return simplified
