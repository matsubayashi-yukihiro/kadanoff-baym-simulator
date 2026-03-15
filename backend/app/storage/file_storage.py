from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from backend.app.schemas import (
    ObservableDescriptor,
    ObservableResponse,
    ObservableSeries,
    ObservableSeriesDescriptor,
    RunDetail,
    RunState,
    RunStatusRecord,
    RunSummary,
    SimulationConfig,
)
from backend.app.solvers.base import ObservableData


TERMINAL_STATES = {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}


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
        return updated_status

    def attach_pid(self, run_id: str, pid: int) -> None:
        status = self.read_status(run_id)
        self._write_model(self._path(run_id, "status.json"), status.model_copy(update={"pid": pid}))

    def write_results(
        self,
        run_id: str,
        *,
        observables: dict[str, ObservableData],
        diagnostics: dict[str, Any],
        diagnostics_excerpt: dict[str, Any],
    ) -> None:
        arrays: dict[str, np.ndarray] = {}
        descriptors: list[ObservableDescriptor] = []
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

        np.savez(self._path(run_id, "observables.npz"), **arrays)
        self._write_json(self._path(run_id, "diagnostics.json"), diagnostics)

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

    def append_log(self, run_id: str, message: str) -> None:
        log_path = self._path(run_id, "run.log")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")

    def run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

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
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
