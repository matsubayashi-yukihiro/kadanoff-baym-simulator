from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.contour import (
    causal_history_rule,
    history_average_matrix,
    history_average_rank3,
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
from backend.app.solvers.nambu import ComplexMatrix, build_bdg_hamiltonian
from backend.app.solvers.numerics import linear_mix
from backend.app.solvers.tdhfb import HFBDynamicsResult


REFERENCE_IMPLEMENTATION_KIND = "gkba_local_nambu_reference"
FACTORIZED_IMPLEMENTATION_KIND = "factorized_hfb"


@dataclass(slots=True)
class SecondBornReferenceResult:
    generalized_densities: list[ComplexMatrix]
    green_functions: TwoTimeGreenFunctionContainer
    diagnostics: dict[str, Any]


def apply_reference_second_born_corrections(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None = None,
    mixed_branch: MixedBranchContainer | None = None,
) -> SecondBornReferenceResult:
    onsite_strength = abs(config.interaction.onsite_u)
    sample_count = len(dynamics.times)
    contour_density_reference = thermal_branch_density_reference(matsubara_branch)
    contour_mode = (
        "full_contour"
        if matsubara_branch is not None and mixed_branch is not None
        else ("thermal_only" if matsubara_branch is not None else "keldysh_only")
    )
    if sample_count <= 1 or onsite_strength <= 1e-12:
        hfb_green_functions = build_reference_green_functions(
            times=dynamics.times,
            generalized_densities=dynamics.generalized_densities,
            cumulative_propagators=dynamics.cumulative_propagators,
        )
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
        return SecondBornReferenceResult(
            generalized_densities=[density.copy() for density in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics=diagnostics,
        )

    corrected = [dynamics.generalized_densities[0].copy()]
    nambu_dimension = 2 * dynamics.lattice.site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
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
    thermal_branch_average = _matsubara_average_matrix(matsubara_branch)

    for time_index in range(1, sample_count):
        base_density = dynamics.generalized_densities[time_index]
        history_start = 0 if config.kbe.memory_window is None else max(0, time_index - config.kbe.memory_window)
        history_rule = causal_history_rule(dynamics.times, history_start=history_start, stop_index=time_index)
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        guess_density = base_density.copy()
        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        last_thermal_norm = 0.0
        last_mixed_norm = 0.0
        last_equation_residual = 0.0
        converged_step = False

        for iteration in range(1, config.kbe.max_fixed_point_iterations + 1):
            row_lesser, column_lesser, row_greater, column_greater = _build_gkba_row_data(
                time_index=time_index,
                guess_density=guess_density,
                corrected_densities=corrected,
                cumulative_propagators=dynamics.cumulative_propagators,
            )
            collision = np.zeros_like(guess_density)
            max_self_energy_norm = 0.0

            history_indices = np.arange(history_start, time_index, dtype=np.int64)
            for weight, history_index in zip(history_rule.past_weights, history_indices, strict=True):
                sigma_lesser = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=row_lesser[history_index],
                    second=column_greater[history_index],
                    third=row_lesser[history_index],
                    site_count=site_count,
                )
                sigma_greater = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=row_greater[history_index],
                    second=column_lesser[history_index],
                    third=row_greater[history_index],
                    site_count=site_count,
                )
                integrand = sigma_greater @ column_lesser[history_index] - sigma_lesser @ column_greater[history_index]
                collision += weight * integrand
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser))),
                    float(np.max(np.abs(sigma_greater))),
                )

            if history_rule.current_weight > 0.0:
                sigma_lesser_eq = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=row_lesser[time_index],
                    second=row_greater[time_index],
                    third=row_lesser[time_index],
                    site_count=site_count,
                )
                sigma_greater_eq = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=row_greater[time_index],
                    second=row_lesser[time_index],
                    third=row_greater[time_index],
                    site_count=site_count,
                )
                integrand_eq = sigma_greater_eq @ row_lesser[time_index] - sigma_lesser_eq @ row_greater[time_index]
                collision += history_rule.current_weight * integrand_eq
                max_self_energy_norm = max(
                    max_self_energy_norm,
                    float(np.max(np.abs(sigma_lesser_eq))),
                    float(np.max(np.abs(sigma_greater_eq))),
                )

            if thermal_branch_average is not None and contour_density_reference is not None:
                sigma_thermal = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=thermal_branch_average,
                    second=thermal_branch_average.conjugate().T,
                    third=thermal_branch_average,
                    site_count=site_count,
                )
                thermal_collision = _damping_collision(
                    _stabilized_kernel(sigma_thermal),
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
                mixed_density_reference = 0.5 * (
                    (-1j * mixed_right_average) + (1j * mixed_left_average)
                )
                mixed_density_reference = 0.5 * (
                    mixed_density_reference + mixed_density_reference.conjugate().T
                )
                sigma_mixed = _build_local_second_born_self_energy(
                    onsite_strength=onsite_strength,
                    first=-1j * mixed_right_average,
                    second=1j * mixed_left_average,
                    third=row_lesser[time_index],
                    site_count=site_count,
                )
                mixed_collision = _damping_collision(
                    _stabilized_kernel(sigma_mixed),
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
            last_equation_residual = float(np.max(np.abs((updated_density - base_density) / step_dt + collision + collision.conjugate().T)))
            guess_density = updated_density
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
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)
        thermal_memory_norm_history.append(last_thermal_norm)
        mixed_memory_norm_history.append(last_mixed_norm)
        history_order_history.append(history_rule.order)
        equation_residual_history.append(last_equation_residual)

    green_functions = build_reference_green_functions(
        times=dynamics.times,
        generalized_densities=corrected,
        cumulative_propagators=dynamics.cumulative_propagators,
    )
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
            "second_born_equation_residual_history": equation_residual_history,
            "max_second_born_memory_norm": float(max(memory_norm_history)) if memory_norm_history else 0.0,
            "max_second_born_collision_norm": float(max(collision_norm_history)) if collision_norm_history else 0.0,
            "max_second_born_thermal_memory_norm": (
                float(max(thermal_memory_norm_history)) if thermal_memory_norm_history else 0.0
            ),
            "max_second_born_mixed_memory_norm": (
                float(max(mixed_memory_norm_history)) if mixed_memory_norm_history else 0.0
            ),
            "second_born_history_integration_max_order": max(history_order_history) if history_order_history else 1,
            "max_second_born_equation_residual": (
                float(max(equation_residual_history)) if equation_residual_history else 0.0
            ),
            "second_born_contour_terms_included": contour_mode != "keldysh_only",
            "second_born_contour_mode": contour_mode,
            "second_born_solver_mode": "gkba_causal_marching",
            "second_born_explicit_self_energy": True,
            "second_born_reference_scope": (
                "equal_time_gkba_full_contour"
                if contour_mode == "full_contour"
                else ("equal_time_gkba_thermal" if contour_mode == "thermal_only" else "equal_time_gkba")
            ),
        }
    )
    return SecondBornReferenceResult(
        generalized_densities=corrected,
        green_functions=green_functions,
        diagnostics=diagnostics,
    )


