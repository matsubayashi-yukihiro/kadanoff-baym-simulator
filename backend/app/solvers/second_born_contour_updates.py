from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.contour import causal_history_rule, history_average_matrix, history_average_rank3, tau_average_matrix
from backend.app.solvers.green_functions import MatsubaraBranchContainer, MixedBranchContainer
from backend.app.solvers.nambu import ComplexMatrix, extract_density_blocks
from backend.app.solvers.numerics import linear_mix
from backend.app.solvers.progress import ProgressCallback
from backend.app.jobs.progress import SolverProgressUpdate

if TYPE_CHECKING:
    from backend.app.solvers.tdhfb import HFBDynamicsResult


LocalSelfEnergyBuilder = Callable[
    [float, ComplexMatrix, ComplexMatrix, ComplexMatrix, int],
    ComplexMatrix,
]
KernelStabilizer = Callable[[ComplexMatrix], ComplexMatrix]
DampingCollision = Callable[[ComplexMatrix, np.ndarray], np.ndarray]
ThermalDensityReferenceBuilder = Callable[[MatsubaraBranchContainer | None], ComplexMatrix | None]


@dataclass(slots=True)
class MatsubaraContourUpdateResult:
    green: np.ndarray
    converged: bool
    iterations: int
    residual_history: list[float]
    memory_norm_history: list[float]
    order_history: list[int]


@dataclass(slots=True)
class MixedContourUpdateResult:
    right: np.ndarray
    left: np.ndarray
    converged: bool
    iterations: int
    residual_history: list[float]
    memory_norm_history: list[float]
    order_history: list[int]


@dataclass(slots=True)
class PrototypeMixedContourUpdateResult:
    right: np.ndarray
    left: np.ndarray
    memory_norm_history: list[float]


def run_reference_matsubara_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    factorized_branch: MatsubaraBranchContainer,
    onsite_strength: float,
    site_count: int,
    build_local_self_energy: LocalSelfEnergyBuilder,
    stabilize_kernel: KernelStabilizer,
    damping_collision: DampingCollision,
    thermal_density_reference: ThermalDensityReferenceBuilder,
    progress_callback: ProgressCallback | None,
) -> MatsubaraContourUpdateResult:
    current_green = factorized_branch.green.copy()
    density_reference = dynamics.equilibrium.generalized_density.copy()
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    residual_history: list[float] = []
    memory_norm_history: list[float] = []
    order_history: list[int] = []
    converged = False
    iterations = config.thermal_branch.max_iterations

    for iteration in range(1, config.thermal_branch.max_iterations + 1):
        updated_green = current_green.copy()
        max_residual = 0.0
        max_memory_norm = 0.0
        max_order = 1

        for tau_index in range(1, len(factorized_branch.tau) - 1):
            history_rule = causal_history_rule(factorized_branch.tau, history_start=0, stop_index=tau_index)
            history_average = history_average_matrix(
                past_values=updated_green[:tau_index],
                past_weights=history_rule.past_weights,
                current_value=current_green[tau_index],
                current_weight=history_rule.current_weight,
            )
            branch_value = current_green[tau_index]
            sigma_tau = build_local_self_energy(
                onsite_strength,
                branch_value,
                history_average,
                branch_value,
                site_count,
            )
            kernel = stabilize_kernel(sigma_tau)
            dtau = float(factorized_branch.tau[tau_index] - factorized_branch.tau[tau_index - 1])
            target = factorized_branch.green[tau_index] + dtau * damping_collision(kernel, branch_value - history_average)
            updated_green[tau_index] = linear_mix(branch_value, target, config.thermal_branch.mixing)
            max_residual = max(max_residual, float(np.max(np.abs(updated_green[tau_index] - branch_value))))
            max_memory_norm = max(max_memory_norm, float(np.max(np.abs(sigma_tau))) if sigma_tau.size else 0.0)
            max_order = max(max_order, history_rule.order)

        density_candidate = thermal_density_reference(
            MatsubaraBranchContainer(tau=factorized_branch.tau, green=updated_green)
        )
        if density_candidate is not None:
            density_reference = linear_mix(density_reference, density_candidate, config.thermal_branch.mixing)
            density_reference = 0.5 * (density_reference + density_reference.conjugate().T)
        updated_green[0] = -(identity - density_reference)
        updated_green[-1] = -density_reference
        current_green = updated_green
        residual_history.append(max_residual)
        memory_norm_history.append(max_memory_norm)
        order_history.append(max_order)
        iterations = iteration

        if progress_callback is not None:
            progress_callback(
                SolverProgressUpdate(
                    phase=RunProgressPhase.THERMAL_BRANCH,
                    status_line=f"thermal branch iteration {iteration}",
                    physical_time_current=float(dynamics.times[-1]),
                    physical_time_final=float(dynamics.times[-1]),
                    physical_progress_fraction=1.0,
                    accepted_steps=int(len(dynamics.times) - 1),
                    requested_steps=int(config.time.n_steps),
                    saved_samples_written=int(len(dynamics.saved_indices)),
                    solver_metrics={
                        "thermal_branch_iterations": int(iteration),
                        "latest_fixed_point_residual": max_residual,
                        "latest_memory_norm": max_memory_norm,
                        "history_integration_order": int(max_order),
                    },
                )
            )
        if max_residual <= config.kbe.tolerance:
            converged = True
            break

    if not converged and residual_history and residual_history[-1] <= 5.0 * config.kbe.tolerance:
        converged = True

    return MatsubaraContourUpdateResult(
        green=current_green,
        converged=converged,
        iterations=iterations,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        order_history=order_history,
    )


