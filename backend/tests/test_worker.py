from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.jobs import worker
from backend.app.schemas import RunState

pytestmark = pytest.mark.workflow


def _minimal_config_data() -> dict[str, object]:
    return {
        "solver": "noninteracting",
        "lattice": {"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
        "time": {"t_final": 0.1, "dt": 0.1},
        "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
        "interaction": {"onsite_u": 0.0, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
        "initial_state": {"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.0},
        "adaptive": {"enabled": False},
        "observables": ["density"],
    }


@pytest.mark.parametrize(
    ("diagnostics", "expected_state"),
    [
        (
            {
                "second_born_converged": True,
                "second_born_convergence_criterion": "strict",
                "thermal_branch_enabled": True,
                "thermal_branch_converged": True,
                "mixed_components_included": True,
                "mixed_branch_converged": True,
            },
            RunState.SUCCEEDED,
        ),
        (
            {
                "second_born_converged": True,
                "second_born_convergence_criterion": "relaxed_5x",
                "thermal_branch_enabled": False,
                "mixed_components_included": False,
            },
            RunState.SUCCEEDED_WITH_WARNINGS,
        ),
        (
            {
                "second_born_converged": True,
                "second_born_convergence_criterion": "strict",
                "thermal_branch_enabled": True,
                "thermal_branch_converged": False,
                "mixed_components_included": True,
                "mixed_branch_converged": True,
            },
            RunState.SUCCEEDED_WITH_WARNINGS,
        ),
    ],
)
def test_execute_run_promotes_warning_state_from_combined_convergence_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    diagnostics: dict[str, object],
    expected_state: RunState,
):
    status_updates: list[RunState] = []

    class _FakeReporter:
        def __init__(self, **kwargs):
            pass

        def initialize(self, *args, **kwargs):
            pass

        def update(self, *args, **kwargs):
            pass

        def finalize(self, *args, **kwargs):
            pass

    class _FakeRepository:
        def __init__(self, **kwargs):
            pass

        def update_status(self, run_id, state, **kwargs):
            status_updates.append(state)

        def write_results(self, run_id, **kwargs):
            pass

        def append_log(self, run_id, message):
            pass

    fake_artifacts = SimpleNamespace(
        observables={},
        diagnostics=diagnostics,
        summary_excerpt={},
        two_time_green_functions=None,
        thermal_branch_green_functions=None,
        mixed_green_functions=None,
    )

    monkeypatch.setattr(worker, "RunProgressReporter", _FakeReporter)
    monkeypatch.setattr(worker, "FileRunStorage", lambda data_dir: object())
    monkeypatch.setattr(worker, "ExperimentRegistry", lambda registry_db_path: object())
    monkeypatch.setattr(worker, "ExperimentRepository", lambda **kwargs: _FakeRepository(**kwargs))
    monkeypatch.setattr(worker, "run_simulation", lambda config, progress_callback=None: fake_artifacts)

    worker.execute_run(
        run_id="run-test",
        config_data=_minimal_config_data(),
        data_dir=str(tmp_path),
        registry_db_path=str(tmp_path / "registry.sqlite"),
    )

    assert status_updates[-1] == expected_state

