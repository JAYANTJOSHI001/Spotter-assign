from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from apps.stations.pricing import resolve_price

US_STATES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}

CANADIAN_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK", "NT", "YT", "NU"}


def collapse_whitespace(text: Any) -> str:
    if text is None or pd.isna(text):
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def pick_canonical_name(names: list[str]) -> str:
    """Select longest non-empty name; alphabetical tie-break."""
    valid_names = [n for n in names if n]
    if not valid_names:
        return ""
    # Sort key: (-len(n), n) -> longest first, then alphabetical
    return min(valid_names, key=lambda n: (-len(n), n))


def prepare_stations_dataframe(
    raw_df: pd.DataFrame,
    policy: str = "min",
    assert_audit: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean and aggregate raw fuel price observations into unique stations."""
    stats: dict[str, Any] = {
        "raw_rows": len(raw_df),
        "canadian_rows_dropped": 0,
        "exact_duplicates_dropped": 0,
        "excluded_price_rows": 0,
        "clean_stations": 0,
        "price_outliers": 0,
    }

    # Normalize text columns
    df = raw_df.copy()
    for col in [
        "OPIS Truckstop ID",
        "Truckstop Name",
        "Address",
        "City",
        "State",
        "Rack ID",
        "Retail Price",
    ]:
        if col in df.columns:
            df[col] = df[col].apply(collapse_whitespace)

    df["State"] = df["State"].str.upper()

    # Drop Canadian / Non-US rows
    canadian_mask = df["State"].isin(CANADIAN_PROVINCES) | (~df["State"].isin(US_STATES))
    stats["canadian_rows_dropped"] = int(canadian_mask.sum())
    if assert_audit:
        assert stats["canadian_rows_dropped"] == 620, (
            f"Expected 620 Canadian rows, got {stats['canadian_rows_dropped']}"
        )

    df_us = df[~canadian_mask].copy()

    # Drop exact duplicate rows
    dup_mask = df_us.duplicated()
    stats["exact_duplicates_dropped"] = int(dup_mask.sum())
    if assert_audit:
        assert stats["exact_duplicates_dropped"] == 26, (
            f"Expected 26 duplicate rows, got {stats['exact_duplicates_dropped']}"
        )

    df_us = df_us[~dup_mask].copy()

    # Cast IDs and Prices
    df_us["opis_id"] = df_us["OPIS Truckstop ID"].astype(int)
    df_us["rack_id"] = df_us["Rack ID"].astype(int)
    df_us["price_dec"] = df_us["Retail Price"].apply(lambda p: Decimal(str(p)))

    # Filter out prices outside [1.5, 10.0]
    valid_price_mask = (df_us["price_dec"] >= Decimal("1.5")) & (
        df_us["price_dec"] <= Decimal("10.0")
    )
    excluded_prices = df_us[~valid_price_mask]
    stats["excluded_price_rows"] = len(excluded_prices)
    df_us = df_us[valid_price_mask].copy()

    # Group by opis_id
    grouped_records = []
    for opis_id, group in df_us.groupby("opis_id"):
        # Verify address, city, state, rack_id are constant per ID
        if assert_audit:
            assert group["Address"].nunique() == 1, f"Multiple addresses for ID {opis_id}"
            assert group["City"].nunique() == 1, f"Multiple cities for ID {opis_id}"
            assert group["State"].nunique() == 1, f"Multiple states for ID {opis_id}"
            assert group["rack_id"].nunique() == 1, f"Multiple rack IDs for ID {opis_id}"

        prices = list(group["price_dec"])
        resolved = resolve_price(prices, policy=policy)
        canonical_name = pick_canonical_name(list(group["Truckstop Name"]))

        grouped_records.append(
            {
                "opis_id": opis_id,
                "name": canonical_name,
                "address": group["Address"].iloc[0],
                "city": group["City"].iloc[0],
                "state": group["State"].iloc[0],
                "rack_id": group["rack_id"].iloc[0],
                "price": resolved,
                "price_min": min(prices),
                "price_max": max(prices),
                "n_price_rows": len(prices),
            }
        )

    clean_df = pd.DataFrame(grouped_records)
    stats["clean_stations"] = len(clean_df)

    if assert_audit:
        assert stats["clean_stations"] == 6626, (
            f"Expected 6,626 clean stations, got {stats['clean_stations']}"
        )

    # Detect price outliers (> mean + 4*sigma)
    if not clean_df.empty:
        prices_float = clean_df["price"].astype(float).values
        mean_price = float(np.mean(prices_float))
        std_price = float(np.std(prices_float))
        outlier_threshold = mean_price + 4.0 * std_price

        clean_df["price_outlier"] = clean_df["price"].apply(lambda p: float(p) > outlier_threshold)
        stats["price_outliers"] = int(clean_df["price_outlier"].sum())
        stats["mean_price"] = mean_price
        stats["std_price"] = std_price
        stats["outlier_threshold"] = outlier_threshold
    else:
        clean_df["price_outlier"] = False

    return clean_df, stats