def run_reference_mixed_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer,
    factorized_branch: MixedBranchContainer,
    reference_densities: list[ComplexMatrix],
    onsite_strength: float,
    site_count: int,
    build_local_self_energy: LocalSelfEnergyBuilder,
    stabilize_kernel: KernelStabilizer,
    damping_collision: DampingCollision,
    progress_callback: ProgressCallback | None,
) -> MixedContourUpdateResult:
    right = factorized_branch.right.copy()
    left = factorized_branch.left.copy()
    residual_history: list[float] = []
    memory_norm_history: list[float] = []
    order_history: list[int] = []
    converged = True
    iterations = 0

    for time_index in range(1, len(dynamics.times)):
        history_rule = causal_history_rule(dynamics.times, history_start=0, stop_index=time_index)
        right_guess = right[time_index].copy()
        left_guess = left[time_index].copy()
        right_reference = np.broadcast_to(-1j * matsubara_branch.green, right_guess.shape)
        left_reference = np.broadcast_to(
            1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1),
            left_guess.shape,
        )
        last_residual = 0.0
        last_memory_norm = 0.0
        converged_step = False
        iterations = config.thermal_branch.max_iterations

        for iteration in range(1, config.thermal_branch.max_iterations + 1):
            right_history = history_average_rank3(
                past_values=right[:time_index],
                past_weights=history_rule.past_weights,
                current_value=right_guess,
                current_weight=history_rule.current_weight,
            )
            left_history = history_average_rank3(
                past_values=left[:time_index],
                past_weights=history_rule.past_weights,
                current_value=left_guess,
                current_weight=history_rule.current_weight,
            )
            mixed_average = 0.5 * (
                (-1j * tau_average_matrix(matsubara_branch.tau, right_history))
                + (1j * tau_average_matrix(matsubara_branch.tau, left_history))
            )
            mixed_average = 0.5 * (mixed_average + mixed_average.conjugate().T)
            sigma_mixed = build_local_self_energy(
                onsite_strength,
                mixed_average,
                reference_densities[time_index],
                mixed_average,
                site_count,
            )
            kernel = stabilize_kernel(sigma_mixed)
            step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
            target_right = factorized_branch.right[time_index] + step_dt * damping_collision(kernel, right_guess - right_reference)
            target_left = factorized_branch.left[time_index] + step_dt * damping_collision(kernel, left_guess - left_reference)
            updated_right = linear_mix(right_guess, target_right, config.thermal_branch.mixing)
            updated_left = linear_mix(left_guess, target_left, config.thermal_branch.mixing)
            last_residual = float(
                max(
                    np.max(np.abs(updated_right - right_guess)),
                    np.max(np.abs(updated_left - left_guess)),
                )
            )
            last_memory_norm = float(np.max(np.abs(sigma_mixed))) if sigma_mixed.size else 0.0
            right_guess = updated_right
            left_guess = updated_left
            iterations = iteration

            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.MIXED_BRANCH,
                        status_line=f"mixed branch t-index {time_index} iteration {iteration}",
                        physical_time_current=float(dynamics.times[time_index]),
                        physical_time_final=float(dynamics.times[-1]),
                        physical_progress_fraction=(
                            float(dynamics.times[time_index] / dynamics.times[-1]) if dynamics.times[-1] > 0 else 1.0
                        ),
                        accepted_steps=int(time_index),
                        requested_steps=int(len(dynamics.times) - 1),
                        saved_samples_written=int(np.count_nonzero(dynamics.saved_indices <= time_index)),
                        solver_metrics={
                            "current_time_index": int(time_index),
                            "latest_fixed_point_iterations": int(iteration),
                            "latest_fixed_point_residual": last_residual,
                            "latest_memory_norm": last_memory_norm,
                            "history_integration_order": int(history_rule.order),
                        },
                    )
                )
            if last_residual <= config.kbe.tolerance:
                converged_step = True
                break

        if not converged_step and last_residual <= 5.0 * config.kbe.tolerance:
            converged_step = True

        converged = converged and converged_step
        right[time_index] = right_guess
        left[time_index] = left_guess
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        order_history.append(history_rule.order)

    return MixedContourUpdateResult(
        right=right,
        left=left,
        converged=converged,
        iterations=iterations,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        order_history=order_history,
    )


