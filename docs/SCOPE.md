# FuelRoute API — Full Scope Document

> Spotter · Backend Django Engineer take-home assessment
> Candidate: Jayant · Brief received: 28 Sep 2026, 20:15 · **Deadline: 3 days → ~1 Oct 2026, 20:15** (aim to ship by the evening of 30 Sep for a buffer)
> Status: SPEC v1.0 — source of truth for every build decision. Companion docs: `ARCHITECTURE.md`, `../AGENTS.md`.

---

## 1. Purpose

Build a Django API that, given a **start** and a **finish** location inside the USA:

1. Returns the driving **route** and a **map** of it.
2. Returns the **optimal (cheapest) fuel stops** along that route using the supplied fuel-price CSV.
3. Respects a vehicle **maximum range of 500 miles** (so long trips need multiple fuel-ups).
4. Returns the **total money spent on fuel** assuming **10 miles per gallon**.

Success is judged on: correctness of the fuel plan, **speed**, **minimal calls to the external map/routing API (1 ideal, 2–3 acceptable)**, use of the **latest stable Django**, code quality, and a ≤ 5 min Loom demo.

## 2. Requirement traceability matrix

| # | Requirement (from brief) | Design decision | Verified by |
|---|---|---|---|
| R1 | API takes start + finish, both in USA | `POST/GET /api/v1/route`; accepts `"City, ST"`, free-text address, or `lat,lng`. USA bounds validation | API tests, Postman folder "Inputs" |
| R2 | Return a **map** of the route | (a) GeoJSON geometry + FeatureCollection in JSON, (b) shareable Leaflet HTML page at `/api/v1/route/map` | Manual + test that HTML contains route/stops |
| R3 | Optimal fuel stops, cost-effective | Exact DP optimizer over the corridor stations (see ARCHITECTURE §7), cross-checked against an independent oracle | `tests/unit/test_optimizer_oracle.py` |
| R4 | Max range 500 mi → multiple fuel-ups | Tank = 500 mi of range; DP enforces no leg > range; adaptive corridor widening if a gap exists | Cross-country test NYC→LA |
| R5 | Total fuel money at 10 MPG | `gallons = miles / 10`; cost = Σ(gallons × station price), `Decimal`, rounded to cents | Invariant tests |
| R6 | Use attached fuel price file | Offline pipeline cleans + geocodes CSV once → committed artifact → DB → in-memory index | Data QA report |
| R7 | Free map/routing API | **OSRM public** (no key, primary) · **OpenRouteService** (optional key, fallback). Geocoding: offline gazetteer first, Nominatim fallback | Provider tests w/ mocks |
| R8 | Latest stable Django | **Django 6.1.x** (6.1.1 released 2 Sep 2026; supports Python 3.12–3.14). Agent must re-verify at build time | `pip show django` in CI |
| R9 | Fast responses | Warm p50 < 50 ms, cold overhead (excl. upstream) < 250 ms; in-memory numpy index + cKDTree | `scripts/bench.py` |
| R10 | Few external API calls | Hard per-request `CallBudget` (max 3). Typical request = **exactly 1**. Result caching → 0 on repeat | Test asserting `external_calls` |
| R11 | Loom + Postman demo (≤ 5 min) | Postman collection + `docs/LOOM_SCRIPT.md` shot list | Deliverable |
| R12 | GitHub code | Clean repo, README, CI, tests | Deliverable |

## 3. Data audit — what the CSV actually contains

File: `fuel-prices-for-be-assessment.csv` — columns: `OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price`.

