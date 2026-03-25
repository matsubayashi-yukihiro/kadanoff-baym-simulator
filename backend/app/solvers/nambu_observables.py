from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.base import ObservableData, SeriesData
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian_derivative
from backend.app.solvers.lattice import SquareLattice
from backend.app.solvers.nambu import ComplexMatrix


def build_complex_observable(
    name: str,
    times: NDArray[np.float64],
    values: NDArray[np.complex128],
    metadata: dict[str, str],
) -> ObservableData:
    return ObservableData(
        name=name,
        time=times,
        series=[
            SeriesData(label="real", values=np.real(values).astype(np.float64)),
            SeriesData(label="imag", values=np.imag(values).astype(np.float64)),
            SeriesData(label="magnitude", values=np.abs(values).astype(np.float64)),
        ],
        metadata=metadata,
    )


def nambu_expectation_value(
    operator: ComplexMatrix,
    generalized_density: ComplexMatrix,
) -> float:
    return float(0.5 * np.real(np.trace(generalized_density @ operator)))


def explicit_bdg_hamiltonian_derivative(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
) -> ComplexMatrix:
    normal_derivative = build_one_body_hamiltonian_derivative(config, lattice, time)
    zero_block = np.zeros_like(normal_derivative)
    return np.block(
        [
            [normal_derivative, zero_block],
            [zero_block, -normal_derivative.conjugate()],
        ]
    )
