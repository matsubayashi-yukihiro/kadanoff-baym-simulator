from __future__ import annotations

from typing import Any

from backend.app.jobs.runner import JobRunner
from backend.app.schemas import (
    GreenFunctionCatalogResponse,
    GreenFunctionSliceResponse,
    MixedGreenFunctionCatalogResponse,
    MixedGreenFunctionSliceResponse,
    ObservableCatalogResponse,
    ObservableResponse,
    RunDetail,
    RunState,
    RunSummary,
    SimulationConfig,
    ThermalBranchCatalogResponse,
    ThermalBranchSliceResponse,
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


def build_tdhfb_preset() -> SimulationConfig:
    return SimulationConfig(
        name="square-4x4-bond-d-tdhfb",
        solver="tdhfb",
        lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
        time={"t_final": 1.0, "dt": 0.1},
        drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
        interaction={
            "onsite_u": -4.0,
            "nearest_neighbor_v": -2.5,
            "pairing_channel": "bond_d",
        },
        initial_state={"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.2},
        observables=["density", "energy", "pairing", "pairing_s", "pairing_d"],
    )


def build_kbe_hfb_preset() -> SimulationConfig:
    return SimulationConfig(
        name="square-4x4-bond-d-kbe-hfb",
        solver="kbe_hfb",
        lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
        time={"t_final": 1.0, "dt": 0.1},
        drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
        interaction={
            "onsite_u": -4.0,
            "nearest_neighbor_v": -2.5,
            "pairing_channel": "bond_d",
        },
        initial_state={"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.2},
        observables=["density", "energy", "pairing", "pairing_s", "pairing_d"],
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

    def list_green_functions(self, run_id: str) -> GreenFunctionCatalogResponse:
        return self.storage.read_green_function_catalog(run_id)

    def get_green_function_slice(
        self,
        run_id: str,
        component: str,
        *,
        row_start: int | None = None,
        row_stop: int | None = None,
        col_start: int | None = None,
        col_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> GreenFunctionSliceResponse:
        return self.storage.read_green_function_slice(
            run_id,
            component,
            row_start=row_start,
            row_stop=row_stop,
            col_start=col_start,
            col_stop=col_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def list_thermal_branch(self, run_id: str) -> ThermalBranchCatalogResponse:
        return self.storage.read_thermal_branch_catalog(run_id)

    def get_thermal_branch_slice(
        self,
        run_id: str,
        component: str,
        *,
        tau_start: int | None = None,
        tau_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> ThermalBranchSliceResponse:
        return self.storage.read_thermal_branch_slice(
            run_id,
            component,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def list_mixed_green_functions(self, run_id: str) -> MixedGreenFunctionCatalogResponse:
        return self.storage.read_mixed_green_function_catalog(run_id)

    def get_mixed_green_function_slice(
        self,
        run_id: str,
        component: str,
        *,
        time_start: int | None = None,
        time_stop: int | None = None,
        tau_start: int | None = None,
        tau_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> MixedGreenFunctionSliceResponse:
        return self.storage.read_mixed_green_function_slice(
            run_id,
            component,
            time_start=time_start,
            time_stop=time_stop,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def get_presets(self) -> list[SimulationConfig]:
        return [build_default_preset(), build_tdhfb_preset(), build_kbe_hfb_preset()]

    def get_schema(self) -> dict[str, Any]:
        return SimulationConfig.model_json_schema()
