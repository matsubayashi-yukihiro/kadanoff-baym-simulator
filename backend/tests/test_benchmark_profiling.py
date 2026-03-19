import pytest

from backend.app.solvers.benchmarks import profile_callable

pytestmark = pytest.mark.physics_unit


def test_profile_callable_reports_ranked_entries():
    def sample_workload() -> int:
        total = 0
        for value in range(200):
            total += value * value
        return total

    report = profile_callable(sample_workload, limit=5)

    assert report.wall_time >= 0.0
    assert report.total_calls >= report.primitive_calls >= 1
    assert 1 <= len(report.top_entries) <= 5
    assert any(entry.function_name == "sample_workload" for entry in report.top_entries)
