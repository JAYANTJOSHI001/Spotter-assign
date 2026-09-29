import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

US_BOUNDS = {
    "lat_min": 24.3,
    "lat_max": 49.5,
    "lng_min": -125.1,
    "lng_max": -66.8,
}

CANADIAN_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK", "NT", "YT", "NU"}


def test_geocoded_stations_artifact():
    artifact_path = Path("data/stations_geocoded.csv")
    report_path = Path("data/geocode_report.md")

    if not artifact_path.exists():
        pytest.skip("Artifact stations_geocoded.csv not yet generated")

    df = pd.read_csv(artifact_path)

    # 1. No null values anywhere in the dataframe
    assert df.notnull().all().all(), (
        f"Null values detected in {artifact_path}:\n{df.isnull().sum()}"
    )

    # 2. Coordinates strictly inside contiguous US bounding box
    assert (df["lat"] >= US_BOUNDS["lat_min"]).all(), "Found lat < 24.3"
    assert (df["lat"] <= US_BOUNDS["lat_max"]).all(), "Found lat > 49.5"
    assert (df["lng"] >= US_BOUNDS["lng_min"]).all(), "Found lng < -125.1"
    assert (df["lng"] <= US_BOUNDS["lng_max"]).all(), "Found lng > -66.8"

    # 3. OPIS ID is strictly unique
    assert df["opis_id"].is_unique, "Duplicate opis_id found in geocoded artifact"

    # 4. Zero Canadian states / provinces present
    assert not df["state"].isin(CANADIAN_PROVINCES).any(), (
        "Found Canadian state in geocoded artifact"
    )

    # 5. Price strictly in range [1.5, 10.0]
    prices = df["price"].apply(lambda p: Decimal(str(p)))
    assert (prices >= Decimal("1.5")).all(), "Found price < 1.5"
    assert (prices <= Decimal("10.0")).all(), "Found price > 10.0"

    # 6. Row count matches report
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        match = re.search(r"\*\*Successfully Geocoded\*\*:\s*([\d,]+)", content)
        if match:
            expected_count = int(match.group(1).replace(",", ""))
            assert len(df) == expected_count, (
                f"Row count ({len(df)}) does not match report ({expected_count})"
            )
