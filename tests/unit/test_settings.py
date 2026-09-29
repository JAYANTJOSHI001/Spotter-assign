import importlib
import os

import pytest

import config.settings as settings


def reload_settings():
    return importlib.reload(settings)


def test_default_settings_valid():
    """Verify that default settings load without error."""
    assert settings.MAX_RANGE_MILES == 500
    assert settings.MPG == 10.0
    assert settings.START_MODE == "priced"
    assert settings.STATION_PRICE_POLICY == "min"
    assert settings.CORRIDOR_MILES == [10.0, 25.0, 50.0]
    assert settings.DETOUR_FACTOR == 2.0
    assert settings.SAFETY_RESERVE_MILES == 0.0
    assert settings.EXTERNAL_CALL_BUDGET == 3


def test_invalid_mpg_fails_fast(monkeypatch):
    monkeypatch.setenv("MPG", "-5")
    with pytest.raises(ValueError, match="must be > 0"):
        reload_settings()

    monkeypatch.setenv("MPG", "0")
    with pytest.raises(ValueError, match="must be > 0"):
        reload_settings()


def test_invalid_start_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("START_MODE", "invalid_mode")
    with pytest.raises(ValueError, match="Must be one of"):
        reload_settings()


def test_invalid_price_policy_fails_fast(monkeypatch):
    monkeypatch.setenv("STATION_PRICE_POLICY", "cheapest")
    with pytest.raises(ValueError, match="Must be one of"):
        reload_settings()


def test_invalid_max_range_fails_fast(monkeypatch):
    monkeypatch.setenv("MAX_RANGE_MILES", "0")
    with pytest.raises(ValueError, match="must be >= 1"):
        reload_settings()


def test_missing_secret_key_in_production(monkeypatch):
    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "")
    with pytest.raises(ValueError, match="DJANGO_SECRET_KEY must be set"):
        reload_settings()


def test_default_secret_key_rejected_in_production(monkeypatch):
    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.setenv("DJANGO_SECRET_KEY", settings.DEV_SECRET_KEY)
    with pytest.raises(ValueError, match="DJANGO_SECRET_KEY must be set"):
        reload_settings()


def test_invalid_corridor_miles(monkeypatch):
    monkeypatch.setenv("CORRIDOR_MILES", "10,-5,50")
    with pytest.raises(ValueError, match="must be > 0"):
        reload_settings()


def test_database_url_parsing(monkeypatch):
    from config.settings import parse_database_url

    sqlite_cfg = parse_database_url("sqlite:///test.db")
    assert sqlite_cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert "test.db" in sqlite_cfg["NAME"]

    pg_cfg = parse_database_url("postgres://user:pass@localhost:5432/fuelroute_db")
    assert pg_cfg["ENGINE"] == "django.db.backends.postgresql"
    assert pg_cfg["NAME"] == "fuelroute_db"
    assert pg_cfg["USER"] == "user"
    assert pg_cfg["PASSWORD"] == "pass"
    assert pg_cfg["HOST"] == "localhost"
    assert pg_cfg["PORT"] == "5432"

    with pytest.raises(ValueError, match="Unsupported DATABASE_URL scheme"):
        parse_database_url("mysql://root@localhost/db")


@pytest.fixture(autouse=True)
def restore_settings():
    """Ensure settings are cleanly reloaded after monkeypatched tests."""
    yield
    # Reset any overrides that might affect other tests
    os.environ["DJANGO_DEBUG"] = "True"
    os.environ["DJANGO_SECRET_KEY"] = "dev-insecure-secret-key-fuelroute-local-dev-only"
    os.environ["MPG"] = "10"
    os.environ["START_MODE"] = "priced"
    os.environ["STATION_PRICE_POLICY"] = "min"
    os.environ["MAX_RANGE_MILES"] = "500"
    os.environ["CORRIDOR_MILES"] = "10,25,50"
    reload_settings()
