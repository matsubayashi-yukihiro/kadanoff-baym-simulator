from __future__ import annotations

import os
import time
import traceback

from backend.app.schemas import RunState, SimulationConfig
from backend.app.solvers.registry import run_simulation
from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.experiment_repository import ExperimentRepository
from backend.app.storage.file_storage import FileRunStorage


def execute_run(run_id: str, config_data: dict, data_dir: str, registry_db_path: str) -> None:
    storage = FileRunStorage(data_dir)
    registry = ExperimentRegistry(registry_db_path)
    repository = ExperimentRepository(storage=storage, registry=registry)
    config = SimulationConfig.model_validate(config_data)
    try:
        repository.update_status(
            run_id,
            RunState.RUNNING,
            message="simulation running",
            pid=os.getpid(),
        )
        startup_delay_seconds = float(os.getenv("TDKB_WORKER_STARTUP_DELAY_SECONDS", "0.0"))
        if startup_delay_seconds > 0.0:
            time.sleep(startup_delay_seconds)
        artifacts = run_simulation(config)
        repository.write_results(
            run_id,
            observables=artifacts.observables,
            diagnostics=artifacts.diagnostics,
            diagnostics_excerpt=artifacts.summary_excerpt,
            two_time_green_functions=artifacts.two_time_green_functions,
            thermal_branch_green_functions=artifacts.thermal_branch_green_functions,
            mixed_green_functions=artifacts.mixed_green_functions,
        )
        repository.update_status(
            run_id,
            RunState.SUCCEEDED,
            message="simulation completed",
            pid=os.getpid(),
        )
    except Exception as exc:  # pragma: no cover - exercised through failure paths
        repository.append_log(run_id, traceback.format_exc())
        repository.update_status(
            run_id,
            RunState.FAILED,
            message="simulation failed",
            error=str(exc),
            pid=os.getpid(),
        )
