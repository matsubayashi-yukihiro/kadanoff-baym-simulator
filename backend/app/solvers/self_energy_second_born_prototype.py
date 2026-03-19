from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.contour import (
    causal_history_rule,
    history_average_matrix,
    history_average_rank3,
    normalized_weights,
    tau_average_matrix,
)
from backend.app.solvers.green_functions import (
    MatsubaraBranchBuildResult,
    MatsubaraBranchContainer,
    MixedBranchBuildResult,
    MixedBranchContainer,
    TwoTimeGreenFunctionContainer,
    build_factorized_matsubara_green_function,
    build_factorized_mixed_branch as build_shared_factorized_mixed_branch,
)
from backend.app.solvers.nambu import ComplexMatrix, build_bdg_hamiltonian, extract_density_blocks
from backend.app.solvers.numerics import linear_mix
from backend.app.solvers.tdhfb import HFBDynamicsResult


PROTOTYPE_IMPLEMENTATION_KIND = "heuristic_prototype"
FACTORIZED_IMPLEMENTATION_KIND = "factorized_hfb"


@dataclass(slots=True)
class SecondBornCorrectionResult:
    generalized_densities: list[ComplexMatrix]
    green_functions: TwoTimeGreenFunctionContainer
    diagnostics: dict[str, Any]


