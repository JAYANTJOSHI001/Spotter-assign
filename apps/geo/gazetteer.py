from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

CENSUS_GAZETTEER_BASE_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"

CENSUS_SUFFIXES = (
    " charter township",
    " township",
    " municipality",
    " borough",
    " village",
    " city",
    " town",
    " cdp",
)


def normalize_place(name: str, is_census: bool = False) -> str:
    """Normalize place or city name for deterministic geospatial lookup.

    Args:
        name: City or place name (e.g. 'St. Louis', 'Ft. Wayne', 'O'Fallon').
        is_census: If True, strip Census-specific suffixes like 'city', 'town', 'CDP'.

    Returns:
        Normalized lowercase ASCII place name without accents or punctuation.
    """
    if not name:
        return ""

    # Normalize unicode and strip accents
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("utf-8").lower()

    # Expand ampersand
    s = s.replace("&", " and ")

    # Expand standard abbreviations before removing dots
    s = re.sub(r"\bst\b|\bst\.", "saint", s)
    s = re.sub(r"\bft\b|\bft\.", "fort", s)
    s = re.sub(r"\bmt\b|\bmt\.", "mount", s)

    # Strip census suffixes if census name
    if is_census:
        # Also remove prefix like "township of ", "charter township of "
        if s.startswith("charter township of "):
            s = s[len("charter township of ") :]
        elif s.startswith("township of "):
            s = s[len("township of ") :]

        for suffix in CENSUS_SUFFIXES:
            if s.endswith(suffix):
                s = s[: -len(suffix)]
                break

    # Remove apostrophes without adding space (O'Fallon -> ofallon)
    s = s.replace("'", "")

    # Replace hyphens and other punctuation with spaces
    s = re.sub(r"[^a-z0-9]+", " ", s)

    # Collapse multiple whitespace
    return re.sub(r"\s+", " ", s).strip()


def discover_latest_gazetteer_year() -> int:
    """Discover the newest available gazetteer year from census.gov."""
    req = urllib.request.Request(
        CENSUS_GAZETTEER_BASE_URL,
        headers={"User-Agent": "fuelroute-assessment/1.0 (contact: assessment@example.com)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8")

    matches = re.findall(r'href="(\d{4})_Gazetteer/"', html)
    if not matches:
        raise RuntimeError("Could not find any Gazetteer year directories on census.gov")

    years = sorted(int(y) for y in set(matches))
    return years[-1]


def download_census_gazetteer(output_dir: Path) -> tuple[Path, Path]:
    """Download the latest place and county-subdivision gazetteer zip files.

    Writes SHA-256 checksums to CHECKSUMS.txt.
    Returns (place_zip_path, cousub_zip_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_year = discover_latest_gazetteer_year()
    year_url = f"{CENSUS_GAZETTEER_BASE_URL}{latest_year}_Gazetteer/"

    place_filename = f"{latest_year}_Gaz_place_national.zip"
    cousub_filename = f"{latest_year}_Gaz_cousubs_national.zip"

    place_path = output_dir / place_filename
    cousub_path = output_dir / cousub_filename
    checksums_path = output_dir / "CHECKSUMS.txt"

    sha256_records: dict[str, str] = {}

    for filename, target_path in [(place_filename, place_path), (cousub_filename, cousub_path)]:
        if not target_path.exists():
            file_url = f"{year_url}{filename}"
            req = urllib.request.Request(
                file_url,
                headers={
                    "User-Agent": "fuelroute-assessment/1.0 (contact: assessment@example.com)"
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as f_out:
                f_out.write(resp.read())

        # Compute SHA-256
        h = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        sha256_records[filename] = h.hexdigest()

    with open(checksums_path, "w", encoding="utf-8") as f:
        for fname, digest in sorted(sha256_records.items()):
            f.write(f"{digest}  {fname}\n")

    return place_path, cousub_path


def load_gazetteer(
    paths: list[Path] | tuple[Path, ...],
) -> dict[tuple[str, str], tuple[float, float]]:
    """Load and parse Gazetteer zip files into a state-keyed lookup dictionary.

    If duplicate (state, normalized_name) keys exist within a state, keeps the
    entry with the largest land area (ALAND).

    Args:
        paths: Sequence of Paths to gazetteer zip files.

    Returns:
        Dictionary mapping (USPS_STATE, normalized_name) -> (lat, lng).
    """
    # Track (lat, lng, aland) to resolve ties by largest land area
    lookup: dict[tuple[str, str], tuple[float, float, int]] = {}
    ambiguities = 0

    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"Gazetteer file not found: {p}")

        with zipfile.ZipFile(p) as zf:
            txt_files = [name for name in zf.namelist() if name.endswith(".txt")]
            if not txt_files:
                continue

            for txt_name in txt_files:
                with zf.open(txt_name) as f:
                    wrapper = io.TextIOWrapper(f, encoding="latin-1")
                    first_line = wrapper.readline()
                    if not first_line:
                        continue

                    delimiter = "|" if "|" in first_line else "\t"
                    wrapper.seek(0)
                    reader = csv.reader(wrapper, delimiter=delimiter)

                    try:
                        raw_headers = next(reader)
                    except StopIteration:
                        continue

                    headers = [h.strip() for h in raw_headers]
                    col_map = {name: idx for idx, name in enumerate(headers)}

                    usps_col = col_map.get("USPS")
                    name_col = col_map.get("NAME")
                    lat_col = col_map.get("INTPTLAT")
                    lng_col = col_map.get("INTPTLONG")
                    aland_col = col_map.get("ALAND")

                    if None in (usps_col, name_col, lat_col, lng_col):
                        continue

                    for row in reader:
                        if len(row) <= max(usps_col, name_col, lat_col, lng_col):
                            continue
                        state = row[usps_col].strip().upper()
                        raw_name = row[name_col].strip()
                        norm_name = normalize_place(raw_name, is_census=True)
                        if not norm_name or not state:
                            continue

                        try:
                            lat = float(row[lat_col].strip())
                            lng = float(row[lng_col].strip())
                            aland = int(row[aland_col].strip()) if aland_col is not None else 0
                        except ValueError:
                            continue

                        key = (state, norm_name)
                        if key in lookup:
                            ambiguities += 1
                            if aland > lookup[key][2]:
                                lookup[key] = (lat, lng, aland)
                        else:
                            lookup[key] = (lat, lng, aland)

    logger.info(
        "Gazetteer loaded: %d unique places (%d ambiguities resolved)", len(lookup), ambiguities
    )
    return {k: (v[0], v[1]) for k, v in lookup.items()}
