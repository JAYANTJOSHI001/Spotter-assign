"""Geodesic distance primitives and spherical coordinate transformations.

All coordinates are in decimal degrees.
All surface distances are in statute miles.
Earth radius constant: WGS-84 mean radius in miles (3958.7613 mi).
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_MILES: float = 3958.7613


def haversine_miles(
    lat1: float | np.ndarray,
    lng1: float | np.ndarray,
    lat2: float | np.ndarray,
    lng2: float | np.ndarray,
) -> float | np.ndarray:
    """Compute great-circle distance between point pairs using the Haversine formula.

    Args:
        lat1: Latitude of start point(s) in decimal degrees.
        lng1: Longitude of start point(s) in decimal degrees.
        lat2: Latitude of end point(s) in decimal degrees.
        lng2: Longitude of end point(s) in decimal degrees.

    Returns:
        Great-circle distance in statute miles. Scalar if all inputs are scalar,
        otherwise NumPy array matching broadcasted input shape.
    """
    lat1_rad = np.radians(lat1)
    lng1_rad = np.radians(lng1)
    lat2_rad = np.radians(lat2)
    lng2_rad = np.radians(lng2)

    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arcsin(np.sqrt(a))
    return EARTH_RADIUS_MILES * c


def to_unit_vectors(
    lat: float | np.ndarray,
    lng: float | np.ndarray,
) -> np.ndarray:
    """Convert geodetic coordinates in degrees to 3D Cartesian coordinates on the unit sphere.

    Args:
        lat: Latitude(s) in decimal degrees.
        lng: Longitude(s) in decimal degrees.

    Returns:
        NumPy array of shape (N, 3) or (3,) with unit Euclidean norm (norm == 1.0).
    """
    lat_rad = np.radians(lat)
    lng_rad = np.radians(lng)

    x = np.cos(lat_rad) * np.cos(lng_rad)
    y = np.cos(lat_rad) * np.sin(lng_rad)
    z = np.sin(lat_rad)

    if np.isscalar(lat) and np.isscalar(lng):
        return np.array([x, y, z], dtype=np.float64)

    return np.column_stack((x, y, z)).astype(np.float64)


def miles_to_chord(miles: float | np.ndarray) -> float | np.ndarray:
    """Convert surface distance along the sphere (in statute miles) to 3D Euclidean chord distance.

    Formula: chord = 2 * sin(theta / 2), where theta = miles / R.

    Args:
        miles: Distance along the sphere in statute miles.

    Returns:
        Straight-line Euclidean chord distance on the unit sphere.
    """
    theta = miles / EARTH_RADIUS_MILES
    return 2.0 * np.sin(theta / 2.0)


def chord_to_miles(chord: float | np.ndarray) -> float | np.ndarray:
    """Convert 3D Euclidean chord distance on the unit sphere back to surface statute miles.

    Formula: theta = 2 * arcsin(chord / 2), miles = theta * R.

    Args:
        chord: Straight-line Euclidean chord distance on the unit sphere.

    Returns:
        Surface distance in statute miles.
    """
    half_chord = np.clip(chord / 2.0, 0.0, 1.0)
    theta = 2.0 * np.arcsin(half_chord)
    return EARTH_RADIUS_MILES * theta
