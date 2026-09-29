# AGENTS.md — FuelRoute API (Spotter Backend Django Assessment)

This file has three parts:

- **Part A — Standing rules** (Antigravity loads these for every agent working in this repo).
- **Part B — How to run the build in Antigravity** (workflow + gates).
- **Part C — Phase prompts P0–P9** (paste one per agent conversation, in order).

Source-of-truth docs (must exist in the repo before starting): `docs/SCOPE.md`, `docs/ARCHITECTURE.md`.
If your Antigravity build does not auto-read `AGENTS.md`, copy Part A into `.agent/rules/fuelroute.md` (or `GEMINI.md`) — the content is tool-agnostic.

---

# PART A — STANDING RULES

## A1. Mission
Build the **FuelRoute API**: a Django service that takes a USA start + finish, calls a free routing API **once**, and returns the route, a map, the **cheapest fuel stops** (500-mile range) and the **total fuel cost at 10 MPG**, using the supplied fuel-price CSV. Speed and few external calls are graded.

## A2. Non-negotiables
1. **Django latest stable.** Before writing code, check PyPI/djangoproject.com for the newest stable release (expected **6.1.x**, Python 3.12–3.14). Pin `django>=6.1,<6.2` (or the newer minor if one exists). Record the verified version in `README.md`. Never use an EOL version.
2. **No DRF.** Plain Django views + small validators (SCOPE risk table).
3. **External calls:** typical request = exactly **1** (route). Hard cap **3** enforced by `CallBudget`. Cache results. No external call at import time, in tests, or in management commands except the one-time geocode fallback.
4. **No network in tests.** Use `respx` + recorded fixtures. CI has no internet dependency.
5. **No invented data.** Never fabricate coordinates, prices, API responses, or library APIs. If a fact can't be verified (URL, endpoint shape, library signature), **stop and verify** (fetch docs / run `pip show` / inspect the package) before coding.
6. **Money uses `Decimal`.** Round half-up to cents per stop; totals = sum of rounded stops.
7. **Pure core.** `apps/geo/*` and `apps/planner/optimizer.py` must not import Django.
8. **Determinism.** Stable sorts with explicit tie-breaks `(mile_marker, price, opis_id)`.
9. **No secrets in git.** Keys via env; `.env.example` only.
10. **Every claim in the README is backed by a test or a command output.**

## A3. Decisions already made (do not re-litigate; see SCOPE §4)
D1 city-centroid station coordinates from Census Gazetteer (+ cached Nominatim fallback) · D2 US only · D3 lowest price per station · D4 500 mi / 10 MPG · D5 `START_MODE=priced` default · D6 arrive with ~0 fuel · D7 corridor 10→25→50 mi only if infeasible · D8 detour = 2×offset miles burned · D9 OSRM primary, ORS optional fallback · D10 offline `City, ST` resolution before Nominatim · D11 Decimal · D12 miles/gallons · D13 Leaflet map in browser.

## A4. Code standards
- Python 3.13, full type hints, `from __future__ import annotations`, dataclasses (`frozen=True, slots=True`) for domain objects.
- `ruff` (lint + format) must pass; line length 100.
- Functions ≤ ~40 lines; no bare `except`; typed exceptions from `apps/providers/errors.py` / `apps/api/errors.py`.
- Docstrings on public functions state units (miles, gallons, USD).
- Logging via stdlib `logging` (JSON formatter), never `print` in app code.
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), one logical change per commit, at the end of every phase.

## A5. Definition of "done" for any phase
1. Code + tests written. 2. `ruff check . && ruff format --check .` clean. 3. `pytest -q` green. 4. Phase acceptance commands (listed in the prompt) run and their output pasted in the walkthrough. 5. Changes committed. 6. A short **Walkthrough** artifact lists: what was built, decisions made, anything deferred, exact commands to verify.

## A6. When uncertain
Prefer the spec. If the spec is silent, choose the simplest option that keeps the API fast and the call budget low, write the choice in `docs/DECISIONS.md`, and continue. Never block on a question that has a safe default.

---

# PART B — RUNNING THE BUILD IN ANTIGRAVITY

