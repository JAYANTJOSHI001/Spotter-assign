import numpy as np
import pytest

from apps.geo.resample import RouteSamples
from apps.planner.schemas import InfeasiblePlan
from apps.planner.search import plan_with_widening
from apps.stations.index import StationIndex


@pytest.fixture
def empty_index():
    return StationIndex(
        opis_id=np.array([], dtype=np.int64),
        lat=np.array([], dtype=np.float64),
        lng=np.array([], dtype=np.float64),
        price=np.array([], dtype=np.float64),
        unit_vectors=np.empty((0, 3), dtype=np.float64),
        metadata=[],
        data_version="test-empty",
    )


def test_plan_with_widening_all_infeasible(empty_index):
    # Route of 800 miles with no stations in corridor
    samples = RouteSamples(
        lat=np.array([40.0, 41.0]),
        lng=np.array([-88.0, -87.0]),
        mile=np.array([0.0, 800.0]),
        total_miles=800.0,
    )
    plan, warnings = plan_with_widening(samples, empty_index, corridors=(10, 25, 50))
    assert not plan.feasible
    assert isinstance(plan, InfeasiblePlan)
    assert plan.corridor_used == 50


def test_plan_with_widening_empty_corridors(empty_index):
    samples = RouteSamples(
        lat=np.array([40.0, 41.0]),
        lng=np.array([-88.0, -87.0]),
        mile=np.array([0.0, 800.0]),
        total_miles=800.0,
    )
    plan, warnings = plan_with_widening(samples, empty_index, corridors=())
    assert not plan.feasible
    assert isinstance(plan, InfeasiblePlan)
    assert plan.corridor_used == 50
