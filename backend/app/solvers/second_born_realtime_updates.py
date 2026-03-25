from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.contour import (
    causal_history_rule,
    history_average_matrix,
    history_average_rank3,
    normalized_weights,
    tau_average_matrix,
)
from backend.app.solvers.green_functions import MixedBranchContainer, TwoTimeGreenFunctionContainer
from backend.app.solvers.nambu import ComplexMatrix, extract_density_blocks
from backend.app.solvers.numerics import linear_mix
from backend.app.solvers.progress import ProgressCallback
from backend.app.jobs.progress import SolverProgressUpdate

if TYPE_CHECKING:
    from backend.app.solvers.tdhfb import HFBDynamicsResult


ReferenceRowDataBuilder = Callable[
    [int, ComplexMatrix, list[ComplexMatrix], list[ComplexMatrix]],
    tuple[list[ComplexMatrix], list[ComplexMatrix], list[ComplexMatrix], list[ComplexMatrix]],
]
ReferenceKspaceRowDataBuilder = Callable[
    [int, np.ndarray, list[np.ndarray], list[np.ndarray]],
    tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[np.ndarray]],
]
LocalSelfEnergyBuilder = Callable[[float, ComplexMatrix, ComplexMatrix, ComplexMatrix, int], ComplexMatrix]
LocalSelfEnergyFromKAverageBuilder = Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
ExtractLocalNambuBlocks = Callable[[ComplexMatrix, int], np.ndarray]
KernelStabilizer = Callable[[ComplexMatrix], ComplexMatrix]
DampingCollision = Callable[[ComplexMatrix, np.ndarray], np.ndarray]
PrototypeCollision = Callable[[ComplexMatrix, NDArray[np.complex128]], NDArray[np.complex128]]


@dataclass(slots=True)
class RealtimeUpdateResult:
    corrected_densities: list[ComplexMatrix]
    iteration_history: list[int]
    residual_history: list[float]
    memory_norm_history: list[float]
    collision_norm_history: list[float]
    thermal_memory_norm_history: list[float]
    mixed_memory_norm_history: list[float]
    history_order_history: list[int]
    equation_residual_history: list[float]
    converged: bool
    used_relaxed_convergence: bool


@dataclass(slots=True)
class RealtimeKspaceUpdateResult:
    corrected_blocks: list[np.ndarray]
    iteration_history: list[int]
    residual_history: list[float]
    memory_norm_history: list[float]
    collision_norm_history: list[float]
    thermal_memory_norm_history: list[float]
    mixed_memory_norm_history: list[float]
    history_order_history: list[int]
    equation_residual_history: list[float]
    converged: bool
    used_relaxed_convergence: bool


@dataclass(slots=True)
class PrototypeRealtimeUpdateResult:
    corrected_densities: list[ComplexMatrix]
    retarded: np.ndarray
    lesser: np.ndarray
    iteration_history: list[int]
    residual_history: list[float]
    memory_norm_history: list[float]
    collision_norm_history: list[float]
    thermal_memory_norm_history: list[float]
    mixed_memory_norm_history: list[float]
    history_order_history: list[int]
    equation_residual_history: list[float]
    converged: bool
    used_relaxed_convergence: bool


