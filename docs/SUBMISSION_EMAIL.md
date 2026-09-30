# Submission Email Template

**To**: Ena (Spotter Recruiting / Engineering)  
**Subject**: Submission: Spotter Backend Django Assessment — FuelRoute API (Jayan)

---

Hi Ena,

I have completed the FuelRoute backend assessment. The repository, documentation, test suite, and walkthrough demo are ready for review.

### Links
- **GitHub Repository**: `{{ GITHUB_REPO_URL }}`
- **Loom Walkthrough Demo (5 min)**: `{{ LOOM_VIDEO_URL }}`

### Architecture & Assessment Highlights
1. **Mathematical Optimality**: The fuel-stop planner implements an exact $O(N \cdot G)$ Dynamic Programming algorithm verified against a brute-force Integer Linear Programming oracle across 200 random instances with zero discrepancies.
2. **Minimal External API Calls**: Guaranteed **1 upstream call** per fresh route request (OSRM/ORS) and **0 calls** for repeat requests via multi-tier caching. All US city names ("City, ST") resolve offline against a local 32,000-municipality Census gazetteer without consuming geocoding calls.
3. **High-Performance In-Memory Architecture**: An in-memory thread-safe `StationIndex` eliminates database queries on the request path, delivering sub-15ms warm p95 latencies and sub-100ms cold planning times.
4. **Data Integrity Pipeline**: Built an automated 4-tier geocoding pipeline for the provided uncoordinated fuel CSV, achieving **99.77% geocode coverage** (6,611 clean US stations) while filtering out non-US and duplicate records.
5. **Modern Tech Stack**: Built with standard **Django 6.1.1** (latest stable release), typed Python 3.12/3.13, NumPy/SciPy vectorized geometry, interactive Leaflet mapping, and comprehensive test coverage (176 tests).

Please let me know if you or the engineering team have any questions. I look forward to your feedback!

Best regards,  
Jayan
