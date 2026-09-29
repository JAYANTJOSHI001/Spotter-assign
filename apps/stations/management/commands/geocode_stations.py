from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from rapidfuzz import fuzz, process

from apps.geo.gazetteer import (
    download_census_gazetteer,
    load_gazetteer,
    normalize_place,
)

logger = logging.getLogger(__name__)

US_BOUNDS = {
    "lat_min": 24.3,
    "lat_max": 49.5,
    "lng_min": -125.1,
    "lng_max": -66.8,
}


def in_us_bounds(lat: float, lng: float) -> bool:
    return (
        US_BOUNDS["lat_min"] <= lat <= US_BOUNDS["lat_max"]
        and US_BOUNDS["lng_min"] <= lng <= US_BOUNDS["lng_max"]
    )


class Command(BaseCommand):
    help = (
        "Geocode fuel stations using tiered matching (Gazetteer places, cousubs, fuzzy, Nominatim)."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            type=str,
            default="data/stations_clean.csv",
            help="Path to clean stations CSV",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="data/stations_geocoded.csv",
            help="Path to write geocoded stations CSV",
        )
        parser.add_argument(
            "--report",
            type=str,
            default="data/geocode_report.md",
            help="Path to write QA report",
        )
        parser.add_argument(
            "--cache",
            type=str,
            default="data/geocode_cache.json",
            help="Path to Nominatim geocode cache",
        )
        parser.add_argument(
            "--gazetteer-dir",
            type=str,
            default="data/gazetteer",
            help="Directory storing Census Gazetteer zip files",
        )
        parser.add_argument(
            "--no-network",
            action="store_true",
            help="Skip Tier 4 Nominatim network calls",
        )

    def handle(self, *args, **options) -> None:
        input_path = Path(options["input"])
        output_path = Path(options["output"])
        report_path = Path(options["report"])
        cache_path = Path(options["cache"])
        gazetteer_dir = Path(options["gazetteer_dir"])
        no_network = options["no_network"]

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        # 1. Load clean stations
        clean_df = pd.read_csv(input_path)
        total_stations = len(clean_df)
        self.stdout.write(f"Loaded {total_stations} clean stations from {input_path}")

        # 2. Ensure gazetteer files exist
        place_files = list(gazetteer_dir.glob("*_Gaz_place_national.zip"))
        cousub_files = list(gazetteer_dir.glob("*_Gaz_cousubs_national.zip"))

        if not place_files or not cousub_files:
            if no_network:
                raise CommandError(
                    f"Gazetteer zip files missing in {gazetteer_dir} and --no-network is specified"
                )
            self.stdout.write("Downloading Census Gazetteer files...")
            place_file, cousub_file = download_census_gazetteer(gazetteer_dir)
        else:
            place_file = place_files[0]
            cousub_file = cousub_files[0]

        # 3. Load gazetteer indexes
        self.stdout.write(f"Loading Gazetteer from {place_file.name} and {cousub_file.name}...")
        places = load_gazetteer([place_file])
        cousubs = load_gazetteer([cousub_file])
        self.stdout.write(f"Loaded {len(places)} places and {len(cousubs)} county-subdivisions")

        # Combine census by state for fuzzy matching
        census_by_state: dict[str, dict[str, tuple[float, float]]] = {}
        for (state, name), coords in {**cousubs, **places}.items():
            census_by_state.setdefault(state, {})[name] = coords

        # 4. Load Nominatim cache
        cache: dict[str, dict[str, float] | None] = {}
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cache = json.load(f)
                self.stdout.write(f"Loaded {len(cache)} cached Nominatim lookups")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not load cache: {e}"))

        from django.conf import settings

        user_agent = getattr(
            settings, "NOMINATIM_USER_AGENT", os.getenv("NOMINATIM_USER_AGENT", "")
        ).strip()
        if not no_network:
            if not user_agent or "you@example.com" in user_agent or "example.com" in user_agent:
                raise CommandError(
                    "NOMINATIM_USER_AGENT environment variable must be set to a valid custom identifier with real contact info (e.g. email) before making Nominatim requests."
                )

        # 5. Geocode Tier by Tier
        clean_df["norm_city"] = clean_df["city"].apply(normalize_place)
        clean_df["state"] = clean_df["state"].str.upper()

        tier_counts = {"place": 0, "cousub": 0, "fuzzy": 0, "nominatim": 0}
        fuzzy_matches: list[dict[str, Any]] = []
        nominatim_matches: list[dict[str, Any]] = []
        excluded_stations: list[dict[str, Any]] = []

        geocoded_records: list[dict[str, Any]] = []

        # Find unmatched unique pairs for fuzzy tier
        tier1_2_matches: dict[tuple[str, str], tuple[str, float, tuple[float, float]]] = {}
        for _, row in clean_df.iterrows():
            key = (row["state"], row["norm_city"])
            if key in tier1_2_matches:
                continue
            if key in places:
                tier1_2_matches[key] = ("place", 1.0, places[key])
            elif key in cousubs:
                tier1_2_matches[key] = ("cousub", 1.0, cousubs[key])

        # Pre-compute fuzzy matches for remaining unique pairs
        fuzzy_lookup: dict[tuple[str, str], tuple[str, float, tuple[float, float]]] = {}
        unmatched_unique_pairs = set()
        for _, row in clean_df.iterrows():
            key = (row["state"], row["norm_city"])
            if key not in tier1_2_matches:
                unmatched_unique_pairs.add(key)

        self.stdout.write(
            f"Evaluating {len(unmatched_unique_pairs)} unmatched places for Tier 3 fuzzy matching..."
        )
        for state, norm_city in unmatched_unique_pairs:
            state_candidates = list(census_by_state.get(state, {}).keys())
            if state_candidates:
                match = process.extractOne(
                    norm_city, state_candidates, scorer=fuzz.ratio, score_cutoff=94
                )
                if match:
                    best_name, score, _ = match
                    coords = census_by_state[state][best_name]
                    fuzzy_lookup[(state, norm_city)] = (best_name, round(score / 100.0, 4), coords)
                    fuzzy_matches.append(
                        {
                            "state": state,
                            "query_city": norm_city,
                            "matched_name": best_name,
                            "ratio": score,
                        }
                    )

        # Pre-compute Nominatim for still-unmatched unique pairs
        nominatim_lookup: dict[tuple[str, str], tuple[float, float] | None] = {}
        still_unmatched = []
        for _, row in clean_df.iterrows():
            key = (row["state"], row["norm_city"])
            if key not in tier1_2_matches and key not in fuzzy_lookup:
                still_unmatched.append((row["city"], row["state"], row["norm_city"]))

        unique_for_nominatim = {}
        for orig_city, state, norm_city in still_unmatched:
            cache_key = f"{orig_city}, {state}"
            unique_for_nominatim[cache_key] = (orig_city, state, norm_city)

        self.stdout.write(
            f"Still unmatched places for Tier 4 Nominatim: {len(unique_for_nominatim)} unique queries"
        )

        for cache_key, (orig_city, state, norm_city) in unique_for_nominatim.items():
            if cache_key in cache:
                coords_cached = cache[cache_key]
                if coords_cached:
                    nominatim_lookup[(state, norm_city)] = (
                        coords_cached["lat"],
                        coords_cached["lon"],
                    )
                else:
                    nominatim_lookup[(state, norm_city)] = None
                continue

            if no_network:
                nominatim_lookup[(state, norm_city)] = None
                continue

            # Query Nominatim
            query_params = {
                "format": "json",
                "city": orig_city,
                "state": state,
                "country": "USA",
                "countrycodes": "us",
                "limit": "1",
            }
            url = (
                f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode(query_params)}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})

            try:
                time.sleep(1.0)  # Nominatim 1 req/s usage policy
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data and len(data) > 0:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        cache[cache_key] = {"lat": lat, "lon": lon}
                        nominatim_lookup[(state, norm_city)] = (lat, lon)
                        nominatim_matches.append(
                            {
                                "city": orig_city,
                                "state": state,
                                "lat": lat,
                                "lng": lon,
                            }
                        )
                    else:
                        cache[cache_key] = None
                        nominatim_lookup[(state, norm_city)] = None
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Nominatim error for '{cache_key}': {e}"))
                cache[cache_key] = None
                nominatim_lookup[(state, norm_city)] = None

            # Persist cache after every query
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, sort_keys=True)

        # 6. Apply geocoding to all stations and validate bounds
        for _, row in clean_df.iterrows():
            key = (row["state"], row["norm_city"])
            method = None
            confidence = 0.0
            coords = None

            if key in tier1_2_matches:
                method, confidence, coords = tier1_2_matches[key]
            elif key in fuzzy_lookup:
                matched_name, confidence, coords = fuzzy_lookup[key]
                method = "fuzzy"
            elif key in nominatim_lookup and nominatim_lookup[key] is not None:
                coords = nominatim_lookup[key]
                method = "nominatim"
                confidence = 0.8

            if coords is not None and in_us_bounds(coords[0], coords[1]):
                tier_counts[method] += 1
                geocoded_records.append(
                    {
                        "opis_id": int(row["opis_id"]),
                        "name": row["name"],
                        "address": row["address"],
                        "city": row["city"],
                        "state": row["state"],
                        "rack_id": int(row["rack_id"]),
                        "price": row["price"],
                        "price_min": row["price_min"],
                        "price_max": row["price_max"],
                        "n_price_rows": int(row["n_price_rows"]),
                        "lat": coords[0],
                        "lng": coords[1],
                        "geocode_method": method,
                        "geocode_confidence": confidence,
                        "price_outlier": bool(row["price_outlier"]),
                    }
                )
            else:
                reason = "Out of US bounds" if coords is not None else "Location not found"
                excluded_stations.append(
                    {
                        "opis_id": int(row["opis_id"]),
                        "name": row["name"],
                        "address": row["address"],
                        "city": row["city"],
                        "state": row["state"],
                        "price": row["price"],
                        "reason": reason,
                    }
                )

        geocoded_df = pd.DataFrame(geocoded_records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        geocoded_df.to_csv(output_path, index=False)

        # 7. Coverage calculations and Gate check
        geocoded_count = len(geocoded_df)
        coverage_pct = (geocoded_count / total_stations) * 100.0

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("GEOCODING SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Total clean stations:     {total_stations}")
        self.stdout.write(
            f"Tier 1 (Census Place):    {tier_counts['place']} ({tier_counts['place'] / total_stations:.2%})"
        )
        self.stdout.write(
            f"Tier 2 (County Subdiv):   {tier_counts['cousub']} ({tier_counts['cousub'] / total_stations:.2%})"
        )
        self.stdout.write(
            f"Tier 3 (Fuzzy Match):     {tier_counts['fuzzy']} ({tier_counts['fuzzy'] / total_stations:.2%})"
        )
        self.stdout.write(
            f"Tier 4 (Nominatim):       {tier_counts['nominatim']} ({tier_counts['nominatim'] / total_stations:.2%})"
        )
        self.stdout.write(f"Total Geocoded:           {geocoded_count} ({coverage_pct:.2f}%)")
        self.stdout.write(f"Total Excluded:           {len(excluded_stations)}")
        self.stdout.write(self.style.SUCCESS("=" * 60))

        # Write QA report
        self._write_report(
            report_path=report_path,
            total_stations=total_stations,
            geocoded_count=geocoded_count,
            coverage_pct=coverage_pct,
            tier_counts=tier_counts,
            fuzzy_matches=fuzzy_matches,
            nominatim_matches=nominatim_matches,
            excluded_stations=excluded_stations,
            geocoded_df=geocoded_df,
            clean_df=clean_df,
        )
        self.stdout.write(self.style.SUCCESS(f"Report written to {report_path}"))
        self.stdout.write(self.style.SUCCESS(f"Geocoded stations written to {output_path}"))

        # Gate Check: coverage >= 98%
        if coverage_pct < 98.0:
            raise CommandError(
                f"Geocoding coverage gate failed: {coverage_pct:.2f}% < 98.00% required."
            )

    def _write_report(
        self,
        report_path: Path,
        total_stations: int,
        geocoded_count: int,
        coverage_pct: float,
        tier_counts: dict[str, int],
        fuzzy_matches: list[dict[str, Any]],
        nominatim_matches: list[dict[str, Any]],
        excluded_stations: list[dict[str, Any]],
        geocoded_df: pd.DataFrame,
        clean_df: pd.DataFrame,
    ) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# FuelRoute Station Geocoding QA Report",
            "",
            "## 1. Executive Summary",
            f"- **Total Clean Stations Input**: {total_stations:,}",
            f"- **Successfully Geocoded**: {geocoded_count:,} ({coverage_pct:.2f}%)",
            f"- **Excluded Stations**: {len(excluded_stations):,} ({len(excluded_stations) / total_stations:.2%})",
            f"- **Target Gate (≥ 98.00%)**: {'PASSED' if coverage_pct >= 98.0 else 'FAILED'}",
            "",
            "## 2. Tier Breakdown",
            "| Tier | Method | Confidence | Station Count | % of Clean Stations |",
            "|---|---|---|---|---|",
            f"| 1 | Census Place Exact | 1.0 | {tier_counts['place']:,} | {tier_counts['place'] / total_stations:.2%} |",
            f"| 2 | Census County-Subdivision Exact | 1.0 | {tier_counts['cousub']:,} | {tier_counts['cousub'] / total_stations:.2%} |",
            f"| 3 | RapidFuzz Match (≥94) | ratio/100 | {tier_counts['fuzzy']:,} | {tier_counts['fuzzy'] / total_stations:.2%} |",
            f"| 4 | Nominatim Fallback | 0.8 | {tier_counts['nominatim']:,} | {tier_counts['nominatim'] / total_stations:.2%} |",
            f"| — | **Total Geocoded** | — | **{geocoded_count:,}** | **{coverage_pct:.2f}%** |",
            "",
            "## 3. Tier 3 Fuzzy Matches",
            "| State | Clean CSV City | Matched Census Place | Similarity Ratio |",
            "|---|---|---|---|",
        ]

        for m in sorted(fuzzy_matches, key=lambda x: (x["state"], x["query_city"])):
            lines.append(
                f"| {m['state']} | {m['query_city']} | {m['matched_name']} | {m['ratio']:.1f} |"
            )

        lines.extend(
            [
                "",
                "## 4. Tier 4 Nominatim Matches",
                "| City | State | Latitude | Longitude |",
                "|---|---|---|---|",
            ]
        )

        for m in sorted(nominatim_matches, key=lambda x: (x["state"], x["city"])):
            lines.append(f"| {m['city']} | {m['state']} | {m['lat']:.5f} | {m['lng']:.5f} |")

        lines.extend(
            [
                "",
                "## 5. Excluded Stations",
                "| OPIS ID | Name | Address | City | State | Price | Reason |",
                "|---|---|---|---|---|---|---|",
            ]
        )

        for s in sorted(excluded_stations, key=lambda x: (x["state"], x["city"], x["opis_id"])):
            lines.append(
                f"| {s['opis_id']} | {s['name']} | {s['address']} | {s['city']} | {s['state']} | ${s['price']} | {s['reason']} |"
            )

        # Per-State Coverage
        lines.extend(
            [
                "",
                "## 6. Per-State Station Coverage",
                "| State | Total Stations | Geocoded | Excluded | Coverage % |",
                "|---|---|---|---|---|",
            ]
        )

        state_totals = clean_df.groupby("state").size()
        state_geocoded = (
            geocoded_df.groupby("state").size() if not geocoded_df.empty else pd.Series(dtype=int)
        )

        for st in sorted(state_totals.index):
            tot = int(state_totals[st])
            geo = int(state_geocoded.get(st, 0))
            exc = tot - geo
            pct = (geo / tot) * 100.0 if tot > 0 else 0.0
            lines.append(f"| {st} | {tot} | {geo} | {exc} | {pct:.1f}% |")

        # Price Stats
        prices = (
            geocoded_df["price"].astype(float) if not geocoded_df.empty else pd.Series(dtype=float)
        )
        lines.extend(
            [
                "",
                "## 7. Price Statistics (Geocoded Stations)",
                f"- **Minimum Retail Price**: ${prices.min():.4f}/gal"
                if not prices.empty
                else "- N/A",
                f"- **Maximum Retail Price**: ${prices.max():.4f}/gal"
                if not prices.empty
                else "- N/A",
                f"- **Mean Retail Price**: ${prices.mean():.4f}/gal"
                if not prices.empty
                else "- N/A",
                f"- **Median Retail Price**: ${prices.median():.4f}/gal"
                if not prices.empty
                else "- N/A",
                f"- **Price Outliers (> 4σ)**: {int(geocoded_df['price_outlier'].sum())}"
                if not geocoded_df.empty
                else "- N/A",
            ]
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
