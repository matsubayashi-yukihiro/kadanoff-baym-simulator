from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ObservableSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    values: list[float]


class ObservableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    time: list[float]
    series: list[ObservableSeries]
    units: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservableCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    observables: list[str]
