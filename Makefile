ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv/Scripts
    PYTHON = $(VENV_BIN)/python.exe
    PIP = $(VENV_BIN)/pip.exe
    RUFF = $(VENV_BIN)/ruff.exe
    PYTEST = $(VENV_BIN)/pytest.exe
else
    VENV_BIN = .venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(VENV_BIN)/pip
    RUFF = $(VENV_BIN)/ruff
    PYTEST = $(VENV_BIN)/pytest
endif

.PHONY: setup run test lint format cov data bench docker-build docker-run

setup:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PYTHON) manage.py migrate

run:
	$(PYTHON) manage.py runserver 0.0.0.0:8000

test:
	$(PYTEST)

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

cov:
	$(PYTEST) --cov=apps --cov=config --cov-report=term-missing

data:
	$(PYTHON) manage.py prepare_stations --input data/raw/fuel-prices-for-be-assessment.csv --output data/stations_clean.csv
	$(PYTHON) manage.py geocode_stations --input data/stations_clean.csv --output data/stations_geocoded.csv --report data/geocode_report.md
	$(PYTHON) manage.py load_stations --input data/stations_geocoded.csv

bench:
	@echo "Benchmark implemented in P7/P8"

docker-build:
	docker build -t fuelroute:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env.example fuelroute:latest
