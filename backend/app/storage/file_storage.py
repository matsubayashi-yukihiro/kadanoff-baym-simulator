from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable
from uuid import uuid4

import numpy as np

from backend.app.schemas import (
    DerivedAnalysisArtifactRecord,
    DerivedAnalysisResultRecord,
    GreenFunctionCatalogResponse,
    GreenFunctionSliceResponse,
    KSpaceNativeCatalogResponse,
    KSpaceNativeLesserSliceResponse,
    KSpaceNativePoint,
    MixedGreenFunctionCatalogResponse,
    MixedGreenFunctionSliceResponse,
    ObservableDescriptor,
    ObservableResponse,
    ObservableSeries,
    ObservableSeriesDescriptor,
    RunProgressPhase,
    RunProgressPoint,
    RunProgressRecord,
    RunDetail,
    RunResearchMetadata,
    RunState,
    RunStatusRecord,
    RunSummary,
    SimulationConfig,
    ThermalBranchCatalogResponse,
    ThermalBranchSliceResponse,
)
from backend.app.solvers.base import (
    KSpaceNativeTrajectoryData,
    MixedGreenFunctionData,
    ObservableData,
    ThermalBranchGreenFunctionData,
    TwoTimeGreenFunctionData,
)


TERMINAL_STATES = {
    RunState.SUCCEEDED,
    RunState.SUCCEEDED_WITH_WARNINGS,
    RunState.FAILED,
    RunState.CANCELLED,
}


class FileRunStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, config: SimulationConfig) -> RunSummary:
        run_id = uuid4().hex
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)

        now = self._utcnow()
        status = RunStatusRecord(
            run_id=run_id,
            state=RunState.QUEUED,
            created_at=now,
            updated_at=now,
            message="run queued",
        )
        summary = RunSummary(
            run_id=run_id,
            name=config.name,
            solver=config.solver.value,
            state=RunState.QUEUED,
            created_at=now,
            updated_at=now,
            status_message="run queued",
            lattice=config.lattice.model_dump(mode="json"),
            time_grid=config.time.model_dump(mode="json"),
        )

        self._write_json(self._path(run_id, "config.json"), config.model_dump(mode="json"))
        self._write_model(self._path(run_id, "status.json"), status)
        self._write_model(self._path(run_id, "summary.json"), summary)
        self._write_json(self._path(run_id, "diagnostics.json"), {})
        self._write_model(
            self._path(run_id, "progress.json"),
            RunProgressRecord(
                run_id=run_id,
                state=RunState.QUEUED,
                phase=RunProgressPhase.QUEUED,
                updated_at=now,
                physical_time_final=float(config.time.t_final),
                requested_steps=int(config.time.n_steps),
                status_line="run queued",
            ),
        )
        self._path(run_id, "run.log").write_text("run created\n", encoding="utf-8")
        return summary

    def list_runs(self) -> list[RunSummary]:
        summaries: list[RunSummary] = []
        for status_path in self.base_dir.glob("*/summary.json"):
            summaries.append(RunSummary.model_validate_json(status_path.read_text(encoding="utf-8")))
        summaries.sort(key=lambda item: item.created_at, reverse=True)
        return summaries

    def read_run_detail(self, run_id: str) -> RunDetail:
        summary = self.read_summary(run_id)
        config = self.read_config(run_id)
        diagnostics = self.read_diagnostics(run_id)
        return RunDetail(**summary.model_dump(mode="json"), config=config, diagnostics=diagnostics)

    def read_config(self, run_id: str) -> SimulationConfig:
        return SimulationConfig.model_validate_json(self._path(run_id, "config.json").read_text(encoding="utf-8"))

    def read_status(self, run_id: str) -> RunStatusRecord:
        return RunStatusRecord.model_validate_json(self._path(run_id, "status.json").read_text(encoding="utf-8"))

    def read_summary(self, run_id: str) -> RunSummary:
        return RunSummary.model_validate_json(self._path(run_id, "summary.json").read_text(encoding="utf-8"))

    def read_diagnostics(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._path(run_id, "diagnostics.json").read_text(encoding="utf-8"))

    def read_progress(self, run_id: str) -> RunProgressRecord:
        return RunProgressRecord.model_validate_json(self._path(run_id, "progress.json").read_text(encoding="utf-8"))

    def update_status(
        self,
        run_id: str,
        state: RunState,
        *,
        message: str | None = None,
        error: str | None = None,
        pid: int | None = None,
    ) -> RunStatusRecord:
        status = self.read_status(run_id)
        now = self._utcnow()
        started_at = status.started_at
        finished_at = status.finished_at
        if state == RunState.RUNNING and started_at is None:
            started_at = now
        if state in TERMINAL_STATES and finished_at is None:
            finished_at = now
        updated_status = status.model_copy(
            update={
                "state": state,
                "updated_at": now,
                "started_at": started_at,
                "finished_at": finished_at,
                "message": message if message is not None else status.message,
                "error": error if error is not None else status.error,
                "pid": pid if pid is not None else status.pid,
            }
        )
        self._write_model(self._path(run_id, "status.json"), updated_status)

        summary = self.read_summary(run_id)
        updated_summary = summary.model_copy(
            update={
                "state": state,
                "updated_at": now,
                "started_at": updated_status.started_at,
                "finished_at": updated_status.finished_at,
                "status_message": updated_status.message if updated_status.error is None else updated_status.error,
            }
        )
        self._write_model(self._path(run_id, "summary.json"), updated_summary)
        self._sync_progress_with_status(
            run_id,
            state=state,
            started_at=updated_status.started_at,
            message=message if error is None else error,
        )
        return updated_status

    def attach_pid(self, run_id: str, pid: int) -> None:
        status = self.read_status(run_id)
        self._write_model(self._path(run_id, "status.json"), status.model_copy(update={"pid": pid}))

    def update_research_metadata(self, run_id: str, metadata: RunResearchMetadata) -> RunSummary:
        summary = self.read_summary(run_id)
        updated_summary = summary.model_copy(
            update={
                "research_metadata": metadata,
                "updated_at": self._utcnow(),
            }
        )
        self._write_model(self._path(run_id, "summary.json"), updated_summary)
        return updated_summary

    def write_results(
        self,
        run_id: str,
        *,
        observables: dict[str, ObservableData],
        diagnostics: dict[str, Any],
        diagnostics_excerpt: dict[str, Any],
        two_time_green_functions: TwoTimeGreenFunctionData | None = None,
        thermal_branch_green_functions: ThermalBranchGreenFunctionData | None = None,
        mixed_green_functions: MixedGreenFunctionData | None = None,
        kspace_native_trajectory: KSpaceNativeTrajectoryData | None = None,
        heartbeat: Callable[[str], None] | None = None,
    ) -> None:
        config = self.read_config(run_id)
        arrays: dict[str, np.ndarray] = {}
        descriptors: list[ObservableDescriptor] = []
        if heartbeat is not None:
            heartbeat("writing observables")
        for name, observable in observables.items():
            time_key = f"{name}__time"
            arrays[time_key] = observable.time
            series_descriptors: list[ObservableSeriesDescriptor] = []
            for series in observable.series:
                series_key = f"{name}__{_slug(series.label)}"
                arrays[series_key] = series.values
                series_descriptors.append(ObservableSeriesDescriptor(label=series.label, key=series_key))
            descriptors.append(
                ObservableDescriptor(
                    name=name,
                    time_key=time_key,
                    series=series_descriptors,
                    units=observable.units,
                    metadata=observable.metadata,
                )
            )

        np.savez_compressed(self._path(run_id, "observables.npz"), **arrays)
        if heartbeat is not None:
            heartbeat("writing diagnostics")
        self._write_json(self._path(run_id, "diagnostics.json"), diagnostics)
        if two_time_green_functions is not None:
            if heartbeat is not None:
                heartbeat("writing green-functions")
            stored_two_time = _subsample_two_time_green_functions(
                two_time_green_functions,
                save_every=config.time.save_every,
            )
            self._write_green_functions(
                run_id,
                stored_two_time,
                full_time_point_count=int(two_time_green_functions.times.shape[0]),
                save_every=config.time.save_every,
            )
        if thermal_branch_green_functions is not None:
            if heartbeat is not None:
                heartbeat("writing thermal-branch")
            self._write_thermal_branch(run_id, thermal_branch_green_functions)
        if mixed_green_functions is not None:
            if heartbeat is not None:
                heartbeat("writing mixed-green-functions")
            stored_mixed = _subsample_mixed_green_functions(
                mixed_green_functions,
                save_every=config.time.save_every,
            )
            self._write_mixed_green_functions(
                run_id,
                stored_mixed,
                full_time_point_count=int(mixed_green_functions.times.shape[0]),
                save_every=config.time.save_every,
            )
        if kspace_native_trajectory is not None:
            if heartbeat is not None:
                heartbeat("writing kspace-native")
            self._write_kspace_native_trajectory(
                run_id,
                kspace_native_trajectory,
                nx=int(config.lattice.nx),
                ny=int(config.lattice.ny),
            )

        summary = self.read_summary(run_id)
        updated_summary = summary.model_copy(
            update={
                "available_observables": descriptors,
                "diagnostics_excerpt": diagnostics_excerpt,
                "updated_at": self._utcnow(),
            }
        )
        self._write_model(self._path(run_id, "summary.json"), updated_summary)

    def read_observable_catalog(self, run_id: str) -> list[ObservableDescriptor]:
        return self.read_summary(run_id).available_observables

    def update_progress(
        self,
        run_id: str,
        *,
        phase: RunProgressPhase | None = None,
        state: RunState | None = None,
        started_at: datetime | None = None,
        wall_seconds_elapsed: float | None = None,
        physical_time_current: float | None = None,
        physical_time_final: float | None = None,
        physical_progress_fraction: float | None = None,
        accepted_steps: int | None = None,
        requested_steps: int | None = None,
        rejected_steps: int | None = None,
        saved_samples_written: int | None = None,
        status_line: str | None = None,
        solver_metrics: dict[str, Any] | None = None,
        history_limit: int = 120,
        append_history: bool = True,
        metric_1: float | None = None,
        metric_2: float | None = None,
        metric_3: float | None = None,
    ) -> RunProgressRecord:
        progress = self.read_progress(run_id)
        now = self._utcnow()
        next_state = state or progress.state
        next_phase = phase or progress.phase
        next_started_at = started_at if started_at is not None else progress.started_at
        next_wall_seconds = wall_seconds_elapsed if wall_seconds_elapsed is not None else progress.wall_seconds_elapsed
        next_solver_metrics = (
            dict(progress.solver_metrics) if solver_metrics is None else dict(solver_metrics)
        )
        updated = progress.model_copy(
            update={
                "state": next_state,
                "phase": next_phase,
                "updated_at": now,
                "started_at": next_started_at,
                "wall_seconds_elapsed": next_wall_seconds,
                "physical_time_current": (
                    physical_time_current if physical_time_current is not None else progress.physical_time_current
                ),
                "physical_time_final": (
                    physical_time_final if physical_time_final is not None else progress.physical_time_final
                ),
                "physical_progress_fraction": (
                    physical_progress_fraction
                    if physical_progress_fraction is not None
                    else progress.physical_progress_fraction
                ),
                "accepted_steps": accepted_steps if accepted_steps is not None else progress.accepted_steps,
                "requested_steps": requested_steps if requested_steps is not None else progress.requested_steps,
                "rejected_steps": rejected_steps if rejected_steps is not None else progress.rejected_steps,
                "saved_samples_written": (
                    saved_samples_written if saved_samples_written is not None else progress.saved_samples_written
                ),
                "status_line": status_line if status_line is not None else progress.status_line,
                "solver_metrics": next_solver_metrics,
            }
        )
        history = list(updated.history)
        if append_history:
            history.append(
                RunProgressPoint(
                    timestamp=now,
                    wall_seconds_elapsed=updated.wall_seconds_elapsed,
                    physical_time_current=updated.physical_time_current,
                    physical_progress_fraction=updated.physical_progress_fraction,
                    saved_samples_written=updated.saved_samples_written,
                    metric_1=metric_1,
                    metric_2=metric_2,
                    metric_3=metric_3,
                )
            )
            if len(history) > history_limit:
                history = history[-history_limit:]
            updated = updated.model_copy(update={"history": history})
        self._write_model(self._path(run_id, "progress.json"), updated)
        return updated

    def read_observable(self, run_id: str, name: str) -> ObservableResponse:
        descriptor = next((item for item in self.read_observable_catalog(run_id) if item.name == name), None)
        if descriptor is None:
            raise KeyError(name)
        observables_path = self._path(run_id, "observables.npz")
        if not observables_path.exists():
            raise FileNotFoundError(observables_path)
        with np.load(observables_path) as payload:
            return ObservableResponse(
                name=descriptor.name,
                time=payload[descriptor.time_key].astype(float).tolist(),
                series=[
                    ObservableSeries(label=series.label, values=payload[series.key].astype(float).tolist())
                    for series in descriptor.series
                ],
                units=descriptor.units,
                metadata=descriptor.metadata,
            )

    def read_green_function_catalog(self, run_id: str) -> GreenFunctionCatalogResponse:
        metadata = self._read_green_function_metadata(run_id)
        return GreenFunctionCatalogResponse(
            run_id=run_id,
            components=list(metadata["components"]),
            shape=[int(value) for value in metadata["shape"]],
            time_point_count=int(metadata["time_point_count"]),
            nambu_dimension=int(metadata["nambu_dimension"]),
        )

    def read_green_function_slice(
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
        metadata = self._read_green_function_metadata(run_id)
        component_file = metadata["component_files"].get(component)
        if component_file is None:
            raise KeyError(component)

        shape = [int(value) for value in metadata["shape"]]
        time_count = shape[0]
        nambu_dimension = shape[2]
        row_start_index, row_stop_index = _normalize_slice_bounds(row_start, row_stop, time_count, axis_name="row")
        col_start_index, col_stop_index = _normalize_slice_bounds(col_start, col_stop, time_count, axis_name="column")
        nambu_start_index, nambu_stop_index = _normalize_slice_bounds(
            nambu_start,
            nambu_stop,
            nambu_dimension,
            axis_name="nambu",
        )

        times = np.load(self._path(run_id, metadata["times_file"]), mmap_mode="r")
        values = np.load(self._path(run_id, component_file), mmap_mode="r")
        selected = values[
            row_start_index:row_stop_index,
            col_start_index:col_stop_index,
            nambu_start_index:nambu_stop_index,
            nambu_start_index:nambu_stop_index,
        ]
        return GreenFunctionSliceResponse(
            component=component,
            times_row=times[row_start_index:row_stop_index].astype(float).tolist(),
            times_col=times[col_start_index:col_stop_index].astype(float).tolist(),
            nambu_start=nambu_start_index,
            nambu_stop=nambu_stop_index,
            shape=[int(value) for value in selected.shape],
            real=np.real(selected).astype(float).tolist(),
            imag=np.imag(selected).astype(float).tolist(),
        )

    def read_green_function_component_array(
        self,
        run_id: str,
        component: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        metadata = self._read_green_function_metadata(run_id)
        component_file = metadata["component_files"].get(component)
        if component_file is None:
            raise KeyError(component)
        times = np.load(self._path(run_id, metadata["times_file"]))
        values = np.load(self._path(run_id, component_file))
        return times, values

    def read_kspace_native_catalog(self, run_id: str) -> KSpaceNativeCatalogResponse:
        metadata = self._read_kspace_native_metadata(run_id)
        points = [
            KSpaceNativePoint(
                index=int(index),
                grid_index_x=int(index % int(metadata["nx"])),
                grid_index_y=int(index // int(metadata["nx"])),
                kx=float(kx),
                ky=float(ky),
            )
            for index, (kx, ky) in enumerate(zip(metadata["kx"], metadata["ky"], strict=True))
        ]
        return KSpaceNativeCatalogResponse(
            run_id=run_id,
            components=list(metadata["components"]),
            time_point_count=int(metadata["time_point_count"]),
            k_point_count=int(metadata["k_point_count"]),
            block_shape=[int(value) for value in metadata["block_shape"]],
            nambu_dimension=int(metadata["nambu_dimension"]),
            reconstruction_mode=metadata.get("reconstruction_mode"),
            points=points,
        )

    def read_kspace_native_lesser_slice(
        self,
        run_id: str,
        *,
        row_start: int | None = None,
        row_stop: int | None = None,
        col_start: int | None = None,
        col_stop: int | None = None,
        k_start: int | None = None,
        k_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> KSpaceNativeLesserSliceResponse:
        metadata = self._read_kspace_native_metadata(run_id)
        times = np.load(self._path(run_id, metadata["times_file"]), mmap_mode="r")
        density_blocks = np.load(self._path(run_id, metadata["density_blocks_file"]), mmap_mode="r")
        propagator_blocks = np.load(self._path(run_id, metadata["propagator_blocks_file"]), mmap_mode="r")

        time_count = int(metadata["time_point_count"])
        k_count = int(metadata["k_point_count"])
        nambu_dimension = int(metadata["nambu_dimension"])
        row_start_index, row_stop_index = _normalize_slice_bounds(row_start, row_stop, time_count, axis_name="row")
        col_start_index, col_stop_index = _normalize_slice_bounds(col_start, col_stop, time_count, axis_name="column")
        k_start_index, k_stop_index = _normalize_slice_bounds(k_start, k_stop, k_count, axis_name="k")
        nambu_start_index, nambu_stop_index = _normalize_slice_bounds(
            nambu_start,
            nambu_stop,
            nambu_dimension,
            axis_name="nambu",
        )

        selected_rows = propagator_blocks[row_start_index:row_stop_index, k_start_index:k_stop_index]
        selected_cols = propagator_blocks[col_start_index:col_stop_index, k_start_index:k_stop_index]
        selected_initial_density = density_blocks[0, k_start_index:k_stop_index]
        selected_cols_dagger = np.conjugate(np.swapaxes(selected_cols, -1, -2))
        intermediate = np.einsum(
            "rkab,kbc->rkac",
            selected_rows,
            selected_initial_density,
            optimize=True,
        )
        lesser_blocks = 1j * np.einsum(
            "rkab,ckbd->rckad",
            intermediate,
            selected_cols_dagger,
            optimize=True,
        )
        selected = lesser_blocks[
            :,
            :,
            :,
            nambu_start_index:nambu_stop_index,
            nambu_start_index:nambu_stop_index,
        ]
        return KSpaceNativeLesserSliceResponse(
            component="lesser",
            times_row=times[row_start_index:row_stop_index].astype(float).tolist(),
            times_col=times[col_start_index:col_stop_index].astype(float).tolist(),
            k_start=k_start_index,
            k_stop=k_stop_index,
            nambu_start=nambu_start_index,
            nambu_stop=nambu_stop_index,
            shape=[int(value) for value in selected.shape],
            real=np.real(selected).astype(float).tolist(),
            imag=np.imag(selected).astype(float).tolist(),
        )

    def read_kspace_native_trajectory(
        self,
        run_id: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
        metadata = self._read_kspace_native_metadata(run_id)
        times = np.load(self._path(run_id, metadata["times_file"]))
        density_blocks = np.load(self._path(run_id, metadata["density_blocks_file"]))
        propagator_blocks = np.load(self._path(run_id, metadata["propagator_blocks_file"]))
        return (
            np.asarray(times, dtype=np.float64),
            np.asarray(density_blocks, dtype=np.complex128),
            np.asarray(propagator_blocks, dtype=np.complex128),
            metadata,
        )

    def read_thermal_branch_catalog(self, run_id: str) -> ThermalBranchCatalogResponse:
        metadata = self._read_thermal_branch_metadata(run_id)
        return ThermalBranchCatalogResponse(
            run_id=run_id,
            components=list(metadata["components"]),
            shape=[int(value) for value in metadata["shape"]],
            tau_point_count=int(metadata["tau_point_count"]),
            nambu_dimension=int(metadata["nambu_dimension"]),
        )

    def read_thermal_branch_slice(
        self,
        run_id: str,
        component: str,
        *,
        tau_start: int | None = None,
        tau_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> ThermalBranchSliceResponse:
        metadata = self._read_thermal_branch_metadata(run_id)
        component_file = metadata["component_files"].get(component)
        if component_file is None:
            raise KeyError(component)

        shape = [int(value) for value in metadata["shape"]]
        tau_count = shape[0]
        nambu_dimension = shape[1]
        tau_start_index, tau_stop_index = _normalize_slice_bounds(tau_start, tau_stop, tau_count, axis_name="tau")
        nambu_start_index, nambu_stop_index = _normalize_slice_bounds(
            nambu_start,
            nambu_stop,
            nambu_dimension,
            axis_name="nambu",
        )

        tau = np.load(self._path(run_id, metadata["tau_file"]), mmap_mode="r")
        values = np.load(self._path(run_id, component_file), mmap_mode="r")
        selected = values[
            tau_start_index:tau_stop_index,
            nambu_start_index:nambu_stop_index,
            nambu_start_index:nambu_stop_index,
        ]
        return ThermalBranchSliceResponse(
            component=component,
            tau=tau[tau_start_index:tau_stop_index].astype(float).tolist(),
            nambu_start=nambu_start_index,
            nambu_stop=nambu_stop_index,
            shape=[int(value) for value in selected.shape],
            real=np.real(selected).astype(float).tolist(),
            imag=np.imag(selected).astype(float).tolist(),
        )

    def read_mixed_green_function_catalog(self, run_id: str) -> MixedGreenFunctionCatalogResponse:
        metadata = self._read_mixed_green_function_metadata(run_id)
        return MixedGreenFunctionCatalogResponse(
            run_id=run_id,
            components=list(metadata["components"]),
            shape=[int(value) for value in metadata["shape"]],
            time_point_count=int(metadata["time_point_count"]),
            tau_point_count=int(metadata["tau_point_count"]),
            nambu_dimension=int(metadata["nambu_dimension"]),
        )

    def read_mixed_green_function_slice(
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
        metadata = self._read_mixed_green_function_metadata(run_id)
        component_file = metadata["component_files"].get(component)
        if component_file is None:
            raise KeyError(component)

        shape = [int(value) for value in metadata["shape"]]
        time_count = shape[0]
        tau_count = shape[1]
        nambu_dimension = shape[2]
        time_start_index, time_stop_index = _normalize_slice_bounds(
            time_start,
            time_stop,
            time_count,
            axis_name="time",
        )
        tau_start_index, tau_stop_index = _normalize_slice_bounds(tau_start, tau_stop, tau_count, axis_name="tau")
        nambu_start_index, nambu_stop_index = _normalize_slice_bounds(
            nambu_start,
            nambu_stop,
            nambu_dimension,
            axis_name="nambu",
        )

        times = np.load(self._path(run_id, metadata["times_file"]), mmap_mode="r")
        tau = np.load(self._path(run_id, metadata["tau_file"]), mmap_mode="r")
        values = np.load(self._path(run_id, component_file), mmap_mode="r")
        selected = values[
            time_start_index:time_stop_index,
            tau_start_index:tau_stop_index,
            nambu_start_index:nambu_stop_index,
            nambu_start_index:nambu_stop_index,
        ]
        return MixedGreenFunctionSliceResponse(
            component=component,
            times=times[time_start_index:time_stop_index].astype(float).tolist(),
            tau=tau[tau_start_index:tau_stop_index].astype(float).tolist(),
            nambu_start=nambu_start_index,
            nambu_stop=nambu_stop_index,
            shape=[int(value) for value in selected.shape],
            real=np.real(selected).astype(float).tolist(),
            imag=np.imag(selected).astype(float).tolist(),
        )

    def append_log(self, run_id: str, message: str) -> None:
        log_path = self._path(run_id, "run.log")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")

    def read_log(self, run_id: str) -> str:
        log_path = self._path(run_id, "run.log")
        if not log_path.exists():
            return ""
        return log_path.read_text(encoding="utf-8")

    def run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

    def derived_analysis_dir(self, analysis_id: str) -> Path:
        path = self.base_dir / "derived_analyses" / analysis_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_derived_analysis_result(
        self,
        analysis_id: str,
        *,
        payload_kind: str,
        payload: dict[str, Any],
    ) -> str:
        analysis_dir = self.derived_analysis_dir(analysis_id)
        result_path = analysis_dir / "result.json"
        self._write_json(
            result_path,
            {
                "payload_kind": payload_kind,
                "payload": payload,
            },
        )
        return str(result_path.relative_to(self.base_dir))

    def read_derived_analysis_result(
        self,
        analysis: DerivedAnalysisArtifactRecord,
    ) -> DerivedAnalysisResultRecord:
        result_ref = next(iter(analysis.data_refs), None)
        if result_ref is None:
            raise FileNotFoundError("derived analysis result payload is missing")
        result_path = self.base_dir / result_ref
        if not result_path.exists():
            raise FileNotFoundError(result_path)
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        return DerivedAnalysisResultRecord(
            analysis=analysis,
            payload_kind=str(payload["payload_kind"]),
            payload=dict(payload["payload"]),
        )

    def _path(self, run_id: str, filename: str) -> Path:
        path = self.run_dir(run_id) / filename
        if not path.parent.exists():
            raise FileNotFoundError(path.parent)
        return path

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(tz=UTC)

    @staticmethod
    def _write_model(path: Path, model: Any) -> None:
        _atomic_write(path, model.model_dump_json(indent=2))

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        _atomic_write(path, json.dumps(payload, indent=2, sort_keys=True))

    def _sync_progress_with_status(
        self,
        run_id: str,
        *,
        state: RunState,
        started_at: datetime | None,
        message: str | None,
    ) -> None:
        try:
            progress = self.read_progress(run_id)
        except FileNotFoundError:
            return
        phase = progress.phase
        append_history = False
        if state == RunState.CANCELLED:
            phase = RunProgressPhase.CANCELLED
        elif state in {RunState.SUCCEEDED, RunState.SUCCEEDED_WITH_WARNINGS}:
            phase = RunProgressPhase.SUCCEEDED
        elif state == RunState.FAILED:
            phase = RunProgressPhase.FAILED
        elif state == RunState.RUNNING and progress.phase == RunProgressPhase.QUEUED:
            phase = RunProgressPhase.PROPAGATING
            append_history = True
        self.update_progress(
            run_id,
            phase=phase,
            state=state,
            started_at=started_at,
            status_line=message,
            append_history=append_history,
        )

    def _write_kspace_native_trajectory(
        self,
        run_id: str,
        trajectory: KSpaceNativeTrajectoryData,
        *,
        nx: int,
        ny: int,
    ) -> None:
        times_file = "kspace_native_times.npy"
        density_blocks_file = "kspace_native_density_blocks.npy"
        propagator_blocks_file = "kspace_native_propagator_blocks.npy"
        np.save(self._path(run_id, times_file), np.asarray(trajectory.times, dtype=np.float64))
        np.save(
            self._path(run_id, density_blocks_file),
            np.asarray(trajectory.density_blocks_history, dtype=np.complex128),
        )
        np.save(
            self._path(run_id, propagator_blocks_file),
            np.asarray(trajectory.cumulative_propagator_blocks, dtype=np.complex128),
        )
        kx = np.asarray(trajectory.kx, dtype=np.float64)
        ky = np.asarray(trajectory.ky, dtype=np.float64)
        k_point_count = int(kx.shape[0])
        if k_point_count != int(ky.shape[0]):
            raise ValueError("kspace native trajectory requires matching kx/ky sizes")
        density_shape = np.asarray(trajectory.density_blocks_history).shape
        if len(density_shape) != 4 or density_shape[1] != k_point_count:
            raise ValueError("kspace native density blocks must have shape [time, k, 2, 2]")
        if int(nx) * int(ny) != k_point_count:
            raise ValueError("kspace native trajectory k-point count must match lattice nx*ny")
        block_shape = [int(density_shape[2]), int(density_shape[3])]
        self._write_json(
            self._path(run_id, "kspace_native.json"),
            {
                "times_file": times_file,
                "density_blocks_file": density_blocks_file,
                "propagator_blocks_file": propagator_blocks_file,
                "components": ["lesser"],
                "time_point_count": int(density_shape[0]),
                "k_point_count": k_point_count,
                "block_shape": block_shape,
                "nambu_dimension": int(block_shape[0]),
                "reconstruction_mode": trajectory.reconstruction_mode,
                "kx": kx.astype(float).tolist(),
                "ky": ky.astype(float).tolist(),
                "nx": int(nx),
                "ny": int(ny),
            },
        )

    def _read_kspace_native_metadata(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._path(run_id, "kspace_native.json").read_text(encoding="utf-8"))

    def _write_green_functions(
        self,
        run_id: str,
        green_functions: TwoTimeGreenFunctionData,
        *,
        full_time_point_count: int | None = None,
        save_every: int | None = None,
    ) -> None:
        times_file = "green_times.npy"
        component_files: dict[str, str] = {}
        shape: list[int] | None = None
        nambu_dimension: int | None = None
        np.save(self._path(run_id, times_file), green_functions.times)
        for component, values in green_functions.components.items():
            component_file = f"green_{_slug(component)}.npy"
            np.save(self._path(run_id, component_file), values)
            component_files[component] = component_file
            if shape is None:
                shape = [int(value) for value in values.shape]
                nambu_dimension = int(values.shape[2])

        if shape is None or nambu_dimension is None:
            raise ValueError("two_time_green_functions must include at least one component")

        self._write_json(
            self._path(run_id, "green_functions.json"),
            {
                "times_file": times_file,
                "component_files": component_files,
                "components": list(green_functions.components),
                "shape": shape,
                "time_point_count": int(green_functions.times.shape[0]),
                "full_time_point_count": int(full_time_point_count or green_functions.times.shape[0]),
                "save_every": int(save_every or 1),
                "nambu_dimension": nambu_dimension,
            },
        )

    def _read_green_function_metadata(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._path(run_id, "green_functions.json").read_text(encoding="utf-8"))

    def _write_thermal_branch(self, run_id: str, thermal_branch: ThermalBranchGreenFunctionData) -> None:
        tau_file = "thermal_tau.npy"
        component_files: dict[str, str] = {}
        shape: list[int] | None = None
        nambu_dimension: int | None = None
        np.save(self._path(run_id, tau_file), thermal_branch.tau)
        for component, values in thermal_branch.components.items():
            component_file = f"thermal_{_slug(component)}.npy"
            np.save(self._path(run_id, component_file), values)
            component_files[component] = component_file
            if shape is None:
                shape = [int(value) for value in values.shape]
                nambu_dimension = int(values.shape[1])

        if shape is None or nambu_dimension is None:
            raise ValueError("thermal_branch_green_functions must include at least one component")

        self._write_json(
            self._path(run_id, "thermal_branch.json"),
            {
                "tau_file": tau_file,
                "component_files": component_files,
                "components": list(thermal_branch.components),
                "shape": shape,
                "tau_point_count": int(thermal_branch.tau.shape[0]),
                "nambu_dimension": nambu_dimension,
            },
        )

    def _read_thermal_branch_metadata(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._path(run_id, "thermal_branch.json").read_text(encoding="utf-8"))

    def _write_mixed_green_functions(
        self,
        run_id: str,
        mixed_green_functions: MixedGreenFunctionData,
        *,
        full_time_point_count: int | None = None,
        save_every: int | None = None,
    ) -> None:
        times_file = "mixed_times.npy"
        tau_file = "mixed_tau.npy"
        component_files: dict[str, str] = {}
        shape: list[int] | None = None
        nambu_dimension: int | None = None
        np.save(self._path(run_id, times_file), mixed_green_functions.times)
        np.save(self._path(run_id, tau_file), mixed_green_functions.tau)
        for component, values in mixed_green_functions.components.items():
            component_file = f"mixed_{_slug(component)}.npy"
            np.save(self._path(run_id, component_file), values)
            component_files[component] = component_file
            if shape is None:
                shape = [int(value) for value in values.shape]
                nambu_dimension = int(values.shape[2])

        if shape is None or nambu_dimension is None:
            raise ValueError("mixed_green_functions must include at least one component")

        self._write_json(
            self._path(run_id, "mixed_green_functions.json"),
            {
                "times_file": times_file,
                "tau_file": tau_file,
                "component_files": component_files,
                "components": list(mixed_green_functions.components),
                "shape": shape,
                "time_point_count": int(mixed_green_functions.times.shape[0]),
                "full_time_point_count": int(full_time_point_count or mixed_green_functions.times.shape[0]),
                "save_every": int(save_every or 1),
                "tau_point_count": int(mixed_green_functions.tau.shape[0]),
                "nambu_dimension": nambu_dimension,
            },
        )

    def _read_mixed_green_function_metadata(self, run_id: str) -> dict[str, Any]:
        return json.loads(self._path(run_id, "mixed_green_functions.json").read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _normalize_slice_bounds(
    start: int | None,
    stop: int | None,
    upper: int,
    *,
    axis_name: str,
) -> tuple[int, int]:
    normalized_start = 0 if start is None else start
    normalized_stop = upper if stop is None else stop
    if normalized_start < 0 or normalized_start >= upper:
        raise ValueError(f"{axis_name}_start must satisfy 0 <= start < {upper}")
    if normalized_stop <= normalized_start or normalized_stop > upper:
        raise ValueError(f"{axis_name}_stop must satisfy {normalized_start} < stop <= {upper}")
    return normalized_start, normalized_stop


def _saved_step_indices(sample_count: int, save_every: int) -> np.ndarray:
    if sample_count <= 1 or save_every <= 1:
        return np.arange(sample_count, dtype=np.int64)
    indices = np.arange(0, sample_count, save_every, dtype=np.int64)
    if indices[-1] != sample_count - 1:
        indices = np.append(indices, sample_count - 1)
    return indices


def _subsample_two_time_green_functions(
    green_functions: TwoTimeGreenFunctionData,
    *,
    save_every: int,
) -> TwoTimeGreenFunctionData:
    indices = _saved_step_indices(int(green_functions.times.shape[0]), save_every)
    if indices.shape[0] == green_functions.times.shape[0]:
        return green_functions
    return TwoTimeGreenFunctionData(
        times=green_functions.times[indices],
        components={
            component: values[indices][:, indices]
            for component, values in green_functions.components.items()
        },
    )


def _subsample_mixed_green_functions(
    mixed_green_functions: MixedGreenFunctionData,
    *,
    save_every: int,
) -> MixedGreenFunctionData:
    indices = _saved_step_indices(int(mixed_green_functions.times.shape[0]), save_every)
    if indices.shape[0] == mixed_green_functions.times.shape[0]:
        return mixed_green_functions
    return MixedGreenFunctionData(
        times=mixed_green_functions.times[indices],
        tau=mixed_green_functions.tau,
        components={
            component: values[indices]
            for component, values in mixed_green_functions.components.items()
        },
    )
