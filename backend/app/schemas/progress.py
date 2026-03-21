from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.runs import RunState


class RunProgressPhase(str, Enum):
    QUEUED = "queued"
    EQUILIBRIUM = "equilibrium"
    PROPAGATING = "propagating"
    THERMAL_BRANCH = "thermal_branch"
    MIXED_BRANCH = "mixed_branch"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunProgressPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    wall_seconds_elapsed: float
    physical_time_current: float | None = None
    physical_progress_fraction: float | None = None
    saved_samples_written: int = 0
    metric_1: float | None = None
    metric_2: float | None = None
    metric_3: float | None = None


class RunProgressRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    state: RunState
    phase: RunProgressPhase
    updated_at: datetime
    started_at: datetime | None = None
    wall_seconds_elapsed: float = 0.0
    physical_time_current: float | None = None
    physical_time_final: float | None = None
    physical_progress_fraction: float | None = None
    accepted_steps: int = 0
    requested_steps: int = 0
    rejected_steps: int = 0
    saved_samples_written: int = 0
    status_line: str | None = None
    solver_metrics: dict[str, Any] = Field(default_factory=dict)
    history: list[RunProgressPoint] = Field(default_factory=list)
