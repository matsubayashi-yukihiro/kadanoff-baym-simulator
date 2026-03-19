from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.research import RunResearchMetadata
from backend.app.schemas.simulation import SimulationConfig


class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ObservableSeriesDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    key: str


class ObservableDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    time_key: str
    series: list[ObservableSeriesDescriptor]
    units: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunStatusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    state: RunState
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    error: str | None = None
    pid: int | None = None


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    name: str | None = None
    solver: str
    state: RunState
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status_message: str | None = None
    lattice: dict[str, Any]
    time_grid: dict[str, Any]
    available_observables: list[ObservableDescriptor] = Field(default_factory=list)
    diagnostics_excerpt: dict[str, Any] = Field(default_factory=dict)
    research_metadata: RunResearchMetadata = Field(default_factory=RunResearchMetadata)


class RunDetail(RunSummary):
    config: SimulationConfig
    diagnostics: dict[str, Any] = Field(default_factory=dict)
