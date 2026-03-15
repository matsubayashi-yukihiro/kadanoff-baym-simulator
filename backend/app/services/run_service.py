from __future__ import annotations

from typing import Any

from backend.app.jobs.runner import JobRunner
from backend.app.schemas import (
    ObservableCatalogResponse,
    ObservableResponse,
    RunDetail,
    RunState,
    RunSummary,
    SimulationConfig,
)
from backend.app.storage.file_storage import FileRunStorage


def build_default_preset() -> SimulationConfig:
    return SimulationConfig(
        name="square-4x4-baseline",
        lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
        time={"t_final": 1.0, "dt": 0.1},
        drive={
            "amplitude_x": 0.25,
            "amplitude_y": 0.0,
            "frequency": 3.0,
            "center": 0.5,
            "width": 0.3,
        },
        initial_state={"filling": 0.5, "temperature": 0.0},
    )


class RunService:
    def __init__(self, storage: FileRunStorage, runner: JobRunner) -> None:
        self.storage = storage
        self.runner = runner

    def create_run(self, config: SimulationConfig) -> RunDetail:
        summary = self.storage.create_run(config)
        pid = self.runner.submit(summary.run_id, config, self.storage.base_dir)
        if pid is not None:
            self.storage.attach_pid(summary.run_id, pid)
        return self.get_run(summary.run_id)

    def list_runs(self) -> list[RunSummary]:
        return self.storage.list_runs()

    def get_run(self, run_id: str) -> RunDetail:
        return self.storage.read_run_detail(run_id)

    def cancel_run(self, run_id: str) -> RunDetail:
        status = self.storage.read_status(run_id)
        if status.state in {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}:
            return self.get_run(run_id)

        cancelled = self.runner.cancel(run_id)
        if cancelled or status.state == RunState.QUEUED:
            self.storage.update_status(run_id, RunState.CANCELLED, message="run cancelled")
        return self.get_run(run_id)

    def list_observables(self, run_id: str) -> ObservableCatalogResponse:
        descriptors = self.storage.read_observable_catalog(run_id)
        return ObservableCatalogResponse(run_id=run_id, observables=[item.name for item in descriptors])

    def get_observable(self, run_id: str, name: str) -> ObservableResponse:
        return self.storage.read_observable(run_id, name)

    def get_presets(self) -> list[SimulationConfig]:
        return [build_default_preset()]

    def get_schema(self) -> dict[str, Any]:
        return SimulationConfig.model_json_schema()
