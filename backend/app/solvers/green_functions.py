from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.nambu import ComplexMatrix
from backend.app.solvers.tdhfb import HFBDynamicsResult


@dataclass(slots=True)
class TwoTimeGreenFunctionContainer:
    times: NDArray[np.float64]
    retarded: NDArray[np.complex128]
    lesser: NDArray[np.complex128]


@dataclass(slots=True)
class MatsubaraBranchContainer:
    tau: NDArray[np.float64]
    green: NDArray[np.complex128]


@dataclass(slots=True)
class MixedBranchContainer:
    times: NDArray[np.float64]
    tau: NDArray[np.float64]
    right: NDArray[np.complex128]
    left: NDArray[np.complex128]


@dataclass(slots=True)
class MatsubaraBranchBuildResult:
    branch: MatsubaraBranchContainer | None
    factorized_branch: MatsubaraBranchContainer | None
    diagnostics: dict[str, Any]


@dataclass(slots=True)
class MixedBranchBuildResult:
    branch: MixedBranchContainer | None
    factorized_branch: MixedBranchContainer | None
    diagnostics: dict[str, Any]


def build_two_time_green_functions(
    dynamics: HFBDynamicsResult,
    generalized_densities: list[ComplexMatrix] | None = None,
) -> TwoTimeGreenFunctionContainer:
    sample_count = len(dynamics.times)
    nambu_dimension = 2 * dynamics.lattice.site_count
    retarded = np.zeros((sample_count, sample_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    lesser = np.zeros_like(retarded)
    initial_density = None
    if generalized_densities is None:
        initial_density = dynamics.generalized_densities[0]

    for row_index, left_propagator in enumerate(dynamics.cumulative_propagators):
        for column_index, right_propagator in enumerate(dynamics.cumulative_propagators):
            if generalized_densities is None:
                lesser[row_index, column_index] = (
                    1j * left_propagator @ initial_density @ right_propagator.conjugate().T
                )
            else:
                lesser[row_index, column_index] = 0.5j * (
                    generalized_densities[row_index] + generalized_densities[column_index]
                )
            if row_index >= column_index:
                retarded[row_index, column_index] = -1j * left_propagator @ right_propagator.conjugate().T

    return TwoTimeGreenFunctionContainer(times=dynamics.times, retarded=retarded, lesser=lesser)


def green_function_diagnostics(
    *,
    dynamics: HFBDynamicsResult,
    green_functions: TwoTimeGreenFunctionContainer,
    reference_densities: list[ComplexMatrix],
    tdhfb_reference_densities: list[ComplexMatrix],
    reconstruction_mode: str | None = None,
) -> dict[str, float | list[int] | str]:
    nambu_dimension = 2 * dynamics.lattice.site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    equal_time_reconstruction_error = 0.0
    equal_time_tdhfb_mismatch = 0.0
    lesser_hermiticity_error = 0.0

    for row_index in range(len(dynamics.times)):
        equal_time_reconstruction_error = max(
            equal_time_reconstruction_error,
            float(np.max(np.abs((-1j) * green_functions.lesser[row_index, row_index] - reference_densities[row_index]))),
        )
        equal_time_tdhfb_mismatch = max(
            equal_time_tdhfb_mismatch,
            float(np.max(np.abs(reference_densities[row_index] - tdhfb_reference_densities[row_index]))),
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
        "kbe_two_time_reconstruction": (
            reconstruction_mode
            if reconstruction_mode is not None
            else ("exact_hfb" if equal_time_tdhfb_mismatch == 0.0 else "equal_time_average")
        ),
        "max_equal_time_tdhfb_mismatch": equal_time_tdhfb_mismatch,
        "max_equal_time_density_reconstruction_error": equal_time_reconstruction_error,
        "max_lesser_hermiticity_error": lesser_hermiticity_error,
        "max_retarded_equal_time_error": retarded_equal_time_error,
        "max_retarded_causality_error": retarded_causality_error,
    }
