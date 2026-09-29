"""Brute-force LP Oracle test verifying DP optimizer optimality across >= 200 instances."""

from __future__ import annotations

import itertools
import random

import numpy as np
from scipy.optimize import linprog

from apps.planner.optimizer import EPS, INF, _solve_dp


def brute_force_oracle(
    cands: list[tuple[int, int, float]],
    M_D: int,
    G: int,
    mpg: float,
    p0: float,
    mode: str,
) -> float:
    """Enumerate all 2^n subsets of candidate stations and solve purchase amounts via LP."""
    best_cost = INF
    n = len(cands)

    for r in range(n + 1):
        for sub in itertools.combinations(range(n), r):
            nodes = [(0, 0, p0)] + [cands[i] for i in sub]
            m = len(nodes)
            cost_coeffs = [nodes[j][2] / mpg for j in range(m)]

            A_ub: list[list[float]] = []
            b_ub: list[float] = []

            pos = [nodes[j][0] for j in range(m)]
            ks = [nodes[j][1] for j in range(m)]

            for j in range(m):
                # Fuel on arrival at node j after detour burn >= 0
                # sum_{t < j} x_t - pos[j] - sum_{t <= j} k_t >= 0
                # => - sum_{t < j} x_t <= - (pos[j] + sum_{t <= j} k_t)
                row_arrive = [-1.0 if t < j else 0.0 for t in range(m)]
                A_ub.append(row_arrive)
                b_ub.append(-(pos[j] + sum(ks[: j + 1])))

                # Fuel after buy at node j <= G
                # sum_{t <= j} x_t - pos[j] - sum_{t <= j} k_t <= G
                row_cap = [1.0 if t <= j else 0.0 for t in range(m)]
                A_ub.append(row_cap)
                b_ub.append(G + pos[j] + sum(ks[: j + 1]))

            # Arrive at destination:
            # sum_{t < m} x_t - M_D - sum_{t < m} k_t >= 0
            row_dest = [-1.0] * m
            A_ub.append(row_dest)
            b_ub.append(-(M_D + sum(ks)))

            bounds = [(0.0, None) for _ in range(m)]
            if mode == "free":
                bounds[0] = (float(G), float(G))
                cost_coeffs[0] = 0.0

            res = linprog(cost_coeffs, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
            if res.success:
                sub_cost = res.fun + EPS * len(sub)
                if sub_cost < best_cost:
                    best_cost = sub_cost

    return best_cost


def test_dp_matches_oracle_across_200_instances() -> None:
    random.seed(42)
    np.random.seed(42)

    total_instances = 250
    feasible_count = 0
    infeasible_count = 0
    max_abs_diff = 0.0

    for t in range(total_instances):
        G = random.choice([20, 30, 40, 50])
        M_D = random.randint(15, 120)
        n = random.randint(0, 6)

        raw_cands = [
            (
                random.randint(0, M_D),
                random.randint(0, 4),
                round(random.uniform(2.5, 4.5), 3),
            )
            for _ in range(n)
        ]
        # Sort candidates deterministically
        cands = sorted(raw_cands, key=lambda x: (x[0], x[2]))

        mode = random.choice(["priced", "free"])
        p0 = round(random.uniform(3.0, 4.0), 3)

        dp_result = _solve_dp(cands, M_D, G, 10.0, p0, mode)
        oracle_cost = brute_force_oracle(cands, M_D, G, 10.0, p0, mode)

        if dp_result is None:
            infeasible_count += 1
            assert oracle_cost == INF, (
                f"Instance {t}: DP returned infeasible but Oracle found cost {oracle_cost}"
            )
        else:
            feasible_count += 1
            dp_cost = dp_result[0]
            diff = abs(dp_cost - oracle_cost)
            if diff > max_abs_diff:
                max_abs_diff = diff
            assert diff <= 1e-6, (
                f"Instance {t} mismatch: DP={dp_cost}, Oracle={oracle_cost}, "
                f"diff={diff}, cands={cands}, M_D={M_D}, G={G}, mode={mode}"
            )

    print(
        f"\nORACLE SUMMARY: instances={total_instances}, feasible={feasible_count}, "
        f"infeasible={infeasible_count}, max_abs_diff={max_abs_diff:.2e}"
    )

    # Ensure both feasible and infeasible instances occurred
    assert feasible_count > 50
    assert infeasible_count > 50
    assert max_abs_diff <= 1e-6
