# FuelRoute API

FuelRoute is a high-performance Django service that plans optimal, cost-minimized fuel stops along long-distance cross-country routes across the contiguous United States. Given a starting point and destination, it calls an upstream routing service (OSRM / OpenRouteService) once, evaluates fuel stations within an adaptive corridor, and determines the mathematically optimal refueling strategy respecting a 500-mile vehicle range and 10 MPG fuel consumption.

## Verified Environment
- **Django Version**: 6.1.1 (latest stable on PyPI)
- **Python Compatibility**: 3.12, 3.13

## Quickstart

### Prerequisites
- Python 3.12+
- Make (or direct command execution)
- Docker (optional)

### Setup & Run
```bash
# Setup environment and run migrations
make setup

# Run the local development server
make run
```

Then verify the service is running:
```bash
curl http://localhost:8000/api/v1/health
```

### Tooling & Quality Checks
```bash
# Run linters and format checks
make lint

# Run automated tests
make test

# Build and run with Docker
make docker-build
make docker-run
```
