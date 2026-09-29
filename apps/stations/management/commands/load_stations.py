from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.stations.models import FuelStation


class Command(BaseCommand):
    help = (
        "Load geocoded fuel stations CSV into the FuelStation database table (idempotent upsert)."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input",
            type=str,
            default="data/stations_geocoded.csv",
            help="Path to geocoded fuel stations CSV",
        )

    def handle(self, *args, **options) -> None:
        input_path = Path(options["input"])
        if not input_path.exists():
            raise CommandError(f"Geocoded stations file not found: {input_path}")

        self.stdout.write(f"Reading stations from {input_path}...")
        df = pd.read_csv(input_path)

        station_objects: list[FuelStation] = []
        for _, row in df.iterrows():
            station_objects.append(
                FuelStation(
                    opis_id=int(row["opis_id"]),
                    name=str(row["name"]),
                    address=str(row["address"]),
                    city=str(row["city"]),
                    state=str(row["state"]),
                    rack_id=int(row["rack_id"]),
                    price=Decimal(str(row["price"])),
                    price_min=Decimal(str(row["price_min"])),
                    price_max=Decimal(str(row["price_max"])),
                    n_price_rows=int(row["n_price_rows"]),
                    lat=float(row["lat"]),
                    lng=float(row["lng"]),
                    geocode_method=str(row["geocode_method"]),
                    geocode_confidence=float(row["geocode_confidence"]),
                    price_outlier=bool(row["price_outlier"]),
                )
            )

        with transaction.atomic():
            existing_opis_ids = set(FuelStation.objects.values_list("opis_id", flat=True))
            incoming_ids = [s.opis_id for s in station_objects]
            inserted_count = len([s_id for s_id in incoming_ids if s_id not in existing_opis_ids])
            updated_count = len(incoming_ids) - inserted_count

            update_fields = [
                "name",
                "address",
                "city",
                "state",
                "rack_id",
                "price",
                "price_min",
                "price_max",
                "n_price_rows",
                "lat",
                "lng",
                "geocode_method",
                "geocode_confidence",
                "price_outlier",
            ]

            FuelStation.objects.bulk_create(
                station_objects,
                update_conflicts=True,
                update_fields=update_fields,
                unique_fields=["opis_id"],
            )

        total_db = FuelStation.objects.count()
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("LOAD STATIONS COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Total processed:  {len(station_objects)}")
        self.stdout.write(f"Inserted:         {inserted_count}")
        self.stdout.write(f"Updated:          {updated_count}")
        self.stdout.write(f"Total in DB:      {total_db}")
        self.stdout.write(self.style.SUCCESS("=" * 60))
