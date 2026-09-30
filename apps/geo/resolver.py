"""Location resolution: coordinates, offline gazetteer index, and Nominatim fallback."""

from __future__ import annotations

import csv
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.geo.bounds import in_supported_us
from apps.geo.gazetteer import load_gazetteer, normalize_place
from apps.providers.budget import CallBudget
from apps.providers.errors import LocationNotFound, OutsideUSA
from apps.providers.nominatim import NominatimGeocoder

logger = logging.getLogger(__name__)

US_STATES: dict[str, str] = {
    "AL": "AL",
    "AK": "AK",
    "AZ": "AZ",
    "AR": "AR",
    "CA": "CA",
    "CO": "CO",
    "CT": "CT",
    "DE": "DE",
    "FL": "FL",
    "GA": "GA",
    "HI": "HI",
    "ID": "ID",
    "IL": "IL",
    "IN": "IN",
    "IA": "IA",
    "KS": "KS",
    "KY": "KY",
    "LA": "LA",
    "ME": "ME",
    "MD": "MD",
    "MA": "MA",
    "MI": "MI",
    "MN": "MN",
    "MS": "MS",
    "MO": "MO",
    "MT": "MT",
    "NE": "NE",
    "NV": "NV",
    "NH": "NH",
    "NJ": "NJ",
    "NM": "NM",
    "NY": "NY",
    "NC": "NC",
    "ND": "ND",
    "OH": "OH",
    "OK": "OK",
    "OR": "OR",
    "PA": "PA",
    "RI": "RI",
    "SC": "SC",
    "SD": "SD",
    "TN": "TN",
    "TX": "TX",
    "UT": "UT",
    "VT": "VT",
    "VA": "VA",
    "WA": "WA",
    "WV": "WV",
    "WI": "WI",
    "WY": "WY",
    "DC": "DC",
    # Full names uppercase
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSOURI": "MO",
    "MISSISSIPPI": "MS",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC",
}


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """Resolved geographic location with coordinate and provenance."""

    lat: float
    lng: float
    label: str
    source: str  # "coordinates" | "gazetteer" | "nominatim"
    query: str
    warning: str | None = None


_index_lock = threading.Lock()
_gazetteer_index: dict[tuple[str, str], tuple[float, float]] | None = None


