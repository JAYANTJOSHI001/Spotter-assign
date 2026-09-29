from __future__ import annotations

import random
import time

import pytest

from apps.planner.optimizer import optimize
from apps.planner.schemas import Candidate, Plan


@pytest.mark.slow
def test_optimizer_performance_large_instance() -> None:
    # 1,500 candidates across a 3,000-mile cross-country route, G=499
    rng = random.Random(42)
    n = 1500
    route_miles = 3000.0

    cands: list[Candidate] = []
    for i in range(n):
        mile = rng.uniform(10.0, route_miles - 10.0)
        offset = rng.uniform(0.1, 5.0)
        price = rng.uniform(2.80, 4.50)
        cands.append(
            Candidate(
                station_idx=i,
                opis_id=10000 + i,
                mile_marker=mile,
                offset_miles=offset,
                price=price,
            )
        )

    # 2 Warmup runs
    for _ in range(2):
        optimize(cands, route_miles, max_range_miles=500.0, mpg=10.0, start_mode="priced")

    # Measure 5 runs
    timings_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        plan = optimize(cands, route_miles, max_range_miles=500.0, mpg=10.0, start_mode="priced")
        t1 = time.perf_counter()
        assert isinstance(plan, Plan)
        assert plan.feasible
        timings_ms.append((t1 - t0) * 1000.0)

    median_ms = sorted(timings_ms)[len(timings_ms) // 2]
    print(
        f"\nOPTIMIZER PERF: n={n}, G=499, median={median_ms:.2f} ms (runs: {[round(x, 1) for x in timings_ms]})"
    )
    assert median_ms < 100.0, f"Median time {median_ms:.2f} ms exceeded target 100 ms"