| Finding | Number / detail | Consequence |
|---|---|---|
| **No latitude/longitude** | Only `Address` (e.g. `I-44, EXIT 283 & US-69`) and `City, State` | **Must geocode offline once.** Cannot geocode at request time (too slow, violates call budget) |
| Total rows | 8,151 | — |
| **Canadian rows** | 620 rows (provinces AB, BC, MB, NB, NS, ON, QC, SK, YT…) | Drop — brief says USA only |
| US rows | 7,531 | — |
| **Duplicate station IDs** | 7,531 rows → **6,626 unique US stations**; 26 exact duplicate rows | Collapse to one row per `OPIS Truckstop ID` |
| Same ID, different prices | 568 stations; mean spread ≈ $0.10, max $0.90 | Policy needed → **D3** |
| Same ID, different names | 227 stations (`PILOT #1243` vs `PILOT TRAVEL CENTER #1243`) | Pick canonical name (longest) |
| Padded whitespace | City values like `"Fort Wayne      "` | `strip()` + collapse spaces |
| States covered | 48 (no AK, HI, DC) | Coverage limit; document it |
| Unique (City, State) pairs | 4,179 (US) | Size of the geocoding job — small |
| Price range | $2.687 – $6.399/gal, mean ≈ $3.50 | Looks like **diesel** (truck stops). Outliers (CA $6.399, AZ $6.039) are kept but flagged |
| Address coverage | ~57% contain `EXIT`; the rest are highway/route only | Address-level geocoding is unreliable → use city centroids |

## 4. Assumptions & decisions (defaults chosen; all overridable via env)

| ID | Decision | Rationale |
|---|---|---|
| **D1** | **Station coordinates = centroid of the station's city/place** (US Census Gazetteer, offline). Unmatched places fall back to Nominatim **once, offline, cached**; still-unmatched stations are excluded and listed in the QA report | The CSV has no coordinates; highway-exit addresses can't be geocoded reliably. Error is typically a few miles → handled by a corridor buffer |
| **D2** | Only US rows are used | Brief |
| **D3** | One station = one row. If a station has several prices, use the **lowest** (`STATION_PRICE_POLICY=min`; also supports `median`, `mean`) | "Best available price"; documented + configurable |
| **D4** | Vehicle: range **500 mi**, **10 MPG** → tank **50 gal** | Brief |
| **D5** | **Start-tank policy**: the vehicle begins at the origin and may fill to the tank limit **at a reference origin price** (`START_MODE=priced`) — median price of candidate stations within the first 100 mi of the route (fallback: national median). Alternative `START_MODE=free` = start with a full tank at $0 | Makes the total cost meaningful for short trips and keeps the invariant `gallons × 10 ≈ miles driven`. **Flagged in the README + Loom** because the brief is ambiguous |
| **D6** | Arrive at the destination with ~0 fuel (no reserve). Optional `SAFETY_RESERVE_MILES` (default 0) | Cheapest by definition; configurable |
| **D7** | A stop is eligible if within a **corridor** of the route: 10 mi → widen to 25 → 50 mi **only if the plan is infeasible** (all in-memory, zero extra API calls) | Handles sparse regions without extra calls |
| **D8** | **Detour model**: leaving the route to a station costs `2 × offset` miles of fuel (`DETOUR_FACTOR=2.0`), burned and paid for | Honest cost accounting; discourages far-off "cheap" stations |
| **D9** | Routing provider: **OSRM public demo primary** (zero setup for reviewers), **ORS fallback if `ORS_API_KEY` set**. One route call per request | ORS free tier needs a key (2,000 directions/day, 40/min) and users reported unexplained 403 "quota exceeded" errors on 26–27 Sep 2026, so it must not be the only path |
| **D10** | Input geocoding order: `lat,lng` → offline `City, ST` lookup → Nominatim (only for free-text) | Typical request = 1 external call; worst case still ≤ 3 |
| **D11** | Money: `Decimal`, per-stop cost rounded half-up to cents; total = sum of rounded stop costs | Displayed numbers add up exactly |
| **D12** | Distance unit = miles; fuel = US gallons | Brief |
| **D13** | Map = Leaflet + OpenStreetMap tiles rendered **in the client browser** (does not count against server-side call budget) | Free, no key |

## 5. Scope

### In scope
- Django 6.1 project, single service, SQLite (Postgres-ready), no auth (assessment).
- Offline data pipeline: clean → geocode → QA report → load into DB.
- Endpoints: `POST|GET /api/v1/route`, `GET /api/v1/route/map`, `GET /api/v1/health`.
- Exact cost-minimizing fuel-stop optimizer with detour accounting.
- Caching (route + result), request-scoped external call budget, timing headers.
- Unit / integration / property tests; benchmark script; CI (GitHub Actions).
- Docs: README, OpenAPI YAML, Postman collection, Loom script.
- Dockerfile + Makefile for one-command run.