def apply_second_born_corrections(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
) -> SecondBornCorrectionResult:
    onsite_strength = abs(config.interaction.onsite_u)
    sample_count = len(dynamics.times)
    if sample_count <= 1 or onsite_strength <= 1e-12:
        diagnostics = _base_second_born_diagnostics(
            sample_count=sample_count,
            memory_window=config.kbe.memory_window,
        )
        diagnostics.update(
            {
                "second_born_contour_terms_included": False,
                "second_born_contour_mode": "hfb_limit",
                "second_born_solver_mode": "hfb_limit",
            }
        )
        return SecondBornCorrectionResult(
            generalized_densities=[density.copy() for density in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics=diagnostics,
        )

    corrected = [density.copy() for density in dynamics.generalized_densities[:1]]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    nambu_dimension = 2 * site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    retarded = hfb_green_functions.retarded.copy()
    lesser = hfb_green_functions.lesser.copy()
    contour_density_reference = thermal_branch_density_reference(matsubara_branch)
    contour_mode = (
        "full_contour"
        if matsubara_branch is not None and mixed_branch is not None
        else ("thermal_only" if matsubara_branch is not None else "keldysh_only")
    )

    residual_history: list[float] = []
    iteration_history: list[int] = []
    memory_norm_history: list[float] = []
    collision_norm_history: list[float] = []
    thermal_memory_norm_history: list[float] = []
    mixed_memory_norm_history: list[float] = []
    history_order_history: list[int] = []
    converged = True

    for time_index in range(1, sample_count):
        base_density = dynamics.generalized_densities[time_index]
        base_row_lesser = lesser[time_index, :time_index].copy()
        base_row_retarded = retarded[time_index, :time_index].copy()
        guess_density = base_density.copy()
        guess_row_lesser = base_row_lesser.copy()
        guess_row_retarded = base_row_retarded.copy()
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
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
            continue

        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        last_thermal_norm = 0.0
        last_mixed_norm = 0.0
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

            density_collision = dissipative_collision(gamma_matrix, density_memory_drive)
            row_lesser_collision = dissipative_collision(gamma_matrix, row_lesser_memory_drive)
            row_retarded_collision = dissipative_collision(gamma_matrix, row_retarded_memory_drive)

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
            guess_density = updated_density
            guess_row_lesser = updated_row_lesser
            guess_row_retarded = updated_row_retarded
            if last_residual <= config.kbe.tolerance:
                converged_step = True
                iteration_history.append(iteration)
                break
        else:
            iteration_history.append(config.kbe.max_fixed_point_iterations)

        if not converged_step and last_residual <= 5.0 * config.kbe.tolerance:
            converged_step = True

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

    diagnostics = _base_second_born_diagnostics(
        sample_count=sample_count,
        memory_window=config.kbe.memory_window,
    )
    diagnostics.update(
        {
            "second_born_converged": converged,
            "second_born_iteration_history": iteration_history,
            "second_born_residual_history": residual_history,
            "second_born_memory_norm_history": memory_norm_history,
            "second_born_collision_norm_history": collision_norm_history,
            "second_born_thermal_memory_norm_history": thermal_memory_norm_history,
            "second_born_mixed_memory_norm_history": mixed_memory_norm_history,
            "second_born_history_integration_order_history": history_order_history,
            "max_second_born_memory_norm": float(max(memory_norm_history)) if memory_norm_history else 0.0,
            "max_second_born_collision_norm": float(max(collision_norm_history)) if collision_norm_history else 0.0,
            "max_second_born_thermal_memory_norm": (
                float(max(thermal_memory_norm_history)) if thermal_memory_norm_history else 0.0
            ),
            "max_second_born_mixed_memory_norm": float(max(mixed_memory_norm_history)) if mixed_memory_norm_history else 0.0,
            "second_born_history_integration_max_order": max(history_order_history) if history_order_history else 1,
            "second_born_contour_terms_included": contour_mode != "keldysh_only",
            "second_born_contour_mode": contour_mode,
            "second_born_solver_mode": "two_time_causal_marching",
        }
    )
    return SecondBornCorrectionResult(
        generalized_densities=corrected,
        green_functions=TwoTimeGreenFunctionContainer(
            times=dynamics.times,
            retarded=retarded,
            lesser=lesser,
        ),
        diagnostics=diagnostics,
    )


def build_matsubara_branch(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
) -> MatsubaraBranchBuildResult:
    factorized_branch = _build_factorized_matsubara_branch(config, dynamics)
    if factorized_branch is None:
        return MatsubaraBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "thermal_branch_enabled": False,
                "thermal_branch_correlated": False,
                "mixed_components_included": False,
                "thermal_branch_factorized_difference": 0.0,
                "thermal_branch_reference_implementation": False,
                "thermal_branch_implementation_kind": "disabled",
            },
        )

    onsite_strength = abs(config.interaction.onsite_u)
    if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN or onsite_strength <= 1e-12:
        return MatsubaraBranchBuildResult(
            branch=factorized_branch,
            factorized_branch=factorized_branch,
            diagnostics=_matsubara_diagnostics(
                config=config,
                dynamics=dynamics,
                matsubara_branch=factorized_branch,
                factorized_branch=factorized_branch,
                converged=True,
                iterations=1,
                residual_history=[0.0],
                memory_norm_history=[0.0],
                order_history=[1],
                implementation_kind=FACTORIZED_IMPLEMENTATION_KIND,
            ),
        )

    current_green = factorized_branch.green.copy()
    density_reference = dynamics.equilibrium.generalized_density.copy()
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    site_count = dynamics.lattice.site_count
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
            gamma_site = (
                onsite_strength**2
                * envelope
                * (density_occupancy * (1.0 - density_occupancy) + density_pairing_strength**2 + 1e-12)
            )
            gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
            dtau = float(factorized_branch.tau[tau_index] - factorized_branch.tau[tau_index - 1])
            collision = dissipative_collision(gamma_matrix, branch_value - history_average)
            target = factorized_branch.green[tau_index] + dtau * collision
            updated_green[tau_index] = linear_mix(branch_value, target, config.thermal_branch.mixing)
            updated_green[tau_index] = 0.5 * (updated_green[tau_index] + updated_green[tau_index].conjugate().T)
            max_residual = max(max_residual, float(np.max(np.abs(updated_green[tau_index] - branch_value))))
            max_memory_norm = max(max_memory_norm, float(np.max(gamma_site)) if len(gamma_site) else 0.0)
            max_order = max(max_order, history_rule.order)

        density_candidate = thermal_branch_density_reference(
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
        if max_residual <= config.kbe.tolerance:
            converged = True
            break

    if not converged and residual_history and residual_history[-1] <= 5.0 * config.kbe.tolerance:
        converged = True

    correlated_branch = MatsubaraBranchContainer(tau=factorized_branch.tau, green=current_green)
    return MatsubaraBranchBuildResult(
        branch=correlated_branch,
        factorized_branch=factorized_branch,
        diagnostics=_matsubara_diagnostics(
            config=config,
            dynamics=dynamics,
            matsubara_branch=correlated_branch,
            factorized_branch=factorized_branch,
            converged=converged,
            iterations=iterations,
            residual_history=residual_history,
            memory_norm_history=memory_norm_history,
            order_history=order_history,
            implementation_kind=PROTOTYPE_IMPLEMENTATION_KIND,
        ),
    )


def build_factorized_mixed_branch(
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> MixedBranchContainer | None:
    return build_shared_factorized_mixed_branch(dynamics, matsubara_branch)


def build_mixed_branch(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
    reference_densities: list[ComplexMatrix],
    factorized_branch: MixedBranchContainer | None,
) -> MixedBranchBuildResult:
    if matsubara_branch is None:
        return MixedBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "mixed_components_included": False,
                "mixed_branch_factorized_difference": 0.0,
                "mixed_branch_reference_implementation": False,
                "mixed_branch_implementation_kind": "disabled",
            },
        )

    if factorized_branch is None:
        factorized_branch = build_factorized_mixed_branch(dynamics, matsubara_branch)
    if factorized_branch is None:
        return MixedBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={
                "mixed_components_included": False,
                "mixed_branch_factorized_difference": 0.0,
                "mixed_branch_reference_implementation": False,
                "mixed_branch_implementation_kind": "disabled",
            },
        )

    onsite_strength = abs(config.interaction.onsite_u)
    if config.kbe.self_energy != KBESelfEnergyMode.SECOND_BORN or onsite_strength <= 1e-12:
        return MixedBranchBuildResult(
            branch=factorized_branch,
            factorized_branch=factorized_branch,
            diagnostics=_mixed_branch_diagnostics(
                matsubara_branch=matsubara_branch,
                mixed_branch=factorized_branch,
                factorized_branch=factorized_branch,
                implementation_kind=FACTORIZED_IMPLEMENTATION_KIND,
            ),
        )

    right = factorized_branch.right.copy()
    left = factorized_branch.left.copy()
    site_count = dynamics.lattice.site_count
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
        gamma_site = (
            onsite_strength**2
            * mixed_envelope
            * (density_occupancy * (1.0 - density_occupancy) + density_pairing_strength**2 + 1e-12)
        )
        gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        right_reference = np.broadcast_to(-1j * matsubara_branch.green, right[time_index].shape)
        left_reference = np.broadcast_to(
            1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1),
            left[time_index].shape,
        )
        right[time_index] = factorized_branch.right[time_index] + step_dt * dissipative_collision(
            gamma_matrix,
            right[time_index] - right_reference,
        )
        left[time_index] = factorized_branch.left[time_index] + step_dt * dissipative_collision(
            gamma_matrix,
            left[time_index] - left_reference,
        )
        memory_norm_history.append(float(np.max(gamma_site)) if len(gamma_site) else 0.0)

    branch = MixedBranchContainer(
        times=dynamics.times,
        tau=matsubara_branch.tau,
        right=right,
        left=left,
    )
    diagnostics = _mixed_branch_diagnostics(
        matsubara_branch=matsubara_branch,
        mixed_branch=branch,
        factorized_branch=factorized_branch,
        implementation_kind=PROTOTYPE_IMPLEMENTATION_KIND,
    )
    diagnostics["mixed_branch_memory_norm_history"] = memory_norm_history
    diagnostics["max_mixed_branch_memory_norm"] = float(max(memory_norm_history)) if memory_norm_history else 0.0
    return MixedBranchBuildResult(
        branch=branch,
        factorized_branch=factorized_branch,
        diagnostics=diagnostics,
    )


def thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    density = -matsubara_branch.green[-1]
    return 0.5 * (density + density.conjugate().T)


def dissipative_collision(
    kernel: ComplexMatrix,
    values: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    if values.ndim == 2:
        return -0.5 * (kernel @ values + values @ kernel)
    if values.ndim == 3:
        return -0.5 * (
            np.einsum("ab,kbc->kac", kernel, values)
            + np.einsum("kab,bc->kac", values, kernel)
        )
    raise ValueError(f"unsupported value rank for collision kernel: {values.ndim}")


def _base_second_born_diagnostics(*, sample_count: int, memory_window: int | None) -> dict[str, Any]:
    zero_history_length = max(sample_count - 1, 0)
    return {
        "second_born_enabled": True,
        "second_born_converged": True,
        "second_born_iteration_history": [1] * zero_history_length,
        "second_born_residual_history": [0.0] * zero_history_length,
        "second_born_memory_norm_history": [0.0] * zero_history_length,
        "second_born_collision_norm_history": [0.0] * zero_history_length,
        "second_born_thermal_memory_norm_history": [0.0] * zero_history_length,
        "second_born_mixed_memory_norm_history": [0.0] * zero_history_length,
        "second_born_history_integration_order_history": [1] * zero_history_length,
        "max_second_born_memory_norm": 0.0,
        "max_second_born_collision_norm": 0.0,
        "max_second_born_thermal_memory_norm": 0.0,
        "max_second_born_mixed_memory_norm": 0.0,
        "second_born_memory_window": int(memory_window or max(sample_count - 1, 0)),
        "second_born_history_integration_max_order": 1,
        "second_born_reference_implementation": False,
        "second_born_implementation_kind": PROTOTYPE_IMPLEMENTATION_KIND,
    }


def _build_factorized_matsubara_branch(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
) -> MatsubaraBranchContainer | None:
    if not config.thermal_branch.enabled:
        return None

    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        dynamics.lattice,
        0.0,
        dynamics.equilibrium.generalized_density,
        dynamics.equilibrium.effective_chemical_potential,
    )
    return build_factorized_matsubara_green_function(
        temperature=config.initial_state.temperature,
        n_tau=config.thermal_branch.n_tau,
        bdg_hamiltonian=bdg_hamiltonian,
    )


