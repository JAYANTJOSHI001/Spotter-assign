from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class IndexEmpty(Exception):
    """Raised when the database has 0 fuel stations."""


@dataclass(frozen=True, slots=True)
class StationIndex:
    """Thread-safe, read-only in-memory index for fuel stations."""

    opis_id: np.ndarray  # int64
    lat: np.ndarray  # float64
    lng: np.ndarray  # float64
    price: np.ndarray  # float64
    unit_vectors: np.ndarray  # (N, 3) float64
    metadata: tuple[dict[str, Any], ...]
    data_version: str

    def __len__(self) -> int:
        return len(self.opis_id)


_index: StationIndex | None = None
_lock = threading.Lock()


def _compute_unit_vectors(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    """Convert geodetic (lat, lng) in degrees to Cartesian (X, Y, Z) unit vectors on the unit sphere."""
    lat_rad = np.radians(lat)
    lng_rad = np.radians(lng)
    x = np.cos(lat_rad) * np.cos(lng_rad)
    y = np.cos(lat_rad) * np.sin(lng_rad)
    z = np.sin(lat_rad)
    return np.column_stack((x, y, z)).astype(np.float64)


def _compute_data_version(
    opis_id: np.ndarray,
    price: np.ndarray,
    lat: np.ndarray,
    lng: np.ndarray,
) -> str:
    """Compute deterministic SHA-1 over sorted station coordinates and prices."""
    hasher = hashlib.sha1()
    for i in range(len(opis_id)):
        record_bytes = f"{opis_id[i]}:{price[i]:.4f}:{lat[i]:.6f}:{lng[i]:.6f}\n".encode("ascii")
        hasher.update(record_bytes)
    return f"sha1:{hasher.hexdigest()}"


def _load_from_db() -> StationIndex:
    from apps.stations.models import FuelStation

    rows = list(
        FuelStation.objects.order_by("opis_id").values_list(
            "opis_id",
            "lat",
            "lng",
            "price",
            "name",
            "address",
            "city",
            "state",
            "geocode_method",
        )
    )

    if not rows:
        raise IndexEmpty("FuelStation table is empty. Run manage.py load_stations first.")

    n = len(rows)
    opis_id_arr = np.empty(n, dtype=np.int64)
    lat_arr = np.empty(n, dtype=np.float64)
    lng_arr = np.empty(n, dtype=np.float64)
    price_arr = np.empty(n, dtype=np.float64)

    metadata_list: list[dict[str, Any]] = []

    for i, r in enumerate(rows):
        opis_id_arr[i] = r[0]
        lat_arr[i] = r[1]
        lng_arr[i] = r[2]
        price_arr[i] = float(r[3])
        metadata_list.append(
            {
                "opis_id": r[0],
                "lat": r[1],
                "lng": r[2],
                "price": float(r[3]),
                "name": r[4],
                "address": r[5],
                "city": r[6],
                "state": r[7],
                "geocode_method": r[8],
            }
        )

    unit_vectors = _compute_unit_vectors(lat_arr, lng_arr)
    data_version = _compute_data_version(opis_id_arr, price_arr, lat_arr, lng_arr)

    return StationIndex(
        opis_id=opis_id_arr,
        lat=lat_arr,
        lng=lng_arr,
        price=price_arr,
        unit_vectors=unit_vectors,
        metadata=tuple(metadata_list),
        data_version=data_version,
    )


def get_index() -> StationIndex:
    """Retrieve the in-memory StationIndex singleton, loading once if necessary."""
    global _index
    if _index is not None:
        return _index

    with _lock:
        if _index is not None:
            return _index
        logger.info("StationIndex loading cold from database...")
        _index = _load_from_db()
        logger.info(
            "StationIndex loaded: %d stations, version %s", len(_index), _index.data_version
        )
        return _index


def reload_index() -> StationIndex:
    """Force reload the StationIndex singleton from the database."""
    global _index
    with _lock:
        logger.info("Forcing StationIndex reload from database...")
        _index = _load_from_db()
        return _index