1. Create the repo folder `fuelroute/`, copy in: `AGENTS.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, and the CSV as `data/raw/fuel-prices-for-be-assessment.csv`. `git init` and make the first commit.
2. Open the folder in Antigravity → **Agent Manager**. Use **one conversation per phase** (P0…P9). Set the mode to **Planning** so each agent first produces an Implementation Plan artifact; **read it and approve** before it edits code.
3. Paste the phase prompt exactly as written. Do not merge phases — smaller scopes make fewer mistakes.
4. After each phase: run the phase's acceptance commands **yourself** in the terminal, skim the diff, then start the next phase. If a gate fails, paste the failing output back into the *same* conversation and ask for a fix — do not start over.
5. Keep terminal/browser permissions on "ask" for anything that touches the network besides `pip`/`uv`, the Census download (P1) and `git`.
6. Before submitting, run **P9 (adversarial audit)** in a fresh conversation, so the reviewing agent has no memory of the build and judges it cold.

**Phase order & effort:** P0 bootstrap (20 min) → P1 data pipeline (60) → P2 index (30) → P3 geo (45) → P4 providers (45) → P5 optimizer (60) → P6 API (60) → P7 hardening/perf (45) → P8 docs/Postman/CI/Loom (45) → P9 audit (30).

---

# PART C — PHASE PROMPTS

Each prompt is self-contained. Paste the whole block.

---

## P0 — Bootstrap the project

~~~text
ROLE: Senior Django backend engineer. You are starting a greenfield repo called `fuelroute`.

READ FIRST: AGENTS.md (Part A), docs/SCOPE.md, docs/ARCHITECTURE.md. Follow them exactly.

GOAL: Create a runnable, empty-but-correct Django project skeleton with tooling, so later phases only add features.

STEPS
1. VERIFY the latest stable Django version on PyPI / djangoproject.com (do not assume). Expected 6.1.x with Python 3.12–3.14. Use Python 3.13 if available. Record the exact versions you verified.
2. Initialize with `uv` (fallback: venv + pip). Create pyproject.toml with dependencies: django (latest stable, pinned to its minor), numpy, scipy, httpx, gunicorn, whitenoise, orjson (optional), rapidfuzz, pandas (pipeline only). Dev deps: pytest, pytest-django, pytest-cov, respx, hypothesis, ruff, mypy (optional). Pin lower bounds; commit the lockfile.
3. Create the repo layout EXACTLY as in docs/ARCHITECTURE.md §3 (empty packages with __init__.py where needed). Project package is `config`; apps live under `apps/` (`apps.stations`, `apps.geo`, `apps.providers`, `apps.planner`, `apps.api`). Register only Django-model/app-config apps in INSTALLED_APPS (stations, api); geo/providers/planner are plain packages.
4. config/settings.py: env-driven with a small helper (no extra dependency needed; use os.environ + explicit casting/validation). Implement every variable in ARCHITECTURE §9 with the stated defaults. Fail fast with a clear error on invalid values (e.g. MPG <= 0, START_MODE not in {priced,free}). DEBUG defaults False. SECRET_KEY from env; in DEBUG use an insecure dev default, in non-DEBUG refuse to start if missing. DATABASES from DATABASE_URL (sqlite default; support postgres URL by simple parsing, no new dependency unless needed). CACHES: LocMemCache by default, Redis if REDIS_URL set (use Django's built-in redis backend). Add GZipMiddleware, WhiteNoise not required for API but fine. Add LOGGING with a JSON formatter to stdout.
5. config/urls.py: mounts `api/v1/` from apps.api.urls. apps/api/urls.py: only `GET /api/v1/health` returning {"status":"ok"} for now.
6. Makefile targets: setup (install + migrate), run (runserver 0.0.0.0:8000), test, lint, format, cov, data (placeholder that echoes "implemented in P1"), bench (placeholder), docker-build, docker-run.
7. Dockerfile (python:3.13-slim, non-root user, gunicorn `config.wsgi` with gthread workers, HEALTHCHECK on /api/v1/health), .dockerignore, .env.example (all vars from ARCHITECTURE §9, no real secrets), .gitignore (venv, .env, db.sqlite3, __pycache__, .pytest_cache, data/gazetteer/*.zip, .DS_Store — but NOT data/stations_geocoded.csv or data/geocode_cache.json).
8. .github/workflows/ci.yml: on push/PR → setup python 3.13, install, ruff check, ruff format --check, pytest --cov. No secrets, no network-dependent tests.
9. Tests: tests/integration/test_health.py hitting /api/v1/health; tests/unit/test_settings.py verifying invalid env values fail fast.
10. README.md stub: title, one-paragraph description, verified Django version, `make setup && make run` instructions (full README comes in P8).

ACCEPTANCE (run and paste output)
- `python -c "import django; print(django.get_version())"` shows the verified latest stable.
- `make lint && make test` pass.
- `make run` then `curl -s localhost:8000/api/v1/health` returns {"status":"ok"}.
- `docker build .` succeeds (if Docker is available; otherwise say so).

DO NOT: add DRF, implement business logic, or call any external API.
COMMIT: `chore: bootstrap django project, tooling, ci`
~~~

---

## P1 — Data pipeline (clean → geocode → QA → load)

~~~text
ROLE: Data engineer + Django engineer.

READ FIRST: AGENTS.md, docs/SCOPE.md §3–4, docs/ARCHITECTURE.md §4.

CONTEXT (verified by audit of data/raw/fuel-prices-for-be-assessment.csv — assert these in code; if they differ, STOP and report):
- Columns: OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price. NO coordinates.
- 8,151 rows total; 620 are Canadian (province codes AB, BC, MB, NB, NL, NS, ON, PE, QC, SK, NT, YT, NU) → drop.
- 7,531 US rows → 6,626 unique OPIS Truckstop IDs; 26 exact duplicate rows.
- Same ID may have several different prices (568 IDs, mean spread ~$0.10) and several name variants (227 IDs). Address/City/State/Rack ID are constant per ID.
- City values contain trailing/leading spaces. 48 US states present (no AK/HI/DC). 4,179 unique (City, State) pairs.
- Price range 2.687–6.399 USD/gal.

GOAL: Produce `data/stations_geocoded.csv` (committed runtime artifact), `data/geocode_cache.json`, `data/geocode_report.md`, the `FuelStation` model, and three management commands.

STEPS
1. `apps/stations/models.py`: FuelStation exactly as ARCHITECTURE §4.3 (opis_id unique+indexed, price DecimalField(6,4), lat/lng FloatField, geocode_method CharField, geocode_confidence FloatField, price_outlier BooleanField, price_min/price_max/n_price_rows). Create + commit migrations.
2. `apps/stations/pricing.py`: `resolve_price(prices: list[Decimal], policy: str) -> Decimal` supporting min|median|mean; unit-tested.
3. `manage.py prepare_stations --input data/raw/... --output data/stations_clean.csv [--policy min]`:
   implement ARCHITECTURE §4.1 precisely. Assert the audit numbers above (6,626 rows). Print a summary table. Exclude prices outside [1.5, 10] and report them; flag outliers > mean + 4σ as price_outlier.
4. `apps/geo/gazetteer.py`: 
   - `normalize_place(name) -> str`: lowercase, strip accents, remove punctuation, `&`→`and`, `st`/`st.`→`saint`, `ft`/`ft.`→`fort`, `mt`/`mt.`→`mount`, collapse spaces; strip Census suffixes (` city`, ` town`, ` village`, ` borough`, ` cdp`, ` municipality`, ` township`, ` charter township`) ONLY for the Census-side key.
   - `load_gazetteer(paths) -> dict[(state, normalized_name), (lat, lng)]`; if duplicate keys exist within a state, keep the entry with the largest land area (ALAND) and log the ambiguity count.
   - Provide a function to download the latest Census Gazetteer files: DISCOVER the latest year by fetching the Census directory listing under https://www2.census.gov/geo/docs/maps-data/data/gazetteer/ (do NOT hardcode a year blindly), download `*_Gaz_place_national.zip` and `*_Gaz_cousubs_national.zip`, store under data/gazetteer/, and write their SHA-256 into data/gazetteer/CHECKSUMS.txt. Parse the tab-delimited files (columns include USPS, NAME, INTPTLAT, INTPTLONG — strip whitespace from header names; INTPTLONG has trailing spaces in some vintages).
5. `manage.py geocode_stations --input data/stations_clean.csv --output data/stations_geocoded.csv --report data/geocode_report.md [--no-network]`:
   Tiered matching per ARCHITECTURE §4.2 (place exact → cousub exact → rapidfuzz ≥ 94 within state → Nominatim for unique still-unmatched (city,state) only).
   - Nominatim: structured query, `countrycodes=us`, 1 request/second, User-Agent from env NOMINATIM_USER_AGENT (must be set to a real value; refuse to run with the default placeholder), results (including misses) cached in data/geocode_cache.json so re-runs make ZERO calls.
   - `--no-network` skips tier 4 (used in tests/CI).
   - Record `geocode_method` ∈ {place, cousub, fuzzy, nominatim} and confidence (1.0, 1.0, ratio/100, 0.8).
   - Validate every coordinate inside US bounds lat 24.3–49.5, lng −125.1…−66.8; failing rows are excluded and reported.
   - Gate: fail (exit code 1) if < 98% of clean stations end up geocoded.
   - Write the QA report (counts per tier, every fuzzy match, every Nominatim match, excluded stations, per-state coverage, price stats, dedupe stats).
6. `manage.py load_stations --input data/stations_geocoded.csv`: idempotent upsert in a transaction; print inserted/updated counts.
7. `make data` runs prepare → geocode → load. Document required env (NOMINATIM_USER_AGENT).
8. Tests (no network): tests/unit/test_pricing.py, test_gazetteer_normalization.py (≥ 25 parametrized cases incl. "St. Louis"/"Saint Louis", "Ft. Wayne", "Mt. Vernon", "O'Fallon", "Winston-Salem", "McAlester"), tests/unit/test_prepare_stations.py on a hand-made 30-row CSV covering: Canadian row dropped, padded city, exact dup, same-ID multiple prices, name variants, out-of-range price. tests/data/test_artifact.py validating the real committed artifact: row count == number in report, no nulls, coords in bounds, opis_id unique, 0 Canadian states, price in range.

ACCEPTANCE (run and paste output)
- `python manage.py prepare_stations ...` prints 6,626 clean stations.
- `python manage.py geocode_stations ...` prints tier counts and coverage ≥ 98%.
- `python manage.py load_stations ...` then `python manage.py shell -c "from apps.stations.models import FuelStation as F; print(F.objects.count())"` matches the artifact.
- `pytest tests/unit tests/data -q` green.
- Show the top 10 lines of geocode_report.md and list the excluded stations.

DO NOT: geocode at request time; guess coordinates; call Nominatim for any city already matched; commit the large Census zip files.
COMMIT: `feat(data): clean, geocode and load fuel stations` (include stations_geocoded.csv, geocode_cache.json, geocode_report.md).
~~~

---

## P2 — Station index (in-memory)

~~~text
ROLE: Django backend engineer focused on performance.

READ FIRST: AGENTS.md, docs/ARCHITECTURE.md §6.4, §8.

GOAL: A thread-safe, read-only in-memory `StationIndex` so no DB query happens on the request path.

STEPS
1. `apps/stations/index.py`: `StationIndex` dataclass holding numpy arrays: opis_id (int64), lat, lng (float64), price (float64), unit_vectors (N×3 float64), and a parallel list of small metadata tuples/dicts (name, address, city, state, geocode_method) for response building. Also `data_version` = sha1 of the sorted (opis_id, price, lat, lng) content (NOT of file mtime).
2. `get_index()` — module-level lazy singleton guarded by `threading.Lock`; loads once from the DB (`FuelStation.objects.values_list(...)` ordered by opis_id for determinism). `reload_index()` for tests/management. Raise a typed `IndexEmpty` error if 0 rows.
3. `apps/stations/apps.py::ready()`: warm-load the index only when running the server (skip when argv contains migrate/makemigrations/test/collectstatic/load_stations etc. and when DB isn't migrated). Must never crash startup; log a warning instead.
4. Extend /api/v1/health: report `db: ok`, `stations: <count>`, `data_version`, and 503 if the index is empty.
5. Helper `national_median_price(index)` and `median_price_in_window(prices, mile_markers, max_mile)` (pure functions in `apps/stations/pricing.py`) for START_MODE=priced.
6. Tests: index loads N rows equal to DB; unit_vectors have norm 1 ± 1e-12; data_version stable across two loads and changes when one price changes; concurrent access from 16 threads results in exactly one load (patch the loader and count calls); health endpoint with empty DB → 503.

ACCEPTANCE
- `pytest -q` green.
- In a Django shell: time `get_index()` cold (must be < 1 s) and warm (< 1 ms). Paste the timings.
- `curl localhost:8000/api/v1/health` shows stations count and data_version.

DO NOT: use the ORM per request; use global mutable state other than the singleton; use pandas at runtime.
COMMIT: `feat(stations): thread-safe in-memory station index`
~~~

---

## P3 — Geo primitives & corridor matcher

~~~text
ROLE: Numerical/geospatial Python engineer.

READ FIRST: AGENTS.md, docs/ARCHITECTURE.md §6.1–6.3, §8.

GOAL: Pure (no Django imports) geo library that turns a route polyline into mile-marked samples and finds candidate stations within a corridor — all in memory, no API calls.

STEPS
1. `apps/geo/distance.py`: EARTH_RADIUS_MILES = 3958.7613; vectorized `haversine_miles`; `to_unit_vectors(lat, lng)`; `miles_to_chord(m)`, `chord_to_miles(c)` (chord = 2·sin(θ/2), θ = miles / R). Document units.
2. `apps/geo/resample.py`:
   - `cumulative_miles(lat, lng)`.
   - `scale_to_provider(cum, provider_miles)`: scale so last == provider distance; guard zero/NaN; raise ValueError if geometry length differs from provider distance by more than 5% (log a warning between 1–5%).
   - `resample(lat, lng, step_miles=0.5) -> RouteSamples(lat, lng, mile, total_miles)` using np.interp over cumulative distance; ALWAYS include the exact last point; must handle routes with < 2 distinct points (raise).
   - `simplify_for_response(coords, max_points=1500)`: Douglas–Peucker (iterative, no recursion depth issues) preserving endpoints; if already ≤ max_points return unchanged.
3. `apps/geo/corridor.py`: `match_corridor(samples: RouteSamples, station_unit_vectors, buffer_miles) -> Candidates(station_idx, mile_marker, offset_miles)` using scipy cKDTree over sample unit vectors with `distance_upper_bound=miles_to_chord(buffer)`. Return arrays sorted by (mile_marker, offset). Also `widening_schedule(env)` parses CORRIDOR_MILES "10,25,50".
4. `apps/geo/bounds.py`: `in_supported_us(lat, lng)` using contiguous-US bbox (lat 24.3–49.5, lng −125.1…−66.8) plus an explicit rejection of obvious Canada/Mexico points via a coarse polygon of the US border simplified to ≤ 60 vertices (build from well-known state extreme points; document its coarse nature and add tests for Toronto, Vancouver, Montreal (reject) and Detroit, Buffalo, Seattle, El Paso, San Diego, Miami, Key West (accept)). If unsure a point is inside, accept it (the routing provider will reject impossible routes).
5. Tests (tests/unit/):
   - Haversine known pairs (NYC–LA ≈ 2,445 mi great circle ±10; equator 1° lng ≈ 69.17 mi).
   - resample: mile markers strictly increasing, spacing ≤ step, last point exact, total preserved, works across antimeridian-free US extents; degenerate input raises.
   - simplify: endpoints preserved, max deviation < 0.05 mi on a synthetic curve, size cap respected.
   - corridor: construct a straight west-east route and synthetic stations at known offsets (0, 5, 9.9, 10.1 miles) → only ≤ 10 included with correct offsets (±0.3 mi due to 0.5-mi sampling) and mile markers (±0.3).
   - property (hypothesis): matched offsets never exceed the buffer; mile_marker within [0, total].
   - benchmark test (marked slow, not in CI default): 10k-sample route × 6.6k stations completes in < 50 ms median.

ACCEPTANCE: `pytest tests/unit -q` green; paste the benchmark numbers.
DO NOT: import Django; use shapely/geopandas (avoid heavy deps); project to planar coordinates.
COMMIT: `feat(geo): route resampling and corridor matcher`
~~~

---

## P4 — Providers, call budget, resolver, cache

~~~text
ROLE: Backend engineer specializing in resilient third-party integrations.

READ FIRST: AGENTS.md, docs/SCOPE.md §4 (D9, D10), docs/ARCHITECTURE.md §6.5, §5.

GOAL: Route + geocode providers behind small protocols, a strict per-request call budget, and an endpoint resolver that avoids external calls whenever possible.

FIRST, VERIFY (do not trust memory): fetch and read the current docs for (a) OSRM HTTP API `route` service (project-osrm.org / the demo server usage policy) and (b) OpenRouteService directions v2 `driving-car/geojson` (auth header format, request body, response shape) and (c) Nominatim search API + usage policy. Put the URLs and any deviations from ARCHITECTURE §6.5 in docs/DECISIONS.md.

STEPS
1. `apps/providers/errors.py`: NoRouteError, UpstreamError, UpstreamTimeout, BudgetExceeded, LocationNotFound (each with `.code`, `.http_status`).
2. `apps/providers/budget.py`: `CallBudget(max_calls)` with `consume(provider, purpose)`; records `[{provider, purpose, ms, status}]`; raises BudgetExceeded when exceeded; `calls` property. Created per request (never global).
3. `apps/providers/base.py`: dataclasses `LatLng`, `RouteResult(distance_miles, duration_minutes, lat: np.ndarray, lng: np.ndarray, provider)`, `GeocodeResult(lat, lng, label, source)`; Protocols `RouteProvider`, `Geocoder`.
4. `osrm.py`: pooled module-level `httpx.Client` (timeouts: connect 3 s, read = UPSTREAM_TIMEOUT_S), request per ARCHITECTURE §6.5 with geometries=geojson & overview=full; convert meters→miles (1609.344), seconds→minutes; handle `code != "Ok"` (`NoRoute` → NoRouteError; other → UpstreamError); validate the coordinates array (≥ 2 points, finite, inside sane bounds).
5. `ors.py`: only active if ORS_API_KEY set; per verified docs; map 401/403/429 → UpstreamError (no retry).
6. `nominatim.py`: free-text geocoding, `countrycodes=us`, `limit=1`, User-Agent header required; cache hits in Django cache (30 days); consumes budget.
7. `fixture.py`: `ROUTING_PROVIDER=fixture` reads `tests/fixtures/routes/{slug}.json` where slug derives from rounded endpoints; raise clear error if missing. Add `scripts/record_fixtures.py` that (manually, one-time) records real OSRM responses for: Chicago→Dallas, New York→Los Angeles, Chicago→St. Louis (short), Seattle→Miami, and a NoRoute case (New York→Honolulu coordinates). Run it ONCE with the network on and commit the JSON fixtures (keep each < 1.5 MB; if larger, store gzipped and read via gzip).
8. `apps/providers/routing.py`: `get_route(start, finish, budget)` implementing: try primary; on timeout/5xx retry once only if `budget` remains; then fallback provider if configured; else raise. Never exceed the budget. Route result cached under `route:v1:{lat1:.4f},{lng1:.4f}:{lat2:.4f},{lng2:.4f}` for CACHE_TTL_S (store as compressed bytes or npz-like structure to keep cache small).
9. `apps/geo/resolver.py` (may import Django settings/cache but no models): `resolve_location(value, budget) -> ResolvedLocation(lat, lng, label, source, query)`:
   a. dict `{lat,lng}` or string "lat,lng" (detect swapped: |lat|>90 and |lng|<=90 → swap and add warning) → source "coordinates".
   b. string "City, ST" (also "City ST", "City, State Name") → look up in the Gazetteer index built from `stations` cities plus the Census place file (lazy-loaded, ~30k entries, cached in process). Source "gazetteer". 0 external calls.
   c. anything else → Nominatim (counts 1 call). Reject if outside supported US (apps/geo/bounds).
   Raise LocationNotFound / OutsideUSA accordingly.
10. Tests (respx, no network): each provider success + malformed JSON + timeout + 5xx + NoRoute; retry only once; fallback engaged; budget exhaustion at call #4; resolver for all input shapes (incl. swapped lat/lng, "Springfield" without state → falls to Nominatim mock, Toronto → OutsideUSA); route cache hit means zero HTTP calls; `meta`-style call log correct.

ACCEPTANCE: `pytest tests/unit tests/integration -q -k "provider or resolver or budget"` green; paste a table of scenario → external calls consumed.
DO NOT: perform real network calls in tests; store API keys in code; call ORS unless the key is configured; call a geocoder for coordinates or a resolvable "City, ST".
COMMIT: `feat(providers): osrm/ors/nominatim, call budget, resolver, route cache`
~~~

---

## P5 — Optimizer (the core)

~~~text
ROLE: Algorithms engineer. Correctness over cleverness.

READ FIRST: AGENTS.md, docs/ARCHITECTURE.md §7 (the algorithm is specified there — implement it faithfully), docs/SCOPE.md §4 (D4–D8, D11).

GOAL: An exact, fast, pure-Python/numpy fuel-stop optimizer and an independent validator.

REFERENCE: `docs/reference/optimizer_prototype.py` is a VALIDATED prototype (matches a brute-force LP oracle on 300 random instances, 0 mismatches). PORT it — same algorithm, same tie-break EPS — into production code with typing, dataclasses, Decimal money and the edge-case handling below; do not redesign the algorithm. Turn its oracle into the pytest oracle test.

STEPS
1. `apps/planner/schemas.py`: frozen dataclasses: `Candidate(station_idx, opis_id, mile_marker, offset_miles, price)`, `PlanStop(sequence, station_idx, opis_id, mile_marker, offset_miles, detour_miles, price, units_bought, gallons, cost_usd, fuel_on_arrival_gal, fuel_after_gal)`, `StartFill(units, gallons, price, cost_usd)`, `Plan(stops, start_fill, total_cost_usd, total_gallons, total_units, feasible, corridor_used)`.
2. `apps/planner/optimizer.py`: `optimize(candidates, route_miles, max_range_miles, mpg, start_mode, start_price, detour_factor, safety_reserve_miles=0) -> Plan | Infeasible(gap info)` implementing ARCHITECTURE §7 EXACTLY: integer-mile grid, G = floor(max_range − 1 − reserve), M_i = round(mile_marker), k_i = ceil(detour_factor·offset), sorted by (M, price, opis_id), prefix-min trick with argmin index array, per-visit EPS = 1e-4, virtual start node for priced/free modes, backward reconstruction. Handle: zero candidates (trip ≤ G in priced mode = buy all at start price; otherwise Infeasible), L > G legs (Infeasible with the gap's mile range), candidates at identical M, k_i > G (skip), M_i outside [0, M_D] (skip). Return the largest uncovered gap `(from_mile, to_mile)` on infeasibility for the error `details`.
   Money: compute stop costs with Decimal (gallons = Decimal(units)/Decimal(mpg); cost = (gallons × Decimal(price)).quantize(0.01, ROUND_HALF_UP)); total = sum of stops (+ start fill).
3. `apps/planner/simulate.py`: `validate_plan(plan, route_miles, candidates_by_idx, max_range, mpg, detour_factor)` replays with FLOAT distances (not the rounded grid): fuel never < −1e-9 nor > tank; every leg between consecutive route positions ≤ max_range; sum of purchases matches; recomputes totals with Decimal; asserts `abs(total_gallons*mpg − (route_miles + sum(detours))) ≤ 1.0`; raises `PlanInvalid` with detail on any violation.
4. `apps/planner/search.py`: `plan_with_widening(matcher, samples, index, params)` looping the corridor schedule (10, 25, 50), returning the first feasible plan (+ warnings), else Infeasible for the widest corridor.
5. TESTS — this is where correctness is proven:
   - `tests/unit/test_optimizer_basic.py`: hand-computed scenarios (write the expected answers by reasoning, in comments): single cheap station mid-route; two stations where the cheaper one is beyond range; equal prices → fewest stops; expensive start price with cheap first station; free-start mode; trip shorter than range with/without a cheaper station in reach; big detour makes a "cheap" station not worth it; leg exactly at limit; leg 1 mile over → Infeasible.
   - `tests/unit/test_optimizer_oracle.py`: a brute-force ORACLE (enumerate all stop subsets ≤ 8 candidates; for each subset solve the purchase amounts by `scipy.optimize.linprog` in the same integer-mile model incl. detour burn and start node) — DP cost must equal oracle cost (abs tol 1e-6) on ≥ 200 seeded random instances (vary prices, offsets, spacing, range). Print a summary of how many instances were feasible/infeasible; ensure both cases occur.
   - `tests/property/test_optimizer_props.py` (hypothesis): plan always passes `validate_plan`; DP cost ≤ greedy-next-cheaper baseline and ≤ fill-at-every-stop baseline (implement both baselines in the test helpers); adding a strictly cheaper candidate never increases cost; scaling all prices by a constant scales cost by the same constant; deterministic across repeated runs.
   - Performance test (slow marker): n = 1,500 candidates, G = 499 → median < 100 ms.
6. Write a short `docs/OPTIMIZER.md` explaining the DP with one worked numeric example (small) that matches a unit test.

ACCEPTANCE: `pytest tests/unit tests/property -q` green; paste the oracle summary line (instances, feasible, max abs diff) and the perf numbers.
DO NOT: use a greedy-only solution; use floating-point equality for money; mutate inputs; skip the oracle test.
COMMIT: `feat(planner): exact DP optimizer, validator, oracle tests`
~~~

---

## P6 — Service orchestration & HTTP API

~~~text
ROLE: Django API engineer.

READ FIRST: AGENTS.md, docs/SCOPE.md §6 & §8, docs/ARCHITECTURE.md §5, §10, §12, §13.

GOAL: The public API: JSON endpoint, map page, uniform errors, headers, caching.

STEPS
1. `apps/planner/service.py::plan_trip(request_params) -> TripPlan` orchestrating: resolve (P4) → result-cache lookup → route (P4, cached) → `scale_to_provider` + `resample` (P3) → `plan_with_widening` (P5) → `validate_plan` → assemble. Start price for START_MODE=priced: `median_price_in_window` over candidates with mile ≤ 100 (fallback national median). Collect timings per stage and `warnings` (widened corridor, swapped coords, ambiguous match, price outlier stops).
   Same-location guard: if straight-line distance < 0.5 mi → SameLocation.
2. `apps/api/validators.py`: parse GET query or POST JSON (`application/json`, ≤ 4 KB): start/finish as string or {lat,lng}; overrides `max_range_miles` 50–1000, `mpg` 1–100, `geometry` ∈ {full, simplified, none}; strings ≤ 200 chars, trimmed, NFC-normalized; reject unknown fields with a clear message listing allowed ones; clear per-field errors in `details`.
3. `apps/api/views.py`:
   - `route_view` (GET+POST, csrf_exempt), `route_map_view` (GET), `health_view`.
   - JSON response per ARCHITECTURE §12: include `request`, `route` (GeoJSON LineString, bbox, provider), `fuel_plan` (assumptions incl. corridor_miles_used, start_fill, stops with all fields listed in SCOPE/ARCH, totals), `map` (html_url + GeoJSON FeatureCollection with route, start, finish, stops with properties), `meta` (request_id, external_calls, external_calls_detail, cache: hit|miss|route-hit, timings_ms, data_version, warnings).
   - Money serialized as JSON numbers with 2 decimals for USD (use Decimal → float via quantize) and 3–4 decimals for $/gal; gallons rounded to 2 decimals for display but computed exactly.
   - Compact JSON (`separators=(",",":")`), `Content-Type: application/json`.
4. `apps/api/templates/api/map.html`: Leaflet (pinned CDN version with SRI hash), OSM tiles with attribution, fit bounds, route polyline, start (green) / finish (red) / numbered stop markers with popups (name, city, state, price/gal, gallons, cost, mile marker), summary panel with totals & assumptions & warnings; responsive; no inline secrets; escape all dynamic text (Django autoescape; JSON via `json_script`). It calls the same `plan_trip` (cache makes it free).
5. `apps/api/errors.py`: one handler/decorator translating domain exceptions to SCOPE §6 codes and statuses in the uniform envelope with `request_id`; unexpected exceptions → 500 `INTERNAL_ERROR` (logged with traceback, never leaked). Wrong method → 405 in the same envelope. Unknown route under /api/v1/ → 404 envelope.
6. `apps/api/middleware.py`: RequestIdMiddleware (accept inbound X-Request-ID if ≤ 64 safe chars), timing → `Server-Timing`, `X-External-Calls` header (read from a request-scoped attribute), simple cache-based per-IP rate limit (RATE_LIMIT_PER_MIN, disabled when 0).
7. `apps/api/openapi.yaml`: hand-written OpenAPI 3.1 for all endpoints, schemas and error codes; add a test that loads the YAML and asserts every documented error code exists in code and vice-versa.
8. Integration tests (fixture provider, in-memory cache cleared per test), tests/integration/:
   - Chicago→Dallas, NYC→LA, Chicago→St. Louis: 200; schema keys; `meta.external_calls == 1`; invariants (no leg > range; totals equal Σ stops; stops ordered by mile marker; `|gallons×mpg − (route+detours)| ≤ 1`).
   - Second identical request → `external_calls == 0`, `cache == "hit"`, identical body except `meta`.
   - Map endpoint returns 200 HTML containing each stop name and the route; second call adds 0 external calls.
   - Errors: missing field, bad JSON, oversize string, invalid overrides, Toronto → OUTSIDE_USA, unresolvable text (mock Nominatim empty) → LOCATION_NOT_FOUND, NYC→Honolulu coords → NO_ROUTE, same point → SAME_LOCATION, forced infeasible (fixture with an artificially sparse index) → NO_FEASIBLE_PLAN with gap details, provider timeout twice → 504, budget exceeded → 502.
   - Headers present: X-Request-ID, X-External-Calls, Server-Timing.
   - GET and POST produce identical results.
9. Manually run the server with ROUTING_PROVIDER=osrm ONCE (network on) to confirm the real OSRM response parses and the plan is sane for NYC→LA; paste the response summary (distance, stops, total cost, external_calls, total ms).

ACCEPTANCE: `pytest -q` green; `curl -s -X POST localhost:8000/api/v1/route -H 'content-type: application/json' -d '{"start":"New York, NY","finish":"Los Angeles, CA"}' | jq '.fuel_plan.totals, .meta.external_calls'` shows sane numbers and 1 call; open the map URL in the Antigravity browser and screenshot it for the walkthrough.
DO NOT: add DRF; query the DB per request; make more than 1 external call for `City, ST` / coordinate inputs; leak stack traces; return 200 with an error body.
COMMIT: `feat(api): route endpoint, map page, error envelope, headers`
~~~

---

## P7 — Hardening, performance, edge cases

~~~text
ROLE: Staff engineer doing a performance + reliability pass.

READ FIRST: AGENTS.md, docs/SCOPE.md §7–8, docs/ARCHITECTURE.md §8.

GOAL: Prove and, if needed, improve speed; close every edge case in SCOPE §8.

STEPS
1. `scripts/bench.py`: with ROUTING_PROVIDER=fixture, run N=50 cold (cache cleared each time) and N=200 warm requests for Chicago→Dallas and NYC→LA via Django's test client (no HTTP server) and again via a live `gunicorn` (2 workers) using httpx; print p50/p95/p99, per-stage timing (from meta.timings_ms) and response size. Save the output to docs/PERFORMANCE.md.
2. Targets (SCOPE §7): warm p50 < 50 ms, p95 < 150 ms; cold compute overhead (excluding upstream) < 250 ms; response < 300 KB default. If a target is missed, profile (cProfile / py-spy) and fix the top offender (likely JSON serialization of geometry, KD-tree build, or per-station Python loops). Re-measure and record before/after.
3. Edge-case tests for SCOPE §8 items 1–15; add any missing. Specifically ensure: 500.4-mile route works with the 1-mile margin; identical-coordinate station ties are deterministic; unicode/whitespace/mixed-case inputs; concurrent requests (20 threads, same and different routes) return correct, consistent results and never exceed the call budget; cache stampede protection (two simultaneous cold requests for the same route make at most 1 upstream call — implement a simple per-key lock in routing.py using the cache `add` primitive or a threading lock + double-checked cache read).
4. Failure injection: provider 500, timeout, invalid JSON, empty geometry, NaN coordinates, geometry length vs distance mismatch > 5% → correct error codes, no 500s, budget respected.
5. Security pass: `DEBUG=False` behaviour, ALLOWED_HOSTS, request body size limit, no reflected unescaped input in the HTML map (test with `<script>` in a location string), `python manage.py check --deploy` — fix or justify every warning in docs/DECISIONS.md.
6. Coverage: `pytest --cov=apps --cov-report=term-missing` — ≥ 90% for apps/planner, apps/geo, apps/providers; add tests for uncovered branches.
7. Add `ruff` + `mypy` (if configured) to CI; fix findings.

ACCEPTANCE: paste bench output tables, the coverage summary, and `manage.py check --deploy` output. All green.
DO NOT: optimize prematurely without a measurement; weaken assertions to make tests pass; add caching layers that could return stale data across `data_version` changes.
COMMIT: `perf/test: benchmarks, edge cases, failure injection, hardening`
~~~

---

## P8 — README, Postman, Loom script, submission packaging

~~~text
ROLE: Developer advocate + release engineer. The reviewer will judge this repo in 5 minutes.

READ FIRST: AGENTS.md, docs/SCOPE.md, docs/ARCHITECTURE.md.

GOAL: A repository and demo kit a hiring manager can run in under 2 minutes.

STEPS
1. README.md (concise, scannable): what it does; 30-second quickstart (`git clone`, `make setup`, `make run`, one `curl`); example request/response (real output from the fixture run, truncated geometry); how it meets each requirement (table mirroring SCOPE §2); **Assumptions D1–D13 in plain English with the START_MODE and price-policy explanation**; architecture diagram (Mermaid from ARCHITECTURE §1); external-call budget explanation (1 call typical, max 3, cache); performance numbers (from docs/PERFORMANCE.md); data pipeline explanation and QA numbers (from geocode_report.md); testing instructions; limitations & future work; verified Django version.
2. `docs/postman/fuelroute.postman_collection.json` (Postman v2.1) + `fuelroute.postman_environment.json` with `base_url`. Folders:
   - "Happy path": Short trip (Chicago, IL → St. Louis, MO), Medium (Chicago, IL → Dallas, TX), Cross-country (New York, NY → Los Angeles, CA), Coordinates input, Free-text address input, GET variant, Map URL.
   - "Options": custom range/mpg, geometry=none, START_MODE note.
   - "Errors": validation error, outside USA (Toronto), no route (NYC → Honolulu), same location, not found.
   Each request has Postman tests (pm.test) asserting status, `fuel_plan.totals.total_fuel_cost_usd` is a number, `meta.external_calls <= 3`, stops ordered by mile marker, and no gap > 500 between consecutive stops (compute in the test script). Include a Postman *visualizer* script on the cross-country request that draws a small table of stops and totals.
   Validate the collection by running it with `newman` against a live local server (fixture provider) — paste the newman summary.
3. `docs/LOOM_SCRIPT.md`: a timed 5:00 script:
   0:00–0:30 problem + the three things graded (correctness, speed, few API calls).
   0:30–2:45 Postman demo: short trip, Chicago→Dallas, NYC→LA — show `total_fuel_cost_usd`, `stops`, `meta.external_calls: 1`, `Server-Timing`, repeat call = 0 calls (`cache: hit`), open the map URL in the browser, one error case.
   2:45–4:30 code tour in this order: data pipeline artifact + QA report (why coordinates were missing and how solved) → `providers/routing.py` (call budget) → `geo/corridor.py` → `planner/optimizer.py` DP (explain in 30 seconds with the diagram) → tests (oracle).
   4:30–5:00 assumptions (start-tank policy, lowest price per station, city centroids) + future work.
   Include exact URLs/commands to have pre-typed and a pre-flight checklist (server running, cache warm, fixtures vs live OSRM, browser tab with the map, Postman collection imported, notifications off).
4. Repo hygiene: LICENSE (MIT), CONTRIBUTING not needed, `.github/workflows/ci.yml` green badge in README, a clean commit history (squash fixups), no large binaries (> 5 MB), no secrets (run `git ls-files | xargs grep -nEi "api[_-]?key|secret|token" ` and explain each hit).
5. `docs/SUBMISSION_EMAIL.md`: a short reply email to Ena template with placeholders for the GitHub URL and Loom URL, 4 bullet summary of highlights (1 routing call, exact optimizer verified against an oracle, offline geocoding pipeline, latency numbers).

ACCEPTANCE: fresh-clone test — clone into a temp dir, `make setup && make run` with NO env vars, run the newman collection, all green; paste output. README renders correctly (check Mermaid + tables).
DO NOT: claim numbers you did not measure; leave TODOs in docs; include the Census zip files.
COMMIT: `docs: readme, postman collection, loom script, submission kit`
~~~

---

## P9 — Cold adversarial audit (fresh conversation, no prior context)

~~~text
ROLE: Skeptical principal engineer performing a pre-submission code review for a hiring assessment. You did NOT write this code. Your job is to find flaws, not to praise.

READ: AGENTS.md (Part A), docs/SCOPE.md, docs/ARCHITECTURE.md, then the whole repository.

AUDIT CHECKLIST — for each item output PASS / FAIL / RISK with evidence (file:line or command output). Actually RUN commands; do not infer.

A. Requirements
 1. Latest stable Django in use? (`pip show django`; compare with djangoproject.com/download.) 
 2. Start & finish anywhere in USA accepted (City, ST / address / lat,lng)?
 3. Map returned (GeoJSON + working HTML page)? Open the page in the browser and screenshot.
 4. Multiple fuel stops for > 500 mi routes; no leg exceeds 500 mi (verify with an independent script that does not import the project's optimizer).
 5. Total cost = Σ(gallons × price) with 10 MPG; independently recompute for NYC→LA from the JSON output.
 6. External calls: log/measure for 20 different inputs; typical must be 1, max 3.
 7. Fuel CSV actually used (trace a station from the CSV → artifact → DB → response).

B. Correctness
 8. Re-derive the optimum for 3 small synthetic cases by hand and compare to the optimizer.
 9. Try to break the optimizer: identical stations, zero candidates, leg = 500 / 501 miles, negative/NaN prices, huge detours. Report crashes.
10. Data: confirm no Canadian stations in the DB; no duplicate opis_id; coordinates inside the US; geocode coverage ≥ 98%; spot-check 10 random stations' coordinates against known city locations.
11. Money rounding: totals equal the sum of displayed stop costs to the cent.

C. Performance
12. Reproduce docs/PERFORMANCE.md numbers ±20%. Any request path touching the DB or doing per-station Python loops?

D. Robustness & security
13. Fuzz the API with 50 malformed inputs (types, unicode, huge strings, SQL/HTML injection, swapped coords). Any 500s? Any reflected HTML in the map page?
14. Provider failure modes (kill network → what happens?). Budget enforced?
15. `manage.py check --deploy`; secrets scan; `DEBUG` default; ALLOWED_HOSTS.

E. Quality
16. `ruff`, tests, coverage numbers reproduce. Flaky tests? (run the suite 3×.)
17. README accuracy: every number and claim traceable; quickstart works from a fresh clone with no env.
18. Dead code, TODOs, commented-out code, unused deps.

OUTPUT: (1) a table of all 18 items with PASS/FAIL/RISK; (2) a prioritized list of defects with minimal reproduction steps; (3) fix every FAIL and every high-severity RISK yourself in small commits (`fix:`), re-run the affected checks, and (4) a final "ready to submit: YES/NO" with remaining risks. Do not mark PASS without evidence.
~~~

---

## Appendix — Quick reference for reviewers of this plan

| Item | Value |
|---|---|
| Django | 6.1.x (verify at build time) |
| Range / MPG / Tank | 500 mi / 10 / 50 gal (DP grid uses 499 usable miles for rounding safety) |
| Stations | 6,626 unique US stations (from 8,151 raw rows; 620 Canadian rows dropped) |
| Routing | OSRM demo primary, ORS optional fallback; typical 1 call, hard cap 3 |
| Optimizer | Exact DP on a 1-mile fuel grid, O(n·G), oracle-verified |
| Endpoints | `POST/GET /api/v1/route`, `GET /api/v1/route/map`, `GET /api/v1/health` |