def run_reference_realtime_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    onsite_strength: float,
    site_count: int,
    contour_density_reference: ComplexMatrix | None,
    thermal_branch_average: ComplexMatrix | None,
    mixed_branch: MixedBranchContainer | None,
    build_gkba_row_data: ReferenceRowDataBuilder,
    build_local_self_energy: LocalSelfEnergyBuilder,
    stabilize_kernel: KernelStabilizer,
    damping_collision: DampingCollision,
    progress_callback: ProgressCallback | None,
) -> RealtimeUpdateResult:
    corrected = [dynamics.generalized_densities[0].copy()]
    sample_count = len(dynamics.times)
    residual_history: list[float] = []
    iteration_history: list[int] = []
    memory_norm_history: list[float] = []
    collision_norm_history: list[float] = []
    thermal_memory_norm_history: list[float] = []
    mixed_memory_norm_history: list[float] = []
    history_order_history: list[int] = []
    equation_residual_history: list[float] = []
    converged = True
    used_relaxed_convergence = False

    for time_index in range(1, sample_count):
        base_density = dynamics.generalized_densities[time_index]
        history_start = 0 if config.kbe.memory_window is None else max(0, time_index - config.kbe.memory_window)
        history_rule = causal_history_rule(dynamics.times, history_start=history_start, stop_index=time_index)
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        equation_tolerance = config.kbe.tolerance / max(step_dt, 1e-12)
        guess_density = base_density.copy()
        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        last_thermal_norm = 0.0
        last_mixed_norm = 0.0
        last_equation_residual = 0.0
        converged_step = False

        for iteration in range(1, config.kbe.max_fixed_point_iterations + 1):
            row_lesser, column_lesser, row_greater, column_greater = build_gkba_row_data(
                time_index,
                guess_density,
                corrected,
                dynamics.cumulative_propagators,
            )
            collision = np.zeros_like(guess_density)
            max_self_energy_norm = 0.0

            history_indices = np.arange(history_start, time_index, dtype=np.int64)
            for weight, history_index in zip(history_rule.past_weights, history_indices, strict=True):
                sigma_lesser = build_local_self_energy(
                    onsite_strength,
                    row_lesser[history_index],
                    column_greater[history_index],
                    row_lesser[history_index],
                    site_count,
                )
                sigma_greater = build_local_self_energy(
                    onsite_strength,
                    row_greater[history_index],
                    column_lesser[history_index],
                    row_greater[history_index],
                    site_count,
                )
                integrand = sigma_greater @ column_lesser[history_index] - sigma_lesser @ column_greater[history_index]
                collision += weight * integrand
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser))),
                    float(np.max(np.abs(sigma_greater))),
                )

            if history_rule.current_weight > 0.0:
                sigma_lesser_eq = build_local_self_energy(
                    onsite_strength,
                    row_lesser[time_index],
                    row_greater[time_index],
                    row_lesser[time_index],
                    site_count,
                )
                sigma_greater_eq = build_local_self_energy(
                    onsite_strength,
                    row_greater[time_index],
                    row_lesser[time_index],
                    row_greater[time_index],
                    site_count,
                )
                integrand_eq = sigma_greater_eq @ row_lesser[time_index] - sigma_lesser_eq @ row_greater[time_index]
                collision += history_rule.current_weight * integrand_eq
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser_eq))),
                    float(np.max(np.abs(sigma_greater_eq))),
                )

            if thermal_branch_average is not None and contour_density_reference is not None:
                sigma_thermal = build_local_self_energy(
                    onsite_strength,
                    thermal_branch_average,
                    thermal_branch_average.conjugate().T,
                    thermal_branch_average,
                    site_count,
                )
                thermal_collision = damping_collision(
                    stabilize_kernel(sigma_thermal),
                    guess_density - contour_density_reference,
                )
                collision += thermal_collision
                last_thermal_norm = float(np.max(np.abs(sigma_thermal))) if sigma_thermal.size else 0.0
                max_self_energy_norm = max(max_self_energy_norm, last_thermal_norm)
            else:
                last_thermal_norm = 0.0

            if mixed_branch is not None and time_index < mixed_branch.right.shape[0]:
                mixed_right_average = tau_average_matrix(mixed_branch.tau, mixed_branch.right[time_index])
                mixed_left_average = tau_average_matrix(mixed_branch.tau, mixed_branch.left[time_index])
                mixed_density_reference = 0.5 * ((-1j * mixed_right_average) + (1j * mixed_left_average))
                mixed_density_reference = 0.5 * (mixed_density_reference + mixed_density_reference.conjugate().T)
                sigma_mixed = build_local_self_energy(
                    onsite_strength,
                    -1j * mixed_right_average,
                    1j * mixed_left_average,
                    row_lesser[time_index],
                    site_count,
                )
                mixed_collision = damping_collision(
                    stabilize_kernel(sigma_mixed),
                    guess_density - mixed_density_reference,
                )
                collision += mixed_collision
                last_mixed_norm = float(np.max(np.abs(sigma_mixed))) if sigma_mixed.size else 0.0
                max_self_energy_norm = max(max_self_energy_norm, last_mixed_norm)
            else:
                last_mixed_norm = 0.0

            target_density = base_density - step_dt * (collision + collision.conjugate().T)
            target_density = 0.5 * (target_density + target_density.conjugate().T)
            updated_density = linear_mix(guess_density, target_density, config.kbe.mixing)
            updated_density = 0.5 * (updated_density + updated_density.conjugate().T)
            last_residual = float(np.max(np.abs(updated_density - guess_density)))
            last_memory_norm = max_self_energy_norm
            last_collision_norm = float(np.max(np.abs(collision))) if collision.size else 0.0
            last_equation_residual = float(
                np.max(np.abs((updated_density - base_density) / step_dt + collision + collision.conjugate().T))
            )
            guess_density = updated_density
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"second Born fixed-point at t={float(dynamics.times[time_index]):.3f}",
                        physical_time_current=float(dynamics.times[time_index]),
                        physical_time_final=float(dynamics.times[-1]),
                        physical_progress_fraction=(
                            float(dynamics.times[time_index] / dynamics.times[-1]) if dynamics.times[-1] > 0 else 1.0
                        ),
                        accepted_steps=int(time_index),
                        requested_steps=int(sample_count - 1),
                        saved_samples_written=int(np.count_nonzero(dynamics.saved_indices <= time_index)),
                        solver_metrics={
                            "current_time_index": int(time_index),
                            "latest_fixed_point_iterations": int(iteration),
                            "latest_fixed_point_residual": last_residual,
                            "latest_equation_residual": last_equation_residual,
                            "latest_memory_norm": last_memory_norm,
                            "history_integration_order": int(history_rule.order),
                        },
                    )
                )
            if last_residual <= config.kbe.tolerance and last_equation_residual <= equation_tolerance:
                converged_step = True
                iteration_history.append(iteration)
                break
        else:
            iteration_history.append(config.kbe.max_fixed_point_iterations)

        if (
            not converged_step
            and last_residual <= 5.0 * config.kbe.tolerance
            and last_equation_residual <= 5.0 * equation_tolerance
        ):
            converged_step = True
            used_relaxed_convergence = True

        converged = converged and converged_step
        corrected.append(guess_density)
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)
        thermal_memory_norm_history.append(last_thermal_norm)
        mixed_memory_norm_history.append(last_mixed_norm)
        history_order_history.append(history_rule.order)
        equation_residual_history.append(last_equation_residual)

    return RealtimeUpdateResult(
        corrected_densities=corrected,
        iteration_history=iteration_history,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        collision_norm_history=collision_norm_history,
        thermal_memory_norm_history=thermal_memory_norm_history,
        mixed_memory_norm_history=mixed_memory_norm_history,
        history_order_history=history_order_history,
        equation_residual_history=equation_residual_history,
        converged=converged,
        used_relaxed_convergence=used_relaxed_convergence,
    )


