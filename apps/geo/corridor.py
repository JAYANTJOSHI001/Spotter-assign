"""Spatial corridor matching for fuel stations along a route.

Uses 3D Cartesian coordinates on the unit sphere and scipy.spatial.cKDTree
to eliminate planar projection distortion and antimeridian singularities.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from apps.geo.distance import chord_to_miles, miles_to_chord, to_unit_vectors
from apps.geo.resample import RouteSamples


@dataclass(frozen=True, slots=True)
class Candidates:
    """Matched candidate fuel stations within a route corridor."""

    station_idx: np.ndarray  # int64 index into StationIndex
    mile_marker: np.ndarray  # float64 mile along the route where closest
    offset_miles: np.ndarray  # float64 perpendicular offset distance from route

    def __len__(self) -> int:
        return len(self.station_idx)


def match_corridor(
    samples: RouteSamples,
    station_unit_vectors: np.ndarray,
    buffer_miles: float,
) -> Candidates:
    """Find all fuel stations within buffer_miles of the sampled route polyline.

    Args:
        samples: Evenly spaced route samples.
        station_unit_vectors: (N, 3) float64 array of station unit vectors.
        buffer_miles: Search corridor radius in statute miles.

    Returns:
        Candidates sorted deterministically by (mile_marker, offset_miles, station_idx).
    """
    if len(samples) == 0 or len(station_unit_vectors) == 0 or buffer_miles <= 0:
        empty_int = np.empty(0, dtype=np.int64)
        empty_float = np.empty(0, dtype=np.float64)
        return Candidates(station_idx=empty_int, mile_marker=empty_float, offset_miles=empty_float)

    # Convert route samples to 3D unit vectors and build KD-Tree
    sample_uv = to_unit_vectors(samples.lat, samples.lng)
    tree = cKDTree(sample_uv)

    # Convert corridor radius in miles to straight-line 3D chord distance on unit sphere
    chord_limit = miles_to_chord(buffer_miles)

    # Query nearest route sample for every station
    d, j = tree.query(station_unit_vectors, distance_upper_bound=chord_limit)

    keep = np.isfinite(d)
    if not np.any(keep):
        empty_int = np.empty(0, dtype=np.int64)
        empty_float = np.empty(0, dtype=np.float64)
        return Candidates(station_idx=empty_int, mile_marker=empty_float, offset_miles=empty_float)

    matched_indices = np.where(keep)[0].astype(np.int64)
    offsets = chord_to_miles(d[keep])
    mile_markers = samples.mile[j[keep]]

    # Stable deterministic sort by (mile_marker, offset_miles, station_idx)
    sort_order = np.lexsort((matched_indices, offsets, mile_markers))

    return Candidates(
        station_idx=matched_indices[sort_order],
        mile_marker=mile_markers[sort_order],
        offset_miles=offsets[sort_order],
    )


def widening_schedule(schedule_str: str | None = None) -> list[float]:
    """Parse comma-separated corridor buffer schedule string into list of float miles.

    Args:
        schedule_str: Comma-delimited radii string (e.g. "10,25,50" or None for default).

    Returns:
        List of strictly positive buffer radii in miles.
    """
    raw = schedule_str if schedule_str is not None else "10,25,50"
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError(f"Corridor schedule cannot be empty: '{schedule_str}'")

    schedule: list[float] = []
    for item in parts:
        val = float(item)
        if val <= 0:
            raise ValueError(f"Corridor step must be > 0: '{val}'")
        schedule.append(val)

    return schedule