def run_prototype_matsubara_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    factorized_branch: MatsubaraBranchContainer,
    onsite_strength: float,
    site_count: int,
    damping_collision: DampingCollision,
    thermal_density_reference: ThermalDensityReferenceBuilder,
    progress_callback: ProgressCallback | None,
) -> MatsubaraContourUpdateResult:
    current_green = factorized_branch.green.copy()
    density_reference = dynamics.equilibrium.generalized_density.copy()
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    residual_history: list[float] = []
    memory_norm_history: list[float] = []
    order_history: list[int] = []
    converged = False
    iterations = config.thermal_branch.max_iterations

    for iteration in range(1, config.thermal_branch.max_iterations + 1):
        updated_green = current_green.copy()
        max_residual = 0.0
        max_memory_norm = 0.0
        max_order = 1
        density_normal, density_pairing = extract_density_blocks(density_reference, site_count)
        density_occupancy = np.clip(np.real(np.diag(density_normal)), 0.0, 1.0)
        density_pairing_strength = np.abs(np.diag(density_pairing))

        for tau_index in range(1, len(factorized_branch.tau) - 1):
            history_rule = causal_history_rule(factorized_branch.tau, history_start=0, stop_index=tau_index)
            history_average = history_average_matrix(
                past_values=updated_green[:tau_index],
                past_weights=history_rule.past_weights,
                current_value=current_green[tau_index],
                current_weight=history_rule.current_weight,
            )
            branch_value = current_green[tau_index]
            envelope = np.abs(np.diagonal(branch_value[:site_count, :site_count]))
            gamma_site = onsite_strength**2 * envelope * (
                density_occupancy * (1.0 - density_occupancy) + density_pairing_strength**2 + 1e-12
            )
            gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
            dtau = float(factorized_branch.tau[tau_index] - factorized_branch.tau[tau_index - 1])
            collision = damping_collision(gamma_matrix, branch_value - history_average)
            target = factorized_branch.green[tau_index] + dtau * collision
            updated_green[tau_index] = linear_mix(branch_value, target, config.thermal_branch.mixing)
            updated_green[tau_index] = 0.5 * (updated_green[tau_index] + updated_green[tau_index].conjugate().T)
            max_residual = max(max_residual, float(np.max(np.abs(updated_green[tau_index] - branch_value))))
            max_memory_norm = max(max_memory_norm, float(np.max(gamma_site)) if len(gamma_site) else 0.0)
            max_order = max(max_order, history_rule.order)

        density_candidate = thermal_density_reference(
            MatsubaraBranchContainer(tau=factorized_branch.tau, green=updated_green)
        )
        if density_candidate is not None:
            density_reference = linear_mix(density_reference, density_candidate, config.thermal_branch.mixing)
            density_reference = 0.5 * (density_reference + density_reference.conjugate().T)
        updated_green[0] = -(identity - density_reference)
        updated_green[-1] = -density_reference

        current_green = updated_green
        residual_history.append(max_residual)
        memory_norm_history.append(max_memory_norm)
        order_history.append(max_order)
        iterations = iteration
        if progress_callback is not None:
            progress_callback(
                SolverProgressUpdate(
                    phase=RunProgressPhase.THERMAL_BRANCH,
                    status_line=f"thermal branch iteration {iteration}",
                    physical_time_current=float(dynamics.times[-1]),
                    physical_time_final=float(dynamics.times[-1]),
                    physical_progress_fraction=1.0,
                    accepted_steps=int(len(dynamics.times) - 1),
                    requested_steps=int(config.time.n_steps),
                    saved_samples_written=int(len(dynamics.saved_indices)),
                    solver_metrics={
                        "thermal_branch_iterations": int(iteration),
                        "latest_fixed_point_residual": max_residual,
                        "latest_memory_norm": max_memory_norm,
                        "history_integration_order": int(max_order),
                    },
                )
            )
        if max_residual <= config.kbe.tolerance:
            converged = True
            break

    if not converged and residual_history and residual_history[-1] <= 5.0 * config.kbe.tolerance:
        converged = True

    return MatsubaraContourUpdateResult(
        green=current_green,
        converged=converged,
        iterations=iterations,
        residual_history=residual_history,
        memory_norm_history=memory_norm_history,
        order_history=order_history,
    )