def run_reference_kspace_realtime_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    onsite_strength: float,
    thermal_kernel_local: ComplexMatrix | None,
    contour_ref_blocks: np.ndarray | None,
    mixed_branch: MixedBranchContainer | None,
    build_gkba_row_data_kspace_blocks: ReferenceKspaceRowDataBuilder,
    build_local_self_energy_from_kaverage: LocalSelfEnergyFromKAverageBuilder,
    extract_local_nambu_blocks: ExtractLocalNambuBlocks,
    damping_collision: DampingCollision,
    progress_callback: ProgressCallback | None,
) -> RealtimeKspaceUpdateResult:
    assert dynamics.density_blocks_history is not None
    assert dynamics.cumulative_propagator_blocks is not None
    corrected_blocks = [dynamics.density_blocks_history[0].copy()]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    residual_history: list[float] = []
    iteration_history: list[int] = []
    memory_norm_history: list[float] = []
    collision_norm_history: list[float] = []
    thermal_memory_norm_history: list[float] = []
    mixed_memory_norm_history: list[float] = []
    history_order_history: list[int] = []
    equation_residual_history: list[float] = []
    converged = True
    used_relaxed_convergence = False

    for time_index in range(1, sample_count):
        base_blocks = dynamics.density_blocks_history[time_index]
        history_start = 0 if config.kbe.memory_window is None else max(0, time_index - config.kbe.memory_window)
        history_rule = causal_history_rule(dynamics.times, history_start=history_start, stop_index=time_index)
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        equation_tolerance = config.kbe.tolerance / max(step_dt, 1e-12)
        guess_blocks = base_blocks.copy()
        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        last_thermal_norm = 0.0
        last_mixed_norm = 0.0
        last_equation_residual = 0.0
        converged_step = False

        for iteration in range(1, config.kbe.max_fixed_point_iterations + 1):
            row_lesser, column_lesser, row_greater, column_greater = build_gkba_row_data_kspace_blocks(
                time_index,
                guess_blocks,
                corrected_blocks,
                dynamics.cumulative_propagator_blocks,
            )
            collision = np.zeros_like(guess_blocks)
            max_self_energy_norm = 0.0

            history_indices = np.arange(history_start, time_index, dtype=np.int64)
            for weight, history_index in zip(history_rule.past_weights, history_indices, strict=True):
                sigma_lesser = build_local_self_energy_from_kaverage(
                    onsite_strength,
                    row_lesser[history_index],
                    column_greater[history_index],
                    row_lesser[history_index],
                )
                sigma_greater = build_local_self_energy_from_kaverage(
                    onsite_strength,
                    row_greater[history_index],
                    column_lesser[history_index],
                    row_greater[history_index],
                )
                integrand = (
                    sigma_greater[np.newaxis] @ column_lesser[history_index]
                    - sigma_lesser[np.newaxis] @ column_greater[history_index]
                )
                collision += weight * integrand
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser))),
                    float(np.max(np.abs(sigma_greater))),
                )

            if history_rule.current_weight > 0.0:
                sigma_lesser_eq = build_local_self_energy_from_kaverage(
                    onsite_strength,
                    row_lesser[time_index],
                    row_greater[time_index],
                    row_lesser[time_index],
                )
                sigma_greater_eq = build_local_self_energy_from_kaverage(
                    onsite_strength,
                    row_greater[time_index],
                    row_lesser[time_index],
                    row_greater[time_index],
                )
                integrand_eq = (
                    sigma_greater_eq[np.newaxis] @ row_lesser[time_index]
                    - sigma_lesser_eq[np.newaxis] @ row_greater[time_index]
                )
                collision += history_rule.current_weight * integrand_eq
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser_eq))),
                    float(np.max(np.abs(sigma_greater_eq))),
                )

            if thermal_kernel_local is not None and contour_ref_blocks is not None:
                thermal_collision = damping_collision(thermal_kernel_local, guess_blocks - contour_ref_blocks)
                collision += thermal_collision
                last_thermal_norm = float(np.max(np.abs(thermal_kernel_local)))
                max_self_energy_norm = max(max_self_energy_norm, last_thermal_norm)
            else:
                last_thermal_norm = 0.0

            if mixed_branch is not None and time_index < mixed_branch.right.shape[0]:
                mixed_right_average = tau_average_matrix(mixed_branch.tau, mixed_branch.right[time_index])
                mixed_left_average = tau_average_matrix(mixed_branch.tau, mixed_branch.left[time_index])
                mixed_right_local = np.mean(extract_local_nambu_blocks(-1j * mixed_right_average, site_count), axis=0)
                mixed_left_local = np.mean(extract_local_nambu_blocks(1j * mixed_left_average, site_count), axis=0)
                mixed_density_ref_local = 0.5 * (mixed_right_local + mixed_left_local)
                mixed_density_ref_local = 0.5 * (mixed_density_ref_local + mixed_density_ref_local.conjugate().T)
                lesser_eq_local = np.mean(row_lesser[time_index], axis=0)
                sigma_mixed_local = onsite_strength**2 * (mixed_right_local @ mixed_left_local @ lesser_eq_local)
                mixed_kernel_local = 0.5 * (sigma_mixed_local + sigma_mixed_local.conjugate().T)
                mixed_ref_blocks = np.tile(mixed_density_ref_local, (site_count, 1, 1))
                mixed_collision = damping_collision(mixed_kernel_local, guess_blocks - mixed_ref_blocks)
                collision += mixed_collision
                last_mixed_norm = float(np.max(np.abs(sigma_mixed_local)))
                max_self_energy_norm = max(max_self_energy_norm, last_mixed_norm)
            else:
                last_mixed_norm = 0.0

            collision_hermitian = collision + np.swapaxes(collision.conjugate(), 1, 2)
            target_blocks = base_blocks - step_dt * collision_hermitian
            target_blocks = 0.5 * (target_blocks + np.swapaxes(target_blocks.conjugate(), 1, 2))
            updated_blocks = (1.0 - config.kbe.mixing) * guess_blocks + config.kbe.mixing * target_blocks
            updated_blocks = 0.5 * (updated_blocks + np.swapaxes(updated_blocks.conjugate(), 1, 2))
            last_residual = float(np.max(np.abs(updated_blocks - guess_blocks)))
            last_memory_norm = max_self_energy_norm
            last_collision_norm = float(np.max(np.abs(collision)))
            last_equation_residual = float(
                np.max(np.abs((updated_blocks - base_blocks) / step_dt + collision_hermitian))
            )
            guess_blocks = updated_blocks
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"second Born fixed-point (kblocks) at t={float(dynamics.times[time_index]):.3f}",
                        physical_time_current=float(dynamics.times[time_index]),
                        physical_time_final=float(dynamics.times[-1]),
                        physical_progress_fraction=(
                            float(dynamics.times[time_index] / dynamics.times[-1]) if dynamics.times[-1] > 0 else 1.0
                        ),
                        accepted_steps=int(time_index),
                        requested_steps=int(sample_count - 1),
                        saved_samples_written=int(np.count_nonzero(dynamics.saved_indices <= time_index)),
                        solver_metrics={
                            "current_time_index": int(time_index),
                            "latest_fixed_point_iterations": int(iteration),
                            "latest_fixed_point_residual": last_residual,
                            "latest_equation_residual": last_equation_residual,
                            "latest_memory_norm": last_memory_norm,
                            "history_integration_order": int(history_rule.order),
                        },
                    )
                )
            if last_residual <= config.kbe.tolerance and last_equation_residual <= equation_tolerance:
                converged_step = True
                iteration_history.append(iteration)
                break
        else:
            iteration_history.append(config.kbe.max_fixed_point_iterations)

        if (
            not converged_step
            and last_residual <= 5.0 * config.kbe.tolerance
            and last_equation_residual <= 5.0 * equation_tolerance
        ):
            converged_step = True
            used_relaxed_convergence = True

        converged = converged and converged_step
        corrected_blocks.append(guess_blocks)
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)
        thermal_memory_norm_history.append(last_thermal_norm)
        mixed_memory_norm_history.append(last_mixed_norm)
        history_order_history.append(history_rule.order)
        equation_residual_history.append(last_equation_residual)

    return RealtimeKspaceUpdateResult(
        corrected_blocks=corrected_blocks,
        iteration_history=iteration_history,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        collision_norm_history=collision_norm_history,
        thermal_memory_norm_history=thermal_memory_norm_history,
        mixed_memory_norm_history=mixed_memory_norm_history,
        history_order_history=history_order_history,
        equation_residual_history=equation_residual_history,
        converged=converged,
        used_relaxed_convergence=used_relaxed_convergence,
    )