def get_gazetteer_index() -> dict[tuple[str, str], tuple[float, float]]:
    """Lazy-load in-memory gazetteer index from clean stations and census data."""
    global _gazetteer_index
    if _gazetteer_index is not None:
        return _gazetteer_index

    with _index_lock:
        if _gazetteer_index is not None:
            return _gazetteer_index

        index: dict[tuple[str, str], tuple[float, float]] = {}
        base_dir = Path(__file__).resolve().parent.parent.parent

        # 1. Load from committed stations_geocoded.csv
        geocoded_csv = base_dir / "data" / "stations_geocoded.csv"
        if geocoded_csv.exists():
            with open(geocoded_csv, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    st = row.get("state", "").strip().upper()
                    city = row.get("city", "").strip()
                    try:
                        lat = float(row["lat"])
                        lng = float(row["lng"])
                    except (KeyError, ValueError):
                        continue
                    if st and city:
                        norm = normalize_place(city)
                        if (st, norm) not in index:
                            index[(st, norm)] = (lat, lng)

        # 2. Augment from Census place gazetteer zip if available
        gazetteer_dir = base_dir / "data" / "gazetteer"
        place_zips = list(gazetteer_dir.glob("*_place_national.zip"))
        if place_zips:
            census_places = load_gazetteer(place_zips)
            for key, coords in census_places.items():
                if key not in index:
                    index[key] = coords

        _gazetteer_index = index
        logger.info("Loaded offline gazetteer index with %d entries", len(_gazetteer_index))
        return _gazetteer_index


def reset_gazetteer_index() -> None:
    """Reset the gazetteer index cache (used in tests)."""
    global _gazetteer_index
    with _index_lock:
        _gazetteer_index = None


def _try_parse_coordinates(value: Any) -> tuple[float, float, str | None] | None:
    """Check if value is a coordinate dict or 'lat,lng' string."""
    lat: float | None = None
    lng: float | None = None

    if isinstance(value, dict):
        lat_val = value.get("lat", value.get("latitude"))
        lng_val = value.get("lng", value.get("lon", value.get("longitude")))
        if lat_val is not None and lng_val is not None:
            try:
                lat = float(lat_val)
                lng = float(lng_val)
            except (ValueError, TypeError):
                return None

    elif isinstance(value, str):
        val = value.strip()
        coord_pattern = r"^[-+]?\d*\.?\d+\s*,\s*[-+]?\d*\.?\d+$"
        if re.match(coord_pattern, val):
            parts = val.split(",")
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
            except (ValueError, TypeError):
                return None

    if lat is None or lng is None:
        return None

    warning = None
    # Check if coordinates are swapped:
    # 1. |lat| > 90 and |lng| <= 90 (impossible latitude, valid longitude)
    # 2. lat < 0 and 20.0 <= lng <= 55.0 and -130.0 <= lat <= -60.0 (clearly swapped US lon,lat)
    if (abs(lat) > 90.0 and abs(lng) <= 90.0) or (
        lat < 0.0 and 20.0 <= lng <= 55.0 and -130.0 <= lat <= -60.0
    ):
        lat, lng = lng, lat
        warning = f"Swapped coordinates detected: inverted to ({lat:.4f}, {lng:.4f})"

    return lat, lng, warning


CANADIAN_PROVINCES: set[str] = {
    "AB",
    "BC",
    "MB",
    "NB",
    "NL",
    "NS",
    "NT",
    "NU",
    "ON",
    "PE",
    "QC",
    "SK",
    "YT",
    "ALBERTA",
    "BRITISH COLUMBIA",
    "MANITOBA",
    "NEW BRUNSWICK",
    "NEWFOUNDLAND",
    "NOVA SCOTIA",
    "NORTHWEST TERRITORIES",
    "NUNAVUT",
    "ONTARIO",
    "PRINCE EDWARD ISLAND",
    "QUEBEC",
    "SASKATCHEWAN",
    "YUKON",
}

NON_US_CITIES: set[str] = {
    "TORONTO",
    "VANCOUVER",
    "MONTREAL",
    "OTTAWA",
    "CALGARY",
    "EDMONTON",
    "QUEBEC CITY",
    "WINNIPEG",
    "HALIFAX",
    "VICTORIA",
    "TIJUANA",
    "MEXICO CITY",
    "JUAREZ",
    "MONTERREY",
    "GUADALAJARA",
    "CANCUN",
}


def _try_parse_city_state(text: str) -> tuple[str, str] | None:
    """Extract (city, state_abbr) from 'City, ST', 'City ST', or 'City, State Name'."""
    val = text.strip()
    if not val:
        return None

    # Check for comma-separated or space-separated state
    match = re.match(r"^([^,]+?)(?:,\s*|\s+)([A-Za-z]{2}|[A-Za-z\s]{3,})$", val)
    if not match:
        return None

    city_raw = match.group(1).strip()
    state_raw = match.group(2).strip().upper()

    if state_raw in CANADIAN_PROVINCES:
        raise OutsideUSA(f"Location '{text}' is in Canada and outside supported contiguous US")

    if state_raw in US_STATES:
        return city_raw, US_STATES[state_raw]

    return None


def resolve_location(value: Any, budget: CallBudget) -> ResolvedLocation:
    """Resolve an input location to coordinates.

    Order:
      1. Coordinates (dict or string) -> source="coordinates", 0 external calls.
      2. Offline Gazetteer ("City, ST" / "City, State") -> source="gazetteer", 0 external calls.
      3. Free-text address -> Nominatim, source="nominatim", 1 external call.

    Raises:
      LocationNotFound: If coordinates are invalid or location cannot be geocoded.
      OutsideUSA: If resolved coordinates are outside supported contiguous US bounds.
    """
    query_str = str(value).strip() if not isinstance(value, dict) else str(value)

    # 1. Coordinate input
    coords = _try_parse_coordinates(value)
    if coords is not None:
        lat, lng, warning = coords
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            raise LocationNotFound(f"Invalid coordinate range: lat={lat}, lng={lng}")

        if not in_supported_us(lat, lng):
            raise OutsideUSA(
                f"Coordinates ({lat:.4f}, {lng:.4f}) are outside supported contiguous US"
            )

        return ResolvedLocation(
            lat=lat,
            lng=lng,
            label=f"{lat:.4f}, {lng:.4f}",
            source="coordinates",
            query=query_str,
            warning=warning,
        )

    if not isinstance(value, str) or not value.strip():
        raise LocationNotFound(f"Invalid location input: {value}")

    text_input = value.strip()
    upper_input = text_input.upper()

    # Reject explicit non-US locations before spending external calls
    if re.search(r"\b(CANADA|MEXICO)\b", upper_input) or upper_input in NON_US_CITIES:
        raise OutsideUSA(f"Location '{text_input}' is outside supported contiguous US")

    # 2. Offline Gazetteer input ("City, ST" or "City, State Name")
    parsed_cs = _try_parse_city_state(text_input)
    if parsed_cs is not None:
        city_raw, state_abbr = parsed_cs
        gazetteer = get_gazetteer_index()
        norm_city = normalize_place(city_raw)

        if (state_abbr, norm_city) in gazetteer:
            lat, lng = gazetteer[(state_abbr, norm_city)]
            if not in_supported_us(lat, lng):
                raise OutsideUSA(
                    f"Location '{city_raw}, {state_abbr}' ({lat:.4f}, {lng:.4f}) is outside contiguous US"
                )
            return ResolvedLocation(
                lat=lat,
                lng=lng,
                label=f"{city_raw.title()}, {state_abbr}",
                source="gazetteer",
                query=query_str,
            )

    # 3. Fallback to Nominatim for free-text or unindexed locations
    geocoder = NominatimGeocoder()
    result = geocoder.geocode(text_input, budget)

    if not in_supported_us(result.lat, result.lng):
        raise OutsideUSA(
            f"Location '{result.label}' ({result.lat:.4f}, {result.lng:.4f}) is outside supported contiguous US"
        )

    return ResolvedLocation(
        lat=result.lat,
        lng=result.lng,
        label=result.label,
        source="nominatim",
        query=query_str,
    )
