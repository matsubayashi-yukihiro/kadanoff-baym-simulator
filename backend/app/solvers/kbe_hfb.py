from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.base import SimulationArtifacts
from backend.app.solvers.tdhfb import HFBDynamicsResult, simulate_hfb_dynamics


@dataclass(slots=True)
class TwoTimeGreenFunctionContainer:
    times: NDArray[np.float64]
    retarded: NDArray[np.complex128]
    lesser: NDArray[np.complex128]


def solve(config: SimulationConfig) -> SimulationArtifacts:
    dynamics = simulate_hfb_dynamics(config)
    green_functions = build_two_time_green_functions(dynamics)
    diagnostics = dict(dynamics.diagnostics)
    diagnostics.update(_green_function_diagnostics(dynamics, green_functions))

    summary_excerpt = dict(dynamics.summary_excerpt)
    summary_excerpt["max_equal_time_tdhfb_mismatch"] = diagnostics["max_equal_time_tdhfb_mismatch"]
    return SimulationArtifacts(
        observables=dynamics.observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
    )


def build_two_time_green_functions(dynamics: HFBDynamicsResult) -> TwoTimeGreenFunctionContainer:
    sample_count = len(dynamics.times)
    nambu_dimension = 2 * dynamics.lattice.site_count
    retarded = np.zeros((sample_count, sample_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    lesser = np.zeros_like(retarded)
    initial_density = dynamics.generalized_densities[0]

    for row_index, left_propagator in enumerate(dynamics.cumulative_propagators):
        for column_index, right_propagator in enumerate(dynamics.cumulative_propagators):
            lesser[row_index, column_index] = 1j * left_propagator @ initial_density @ right_propagator.conjugate().T
            if row_index >= column_index:
                retarded[row_index, column_index] = -1j * left_propagator @ right_propagator.conjugate().T

    return TwoTimeGreenFunctionContainer(times=dynamics.times, retarded=retarded, lesser=lesser)


def _green_function_diagnostics(
    dynamics: HFBDynamicsResult,
    green_functions: TwoTimeGreenFunctionContainer,
) -> dict[str, float | list[int]]:
    nambu_dimension = 2 * dynamics.lattice.site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    equal_time_mismatch = 0.0
    lesser_hermiticity_error = 0.0

    for row_index in range(len(dynamics.times)):
        equal_time_mismatch = max(
            equal_time_mismatch,
            float(np.max(np.abs((-1j) * green_functions.lesser[row_index, row_index] - dynamics.generalized_densities[row_index]))),
        )
        for column_index in range(len(dynamics.times)):
            lesser_hermiticity_error = max(
                lesser_hermiticity_error,
                float(
                    np.max(
                        np.abs(
                            green_functions.lesser[row_index, column_index].conjugate().T
                            + green_functions.lesser[column_index, row_index]
                        )
                    )
                ),
            )

    retarded_equal_time_error = float(
        np.max(
            np.abs(
                green_functions.retarded[np.arange(len(dynamics.times)), np.arange(len(dynamics.times))] + 1j * identity
            )
        )
    )
    upper_triangle = np.triu(np.ones((len(dynamics.times), len(dynamics.times)), dtype=bool), k=1)
    retarded_causality_error = (
        float(np.max(np.abs(green_functions.retarded[upper_triangle])))
        if np.any(upper_triangle)
        else 0.0
    )
    return {
        "two_time_grid_shape": [
            int(green_functions.retarded.shape[0]),
            int(green_functions.retarded.shape[1]),
            int(green_functions.retarded.shape[2]),
            int(green_functions.retarded.shape[3]),
        ],
        "max_equal_time_tdhfb_mismatch": equal_time_mismatch,
        "max_lesser_hermiticity_error": lesser_hermiticity_error,
        "max_retarded_equal_time_error": retarded_equal_time_error,
        "max_retarded_causality_error": retarded_causality_error,
    }
