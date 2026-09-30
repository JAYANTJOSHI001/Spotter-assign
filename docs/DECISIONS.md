# DECISIONS.md — FuelRoute Architecture & Provider Decisions

## 1. Upstream Routing & Geocoding Provider Specifications (Verified Phase P4)

### 1.1 OSRM Route Service
- **Endpoint**: `GET {OSRM_BASE_URL}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson&steps=false&alternatives=false`
- **Default Base URL**: `https://router.project-osrm.org`
- **Documentation**: https://project-osrm.org/docs/v5.24.0/api/#route-service
- **Coordinates Order**: Longitude first, then latitude (`{lng},{lat}`).
- **Success Response Shape**:
  ```json
  {
    "code": "Ok",
    "routes": [
      {
        "distance": 123456.7, // meters
        "duration": 5432.1,   // seconds
        "geometry": {
          "type": "LineString",
          "coordinates": [[-87.6298, 41.8781], ...]
        }
      }
    ],
    "waypoints": [...]
  }
  ```
- **Error Conditions**:
  - `code == "NoRoute"`: Map to `NoRouteError` (HTTP 422 `NO_ROUTE`).
  - Other codes or HTTP status >= 400: Map to `UpstreamError` (HTTP 502).
- **Usage Policy**: Public demo server is shared infrastructure with strict per-IP rate limits and no SLA. Must enforce timeouts (connect 3s, read 8s), single retry only on timeout/5xx, and extensive caching.
- **Deviations from ARCHITECTURE §6.5**: None. Specification confirmed exact.

### 1.2 OpenRouteService (ORS) Directions v2
- **Endpoint**: `POST https://api.openrouteservice.org/v2/directions/driving-car/geojson`
- **Documentation**: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/geojson/post
- **Auth & Headers**:
  - `Authorization: <ORS_API_KEY>` (in request header)
  - `Content-Type: application/json`
  - `Accept: application/json, application/geo+json`
- **Request Body**:
  ```json
  {
    "coordinates": [[lng1, lat1], [lng2, lat2]]
  }
  ```
- **Success Response Shape**:
  GeoJSON `FeatureCollection`:
  ```json
  {
    "type": "FeatureCollection",
    "features": [
      {
        "properties": {
          "summary": {
            "distance": 123456.7, // meters
            "duration": 5432.1    // seconds
          }
        },
        "geometry": {
          "type": "LineString",
          "coordinates": [[lng1, lat1], ...]
        }
      }
    ],
    "bbox": [...]
  }
  ```
- **Error Handling**:
  - HTTP 401 / 403 / 429: Map to `UpstreamError` (no retry; indicates missing key, invalid key, or quota exhausted).
- **Activation**: Active only when `ORS_API_KEY` environment variable is set.
- **Deviations from ARCHITECTURE §6.5**: None.

### 1.3 Nominatim Search Service
- **Endpoint**: `GET {NOMINATIM_BASE_URL}/search`
- **Default Base URL**: `https://nominatim.openstreetmap.org`
- **Documentation**: https://nominatim.org/release-docs/develop/api/Search/ and https://operations.osmfoundation.org/policies/nominatim/
- **Query Parameters**: `q={query}&format=jsonv2&countrycodes=us&limit=1`
- **Headers**: Mandatory custom `User-Agent` (from `NOMINATIM_USER_AGENT` env var). Stock library user-agents receive HTTP 403.
- **Usage Policy**: Max 1 request per second. Heavy caching required (cached in Django cache for 30 days). Used only for free-text geocoding fallback (offline gazetteer handles `City, ST` with 0 calls).
- **Deviations from ARCHITECTURE §6.5**: None.

---

## 2. Location Resolver Priority (SCOPE D10)
1. **Coordinates input** (`{lat, lng}` or string `"lat, lng"`): 0 external calls. Validates coordinate bounds. Detects swapped coordinates (e.g., `|lat| > 90` and `|lng| <= 90`) and swaps with warning.
2. **City, State input** (`"City, ST"`, `"City ST"`, `"City, State Name"`): 0 external calls. Resolved via in-memory offline gazetteer loaded from clean stations and census data (~30k place entries).
3. **Free-text address fallback**: 1 external call to Nominatim with `countrycodes=us`. Results cached for 30 days.
4. **Boundary Validation**: Resolved coordinates checked against contiguous US bounds + 60-vertex boundary polygon (`in_supported_us`). Points in Canada/Mexico raise `OutsideUSA` (HTTP 422).

---

## 3. Deployment Security Checklist & Warning Justifications (`manage.py check --deploy`)

When running `python manage.py check --deploy`, Django issues three security warnings that are justified by architectural design:
1. `security.W004 (SECURE_HSTS_SECONDS)`: In production deployments (e.g. AWS ALB, Cloudflare, Nginx reverse proxy, Docker Swarm), HSTS headers are terminated and injected at the ingress/reverse-proxy layer to ensure HTTP-to-HTTPS enforcement without double-header conflicts.
2. `security.W008 (SECURE_SSL_REDIRECT)`: Similarly, TLS termination and HTTPS redirection are managed at the edge reverse proxy / load balancer. Managing this outside Python worker processes improves throughput and allows internal container health checks over plain HTTP.
3. `security.W009 (SECRET_KEY length/dev default)`: In non-DEBUG production runs, `SECRET_KEY` is strictly required via the `SECRET_KEY` environment variable (an error is raised on startup if missing or using default). In local development and automated testing, an insecure dev fallback key is permitted for zero-configuration out-of-the-box evaluation.
