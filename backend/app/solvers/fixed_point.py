from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import anderson as scipy_anderson
from scipy.optimize import broyden1 as scipy_broyden1

from backend.app.solvers.numerics import linear_mix


ComplexArray = NDArray[np.complex128]
RealArray = NDArray[np.float64]


@dataclass(slots=True)
class FixedPointSolveResult:
    method: str
    iterations: int
    converged: bool
    residual_norm: float
    solution: RealArray


@dataclass(slots=True)
class AndersonMixer:
    mixing: float
    max_history: int = 4
    regularization: float = 1e-10
    start_iteration: int = 2
    _targets: list[ComplexArray] = field(default_factory=list)
    _residuals: list[ComplexArray] = field(default_factory=list)

    def update(self, current: NDArray[Any], target: NDArray[Any]) -> NDArray[Any]:
        current_array = np.asarray(current, dtype=np.complex128)
        target_array = np.asarray(target, dtype=np.complex128)
        if current_array.shape != target_array.shape:
            raise ValueError("current and target must have the same shape")

        residual = (target_array - current_array).reshape(-1)
        self._targets.append(target_array.reshape(-1).copy())
        self._residuals.append(residual.copy())
        if len(self._targets) > self.max_history:
            self._targets.pop(0)
            self._residuals.pop(0)

        if len(self._targets) < self.start_iteration:
            return _restore_dtype(linear_mix(current_array, target_array, self.mixing), current)

        coefficients = _diis_coefficients(self._residuals, self.regularization)
        accelerated_target = np.zeros_like(self._targets[-1])
        for coefficient, history_target in zip(coefficients, self._targets, strict=True):
            accelerated_target += coefficient * history_target
        mixed = linear_mix(current_array.reshape(-1), accelerated_target, self.mixing).reshape(current_array.shape)
        return _restore_dtype(mixed, current)

    def reset(self) -> None:
        self._targets.clear()
        self._residuals.clear()


def evaluate_fixed_point_solver(
    mapping: Callable[[RealArray], RealArray],
    *,
    initial: Iterable[float] | RealArray,
    method: str,
    tolerance: float = 1e-10,
    max_iterations: int = 64,
) -> FixedPointSolveResult:
    initial_array = np.asarray(initial, dtype=np.float64)
    iterations = 0

    def residual(state: RealArray) -> RealArray:
        nonlocal iterations
        iterations += 1
        return np.asarray(mapping(state), dtype=np.float64) - state

    if method == "anderson":
        solution = np.asarray(
            scipy_anderson(
                residual,
                xin=initial_array,
                maxiter=max_iterations,
                f_tol=tolerance,
                M=min(5, max(1, initial_array.size)),
                w0=0.01,
            ),
            dtype=np.float64,
        )
    elif method == "broyden1":
        solution = np.asarray(
            scipy_broyden1(
                residual,
                xin=initial_array,
                maxiter=max_iterations,
                f_tol=tolerance,
                alpha=0.5,
            ),
            dtype=np.float64,
        )
    else:
        raise ValueError(f"unsupported fixed-point evaluation method: {method}")

    residual_norm = float(np.max(np.abs(residual(solution))))
    return FixedPointSolveResult(
        method=method,
        iterations=iterations,
        converged=residual_norm <= tolerance,
        residual_norm=residual_norm,
        solution=solution,
    )


def _diis_coefficients(
    residuals: list[ComplexArray],
    regularization: float,
) -> NDArray[np.float64]:
    history_size = len(residuals)
    augmented = np.zeros((history_size + 1, history_size + 1), dtype=np.float64)
    rhs = np.zeros(history_size + 1, dtype=np.float64)
    rhs[-1] = 1.0

    for row in range(history_size):
        for column in range(history_size):
            augmented[row, column] = float(np.real(np.vdot(residuals[row], residuals[column])))
        augmented[row, row] += regularization
        augmented[row, -1] = 1.0
        augmented[-1, row] = 1.0

    try:
        solution = np.linalg.solve(augmented, rhs)
    except np.linalg.LinAlgError:
        solution, *_ = np.linalg.lstsq(augmented, rhs, rcond=None)
    return solution[:-1]


def _restore_dtype(value: ComplexArray, reference: NDArray[Any]) -> NDArray[Any]:
    reference_array = np.asarray(reference)
    if np.iscomplexobj(reference_array):
        return value.astype(np.complex128, copy=False)
    return np.real(value).astype(reference_array.dtype if reference_array.dtype != np.dtype("O") else np.float64, copy=False)