def run_prototype_mixed_updates(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer,
    factorized_branch: MixedBranchContainer,
    reference_densities: list[ComplexMatrix],
    onsite_strength: float,
    site_count: int,
    damping_collision: DampingCollision,
    progress_callback: ProgressCallback | None,
) -> PrototypeMixedContourUpdateResult:
    right = factorized_branch.right.copy()
    left = factorized_branch.left.copy()
    memory_norm_history: list[float] = []
    sample_count = len(dynamics.times)

    for time_index in range(1, sample_count):
        density_reference = reference_densities[time_index]
        density_normal, density_pairing = extract_density_blocks(density_reference, site_count)
        density_occupancy = np.clip(np.real(np.diag(density_normal)), 0.0, 1.0)
        density_pairing_strength = np.abs(np.diag(density_pairing))
        mixed_envelope = np.abs(
            np.diagonal(tau_average_matrix(matsubara_branch.tau, right[time_index])[:site_count, :site_count])
        )
        gamma_site = onsite_strength**2 * mixed_envelope * (
            density_occupancy * (1.0 - density_occupancy) + density_pairing_strength**2 + 1e-12
        )
        gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        right_reference = np.broadcast_to(-1j * matsubara_branch.green, right[time_index].shape)
        left_reference = np.broadcast_to(
            1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1),
            left[time_index].shape,
        )
        right[time_index] = factorized_branch.right[time_index] + step_dt * damping_collision(
            gamma_matrix,
            right[time_index] - right_reference,
        )
        left[time_index] = factorized_branch.left[time_index] + step_dt * damping_collision(
            gamma_matrix,
            left[time_index] - left_reference,
        )
        latest_memory_norm = float(np.max(gamma_site)) if len(gamma_site) else 0.0
        memory_norm_history.append(latest_memory_norm)
        if progress_callback is not None:
            progress_callback(
                SolverProgressUpdate(
                    phase=RunProgressPhase.MIXED_BRANCH,
                    status_line=f"mixed branch t-index {time_index}",
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
                        "latest_memory_norm": latest_memory_norm,
                    },
                )
            )

    return PrototypeMixedContourUpdateResult(
        right=right,
        left=left,
        memory_norm_history=memory_norm_history,
    )
