"""Record real OSRM route responses once for offline tests and predictable demos.

Usage:
    python scripts/record_fixtures.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = BASE_DIR / "tests" / "fixtures" / "routes"
OSRM_BASE_URL = "https://router.project-osrm.org"

ROUTES = [
    {
        "alias": "chicago_il_to_dallas_tx",
        "start": {"name": "Chicago, IL", "lat": 41.8781, "lng": -87.6298},
        "finish": {"name": "Dallas, TX", "lat": 32.7767, "lng": -96.7970},
    },
    {
        "alias": "new_york_ny_to_los_angeles_ca",
        "start": {"name": "New York, NY", "lat": 40.7128, "lng": -74.0060},
        "finish": {"name": "Los Angeles, CA", "lat": 34.0522, "lng": -118.2437},
    },
    {
        "alias": "chicago_il_to_st_louis_mo",
        "start": {"name": "Chicago, IL", "lat": 41.8781, "lng": -87.6298},
        "finish": {"name": "St. Louis, MO", "lat": 38.6270, "lng": -90.1994},
    },
    {
        "alias": "seattle_wa_to_miami_fl",
        "start": {"name": "Seattle, WA", "lat": 47.6062, "lng": -122.3321},
        "finish": {"name": "Miami, FL", "lat": 25.7617, "lng": -80.1918},
    },
    {
        "alias": "new_york_ny_to_honolulu_hi",
        "start": {"name": "New York, NY", "lat": 40.7128, "lng": -74.0060},
        "finish": {"name": "Honolulu, HI", "lat": 21.3069, "lng": -157.8583},
    },
]


def record_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(30.0, connect=5.0)

    with httpx.Client(timeout=timeout) as client:
        for r in ROUTES:
            start = r["start"]
            finish = r["finish"]
            alias = r["alias"]

            url = f"{OSRM_BASE_URL}/route/v1/driving/{start['lng']:.6f},{start['lat']:.6f};{finish['lng']:.6f},{finish['lat']:.6f}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
                "alternatives": "false",
            }
            print(f"Recording {alias} ({start['name']} -> {finish['name']})...")
            try:
                resp = client.get(url, params=params)
                data = resp.json()
            except Exception as exc:
                print(f"  Error fetching {alias}: {exc}")
                raise

            out_path = FIXTURES_DIR / f"{alias}.json"
            content = json.dumps(data, separators=(",", ":"))
            size_kb = len(content.encode("utf-8")) / 1024
            if size_kb > 1500:
                gz_path = FIXTURES_DIR / f"{alias}.json.gz"
                with gzip.open(gz_path, "wt", encoding="utf-8") as f:
                    f.write(content)
                if out_path.exists():
                    out_path.unlink()
                print(f"  Saved gzipped {gz_path.name}: {len(gz_path.read_bytes()) / 1024:.1f} KB")
            else:
                out_path.write_text(content, encoding="utf-8")
                print(f"  Saved {out_path.name}: {size_kb:.1f} KB")

            # Also create coordinate-slug copy
            from apps.providers.base import LatLng
            from apps.providers.fixture import coordinate_slug

            slug = coordinate_slug(
                LatLng(lat=start["lat"], lng=start["lng"]),
                LatLng(lat=finish["lat"], lng=finish["lng"]),
            )
            if size_kb > 1500:
                (FIXTURES_DIR / f"{slug}.json.gz").write_bytes(
                    (FIXTURES_DIR / f"{alias}.json.gz").read_bytes()
                )
            else:
                (FIXTURES_DIR / f"{slug}.json").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    record_fixtures()
