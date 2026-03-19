from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.benchmarks.exact_diagonalization import ExactDiagonalizationBenchmarkResult


ObservableName = Literal["density", "current_x", "current_y", "energy"]


@dataclass(slots=True)
class BenchmarkTrajectory:
    label: str
    times: NDArray[np.float64]
    values: NDArray[np.complex128]


@dataclass(slots=True)
class BenchmarkErrorSummary:
    max_abs_error: float
    mean_abs_error: float
    final_abs_error: float


@dataclass(slots=True)
class BenchmarkTableRow:
    label: str
    sample_count: int
    max_abs_error: float
    mean_abs_error: float
    final_abs_error: float


def build_benchmark_trajectory(
    label: str,
    *,
    times: Sequence[float] | NDArray[np.float64],
    values: Sequence[complex] | NDArray[np.complex128],
) -> BenchmarkTrajectory:
    times_array = np.asarray(times, dtype=np.float64)
    values_array = np.asarray(values, dtype=np.complex128)
    if times_array.ndim != 1:
        raise ValueError("benchmark trajectory times must be one-dimensional")
    if values_array.ndim != 1:
        raise ValueError("benchmark trajectory values must be one-dimensional")
    if len(times_array) == 0:
        raise ValueError("benchmark trajectory must contain at least one sample")
    if len(times_array) != len(values_array):
        raise ValueError("benchmark trajectory times and values must have the same length")
    if np.any(np.diff(times_array) < -1e-12):
        raise ValueError("benchmark trajectory times must be monotonically nondecreasing")
    return BenchmarkTrajectory(label=label, times=times_array, values=values_array)


def exact_diagonalization_trajectory(
    result: ExactDiagonalizationBenchmarkResult,
    observable_name: ObservableName,
    *,
    label: str | None = None,
) -> BenchmarkTrajectory:
    observable_map: dict[ObservableName, NDArray[np.float64]] = {
        "density": result.density_mean,
        "current_x": result.current_x,
        "current_y": result.current_y,
        "energy": result.total_energy,
    }
    return build_benchmark_trajectory(
        label or f"exact:{observable_name}",
        times=result.times,
        values=observable_map[observable_name],
    )


def interpolate_trajectory(
    reference: BenchmarkTrajectory,
    sample_times: Sequence[float] | NDArray[np.float64],
) -> NDArray[np.complex128]:
    target_times = np.asarray(sample_times, dtype=np.float64)
    if target_times.ndim != 1:
        raise ValueError("sample_times must be one-dimensional")
    if len(target_times) == 0:
        raise ValueError("sample_times must contain at least one sample")
    if np.any(np.diff(target_times) < -1e-12):
        raise ValueError("sample_times must be monotonically nondecreasing")
    if target_times[0] < reference.times[0] - 1e-12 or target_times[-1] > reference.times[-1] + 1e-12:
        raise ValueError("sample_times must lie within the reference trajectory range")
    real_values = np.interp(target_times, reference.times, np.real(reference.values))
    imag_values = np.interp(target_times, reference.times, np.imag(reference.values))
    return real_values.astype(np.complex128) + 1j * imag_values.astype(np.complex128)


def summarize_trajectory_error(
    reference: BenchmarkTrajectory,
    candidate: BenchmarkTrajectory,
) -> BenchmarkErrorSummary:
    reference_values = interpolate_trajectory(reference, candidate.times)
    absolute_error = np.abs(candidate.values - reference_values)
    return BenchmarkErrorSummary(
        max_abs_error=float(np.max(absolute_error)),
        mean_abs_error=float(np.mean(absolute_error)),
        final_abs_error=float(absolute_error[-1]),
    )


def build_convergence_table(
    reference: BenchmarkTrajectory,
    candidates: Sequence[BenchmarkTrajectory],
) -> list[BenchmarkTableRow]:
    rows: list[BenchmarkTableRow] = []
    for candidate in candidates:
        error_summary = summarize_trajectory_error(reference, candidate)
        rows.append(
            BenchmarkTableRow(
                label=candidate.label,
                sample_count=int(len(candidate.times)),
                max_abs_error=error_summary.max_abs_error,
                mean_abs_error=error_summary.mean_abs_error,
                final_abs_error=error_summary.final_abs_error,
            )
        )
    return rows
