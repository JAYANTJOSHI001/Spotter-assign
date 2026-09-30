# FuelRoute Demo Video Script (5:00 Walkthrough)

Target Duration: Exactly 5 minutes.
Tone: Confident, technical, focused on grading criteria (correctness, speed, minimal external calls).

---

## Pre-Flight Checklist (Before Recording)
- [ ] Dev server running (`make run` or `python manage.py runserver`).
- [ ] Cache warmed up.
- [ ] Browser window open with tabs:
  1. Map visualization: `http://localhost:8000/api/v1/route/map?start=Chicago,%20IL&finish=Dallas,%20TX`
  2. Health check: `http://localhost:8000/api/v1/health`
- [ ] Postman open with `FuelRoute API` collection loaded and `FuelRoute Local` environment active.
- [ ] VS Code / editor open with key files bookmarked:
  - `apps/stations/pipeline.py`
  - `apps/providers/routing.py`
  - `apps/geo/corridor.py`
  - `apps/planner/optimizer.py`
  - `tests/unit/test_optimizer_oracle.py`
- [ ] Notifications disabled / Do Not Disturb on.

---

## Timed Script Breakdown

### 0:00 – 0:30 | Introduction & Assessment Focus
- **Screen**: Title slide / VS Code showing `README.md`.
- **Narration**:
  > "Hi everyone, welcome to the walkthrough of the FuelRoute API. The challenge asks us to take an arbitrary start and destination in the United States, query a routing engine, and return the optimal, cost-minimized fuel stops along the path using a 500-mile vehicle range, 10 MPG fuel economy, and real-world fuel prices.
  >
  > In this walkthrough, I want to specifically focus on the three pillars this service was evaluated on:
  > 1. Mathematical correctness of the refueling strategy.
  > 2. Sub-50ms speed.
  > 3. Strict conservation of external API calls — guaranteeing exactly 1 upstream routing call per fresh query, and 0 for cached queries."

---

### 0:30 – 2:45 | Postman Demo & Map UI
- **Screen**: Postman.
- **Actions**:
  1. **Short Trip (Chicago, IL → St. Louis, MO)**:
     - Run request.
     - Show: 298.5 miles (< 500-mile range).
     - Point out: In `priced` start mode, initial fuel is purchased at the start window rate ($3.269/gal) and zero stops are required because it is within one single tank range.
     - Show `meta.external_calls: 1`.
  2. **Medium Trip (Chicago, IL → Dallas, TX)**:
     - Run request.
     - Show: 967 miles, 4 planned stops.
     - Show `total_fuel_cost_usd`: $288.89.
     - Point out `Server-Timing` header: `total;dur=5.2`.
     - **Re-send immediately**:
       - Latency drops to **1.1 ms**.
       - `meta.cache: "hit"`, `meta.external_calls: 0`.
  3. **Cross-Country Trip (New York, NY → Los Angeles, CA)**:
     - Run request.
     - Switch to Postman **Visualize** tab showing the formatted stops table:
       - 2,794 miles, 9 stops, total fuel cost $861.48.
       - Demonstrate that every single consecutive leg (including to destination) is strictly ≤ 500 miles.
  4. **Browser Tab (Interactive Leaflet Map)**:
     - Switch to browser displaying `/api/v1/route/map?start=Chicago,%20IL&finish=Dallas,%20TX`.
     - Highlight:
       - Green start pin (A), Red destination pin (B).
       - Numbered blue fuel stop badges with popups showing station brand, city, retail price, gallons, and leg cost.
       - Responsive summary panel on top-left showing totals, assumptions, and corridor used.
  5. **Error Case**:
     - Send request with `start: "Toronto, ON"` or `43.6532, -79.3832`.
     - Show: Uniform error envelope with `OUTSIDE_USA` (HTTP 422) and `request_id`.

---

### 2:45 – 4:30 | Code Tour
- **Screen**: VS Code editor.
- **Narrative sequence**:
  1. **Data Pipeline & Station Geocoding (`data/stations_geocoded.csv` & `data/geocode_report.md`)**:
     - *Explanation*: The raw fuel price CSV lacked coordinates. We built a deterministic 4-tier geocoding pipeline (Census Place exact → Census County-Subdivision → RapidFuzz ≥ 94 → cached Nominatim fallback).
     - *Key stat*: **99.77% geocode coverage** (6,611 of 6,626 clean US stations), 0 Canadian stations, verified bounding box.
  2. **In-Memory Thread-Safe Station Index (`apps/stations/index.py`)**:
     - Station data (coordinates converted to 3D unit vectors, prices, metadata) loads once into memory.
     - Zero database queries occur on the request path.
  3. **Call Budget & Resolver (`apps/providers/routing.py`, `apps/geo/resolver.py`)**:
     - Every request receives an explicit `CallBudget(max_calls=3)`.
     - `City, ST` inputs resolve against our in-memory 32,000-city gazetteer in 0 ms with **0 external calls**.
     - Routing queries go to OSRM / ORS, with automatic retry and SHA-256 result caching.
  4. **Corridor Matcher (`apps/geo/corridor.py`)**:
     - Route polyline is sampled every 0.5 miles.
     - A spatial `scipy.spatial.cKDTree` matches candidate stations within an adaptive corridor (10 mi → 25 mi → 50 mi).
  5. **Dynamic Programming Optimizer (`apps/planner/optimizer.py`)**:
     - Show the DP algorithm: $O(N \cdot G)$ where $G = 499$ miles.
     - Vectorized prefix-minimum formulation over 1-mile grid states.
     - Accounts for detour burn ($2 \times \text{offset}$).
     - Solves true multi-stop global optimum in under 15 ms.
  6. **Oracle Correctness Test (`tests/unit/test_optimizer_oracle.py`)**:
     - Highlight the mathematical oracle test: 200 randomized route instances solved via exact integer LP (`scipy.optimize.linprog`) versus our DP engine.
     - **0 mismatches, exact cost parity within 1e-6**.

---

### 4:30 – 5:00 | Assumptions & Conclusion
- **Screen**: `README.md` or Summary slide.
- **Narration**:
  > "To wrap up, a quick note on the key assumptions documented in `docs/SCOPE.md`:
  > - **START_MODE**: By default, vehicles depart with fuel priced at the local departure window rate (`START_MODE=priced`), reflecting realistic commercial fleet refueling.
  > - **Station Prices**: The lowest available price per station is resolved deterministically from the raw data.
  > - **Coordinates**: High-precision Census centroids represent each municipality's fueling cluster.
  >
  > The entire service is containerized, runs with zero dependencies beyond pure Python scientific libraries and standard Django 6.1.1, and delivers 100% test coverage across core planning domains.
  >
  > Thank you for your time and review!"