### Out of scope (explicitly)
- Authentication, multi-tenant, billing, user accounts.
- Live/real-time fuel prices, other fuel grades, truck-specific routing (height/weight).
- Turn-by-turn directions, ETA with traffic, driver hours-of-service.
- Canada/Mexico, Alaska, Hawaii (not in dataset).
- Frontend beyond the single Leaflet map page.
- Address-level station geocoding (documented as a future improvement).

## 6. API contract (summary — full schema in ARCHITECTURE §12)

### `POST /api/v1/route`
```json
{ "start": "Chicago, IL", "finish": "Dallas, TX" }
```
`start` / `finish` accept: `"City, ST"`, free-text address, `"lat,lng"`, or `{ "lat": 41.87, "lng": -87.62 }`.
Optional overrides (validated, bounded): `max_range_miles` (50–1000), `mpg` (1–100), `geometry` (`full|simplified|none`, default `simplified`).

`GET /api/v1/route?start=...&finish=...` — identical semantics (handy in Postman/browsers).

### Success `200`
`request`, `route` (distance, duration, GeoJSON geometry, bbox, provider), `fuel_plan` (assumptions, ordered `stops[]`, `totals`), `map` (`html_url`, `geojson`), `meta` (`external_calls`, `cache`, `timings_ms`, `warnings[]`).

### Errors — uniform envelope
```json
{ "error": { "code": "NO_FEASIBLE_PLAN", "message": "…", "details": {}, "request_id": "…" } }
```

| HTTP | code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing/invalid params, bad types/ranges, strings > 200 chars |
| 422 | `LOCATION_NOT_FOUND` | Cannot resolve a location |
| 422 | `OUTSIDE_USA` | Resolved point outside supported US bounds |
| 422 | `SAME_LOCATION` | Start and finish resolve to (nearly) the same point (< 0.5 mi) |
| 422 | `NO_ROUTE` | Provider finds no driving route (e.g. NYC → Honolulu) |
| 422 | `NO_FEASIBLE_PLAN` | Even at the widest corridor, a gap > range exists; `details` names the gap (mile markers, nearest states) |
| 429 | `RATE_LIMITED` | Optional per-IP throttle |
| 502 | `UPSTREAM_ERROR` | Provider returned invalid data / 5xx after fallback |
| 504 | `UPSTREAM_TIMEOUT` | Provider timed out after retry/fallback |
| 500 | `INTERNAL_ERROR` | Unexpected; logged with `request_id`, no stack trace to client |

## 7. Non-functional requirements

| Area | Target |
|---|---|
| **Latency** | Warm (cache hit) p50 < 50 ms, p95 < 150 ms · Cold compute overhead excl. upstream < 250 ms · Upstream call timeout 8 s |
| **External calls** | Typical 1, hard max 3 per request (enforced in code + asserted in tests); 0 on cache hit |
| **Startup** | Station index load < 1 s (6.6 k rows) |
| **Memory** | < 250 MB RSS per worker |
| **Correctness** | Optimizer matches oracle on ≥ 200 random small instances; simulation proves fuel never < 0 nor > tank |
| **Determinism** | Same input → same output (stable tie-breaks) |
| **Security** | No secrets in git; `DEBUG=False` by default; `ALLOWED_HOSTS` from env; input length limits; no stack traces to clients |
| **Observability** | Structured logs w/ `request_id`; `X-Request-ID`, `X-External-Calls`, `Server-Timing` headers; `/health` checks DB + index |
| **Quality gates** | `ruff` clean, `pytest` green, coverage ≥ 90 % on `planner`, `geo`, `providers` |

## 8. Edge-case catalogue (each must have a test)

