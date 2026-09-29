from __future__ import annotations

import logging
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)

SKIP_COMMANDS = {
    "migrate",
    "makemigrations",
    "test",
    "collectstatic",
    "load_stations",
    "prepare_stations",
    "geocode_stations",
    "shell",
    "check",
}


class StationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stations"

    def ready(self) -> None:
        # Avoid warm loading during management commands or test execution
        args = set(sys.argv)
        if any(cmd in args for cmd in SKIP_COMMANDS) or "pytest" in sys.modules:
            return

        try:
            import warnings

            from apps.stations.index import get_index

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=RuntimeWarning, message="Accessing the database"
                )
                get_index()
        except Exception as exc:
            logger.warning("StationIndex warm-load skipped or failed at startup: %s", exc)
