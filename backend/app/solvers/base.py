from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(slots=True)
class SeriesData:
    label: str
    values: NDArray[np.float64]


@dataclass(slots=True)
class ObservableData:
    name: str
    time: NDArray[np.float64]
    series: list[SeriesData]
    units: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SimulationArtifacts:
    observables: dict[str, ObservableData]
    diagnostics: dict[str, Any]
    summary_excerpt: dict[str, Any]
