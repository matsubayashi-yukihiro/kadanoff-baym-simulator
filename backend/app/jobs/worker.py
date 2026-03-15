from __future__ import annotations

import os
import traceback

from backend.app.schemas import RunState, SimulationConfig
from backend.app.solvers.registry import run_simulation
from backend.app.storage.file_storage import FileRunStorage


def execute_run(run_id: str, config_data: dict, data_dir: str) -> None:
    storage = FileRunStorage(data_dir)
    config = SimulationConfig.model_validate(config_data)
    try:
        storage.update_status(
            run_id,
            RunState.RUNNING,
            message="simulation running",
            pid=os.getpid(),
        )
        artifacts = run_simulation(config)
        storage.write_results(
            run_id,
            observables=artifacts.observables,
            diagnostics=artifacts.diagnostics,
            diagnostics_excerpt=artifacts.summary_excerpt,
        )
        storage.update_status(
            run_id,
            RunState.SUCCEEDED,
            message="simulation completed",
            pid=os.getpid(),
        )
    except Exception as exc:  # pragma: no cover - exercised through failure paths
        storage.append_log(run_id, traceback.format_exc())
        storage.update_status(
            run_id,
            RunState.FAILED,
            message="simulation failed",
            error=str(exc),
            pid=os.getpid(),
        )
