from __future__ import annotations

import os
import time
import traceback

from backend.app.jobs.progress import RunProgressReporter, SolverProgressUpdate
from backend.app.schemas import RunState, SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.registry import run_simulation
from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.experiment_repository import ExperimentRepository
from backend.app.storage.file_storage import FileRunStorage


def execute_run(run_id: str, config_data: dict, data_dir: str, registry_db_path: str) -> None:
    """Execute one run lifecycle in a worker process and persist final artifacts/status."""
    storage = FileRunStorage(data_dir)
    registry = ExperimentRegistry(registry_db_path)
    repository = ExperimentRepository(storage=storage, registry=registry)
    config = SimulationConfig.model_validate(config_data)
    reporter = RunProgressReporter(
        storage=storage,
        run_id=run_id,
        requested_steps=int(config.time.n_steps),
        physical_time_final=float(config.time.t_final),
    )
    try:
        repository.update_status(
            run_id,
            RunState.RUNNING,
            message="simulation running",
            pid=os.getpid(),
        )
        reporter.initialize(
            RunProgressPhase.EQUILIBRIUM if config.solver.value != "noninteracting" else RunProgressPhase.PROPAGATING,
            "simulation running",
        )
        startup_delay_seconds = float(os.getenv("TDKB_WORKER_STARTUP_DELAY_SECONDS", "0.0"))
        if startup_delay_seconds > 0.0:
            time.sleep(startup_delay_seconds)
        artifacts = run_simulation(config, progress_callback=reporter.update)
        reporter.update(
            SolverProgressUpdate(
                phase=RunProgressPhase.FINALIZING,
                status_line="finalizing artifacts",
                physical_time_current=float(config.time.t_final),
                physical_time_final=float(config.time.t_final),
                physical_progress_fraction=1.0,
                accepted_steps=int(config.time.n_steps),
                requested_steps=int(config.time.n_steps),
                saved_samples_written=int(artifacts.diagnostics.get("saved_samples", 0)),
                solver_metrics={},
            ),
            force=True,
        )
        repository.write_results(
            run_id,
            observables=artifacts.observables,
            diagnostics=artifacts.diagnostics,
            diagnostics_excerpt=artifacts.summary_excerpt,
            two_time_green_functions=artifacts.two_time_green_functions,
            thermal_branch_green_functions=artifacts.thermal_branch_green_functions,
            mixed_green_functions=artifacts.mixed_green_functions,
        )
        converged = artifacts.diagnostics.get("second_born_converged", True)
        final_state = RunState.SUCCEEDED if converged else RunState.SUCCEEDED_WITH_WARNINGS
        repository.update_status(
            run_id,
            final_state,
            message="simulation completed",
            pid=os.getpid(),
        )
        reporter.finalize(final_state, RunProgressPhase.SUCCEEDED, "simulation completed")
    except Exception as exc:  # pragma: no cover - exercised through failure paths
        repository.append_log(run_id, traceback.format_exc())
        repository.update_status(
            run_id,
            RunState.FAILED,
            message="simulation failed",
            error=str(exc),
            pid=os.getpid(),
        )
        reporter.finalize(RunState.FAILED, RunProgressPhase.FAILED, str(exc))
