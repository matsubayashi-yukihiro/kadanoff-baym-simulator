from __future__ import annotations

import pytest

from backend.app.schemas import RunProgressPhase, RunState, SimulationConfig
from backend.app.storage.file_storage import FileRunStorage


pytestmark = pytest.mark.workflow


def test_progress_storage_keeps_only_recent_history_entries(tmp_path):
    storage = FileRunStorage(tmp_path / "runs")
    summary = storage.create_run(
        SimulationConfig.model_validate(
            {
                "name": "progress-history",
                "solver": "noninteracting",
                "lattice": {"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
                "time": {"t_final": 0.4, "dt": 0.1},
                "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
                "interaction": {"onsite_u": 0.0, "nearest_neighbor_v": 0.0},
                "initial_state": {"filling": 0.5, "temperature": 0.0},
                "observables": ["density"],
            }
        )
    )

    for index in range(150):
        storage.update_progress(
            summary.run_id,
            phase=RunProgressPhase.PROPAGATING,
            state=RunState.RUNNING,
            physical_time_current=0.4 * index / 149.0,
            physical_time_final=0.4,
            physical_progress_fraction=index / 149.0,
            accepted_steps=index,
            requested_steps=149,
            saved_samples_written=index,
            status_line="progress update",
            solver_metrics={"current_dt": 0.1},
            history_limit=120,
        )

    progress = storage.read_progress(summary.run_id)
    assert len(progress.history) == 120
    assert progress.history[0].saved_samples_written == 30
    assert progress.history[-1].saved_samples_written == 149