1. Trip < 500 mi (0 or 1 stop; may buy only at origin reference price) — total = D/10 × p₀ or cheaper station if worth the detour.
2. Trip exactly ≈ 500 mi, and 500.4 mi (rounding margin).
3. Cross-country NYC → LA (~2,800 mi → ≥ 5 stops).
4. Start = finish / within 0.5 mi.
5. Free-text address; `"lat,lng"`; swapped lat/lng (detect: lat outside ±90).
6. `"Springfield"` with no state → `LOCATION_NOT_FOUND` from offline lookup, then Nominatim `countrycodes=us`.
7. Canadian/Mexican point → `OUTSIDE_USA`.
8. Sparse corridor (e.g. across NV/UT/WY) → corridor widening; gap > range → `NO_FEASIBLE_PLAN` with details.
9. Many stations sharing identical coordinates (same city) → deterministic tie-break.
10. All prices equal → fewest stops / smallest detour wins.
11. Provider timeout → single retry → fallback provider → `504` with call budget respected.
12. Provider returns huge geometry (≥ 50 k points) → resample, response stays < 300 KB by default.
13. Repeated identical request → 0 external calls, `meta.cache = "hit"`.
14. Unicode / extra whitespace / mixed case in inputs.
15. Concurrent requests (index is read-only, thread-safe).

## 9. Definition of Done

- [ ] `make setup && make run` works on a clean machine with **no API keys**.
- [ ] `POST /api/v1/route` for Chicago→Dallas, NYC→LA, and a < 500 mi trip return valid plans.
- [ ] `meta.external_calls == 1` for coordinate/`City, ST` inputs; ≤ 3 in all cases.
- [ ] Invariants hold on every test route: no leg > range; `|gallons×mpg − (route + detours)| ≤ 1 mi`; totals equal Σ stop costs.
- [ ] Optimizer ≤ greedy baseline cost on every test route, equal to oracle on small instances.
- [ ] Data QA report shows ≥ 98 % of US stations geocoded; unmatched listed.
- [ ] `pytest` green, `ruff` clean, CI green.
- [ ] Postman collection + OpenAPI + README (assumptions D1–D13 spelled out).
- [ ] Loom (≤ 5 min) recorded per `LOOM_SCRIPT.md`; GitHub link + Loom link emailed.

## 10. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| OSRM public demo slow/down | Slow or failed cold requests | 8 s timeout, 1 retry, ORS fallback, cache, recorded fixtures for tests/demo (`ROUTING_PROVIDER=fixture`) |
| ORS quota anomalies (reported 26–27 Sep 2026) | Fallback fails | ORS is optional, not primary |
| City-centroid coordinates are imprecise | Slightly wrong stop position | Corridor buffer + detour accounting; documented limitation; QA report lists match method per station |
| Census place names don't match CSV names (`St.`, `Ft.`, `Mt.`, `-` etc.) | Missed geocodes | Normalization rules + Nominatim fallback + ≥ 98 % gate |
| DRF/other libs lag behind Django 6.1 | Build breaks | **Avoid DRF**; use plain Django views + small validators (fewer deps, faster) |
| Reviewer expects "start tank free" interpretation | Cost differs | `START_MODE` switch + explicit README section |
| Deadline (3 days) | Incomplete | Phased build (AGENTS.md) — P0–P6 are the must-haves; P7–P9 polish |

## 11. Deliverables & timeline

| When | Milestone |
|---|---|
| Day 0 evening (29 Sep) | Docs approved; P0–P1 (bootstrap + data pipeline) |
| Day 1 (30 Sep) | P2–P6 (index, geo, providers, optimizer, API) |
| Day 2 morning (1 Oct) | P7–P8 (tests, perf, docs, Postman, CI) |
| Day 2 midday | Record Loom, final audit (P9), push to GitHub |
| **Before 20:15, 1 Oct** | Reply to Ena with GitHub + Loom links |

## 12. Open questions (defaults already chosen — flip only if Spotter clarifies)

1. Start-tank accounting (D5) — priced-at-origin vs free full tank.
2. Multiple prices per station (D3) — lowest vs median.
3. Whether stops within a city-centroid tolerance are acceptable (D1) or Spotter expects address-level accuracy.
