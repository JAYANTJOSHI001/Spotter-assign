"""Django settings for fuelroute project.

Strictly env-driven configuration with fail-fast validation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# -----------------------------------------------------------------------------
# Optional .env Loader (No third-party dependency)
# -----------------------------------------------------------------------------
def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            k, v = k.strip(), v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if k and k not in os.environ:
                os.environ[k] = v


_load_env_file(BASE_DIR / ".env")


# -----------------------------------------------------------------------------
# Configuration Helpers & Validation
# -----------------------------------------------------------------------------
def get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    val_clean = val.strip().lower()
    if val_clean in ("true", "1", "yes", "on"):
        return True
    if val_clean in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"Invalid boolean value for environment variable '{key}': '{val}'")


def get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def get_choice(key: str, allowed: set[str], default: str) -> str:
    val = os.getenv(key, default).strip()
    if val not in allowed:
        raise ValueError(f"Invalid value for '{key}': '{val}'. Must be one of {sorted(allowed)}")
    return val


def get_int(
    key: str,
    default: int,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    raw = os.getenv(key)
    if raw is None:
        val = default
    else:
        try:
            val = int(raw.strip())
        except ValueError as err:
            raise ValueError(
                f"Invalid integer value for environment variable '{key}': '{raw}'"
            ) from err

    if min_val is not None and val < min_val:
        raise ValueError(f"Value for '{key}' ({val}) must be >= {min_val}")
    if max_val is not None and val > max_val:
        raise ValueError(f"Value for '{key}' ({val}) must be <= {max_val}")
    return val


def get_float(
    key: str,
    default: float,
    min_val: float | None = None,
    max_val: float | None = None,
    must_be_strictly_positive: bool = False,
) -> float:
    raw = os.getenv(key)
    if raw is None:
        val = default
    else:
        try:
            val = float(raw.strip())
        except ValueError as err:
            raise ValueError(
                f"Invalid float value for environment variable '{key}': '{raw}'"
            ) from err

    if must_be_strictly_positive and val <= 0:
        raise ValueError(f"Value for '{key}' ({val}) must be > 0")
    if min_val is not None and val < min_val:
        raise ValueError(f"Value for '{key}' ({val}) must be >= {min_val}")
    if max_val is not None and val > max_val:
        raise ValueError(f"Value for '{key}' ({val}) must be <= {max_val}")
    return val


def get_corridor_miles(key: str, default: str = "10,25,50") -> list[float]:
    raw = os.getenv(key, default).strip()
    if not raw:
        raise ValueError(f"'{key}' cannot be empty")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError(f"'{key}' must contain at least one valid number")
    values = []
    for item in parts:
        try:
            v = float(item)
        except ValueError as err:
            raise ValueError(f"Invalid corridor mile value in '{key}': '{item}'") from err
        if v <= 0:
            raise ValueError(f"Corridor step '{v}' in '{key}' must be > 0")
        values.append(v)
    return values


# -----------------------------------------------------------------------------
# Core Django Settings
# -----------------------------------------------------------------------------
DEBUG = get_bool("DJANGO_DEBUG", default=False)

DEV_SECRET_KEY = "dev-insecure-secret-key-fuelroute-local-dev-only"
_raw_secret = os.getenv("DJANGO_SECRET_KEY", "").strip()

if not _raw_secret or (not DEBUG and _raw_secret == DEV_SECRET_KEY):
    if DEBUG:
        SECRET_KEY = DEV_SECRET_KEY
    else:
        raise ValueError(
            "DJANGO_SECRET_KEY must be set to a secure secret key when DJANGO_DEBUG=False"
        )
else:
    SECRET_KEY = _raw_secret

_raw_allowed = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").strip()
ALLOWED_HOSTS = [h.strip() for h in _raw_allowed.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Register only Django-model/app-config apps (geo/providers/planner are plain packages)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.stations",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "apps" / "api" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------
DATABASE_URL = get_str("DATABASE_URL", "sqlite:///db.sqlite3")


def parse_database_url(url: str) -> dict:
    if url.startswith("sqlite:///"):
        sqlite_path = url[len("sqlite:///") :]
        if sqlite_path == ":memory:":
            db_name = ":memory:"
        else:
            db_name = str(BASE_DIR / sqlite_path)
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db_name,
        }
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        parsed = urlparse(url)
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or 5432),
        }
    raise ValueError(f"Unsupported DATABASE_URL scheme in '{url}'")


DATABASES = {
    "default": parse_database_url(DATABASE_URL),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Cache Configuration
# -----------------------------------------------------------------------------
REDIS_URL = get_str("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fuelroute-cache",
        }
    }

# -----------------------------------------------------------------------------
# Domain & Provider Configuration (ARCHITECTURE §9)
# -----------------------------------------------------------------------------
ROUTING_PROVIDER = get_choice("ROUTING_PROVIDER", {"osrm", "ors", "fixture"}, default="osrm")
OSRM_BASE_URL = get_str("OSRM_BASE_URL", "https://router.project-osrm.org")
ORS_API_KEY = get_str("ORS_API_KEY", "")
NOMINATIM_BASE_URL = get_str("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_USER_AGENT = get_str(
    "NOMINATIM_USER_AGENT",
    "fuelroute-assessment/1.0 (contact: you@example.com)",
)

MAX_RANGE_MILES = get_int("MAX_RANGE_MILES", default=500, min_val=1)
MPG = get_float("MPG", default=10.0, must_be_strictly_positive=True)
START_MODE = get_choice("START_MODE", {"priced", "free"}, default="priced")
STATION_PRICE_POLICY = get_choice("STATION_PRICE_POLICY", {"min", "median", "mean"}, default="min")

CORRIDOR_MILES = get_corridor_miles("CORRIDOR_MILES", default="10,25,50")
DETOUR_FACTOR = get_float("DETOUR_FACTOR", default=2.0, min_val=0.0)
SAFETY_RESERVE_MILES = get_float("SAFETY_RESERVE_MILES", default=0.0, min_val=0.0)

EXTERNAL_CALL_BUDGET = get_int("EXTERNAL_CALL_BUDGET", default=3, min_val=1)
UPSTREAM_TIMEOUT_S = get_float("UPSTREAM_TIMEOUT_S", default=8.0, must_be_strictly_positive=True)
CACHE_TTL_S = get_int("CACHE_TTL_S", default=86400, min_val=0)
RATE_LIMIT_PER_MIN = get_int("RATE_LIMIT_PER_MIN", default=60, min_val=0)

# -----------------------------------------------------------------------------
# Static Files
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# -----------------------------------------------------------------------------
# Logging (JSON to stdout)
# -----------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": JSONFormatter,
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": "INFO",
            "propagate": False,
        },
        "fuelroute": {
            "handlers": ["stdout"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