def build_reference_green_functions(
    *,
    times: np.ndarray,
    generalized_densities: list[ComplexMatrix],
    cumulative_propagators: list[ComplexMatrix],
) -> TwoTimeGreenFunctionContainer:
    sample_count = len(times)
    nambu_dimension = generalized_densities[0].shape[0]
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    retarded = np.zeros((sample_count, sample_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    lesser = np.zeros_like(retarded)

    for row_index in range(sample_count):
        lesser[row_index, row_index] = 1j * generalized_densities[row_index]
        retarded[row_index, row_index] = -1j * identity
        for column_index in range(row_index):
            retarded[row_index, column_index] = (
                -1j * cumulative_propagators[row_index] @ cumulative_propagators[column_index].conjugate().T
            )
            lesser[row_index, column_index] = -retarded[row_index, column_index] @ generalized_densities[column_index]
            lesser[column_index, row_index] = -lesser[row_index, column_index].conjugate().T

    return TwoTimeGreenFunctionContainer(times=times, retarded=retarded, lesser=lesser)


def build_matsubara_branch_reference(
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
    if onsite_strength <= 1e-12:
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
                is_reference=False,
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

        for tau_index in range(1, len(factorized_branch.tau) - 1):
            history_rule = causal_history_rule(factorized_branch.tau, history_start=0, stop_index=tau_index)
            history_average = history_average_matrix(
                past_values=updated_green[:tau_index],
                past_weights=history_rule.past_weights,
                current_value=current_green[tau_index],
                current_weight=history_rule.current_weight,
            )
            branch_value = current_green[tau_index]
            sigma_tau = _build_local_second_born_self_energy(
                onsite_strength=onsite_strength,
                first=branch_value,
                second=history_average,
                third=branch_value,
                site_count=site_count,
            )
            kernel = _stabilized_kernel(sigma_tau)
            dtau = float(factorized_branch.tau[tau_index] - factorized_branch.tau[tau_index - 1])
            target = factorized_branch.green[tau_index] + dtau * _damping_collision(
                kernel,
                branch_value - history_average,
            )
            updated_green[tau_index] = linear_mix(branch_value, target, config.thermal_branch.mixing)
            max_residual = max(max_residual, float(np.max(np.abs(updated_green[tau_index] - branch_value))))
            max_memory_norm = max(
                max_memory_norm,
                float(np.max(np.abs(sigma_tau))) if sigma_tau.size else 0.0,
            )
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
            implementation_kind=REFERENCE_IMPLEMENTATION_KIND,
            is_reference=True,
        ),
    )


def build_mixed_branch_reference(
    *,
    config: SimulationConfig,
    matsubara_branch: MatsubaraBranchContainer | None,
    dynamics: HFBDynamicsResult,
    reference_densities: list[ComplexMatrix],
    factorized_branch: MixedBranchContainer | None = None,
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
    if onsite_strength <= 1e-12:
        return MixedBranchBuildResult(
            branch=factorized_branch,
            factorized_branch=factorized_branch,
            diagnostics=_mixed_branch_diagnostics(
                matsubara_branch=matsubara_branch,
                mixed_branch=factorized_branch,
                factorized_branch=factorized_branch,
                implementation_kind=FACTORIZED_IMPLEMENTATION_KIND,
                is_reference=False,
                converged=True,
                iterations=1,
                residual_history=[0.0],
                memory_norm_history=[0.0],
                order_history=[1],
            ),
        )

    right = factorized_branch.right.copy()
    left = factorized_branch.left.copy()
    site_count = dynamics.lattice.site_count
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
            sigma_mixed = _build_local_second_born_self_energy(
                onsite_strength=onsite_strength,
                first=mixed_average,
                second=reference_densities[time_index],
                third=mixed_average,
                site_count=site_count,
            )
            kernel = _stabilized_kernel(sigma_mixed)
            step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
            target_right = factorized_branch.right[time_index] + step_dt * _damping_collision(
                kernel,
                right_guess - right_reference,
            )
            target_left = factorized_branch.left[time_index] + step_dt * _damping_collision(
                kernel,
                left_guess - left_reference,
            )
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

    branch = MixedBranchContainer(
        times=dynamics.times,
        tau=matsubara_branch.tau,
        right=right,
        left=left,
    )
    return MixedBranchBuildResult(
        branch=branch,
        factorized_branch=factorized_branch,
        diagnostics=_mixed_branch_diagnostics(
            matsubara_branch=matsubara_branch,
            mixed_branch=branch,
            factorized_branch=factorized_branch,
            implementation_kind=REFERENCE_IMPLEMENTATION_KIND,
            is_reference=True,
            converged=converged,
            iterations=iterations,
            residual_history=residual_history,
            memory_norm_history=memory_norm_history,
            order_history=order_history,
        ),
    )


def build_factorized_mixed_branch(
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> MixedBranchContainer | None:
    return build_shared_factorized_mixed_branch(dynamics, matsubara_branch)


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


def _build_gkba_row_data(
    *,
    time_index: int,
    guess_density: ComplexMatrix,
    corrected_densities: list[ComplexMatrix],
    cumulative_propagators: list[ComplexMatrix],
) -> tuple[
    list[ComplexMatrix],
    list[ComplexMatrix],
    list[ComplexMatrix],
    list[ComplexMatrix],
]:
    nambu_dimension = guess_density.shape[0]
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    row_lesser = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    column_lesser = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    row_greater = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    column_greater = [np.zeros((nambu_dimension, nambu_dimension), dtype=np.complex128) for _ in range(time_index + 1)]
    row_lesser[time_index] = 1j * guess_density
    row_greater[time_index] = 1j * (guess_density - identity)

    for history_index in range(time_index):
        row_retarded = (
            -1j * cumulative_propagators[time_index] @ cumulative_propagators[history_index].conjugate().T
        )
        row_lesser[history_index] = -row_retarded @ corrected_densities[history_index]
        column_lesser[history_index] = -row_lesser[history_index].conjugate().T
        row_greater[history_index] = row_lesser[history_index] - 1j * row_retarded
        column_greater[history_index] = column_lesser[history_index] + 1j * row_retarded.conjugate().T

    column_lesser[time_index] = row_lesser[time_index]
    column_greater[time_index] = row_greater[time_index]
    return row_lesser, column_lesser, row_greater, column_greater


def _build_local_second_born_self_energy(
    *,
    onsite_strength: float,
    first: ComplexMatrix,
    second: ComplexMatrix,
    third: ComplexMatrix,
    site_count: int,
) -> ComplexMatrix:
    sigma = np.zeros_like(first)
    if site_count == 0:
        return sigma

    coupling = onsite_strength**2
    first_local = _extract_local_nambu_blocks(first, site_count)
    second_local = _extract_local_nambu_blocks(second, site_count)
    third_local = _extract_local_nambu_blocks(third, site_count)
    local_sigma = coupling * (first_local @ second_local @ third_local)
    particle_indices = np.arange(site_count, dtype=np.int64)
    hole_indices = particle_indices + site_count
    sigma[particle_indices, particle_indices] = local_sigma[:, 0, 0]
    sigma[particle_indices, hole_indices] = local_sigma[:, 0, 1]
    sigma[hole_indices, particle_indices] = local_sigma[:, 1, 0]
    sigma[hole_indices, hole_indices] = local_sigma[:, 1, 1]
    return sigma


def _extract_local_nambu_blocks(
    values: ComplexMatrix,
    site_count: int,
) -> np.ndarray:
    blocks = np.empty((site_count, 2, 2), dtype=np.complex128)
    particle_slice = values[:site_count, :site_count]
    pairing_slice = values[:site_count, site_count:]
    anomalous_slice = values[site_count:, :site_count]
    hole_slice = values[site_count:, site_count:]
    blocks[:, 0, 0] = np.diagonal(particle_slice)
    blocks[:, 0, 1] = np.diagonal(pairing_slice)
    blocks[:, 1, 0] = np.diagonal(anomalous_slice)
    blocks[:, 1, 1] = np.diagonal(hole_slice)
    return blocks


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
        "second_born_reference_implementation": True,
        "second_born_implementation_kind": REFERENCE_IMPLEMENTATION_KIND,
    }


def _matsubara_diagnostics(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer,
    factorized_branch: MatsubaraBranchContainer,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
    implementation_kind: str,
    is_reference: bool,
) -> dict[str, Any]:
    density_reference = -matsubara_branch.green[-1]
    density_reference = 0.5 * (density_reference + density_reference.conjugate().T)
    identity = np.eye(density_reference.shape[0], dtype=np.complex128)
    return {
        "thermal_branch_enabled": True,
        "thermal_branch_correlated": float(np.max(np.abs(matsubara_branch.green - factorized_branch.green))) > 0.0,
        "mixed_components_included": False,
        "matsubara_beta": float(1.0 / config.initial_state.temperature),
        "matsubara_grid_shape": [
            int(matsubara_branch.green.shape[0]),
            int(matsubara_branch.green.shape[1]),
            int(matsubara_branch.green.shape[2]),
        ],
        "matsubara_zero_plus_error": float(np.max(np.abs(matsubara_branch.green[0] + (identity - density_reference)))),
        "matsubara_beta_minus_error": float(np.max(np.abs(matsubara_branch.green[-1] + density_reference))),
        "thermal_branch_converged": converged,
        "thermal_branch_iterations": iterations,
        "thermal_branch_residual_history": residual_history,
        "thermal_branch_memory_norm_history": memory_norm_history,
        "thermal_branch_history_integration_order_history": order_history,
        "thermal_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "thermal_branch_factorized_difference": float(np.max(np.abs(matsubara_branch.green - factorized_branch.green))),
        "thermal_branch_density_shift": float(
            np.max(np.abs(density_reference - dynamics.equilibrium.generalized_density))
        ),
        "thermal_branch_reference_implementation": is_reference,
        "thermal_branch_implementation_kind": implementation_kind,
    }


def _mixed_branch_diagnostics(
    *,
    matsubara_branch: MatsubaraBranchContainer,
    mixed_branch: MixedBranchContainer,
    factorized_branch: MixedBranchContainer,
    implementation_kind: str,
    is_reference: bool,
    converged: bool,
    iterations: int,
    residual_history: list[float],
    memory_norm_history: list[float],
    order_history: list[int],
) -> dict[str, Any]:
    right_initial_target = -1j * matsubara_branch.green
    left_initial_target = 1j * matsubara_branch.green[::-1].conjugate().transpose(0, 2, 1)
    right_factorized_difference = float(np.max(np.abs(mixed_branch.right - factorized_branch.right)))
    left_factorized_difference = float(np.max(np.abs(mixed_branch.left - factorized_branch.left)))
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
        "mixed_branch_converged": converged,
        "mixed_branch_iterations": iterations,
        "mixed_branch_residual_history": residual_history,
        "mixed_branch_memory_norm_history": memory_norm_history,
        "mixed_branch_history_integration_order_history": order_history,
        "mixed_branch_history_integration_max_order": max(order_history) if order_history else 1,
        "max_mixed_branch_memory_norm": float(max(memory_norm_history)) if memory_norm_history else 0.0,
        "mixed_branch_reference_implementation": is_reference,
        "mixed_branch_implementation_kind": implementation_kind,
    }


def _matsubara_average_matrix(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    return tau_average_matrix(matsubara_branch.tau, matsubara_branch.green)


def thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    density = -matsubara_branch.green[-1]
    return 0.5 * (density + density.conjugate().T)


def _stabilized_kernel(self_energy: ComplexMatrix) -> ComplexMatrix:
    return 0.5 * (self_energy + self_energy.conjugate().T)


def _damping_collision(
    kernel: ComplexMatrix,
    values: np.ndarray,
) -> np.ndarray:
    if values.ndim == 2:
        return -0.5 * (kernel @ values + values @ kernel)
    if values.ndim == 3:
        return -0.5 * (
            np.einsum("ab,kbc->kac", kernel, values)
            + np.einsum("kab,bc->kac", values, kernel)
        )
    raise ValueError(f"unsupported value rank for collision kernel: {values.ndim}")
