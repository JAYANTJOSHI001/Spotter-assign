from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from apps.stations.pipeline import prepare_stations_dataframe


class Command(BaseCommand):
    help = "Clean and prepare raw fuel price CSV into canonical unique fuel stations."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            type=str,
            default="data/raw/fuel-prices-for-be-assessment.csv",
            help="Path to raw fuel prices CSV",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="data/stations_clean.csv",
            help="Path to write cleaned stations CSV",
        )
        parser.add_argument(
            "--policy",
            type=str,
            default="min",
            choices=["min", "median", "mean"],
            help="Pricing policy for stations with multiple observations",
        )
        parser.add_argument(
            "--no-assert",
            action="store_true",
            help="Skip strict audit assertions (for testing custom CSVs)",
        )

    def handle(self, *args, **options) -> None:
        input_path = Path(options["input"])
        output_path = Path(options["output"])
        policy = options["policy"]
        assert_audit = not options["no_assert"]

        if not input_path.exists():
            self.stderr.write(self.style.ERROR(f"Input file not found: {input_path}"))
            return

        self.stdout.write(f"Reading raw data from {input_path}...")
        raw_df = pd.read_csv(input_path, dtype=str)

        clean_df, stats = prepare_stations_dataframe(
            raw_df, policy=policy, assert_audit=assert_audit
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        clean_df.to_csv(output_path, index=False)

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("STATIONS CLEANING SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Total raw rows:              {stats['raw_rows']}")
        self.stdout.write(f"Canadian rows dropped:       {stats['canadian_rows_dropped']}")
        self.stdout.write(f"Exact duplicates dropped:    {stats['exact_duplicates_dropped']}")
        self.stdout.write(f"Excluded price rows:         {stats['excluded_price_rows']}")
        self.stdout.write(f"Unique clean stations:       {stats['clean_stations']}")
        self.stdout.write(f"Price outliers (>4 sigma):   {stats['price_outliers']}")
        if "mean_price" in stats:
            self.stdout.write(f"Mean retail price:           ${stats['mean_price']:.4f}")
            self.stdout.write(f"Price outlier cutoff:        ${stats['outlier_threshold']:.4f}")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"Clean stations saved to {output_path}"))