def _matsubara_diagnostics(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
    factorized_branch: MatsubaraBranchContainer | None,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
    implementation_kind: str,
) -> dict[str, Any]:
    if matsubara_branch is None:
        return {
            "thermal_branch_enabled": False,
            "thermal_branch_correlated": False,
            "mixed_components_included": False,
            "thermal_branch_factorized_difference": 0.0,
            "thermal_branch_reference_implementation": False,
            "thermal_branch_implementation_kind": "disabled",
        }

    density_reference = thermal_branch_density_reference(matsubara_branch)
    if density_reference is None:
        density_reference = dynamics.equilibrium.generalized_density
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    zero_plus_error = float(np.max(np.abs(matsubara_branch.green[0] + (identity - density_reference))))
    beta_minus_error = float(np.max(np.abs(matsubara_branch.green[-1] + density_reference)))
    factorized_difference = (
        float(np.max(np.abs(matsubara_branch.green - factorized_branch.green)))
        if factorized_branch is not None
        else 0.0
    )
    density_shift = float(np.max(np.abs(density_reference - dynamics.equilibrium.generalized_density)))
    return {
        "thermal_branch_enabled": True,
        "thermal_branch_correlated": factorized_difference > 0.0,
        "mixed_components_included": False,
        "matsubara_beta": float(1.0 / config.initial_state.temperature),
        "matsubara_grid_shape": [
            int(matsubara_branch.green.shape[0]),
            int(matsubara_branch.green.shape[1]),
            int(matsubara_branch.green.shape[2]),
        ],
        "matsubara_zero_plus_error": zero_plus_error,
        "matsubara_beta_minus_error": beta_minus_error,
        "thermal_branch_converged": converged,
        "thermal_branch_iterations": iterations,
        "thermal_branch_residual_history": residual_history,
        "thermal_branch_memory_norm_history": memory_norm_history,
        "thermal_branch_history_integration_order_history": order_history,
        "thermal_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "thermal_branch_factorized_difference": factorized_difference,
        "thermal_branch_density_shift": density_shift,
        "thermal_branch_reference_implementation": False,
        "thermal_branch_implementation_kind": implementation_kind,
    }


def _mixed_branch_diagnostics(
    *,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
    factorized_branch: MixedBranchContainer | None,
    implementation_kind: str,
) -> dict[str, Any]:
    if matsubara_branch is None or mixed_branch is None:
        return {
            "mixed_components_included": False,
            "mixed_branch_factorized_difference": 0.0,
            "mixed_branch_reference_implementation": False,
            "mixed_branch_implementation_kind": "disabled",
        }

    right_initial_target = -1j * matsubara_branch.green
    left_initial_target = 1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1)
    right_factorized_difference = (
        float(np.max(np.abs(mixed_branch.right - factorized_branch.right)))
        if factorized_branch is not None
        else 0.0
    )
    left_factorized_difference = (
        float(np.max(np.abs(mixed_branch.left - factorized_branch.left)))
        if factorized_branch is not None
        else 0.0
    )
    return {
        "mixed_components_included": True,
        "mixed_component_names": ["mixed_right", "mixed_left"],
        "mixed_grid_shape": [
            int(mixed_branch.right.shape[0]),
            int(mixed_branch.right.shape[1]),
            int(mixed_branch.right.shape[2]),
            int(mixed_branch.right.shape[3]),
        ],
        "mixed_right_initial_error": float(np.max(np.abs(mixed_branch.right[0] - right_initial_target))),
        "mixed_left_initial_error": float(np.max(np.abs(mixed_branch.left[0] - left_initial_target))),
        "mixed_right_factorized_difference": right_factorized_difference,
        "mixed_left_factorized_difference": left_factorized_difference,
        "mixed_branch_factorized_difference": max(right_factorized_difference, left_factorized_difference),
        "mixed_branch_reference_implementation": False,
        "mixed_branch_implementation_kind": implementation_kind,
    }