def run_prototype_realtime_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer,
    contour_density_reference: ComplexMatrix | None,
    mixed_branch: MixedBranchContainer | None,
    collision: PrototypeCollision,
    progress_callback: ProgressCallback | None,
) -> PrototypeRealtimeUpdateResult:
    corrected = [density.copy() for density in dynamics.generalized_densities[:1]]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    nambu_dimension = 2 * site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    retarded = hfb_green_functions.retarded.copy()
    lesser = hfb_green_functions.lesser.copy()

    residual_history: list[float] = []
    iteration_history: list[int] = []
    memory_norm_history: list[float] = []
    collision_norm_history: list[float] = []
    thermal_memory_norm_history: list[float] = []
    mixed_memory_norm_history: list[float] = []
    history_order_history: list[int] = []
    equation_residual_history: list[float] = []
    converged = True
    used_relaxed_convergence = False

    for time_index in range(1, sample_count):
        base_density = dynamics.generalized_densities[time_index]
        base_row_lesser = lesser[time_index, :time_index].copy()
        base_row_retarded = retarded[time_index, :time_index].copy()
        guess_density = base_density.copy()
        guess_row_lesser = base_row_lesser.copy()
        guess_row_retarded = base_row_retarded.copy()
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        equation_tolerance = config.kbe.tolerance / max(step_dt, 1e-12)
        history_start = 0 if config.kbe.memory_window is None else max(0, time_index - config.kbe.memory_window)
        window_indices = np.arange(history_start, time_index, dtype=np.int64)
        history_rule = causal_history_rule(dynamics.times, history_start=history_start, stop_index=time_index)
        if len(window_indices) == 0 or (
            float(np.sum(history_rule.past_weights)) <= 1e-15 and history_rule.current_weight <= 1e-15
        ):
            corrected.append(base_density.copy())
            lesser[time_index, time_index] = 1j * base_density
            retarded[time_index, time_index] = -1j * identity
            residual_history.append(0.0)
            iteration_history.append(1)
            memory_norm_history.append(0.0)
            collision_norm_history.append(0.0)
            thermal_memory_norm_history.append(0.0)
            mixed_memory_norm_history.append(0.0)
            history_order_history.append(history_rule.order)
            equation_residual_history.append(0.0)
            continue

        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        last_thermal_norm = 0.0
        last_mixed_norm = 0.0
        last_equation_residual = 0.0
        converged_step = False

        for iteration in range(1, config.kbe.max_fixed_point_iterations + 1):
            density_history_average = history_average_matrix(
                past_values=np.asarray([corrected[index] for index in window_indices], dtype=np.complex128),
                past_weights=history_rule.past_weights,
                current_value=guess_density,
                current_weight=history_rule.current_weight,
            )
            row_lesser_history_average = history_average_rank3(
                past_values=lesser[window_indices, :time_index],
                past_weights=history_rule.past_weights,
                current_value=guess_row_lesser,
                current_weight=history_rule.current_weight,
            )
            row_retarded_history_average = history_average_rank3(
                past_values=retarded[window_indices, :time_index],
                past_weights=history_rule.past_weights,
                current_value=guess_row_retarded,
                current_weight=history_rule.current_weight,
            )
            normal_guess, pairing_guess = extract_density_blocks(guess_density, site_count)
            guess_occupancy = np.clip(np.real(np.diag(normal_guess)), 0.0, 1.0)
            guess_pairing = np.abs(np.diag(pairing_guess))
            gamma_site = np.zeros(site_count, dtype=np.float64)
            keldysh_envelope_scale = 0.0

            normalized_past_weights = normalized_weights(history_rule.past_weights)
            for normalized_weight, weight, history_index in zip(
                normalized_past_weights,
                history_rule.past_weights,
                window_indices,
                strict=True,
            ):
                history_normal, history_pairing = extract_density_blocks(corrected[history_index], site_count)
                history_occupancy = np.clip(np.real(np.diag(history_normal)), 0.0, 1.0)
                history_pairing_strength = np.abs(np.diag(history_pairing))
                envelope = np.abs(np.diagonal(guess_row_lesser[history_index, :site_count, :site_count]))
                gamma_site += (
                    weight
                    * abs(config.interaction.onsite_u) ** 2
                    * envelope
                    * (guess_occupancy * (1.0 - guess_occupancy) + guess_pairing**2)
                    * (history_occupancy * (1.0 - history_occupancy) + history_pairing_strength**2 + 1e-12)
                )
                keldysh_envelope_scale += normalized_weight * float(np.mean(envelope))

            thermal_reference = density_history_average
            thermal_envelope_scale = 0.0
            if contour_density_reference is not None:
                thermal_reference = 0.5 * (density_history_average + contour_density_reference)
                contour_normal, contour_pairing = extract_density_blocks(contour_density_reference, site_count)
                contour_occupancy = np.clip(np.real(np.diag(contour_normal)), 0.0, 1.0)
                contour_pairing_strength = np.abs(np.diag(contour_pairing))
                thermal_gamma = (
                    abs(config.interaction.onsite_u) ** 2
                    * (guess_occupancy * (1.0 - guess_occupancy) + guess_pairing**2)
                    * (contour_occupancy * (1.0 - contour_occupancy) + contour_pairing_strength**2 + 1e-12)
                )
                gamma_site += thermal_gamma
                thermal_envelope_scale = float(np.mean(contour_occupancy + contour_pairing_strength))
                last_thermal_norm = float(np.max(thermal_gamma)) if len(thermal_gamma) else 0.0
            else:
                last_thermal_norm = 0.0

            mixed_reference = row_lesser_history_average
            if mixed_branch is not None and time_index < mixed_branch.right.shape[0]:
                mixed_right_average = tau_average_matrix(mixed_branch.tau, mixed_branch.right[time_index])
                mixed_left_average = tau_average_matrix(mixed_branch.tau, mixed_branch.left[time_index])
                mixed_reference = np.broadcast_to(
                    0.5 * (-1j * mixed_right_average + 1j * mixed_left_average),
                    guess_row_lesser.shape,
                ).copy()
                mixed_envelope = 0.5 * (
                    np.abs(np.diagonal(mixed_right_average[:site_count, :site_count]))
                    + np.abs(np.diagonal(mixed_left_average[:site_count, :site_count]))
                )
                mixed_gamma = abs(config.interaction.onsite_u) ** 2 * mixed_envelope
                gamma_site += mixed_gamma
                last_mixed_norm = float(np.max(mixed_gamma)) if len(mixed_gamma) else 0.0
            else:
                last_mixed_norm = 0.0

            gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
            density_memory_drive = (
                keldysh_envelope_scale * (guess_density - density_history_average)
                + thermal_envelope_scale * (guess_density - thermal_reference)
            )
            row_lesser_memory_drive = (
                keldysh_envelope_scale * (guess_row_lesser - row_lesser_history_average)
                + max(last_mixed_norm, 1e-12) * (guess_row_lesser - mixed_reference)
            )
            row_retarded_memory_drive = keldysh_envelope_scale * (guess_row_retarded - row_retarded_history_average)

            density_collision = collision(gamma_matrix, density_memory_drive)
            row_lesser_collision = collision(gamma_matrix, row_lesser_memory_drive)
            row_retarded_collision = collision(gamma_matrix, row_retarded_memory_drive)

            target_density = base_density + step_dt * density_collision
            target_row_lesser = base_row_lesser + step_dt * row_lesser_collision
            target_row_retarded = base_row_retarded + step_dt * row_retarded_collision

            updated_density = linear_mix(guess_density, target_density, config.kbe.mixing)
            updated_density = 0.5 * (updated_density + updated_density.conjugate().T)
            updated_row_lesser = linear_mix(guess_row_lesser, target_row_lesser, config.kbe.mixing)
            updated_row_retarded = linear_mix(guess_row_retarded, target_row_retarded, config.kbe.mixing)

            last_residual = float(
                max(
                    np.max(np.abs(updated_density - guess_density)),
                    np.max(np.abs(updated_row_lesser - guess_row_lesser)) if updated_row_lesser.size else 0.0,
                    np.max(np.abs(updated_row_retarded - guess_row_retarded)) if updated_row_retarded.size else 0.0,
                )
            )
            last_memory_norm = float(np.max(gamma_site)) if len(gamma_site) else 0.0
            last_collision_norm = float(
                max(
                    np.max(np.abs(density_collision)),
                    np.max(np.abs(row_lesser_collision)) if row_lesser_collision.size else 0.0,
                    np.max(np.abs(row_retarded_collision)) if row_retarded_collision.size else 0.0,
                )
            )
            last_equation_residual = float(
                max(
                    np.max(np.abs((updated_density - base_density) / step_dt - density_collision)),
                    (
                        np.max(np.abs((updated_row_lesser - base_row_lesser) / step_dt - row_lesser_collision))
                        if updated_row_lesser.size
                        else 0.0
                    ),
                    (
                        np.max(np.abs((updated_row_retarded - base_row_retarded) / step_dt - row_retarded_collision))
                        if updated_row_retarded.size
                        else 0.0
                    ),
                )
            )
            guess_density = updated_density
            guess_row_lesser = updated_row_lesser
            guess_row_retarded = updated_row_retarded
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"prototype second Born fixed-point at t={float(dynamics.times[time_index]):.3f}",
                        physical_time_current=float(dynamics.times[time_index]),
                        physical_time_final=float(dynamics.times[-1]),
                        physical_progress_fraction=(
                            float(dynamics.times[time_index] / dynamics.times[-1]) if dynamics.times[-1] > 0 else 1.0
                        ),
                        accepted_steps=int(time_index),
                        requested_steps=int(sample_count - 1),
                        saved_samples_written=int(np.count_nonzero(dynamics.saved_indices <= time_index)),
                        solver_metrics={
                            "current_time_index": int(time_index),
                            "latest_fixed_point_iterations": int(iteration),
                            "latest_fixed_point_residual": last_residual,
                            "latest_equation_residual": last_equation_residual,
                            "latest_memory_norm": last_memory_norm,
                            "history_integration_order": int(history_rule.order),
                        },
                    )
                )
            if last_residual <= config.kbe.tolerance and last_equation_residual <= equation_tolerance:
                converged_step = True
                iteration_history.append(iteration)
                break
        else:
            iteration_history.append(config.kbe.max_fixed_point_iterations)

        if (
            not converged_step
            and last_residual <= 5.0 * config.kbe.tolerance
            and last_equation_residual <= 5.0 * equation_tolerance
        ):
            converged_step = True
            used_relaxed_convergence = True

        converged = converged and converged_step
        corrected.append(guess_density)
        lesser[time_index, time_index] = 1j * guess_density
        retarded[time_index, time_index] = -1j * identity
        lesser[time_index, :time_index] = guess_row_lesser
        lesser[:time_index, time_index] = -guess_row_lesser.conjugate().transpose(0, 2, 1)
        retarded[time_index, :time_index] = guess_row_retarded
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)
        thermal_memory_norm_history.append(last_thermal_norm)
        mixed_memory_norm_history.append(last_mixed_norm)
        history_order_history.append(history_rule.order)
        equation_residual_history.append(last_equation_residual)

    return PrototypeRealtimeUpdateResult(
        corrected_densities=corrected,
        retarded=retarded,
        lesser=lesser,
        iteration_history=iteration_history,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        collision_norm_history=collision_norm_history,
        thermal_memory_norm_history=thermal_memory_norm_history,
        mixed_memory_norm_history=mixed_memory_norm_history,
        history_order_history=history_order_history,
        equation_residual_history=equation_residual_history,
        converged=converged,
        used_relaxed_convergence=used_relaxed_convergence,
    )
