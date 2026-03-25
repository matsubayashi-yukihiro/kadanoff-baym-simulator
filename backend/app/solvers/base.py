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
class TwoTimeGreenFunctionData:
    times: NDArray[np.float64]
    components: dict[str, NDArray[np.complex128]]


@dataclass(slots=True)
class ThermalBranchGreenFunctionData:
    tau: NDArray[np.float64]
    components: dict[str, NDArray[np.complex128]]


@dataclass(slots=True)
class MixedGreenFunctionData:
    times: NDArray[np.float64]
    tau: NDArray[np.float64]
    components: dict[str, NDArray[np.complex128]]


@dataclass(slots=True)
class KSpaceNativeTrajectoryData:
    times: NDArray[np.float64]
    density_blocks_history: NDArray[np.complex128]
    cumulative_propagator_blocks: NDArray[np.complex128]
    kx: NDArray[np.float64]
    ky: NDArray[np.float64]
    reconstruction_mode: str | None = None


@dataclass(slots=True)
class SimulationArtifacts:
    observables: dict[str, ObservableData]
    diagnostics: dict[str, Any]
    summary_excerpt: dict[str, Any]
    two_time_green_functions: TwoTimeGreenFunctionData | None = None
    thermal_branch_green_functions: ThermalBranchGreenFunctionData | None = None
    mixed_green_functions: MixedGreenFunctionData | None = None
    kspace_native_trajectory: KSpaceNativeTrajectoryData | None = None
