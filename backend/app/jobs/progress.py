from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.schemas import RunProgressPhase, RunState
from backend.app.storage.file_storage import FileRunStorage


@dataclass(slots=True)
class SolverProgressUpdate:
    phase: RunProgressPhase
    status_line: str | None = None
    physical_time_current: float | None = None
    physical_time_final: float | None = None
    physical_progress_fraction: float | None = None
    accepted_steps: int | None = None
    requested_steps: int | None = None
    rejected_steps: int | None = None
    saved_samples_written: int | None = None
    solver_metrics: dict[str, Any] | None = None


class RunProgressReporter:
    def __init__(
        self,
        *,
        storage: FileRunStorage,
        run_id: str,
        requested_steps: int,
        physical_time_final: float,
        history_limit: int = 120,
        min_write_interval_seconds: float = 0.25,
    ) -> None:
        self.storage = storage
        self.run_id = run_id
        self.requested_steps = requested_steps
        self.physical_time_final = physical_time_final
        self.history_limit = history_limit
        self.min_write_interval_seconds = min_write_interval_seconds
        self.started_at = datetime.now(tz=UTC)
        self._started_perf = time.perf_counter()
        self._last_write_perf = 0.0

    def initialize(self, phase: RunProgressPhase, status_line: str) -> None:
        self.storage.update_progress(
            self.run_id,
            phase=phase,
            state=RunState.RUNNING,
            started_at=self.started_at,
            requested_steps=self.requested_steps,
            physical_time_final=self.physical_time_final,
            status_line=status_line,
            wall_seconds_elapsed=0.0,
            append_history=True,
        )
        self._last_write_perf = time.perf_counter()

    def update(self, update: SolverProgressUpdate, *, force: bool = False) -> None:
        now_perf = time.perf_counter()
        if not force and now_perf - self._last_write_perf < self.min_write_interval_seconds:
            return
        wall_seconds_elapsed = now_perf - self._started_perf
        existing_metrics = {}
        try:
            existing_metrics = dict(self.storage.read_progress(self.run_id).solver_metrics)
        except FileNotFoundError:
            existing_metrics = {}
        solver_metrics = dict(existing_metrics)
        solver_metrics.update(update.solver_metrics or {})
        metric_1, metric_2, metric_3 = _history_metrics(solver_metrics)
        self.storage.update_progress(
            self.run_id,
            phase=update.phase,
            state=RunState.RUNNING,
            started_at=self.started_at,
            wall_seconds_elapsed=wall_seconds_elapsed,
            physical_time_current=update.physical_time_current,
            physical_time_final=(
                update.physical_time_final
                if update.physical_time_final is not None
                else self.physical_time_final
            ),
            physical_progress_fraction=update.physical_progress_fraction,
            accepted_steps=update.accepted_steps,
            requested_steps=update.requested_steps if update.requested_steps is not None else self.requested_steps,
            rejected_steps=update.rejected_steps,
            saved_samples_written=update.saved_samples_written,
            status_line=update.status_line,
            solver_metrics=solver_metrics,
            history_limit=self.history_limit,
            append_history=True,
            metric_1=metric_1,
            metric_2=metric_2,
            metric_3=metric_3,
        )
        self._last_write_perf = now_perf

    def finalize(self, state: RunState, phase: RunProgressPhase, status_line: str) -> None:
        now_perf = time.perf_counter()
        self.storage.update_progress(
            self.run_id,
            phase=phase,
            state=state,
            started_at=self.started_at,
            wall_seconds_elapsed=now_perf - self._started_perf,
            status_line=status_line,
            history_limit=self.history_limit,
            append_history=False,
        )


def _history_metrics(solver_metrics: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    preferred = (
        "latest_fixed_point_residual",
        "latest_fixed_point_iterations",
        "latest_memory_norm",
        "current_dt",
        "latest_adaptive_error_estimate",
        "max_continuity_residual_so_far",
    )
    values: list[float | None] = []
    for key in preferred:
        value = solver_metrics.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
        if len(values) == 3:
            break
    while len(values) < 3:
        values.append(None)
    return values[0], values[1], values[2]
