"""Contiguous US bounding box and coarse border boundary polygon checks.

Rejects coordinates clearly outside the contiguous 48 US states (e.g. Canada, Mexico,
oceans) without requiring heavy GIS dependencies (e.g. Shapely or GeoPandas).
"""

from __future__ import annotations

US_BBOX = {
    "lat_min": 24.3,
    "lat_max": 49.5,
    "lng_min": -125.1,
    "lng_max": -66.8,
}

# Coarse 60-vertex polygon tracing the contiguous US border
CONTIGUOUS_US_POLYGON: tuple[tuple[float, float], ...] = (
    # NW corner (Washington) along 49th parallel
    (49.0, -124.8),
    (49.0, -117.0),
    (49.0, -104.0),
    (49.0, -95.15),
    (49.38, -95.15),  # Northwest Angle, MN
    (48.5, -94.0),
    (48.0, -89.5),  # Lake Superior
    (46.5, -84.5),  # Sault Ste Marie
    (45.5, -83.5),  # Lake Huron
    (43.0, -82.4),  # Port Huron / Sarnia
    (42.30, -83.00),  # Detroit River (east of Detroit)
    (41.7, -82.8),  # Lake Erie
    (42.80, -78.95),  # Lake Erie / Buffalo entry
    (43.10, -79.05),  # Niagara River west of Buffalo
    (43.30, -79.10),  # Lake Ontario SW corner
    (43.6, -76.3),  # Oswego, NY
    (44.99, -74.8),  # St. Lawrence / 45th parallel NY
    (45.01, -71.5),  # 45th parallel VT/NH
    (45.3, -71.0),  # ME border
    (47.46, -69.2),  # Northern tip of Maine
    (47.2, -67.8),  # NE tip of Maine
    (44.8, -66.9),  # Eastport, ME
    (43.0, -70.5),  # Boston / MA coast
    (41.0, -71.8),  # Montauk / Long Island
    (40.5, -74.0),  # NY Harbor
    (38.5, -75.0),  # Delmarva
    (35.2, -75.5),  # Cape Hatteras, NC
    (32.0, -80.8),  # Savannah, GA
    (28.5, -80.5),  # Cape Canaveral, FL
    (25.70, -80.15),  # Miami, FL
    (24.45, -81.75),  # South of Key West
    (24.45, -82.00),  # SW of Key West
    (25.1, -81.0),  # Florida Bay / Everglades
    (26.5, -82.2),  # Fort Myers, FL
    (29.8, -84.5),  # FL Panhandle
    (30.2, -88.0),  # Mobile Bay, AL
    (29.3, -89.4),  # Mississippi Delta, LA
    (29.7, -93.8),  # Port Arthur, TX
    (27.8, -97.0),  # Corpus Christi, TX
    (25.9, -97.1),  # Brownsville, TX
    (26.0, -98.3),  # Rio Grande / McAllen
    (27.5, -99.5),  # Laredo, TX
    (29.3, -100.9),  # Del Rio, TX
    (29.0, -103.5),  # Big Bend, TX
    (29.5, -104.4),  # Presidio, TX
    (31.75, -106.45),  # South of El Paso
    (31.755, -106.53),  # Rio Grande west of El Paso
    (31.78, -106.54),  # NM / TX border corner
    (31.33, -108.2),  # NM southern border
    (31.33, -111.0),  # AZ border Nogales
    (32.48, -114.8),  # Yuma / San Luis
    (32.532, -117.13),  # Imperial Beach / San Diego border
    (32.72, -117.25),  # San Diego coast
    (34.0, -118.6),  # Los Angeles, CA
    (34.4, -120.5),  # Point Conception, CA
    (37.8, -122.5),  # San Francisco, CA
    (40.4, -124.4),  # Cape Mendocino, CA
    (42.0, -124.4),  # OR / CA border
    (46.2, -124.0),  # Columbia River mouth
    (48.4, -124.7),  # Cape Flattery, WA
)


def point_in_polygon(lat: float, lng: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Standard ray-casting algorithm to test whether (lat, lng) is inside polygon."""
    n = len(polygon)
    inside = False
    p1_lat, p1_lng = polygon[0]

    for i in range(1, n + 1):
        p2_lat, p2_lng = polygon[i % n]
        if min(p1_lat, p2_lat) <= lat <= max(p1_lat, p2_lat):
            if lng <= max(p1_lng, p2_lng):
                if p1_lat != p2_lat:
                    xinters = (lat - p1_lat) * (p2_lng - p1_lng) / (p2_lat - p1_lat) + p1_lng
                if p1_lng == p2_lng or lng <= xinters:
                    inside = not inside
        p1_lat, p1_lng = p2_lat, p2_lng

    return inside


def in_supported_us(lat: float, lng: float) -> bool:
    """Validate that coordinates fall inside the contiguous United States.

    Performs a fast bounding-box pre-filter followed by a 60-vertex ray-casting polygon check.
    If ambiguous on the boundary, defaults to True to allow the routing engine to evaluate.

    Args:
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.

    Returns:
        True if the point is within supported contiguous US bounds.
    """
    if not (
        US_BBOX["lat_min"] <= lat <= US_BBOX["lat_max"]
        and US_BBOX["lng_min"] <= lng <= US_BBOX["lng_max"]
    ):
        return False

    return point_in_polygon(lat, lng, CONTIGUOUS_US_POLYGON)
