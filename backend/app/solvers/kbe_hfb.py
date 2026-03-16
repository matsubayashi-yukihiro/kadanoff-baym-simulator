from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.base import (
    MixedGreenFunctionData,
    ObservableData,
    SeriesData,
    SimulationArtifacts,
    ThermalBranchGreenFunctionData,
    TwoTimeGreenFunctionData,
)
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian_derivative, vector_potential
from backend.app.solvers.lattice import SquareLattice
from backend.app.solvers.nambu import (
    ComplexMatrix,
    build_bdg_hamiltonian,
    effective_energy,
    extract_density_blocks,
    pairing_channel,
    pairing_projections,
)
from backend.app.solvers.observables import average_current, particle_density_statistics
from backend.app.solvers.tdhfb import HFBDynamicsResult, simulate_hfb_dynamics


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


@dataclass(slots=True)
class SecondBornCorrectionResult:
    generalized_densities: list[ComplexMatrix]
    green_functions: TwoTimeGreenFunctionContainer
    diagnostics: dict[str, Any]


@dataclass(slots=True)
class CausalHistoryIntegrationRule:
    past_weights: NDArray[np.float64]
    current_weight: float
    order: int


def solve(config: SimulationConfig) -> SimulationArtifacts:
    dynamics = simulate_hfb_dynamics(config)
    diagnostics = dict(dynamics.diagnostics)
    summary_excerpt = dict(dynamics.summary_excerpt)
    observables = dynamics.observables
    reference_densities = dynamics.generalized_densities

    diagnostics["kbe_self_energy_mode"] = config.kbe.self_energy.value
    diagnostics["kbe_fixed_point_tolerance"] = float(config.kbe.tolerance)
    diagnostics["kbe_fixed_point_mixing"] = float(config.kbe.mixing)
    diagnostics["kbe_fixed_point_max_iterations"] = int(config.kbe.max_fixed_point_iterations)

    hfb_green_functions = build_two_time_green_functions(dynamics)
    green_function_reference = hfb_green_functions
    matsubara_result = _build_matsubara_branch(config, dynamics)
    contour_seed_mixed = _build_factorized_mixed_branch(dynamics, matsubara_result.branch)

    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN:
        second_born_result = _apply_second_born_corrections(
            config=config,
            dynamics=dynamics,
            hfb_green_functions=hfb_green_functions,
            matsubara_branch=matsubara_result.branch,
            mixed_branch=contour_seed_mixed,
        )
        reference_densities = second_born_result.generalized_densities
        observables, trajectory_diagnostics, summary_excerpt = _analyze_trajectory(
            config=config,
            dynamics=dynamics,
            generalized_densities=reference_densities,
        )
        diagnostics.update(trajectory_diagnostics)
        diagnostics.update(second_born_result.diagnostics)
        green_function_reference = second_born_result.green_functions
    else:
        diagnostics.update(
            {
                "second_born_enabled": False,
                "second_born_converged": True,
                "second_born_iteration_history": [],
                "second_born_residual_history": [],
                "second_born_memory_norm_history": [],
                "second_born_collision_norm_history": [],
                "max_second_born_memory_norm": 0.0,
                "max_second_born_collision_norm": 0.0,
                "second_born_solver_mode": "disabled",
            }
        )

    diagnostics.update(
        _green_function_diagnostics(
            dynamics=dynamics,
            green_functions=green_function_reference,
            reference_densities=reference_densities,
            tdhfb_reference_densities=dynamics.generalized_densities,
            reconstruction_mode=(
                "causal_marching"
                if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN
                and diagnostics.get("second_born_solver_mode") == "two_time_causal_marching"
                else None
            ),
        )
    )

    mixed_result = _build_mixed_branch(
        config=config,
        dynamics=dynamics,
        matsubara_branch=matsubara_result.branch,
        reference_densities=reference_densities,
        factorized_branch=contour_seed_mixed,
    )
    diagnostics.update(matsubara_result.diagnostics)
    diagnostics.update(mixed_result.diagnostics)
    summary_excerpt["max_equal_time_tdhfb_mismatch"] = diagnostics["max_equal_time_tdhfb_mismatch"]
    if matsubara_result.branch is not None:
        summary_excerpt["matsubara_beta"] = diagnostics["matsubara_beta"]
        summary_excerpt["thermal_branch_factorized_difference"] = diagnostics["thermal_branch_factorized_difference"]
    if mixed_result.branch is not None:
        summary_excerpt["mixed_branch_factorized_difference"] = diagnostics["mixed_branch_factorized_difference"]
    return SimulationArtifacts(
        observables=observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
        two_time_green_functions=TwoTimeGreenFunctionData(
            times=green_function_reference.times,
            components={
                "retarded": green_function_reference.retarded,
                "lesser": green_function_reference.lesser,
            },
        ),
        thermal_branch_green_functions=(
            ThermalBranchGreenFunctionData(
                tau=matsubara_result.branch.tau,
                components={"matsubara": matsubara_result.branch.green},
            )
            if matsubara_result.branch is not None
            else None
        ),
        mixed_green_functions=(
            MixedGreenFunctionData(
                times=mixed_result.branch.times,
                tau=mixed_result.branch.tau,
                components={
                    "mixed_right": mixed_result.branch.right,
                    "mixed_left": mixed_result.branch.left,
                },
            )
            if mixed_result.branch is not None
            else None
        ),
    )


def build_two_time_green_functions(
    dynamics: HFBDynamicsResult,
    generalized_densities: list[ComplexMatrix] | None = None,
) -> TwoTimeGreenFunctionContainer:
    sample_count = len(dynamics.times)
    nambu_dimension = 2 * dynamics.lattice.site_count
    retarded = np.zeros((sample_count, sample_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    lesser = np.zeros_like(retarded)
    if generalized_densities is None:
        initial_density = dynamics.generalized_densities[0]

    for row_index, left_propagator in enumerate(dynamics.cumulative_propagators):
        for column_index, right_propagator in enumerate(dynamics.cumulative_propagators):
            if generalized_densities is None:
                lesser[row_index, column_index] = 1j * left_propagator @ initial_density @ right_propagator.conjugate().T
            else:
                lesser[row_index, column_index] = 0.5j * (
                    generalized_densities[row_index] + generalized_densities[column_index]
                )
            if row_index >= column_index:
                retarded[row_index, column_index] = -1j * left_propagator @ right_propagator.conjugate().T

    return TwoTimeGreenFunctionContainer(times=dynamics.times, retarded=retarded, lesser=lesser)


def _green_function_diagnostics(
    dynamics: HFBDynamicsResult,
    green_functions: TwoTimeGreenFunctionContainer,
    reference_densities: list[ComplexMatrix],
    tdhfb_reference_densities: list[ComplexMatrix],
    reconstruction_mode: str | None = None,
) -> dict[str, float | list[int]]:
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


def _apply_second_born_corrections(
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
        return SecondBornCorrectionResult(
            generalized_densities=[density.copy() for density in dynamics.generalized_densities],
            green_functions=hfb_green_functions,
            diagnostics={
                "second_born_enabled": True,
                "second_born_converged": True,
                "second_born_iteration_history": [1] * max(sample_count - 1, 0),
                "second_born_residual_history": [0.0] * max(sample_count - 1, 0),
                "second_born_memory_norm_history": [0.0] * max(sample_count - 1, 0),
                "second_born_collision_norm_history": [0.0] * max(sample_count - 1, 0),
                "second_born_thermal_memory_norm_history": [0.0] * max(sample_count - 1, 0),
                "second_born_mixed_memory_norm_history": [0.0] * max(sample_count - 1, 0),
                "second_born_history_integration_order_history": [1] * max(sample_count - 1, 0),
                "max_second_born_memory_norm": 0.0,
                "max_second_born_collision_norm": 0.0,
                "max_second_born_thermal_memory_norm": 0.0,
                "max_second_born_mixed_memory_norm": 0.0,
                "second_born_memory_window": int(config.kbe.memory_window or max(sample_count - 1, 0)),
                "second_born_history_integration_max_order": 1,
                "second_born_contour_terms_included": False,
                "second_born_contour_mode": "hfb_limit",
                "second_born_solver_mode": "hfb_limit",
            },
        )

    return _apply_second_born_two_time_corrections(
        config=config,
        dynamics=dynamics,
        hfb_green_functions=hfb_green_functions,
        matsubara_branch=matsubara_branch,
        mixed_branch=mixed_branch,
    )


def _apply_second_born_two_time_corrections(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
) -> SecondBornCorrectionResult:
    corrected = [density.copy() for density in dynamics.generalized_densities[:1]]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    nambu_dimension = 2 * site_count
    identity = np.eye(nambu_dimension, dtype=np.complex128)
    retarded = hfb_green_functions.retarded.copy()
    lesser = hfb_green_functions.lesser.copy()
    contour_density_reference = _thermal_branch_density_reference(matsubara_branch)
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
        history_rule = _causal_history_rule(dynamics.times, history_start=history_start, stop_index=time_index)
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
            density_history_average = _history_average_matrix(
                past_values=np.asarray([corrected[index] for index in window_indices], dtype=np.complex128),
                past_weights=history_rule.past_weights,
                current_value=guess_density,
                current_weight=history_rule.current_weight,
            )
            row_lesser_history_average = _history_average_rank3(
                past_values=lesser[window_indices, :time_index],
                past_weights=history_rule.past_weights,
                current_value=guess_row_lesser,
                current_weight=history_rule.current_weight,
            )
            row_retarded_history_average = _history_average_rank3(
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

            normalized_past_weights = _normalized_weights(history_rule.past_weights)
            for normalized_weight, weight, history_index in zip(
                normalized_past_weights,
                history_rule.past_weights,
                window_indices,
                strict=True,
            ):
                history_normal, history_pairing = extract_density_blocks(corrected[history_index], site_count)
                history_occupancy = np.clip(np.real(np.diag(history_normal)), 0.0, 1.0)
                history_pairing_strength = np.abs(np.diag(history_pairing))
                envelope = np.abs(
                    np.diagonal(
                        guess_row_lesser[history_index, :site_count, :site_count],
                    )
                )
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
                mixed_right_average = _tau_average_matrix(mixed_branch.tau, mixed_branch.right[time_index])
                mixed_left_average = _tau_average_matrix(mixed_branch.tau, mixed_branch.left[time_index])
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

            density_collision = _dissipative_collision(gamma_matrix, density_memory_drive)
            row_lesser_collision = _dissipative_collision(gamma_matrix, row_lesser_memory_drive)
            row_retarded_collision = _dissipative_collision(gamma_matrix, row_retarded_memory_drive)

            target_density = base_density + step_dt * density_collision
            target_row_lesser = base_row_lesser + step_dt * row_lesser_collision
            target_row_retarded = base_row_retarded + step_dt * row_retarded_collision

            updated_density = config.kbe.mixing * target_density + (1.0 - config.kbe.mixing) * guess_density
            updated_density = 0.5 * (updated_density + updated_density.conjugate().T)
            updated_row_lesser = (
                config.kbe.mixing * target_row_lesser + (1.0 - config.kbe.mixing) * guess_row_lesser
            )
            updated_row_retarded = (
                config.kbe.mixing * target_row_retarded + (1.0 - config.kbe.mixing) * guess_row_retarded
            )

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
        if time_index > 0:
            lesser[time_index, :time_index] = guess_row_lesser
            lesser[:time_index, time_index] = -guess_row_lesser.conjugate().transpose(0, 2, 1)
            retarded[time_index, :time_index] = guess_row_retarded
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)
        thermal_memory_norm_history.append(last_thermal_norm)
        mixed_memory_norm_history.append(last_mixed_norm)
        history_order_history.append(history_rule.order)

    return SecondBornCorrectionResult(
        generalized_densities=corrected,
        green_functions=TwoTimeGreenFunctionContainer(
            times=dynamics.times,
            retarded=retarded,
            lesser=lesser,
        ),
        diagnostics={
            "second_born_enabled": True,
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
            "max_second_born_mixed_memory_norm": (
                float(max(mixed_memory_norm_history)) if mixed_memory_norm_history else 0.0
            ),
            "second_born_memory_window": int(config.kbe.memory_window or max(sample_count - 1, 0)),
            "second_born_history_integration_max_order": max(history_order_history) if history_order_history else 1,
            "second_born_contour_terms_included": contour_mode != "keldysh_only",
            "second_born_contour_mode": contour_mode,
            "second_born_solver_mode": "two_time_causal_marching",
        },
    )


def _apply_second_born_density_prototype(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    hfb_green_functions: TwoTimeGreenFunctionContainer,
) -> tuple[list[ComplexMatrix], dict[str, Any]]:
    corrected = [density.copy() for density in dynamics.generalized_densities[:1]]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    onsite_strength = abs(config.interaction.onsite_u)

    history_weights = _quadrature_weights(dynamics.times)
    particle_lesser = hfb_green_functions.lesser[:, :, :site_count, :site_count]
    local_memory_envelope = np.abs(np.diagonal(particle_lesser, axis1=2, axis2=3))

    residual_history: list[float] = []
    iteration_history: list[int] = []
    memory_norm_history: list[float] = []
    collision_norm_history: list[float] = []
    converged = True

    for time_index in range(1, sample_count):
        base_density = dynamics.generalized_densities[time_index]
        guess = base_density.copy()
        step_dt = float(dynamics.times[time_index] - dynamics.times[time_index - 1])
        history_start = 0 if config.kbe.memory_window is None else max(0, time_index - config.kbe.memory_window)
        window_indices = list(range(history_start, time_index))
        window_weights = history_weights[history_start:time_index]
        if len(window_indices) == 0 or float(np.sum(window_weights)) <= 1e-15:
            corrected.append(base_density.copy())
            residual_history.append(0.0)
            iteration_history.append(1)
            memory_norm_history.append(0.0)
            collision_norm_history.append(0.0)
            continue

        last_residual = 0.0
        last_memory_norm = 0.0
        last_collision_norm = 0.0
        converged_step = False

        for iteration in range(1, config.kbe.max_fixed_point_iterations + 1):
            normal_guess, pairing_guess = extract_density_blocks(guess, site_count)
            guess_occupancy = np.clip(np.real(np.diag(normal_guess)), 0.0, 1.0)
            guess_pairing = np.abs(np.diag(pairing_guess))
            gamma_site = np.zeros(site_count, dtype=np.float64)
            memory_drive = np.zeros_like(guess)

            for weight, history_index in zip(window_weights, window_indices, strict=True):
                history_normal, history_pairing = extract_density_blocks(corrected[history_index], site_count)
                history_occupancy = np.clip(np.real(np.diag(history_normal)), 0.0, 1.0)
                history_pairing_strength = np.abs(np.diag(history_pairing))
                envelope = local_memory_envelope[time_index, history_index]
                gamma_site += (
                    weight
                    * onsite_strength**2
                    * envelope
                    * (guess_occupancy * (1.0 - guess_occupancy) + guess_pairing**2)
                    * (history_occupancy * (1.0 - history_occupancy) + history_pairing_strength**2 + 1e-12)
                )
                memory_drive += weight * float(np.mean(envelope)) * (guess - corrected[history_index])

            gamma_matrix = np.diag(np.concatenate([gamma_site, gamma_site]).astype(np.complex128))
            collision = -0.5 * (gamma_matrix @ memory_drive + memory_drive @ gamma_matrix)
            target = base_density + step_dt * collision
            updated = config.kbe.mixing * target + (1.0 - config.kbe.mixing) * guess
            updated = 0.5 * (updated + updated.conjugate().T)

            last_residual = float(np.max(np.abs(updated - guess)))
            last_memory_norm = float(np.max(gamma_site)) if len(gamma_site) else 0.0
            last_collision_norm = float(np.max(np.abs(collision))) if collision.size else 0.0
            guess = updated
            if last_residual <= config.kbe.tolerance:
                converged_step = True
                iteration_history.append(iteration)
                break
        else:
            iteration_history.append(config.kbe.max_fixed_point_iterations)

        converged = converged and converged_step
        corrected.append(guess)
        residual_history.append(last_residual)
        memory_norm_history.append(last_memory_norm)
        collision_norm_history.append(last_collision_norm)

    return corrected, {
        "second_born_enabled": True,
        "second_born_converged": converged,
        "second_born_iteration_history": iteration_history,
        "second_born_residual_history": residual_history,
        "second_born_memory_norm_history": memory_norm_history,
        "second_born_collision_norm_history": collision_norm_history,
        "max_second_born_memory_norm": float(max(memory_norm_history)) if memory_norm_history else 0.0,
        "max_second_born_collision_norm": float(max(collision_norm_history)) if collision_norm_history else 0.0,
        "second_born_memory_window": int(config.kbe.memory_window or max(sample_count - 1, 0)),
    }


def _analyze_trajectory(
    *,
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    generalized_densities: list[ComplexMatrix],
) -> tuple[dict[str, ObservableData], dict[str, Any], dict[str, float | str]]:
    density_mean: list[float] = []
    density_min: list[float] = []
    density_max: list[float] = []
    current_x: list[float] = []
    current_y: list[float] = []
    energy: list[float] = []
    vector_ax: list[float] = []
    vector_ay: list[float] = []
    particle_trace: list[float] = []
    external_power: list[float] = []
    hermiticity_error: list[float] = []
    density_bound_violation: list[float] = []
    pairing_primary: list[complex] = []
    pairing_s: list[complex] = []
    pairing_d: list[complex] = []

    for time, generalized_density in zip(dynamics.times, generalized_densities, strict=True):
        normal_hamiltonian, pairing_field, _, bdg_hamiltonian = build_bdg_hamiltonian(
            config,
            dynamics.lattice,
            float(time),
            generalized_density,
            dynamics.equilibrium.effective_chemical_potential,
        )
        normal_density, _ = extract_density_blocks(generalized_density, dynamics.lattice.site_count)
        density_stats = particle_density_statistics(normal_density)
        density_mean.append(density_stats[0])
        density_min.append(density_stats[1])
        density_max.append(density_stats[2])
        current_x.append(average_current(dynamics.lattice.bonds_x, normal_hamiltonian, normal_density))
        current_y.append(average_current(dynamics.lattice.bonds_y, normal_hamiltonian, normal_density))
        energy.append(effective_energy(generalized_density, bdg_hamiltonian))
        ax, ay = vector_potential(config.drive, float(time))
        vector_ax.append(ax)
        vector_ay.append(ay)
        particle_trace.append(float(np.real(np.trace(normal_density))))
        external_power.append(
            _nambu_expectation_value(
                _explicit_bdg_hamiltonian_derivative(config, dynamics.lattice, float(time)),
                generalized_density,
            )
        )
        hermiticity_error.append(float(np.max(np.abs(generalized_density - generalized_density.conjugate().T))))
        site_density = np.real(np.diag(normal_density))
        density_bound_violation.append(float(np.max(np.maximum(site_density - 1.0, 0.0) + np.maximum(-site_density, 0.0))))
        pairing_value = pairing_projections(config, dynamics.lattice, pairing_field)
        pairing_primary.append(pairing_value.primary)
        pairing_s.append(pairing_value.s_wave)
        pairing_d.append(pairing_value.d_wave)

    density_mean_array = np.asarray(density_mean, dtype=np.float64)
    density_min_array = np.asarray(density_min, dtype=np.float64)
    density_max_array = np.asarray(density_max, dtype=np.float64)
    current_x_array = np.asarray(current_x, dtype=np.float64)
    current_y_array = np.asarray(current_y, dtype=np.float64)
    energy_array = np.asarray(energy, dtype=np.float64)
    vector_ax_array = np.asarray(vector_ax, dtype=np.float64)
    vector_ay_array = np.asarray(vector_ay, dtype=np.float64)
    particle_trace_array = np.asarray(particle_trace, dtype=np.float64)
    external_power_array = np.asarray(external_power, dtype=np.float64)
    hermiticity_error_array = np.asarray(hermiticity_error, dtype=np.float64)
    density_bound_violation_array = np.asarray(density_bound_violation, dtype=np.float64)
    pairing_primary_array = np.asarray(pairing_primary, dtype=np.complex128)
    pairing_s_array = np.asarray(pairing_s, dtype=np.complex128)
    pairing_d_array = np.asarray(pairing_d, dtype=np.complex128)
    conservation_diagnostics = _conservation_diagnostics(
        times=dynamics.times,
        energy=energy_array,
        particle_trace=particle_trace_array,
        external_power=external_power_array,
    )

    metadata = {
        "solver": config.solver.value if hasattr(config.solver, "value") else str(config.solver),
        "pairing_channel": pairing_channel(config).value,
        "kbe_self_energy": config.kbe.self_energy.value,
    }
    saved_indices = dynamics.saved_indices
    saved_times = dynamics.times[saved_indices]
    observables = {
        "density": ObservableData(
            name="density",
            time=saved_times,
            series=[
                SeriesData(label="mean", values=density_mean_array[saved_indices]),
                SeriesData(label="min", values=density_min_array[saved_indices]),
                SeriesData(label="max", values=density_max_array[saved_indices]),
            ],
            metadata=metadata,
        ),
        "current_x": ObservableData(
            name="current_x",
            time=saved_times,
            series=[SeriesData(label="total", values=current_x_array[saved_indices])],
            metadata=metadata,
        ),
        "current_y": ObservableData(
            name="current_y",
            time=saved_times,
            series=[SeriesData(label="total", values=current_y_array[saved_indices])],
            metadata=metadata,
        ),
        "energy": ObservableData(
            name="energy",
            time=saved_times,
            series=[SeriesData(label="total", values=energy_array[saved_indices])],
            metadata=metadata,
        ),
        "vector_potential": ObservableData(
            name="vector_potential",
            time=saved_times,
            series=[
                SeriesData(label="ax", values=vector_ax_array[saved_indices]),
                SeriesData(label="ay", values=vector_ay_array[saved_indices]),
            ],
            metadata=metadata,
        ),
        "pairing": _complex_observable("pairing", saved_times, pairing_primary_array[saved_indices], metadata),
        "pairing_s": _complex_observable("pairing_s", saved_times, pairing_s_array[saved_indices], metadata),
        "pairing_d": _complex_observable("pairing_d", saved_times, pairing_d_array[saved_indices], metadata),
    }
    diagnostics = {
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_trace_array[0]))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_generalized_hermiticity_error": float(np.max(hermiticity_error_array)),
        "max_density_bound_violation": float(np.max(density_bound_violation_array)),
        "max_pairing_magnitude": float(np.max(np.abs(pairing_primary_array))),
        "max_pairing_s_magnitude": float(np.max(np.abs(pairing_s_array))),
        "max_pairing_d_magnitude": float(np.max(np.abs(pairing_d_array))),
        "final_pairing_magnitude": float(np.abs(pairing_primary_array[-1])),
    }
    diagnostics.update(conservation_diagnostics)
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean_array[-1]),
        "final_pairing_magnitude": diagnostics["final_pairing_magnitude"],
        "pairing_s_final": float(np.abs(pairing_s_array[-1])),
        "pairing_d_final": float(np.abs(pairing_d_array[-1])),
        "particle_number_drift": diagnostics["particle_number_drift"],
        "max_particle_conservation_residual": diagnostics["max_particle_conservation_residual"],
        "max_energy_work_mismatch": diagnostics["max_energy_work_mismatch"],
        "time_grid_mode": dynamics.diagnostics["time_grid_mode"],
    }
    return {name: observables[name] for name in config.observables}, diagnostics, summary_excerpt


def _complex_observable(
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


def _quadrature_weights(times: NDArray[np.float64]) -> NDArray[np.float64]:
    if len(times) <= 1:
        return np.zeros(len(times), dtype=np.float64)
    if len(times) == 2:
        dt = float(times[1] - times[0])
        return np.asarray([dt, dt], dtype=np.float64)
    weights = np.zeros(len(times), dtype=np.float64)
    weights[0] = 0.5 * float(times[1] - times[0])
    weights[-1] = 0.5 * float(times[-1] - times[-2])
    for index in range(1, len(times) - 1):
        weights[index] = 0.5 * float(times[index + 1] - times[index - 1])
    return weights


def _causal_history_rule(
    times: NDArray[np.float64],
    *,
    history_start: int,
    stop_index: int,
) -> CausalHistoryIntegrationRule:
    sub_times = times[history_start : stop_index + 1]
    if len(sub_times) <= 1:
        return CausalHistoryIntegrationRule(
            past_weights=np.zeros(0, dtype=np.float64),
            current_weight=0.0,
            order=1,
        )

    if len(sub_times) >= 3 and _is_quasi_uniform(sub_times):
        node_weights = _composite_simpson_weights(sub_times)
        return CausalHistoryIntegrationRule(
            past_weights=node_weights[:-1],
            current_weight=float(node_weights[-1]),
            order=2,
        )

    node_weights = _quadrature_weights(sub_times)
    return CausalHistoryIntegrationRule(
        past_weights=node_weights[:-1],
        current_weight=float(node_weights[-1]),
        order=1,
    )


def _is_quasi_uniform(times: NDArray[np.float64]) -> bool:
    if len(times) <= 2:
        return True
    deltas = np.diff(times)
    reference = float(np.mean(deltas))
    tolerance = max(1e-12, 0.05 * abs(reference))
    return bool(np.max(np.abs(deltas - reference)) <= tolerance)


def _composite_simpson_weights(times: NDArray[np.float64]) -> NDArray[np.float64]:
    point_count = len(times)
    if point_count <= 2:
        return _quadrature_weights(times)

    h = float((times[-1] - times[0]) / max(point_count - 1, 1))
    interval_count = point_count - 1
    weights = np.zeros(point_count, dtype=np.float64)
    if interval_count % 2 == 0:
        weights[0] = 1.0
        weights[-1] = 1.0
        for index in range(1, point_count - 1):
            weights[index] = 4.0 if index % 2 == 1 else 2.0
        return (h / 3.0) * weights

    simpson_weights = _composite_simpson_weights(times[:-1])
    weights[:-1] += simpson_weights
    tail_dt = float(times[-1] - times[-2])
    weights[-2] += 0.5 * tail_dt
    weights[-1] += 0.5 * tail_dt
    return weights


def _normalized_weights(weights: NDArray[np.float64]) -> NDArray[np.float64]:
    if len(weights) == 0:
        return weights
    total_weight = float(np.sum(weights))
    if total_weight <= 1e-15:
        return np.zeros_like(weights)
    return weights / total_weight


def _history_average_matrix(
    *,
    past_values: NDArray[np.complex128],
    past_weights: NDArray[np.float64],
    current_value: NDArray[np.complex128],
    current_weight: float,
) -> NDArray[np.complex128]:
    total_weight = float(np.sum(past_weights)) + current_weight
    if total_weight <= 1e-15:
        return current_value.copy()
    averaged = np.zeros_like(current_value)
    if len(past_weights) > 0:
        averaged += np.einsum("w,wab->ab", past_weights, past_values)
    averaged += current_weight * current_value
    return averaged / total_weight


def _history_average_rank3(
    *,
    past_values: NDArray[np.complex128],
    past_weights: NDArray[np.float64],
    current_value: NDArray[np.complex128],
    current_weight: float,
) -> NDArray[np.complex128]:
    total_weight = float(np.sum(past_weights)) + current_weight
    if total_weight <= 1e-15:
        return current_value.copy()
    averaged = np.zeros_like(current_value)
    if len(past_weights) > 0:
        averaged += np.einsum("w,wkab->kab", past_weights, past_values)
    averaged += current_weight * current_value
    return averaged / total_weight


def _tau_average_matrix(
    tau: NDArray[np.float64],
    values: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    weights = _quadrature_weights(tau)
    total_weight = float(np.sum(weights))
    if total_weight <= 1e-15:
        return values[0].copy()
    return np.einsum("w,wab->ab", weights, values) / total_weight


def _thermal_branch_density_reference(
    matsubara_branch: MatsubaraBranchContainer | None,
) -> ComplexMatrix | None:
    if matsubara_branch is None:
        return None
    density = -matsubara_branch.green[-1]
    return 0.5 * (density + density.conjugate().T)


def _dissipative_collision(
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


def _nambu_expectation_value(
    operator: ComplexMatrix,
    generalized_density: ComplexMatrix,
) -> float:
    return float(0.5 * np.real(np.trace(generalized_density @ operator)))


def _explicit_bdg_hamiltonian_derivative(
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


def _cumulative_trapezoid(values: NDArray[np.float64], times: NDArray[np.float64]) -> NDArray[np.float64]:
    cumulative = np.zeros_like(values)
    if len(values) <= 1:
        return cumulative
    increments = 0.5 * (values[1:] + values[:-1]) * np.diff(times)
    cumulative[1:] = np.cumsum(increments)
    return cumulative


def _conservation_diagnostics(
    *,
    times: NDArray[np.float64],
    energy: NDArray[np.float64],
    particle_trace: NDArray[np.float64],
    external_power: NDArray[np.float64],
) -> dict[str, float | list[float]]:
    cumulative_external_work = _cumulative_trapezoid(external_power, times)
    particle_residual = np.abs(particle_trace - particle_trace[0])
    energy_work_mismatch = energy - energy[0] - cumulative_external_work
    energy_residual = np.abs(energy_work_mismatch)
    return {
        "particle_conservation_residual_history": particle_residual.astype(np.float64).tolist(),
        "max_particle_conservation_residual": float(np.max(particle_residual)),
        "final_particle_conservation_residual": float(particle_residual[-1]),
        "energy_work_mismatch_history": energy_work_mismatch.astype(np.float64).tolist(),
        "energy_conservation_residual_history": energy_residual.astype(np.float64).tolist(),
        "max_energy_work_mismatch": float(np.max(energy_residual)),
        "final_energy_work_mismatch": float(energy_residual[-1]),
    }


def _build_factorized_matsubara_branch(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
) -> MatsubaraBranchContainer | None:
    if not config.thermal_branch.enabled:
        return None

    beta = 1.0 / config.initial_state.temperature
    tau = np.linspace(0.0, beta, config.thermal_branch.n_tau + 1, dtype=np.float64)
    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        dynamics.lattice,
        0.0,
        dynamics.equilibrium.generalized_density,
        dynamics.equilibrium.effective_chemical_potential,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(bdg_hamiltonian)
    argument = np.clip(beta * eigenvalues, -120.0, 120.0)
    occupations = 1.0 / (np.exp(argument) + 1.0)
    empty_weights = 1.0 - occupations
    green = np.zeros((len(tau), bdg_hamiltonian.shape[0], bdg_hamiltonian.shape[1]), dtype=np.complex128)
    for index, tau_value in enumerate(tau):
        phase = np.exp(-tau_value * eigenvalues)
        green[index] = -(eigenvectors * (phase * empty_weights)[np.newaxis, :]) @ eigenvectors.conjugate().T
    return MatsubaraBranchContainer(tau=tau, green=green)


def _build_matsubara_branch(
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
            history_rule = _causal_history_rule(factorized_branch.tau, history_start=0, stop_index=tau_index)
            history_average = _history_average_matrix(
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
            collision = _dissipative_collision(gamma_matrix, branch_value - history_average)
            target = factorized_branch.green[tau_index] + dtau * collision
            updated_green[tau_index] = (
                config.thermal_branch.mixing * target + (1.0 - config.thermal_branch.mixing) * branch_value
            )
            updated_green[tau_index] = 0.5 * (updated_green[tau_index] + updated_green[tau_index].conjugate().T)
            max_residual = max(max_residual, float(np.max(np.abs(updated_green[tau_index] - branch_value))))
            max_memory_norm = max(max_memory_norm, float(np.max(gamma_site)) if len(gamma_site) else 0.0)
            max_order = max(max_order, history_rule.order)

        density_candidate = _thermal_branch_density_reference(
            MatsubaraBranchContainer(tau=factorized_branch.tau, green=updated_green)
        )
        if density_candidate is not None:
            density_reference = (
                config.thermal_branch.mixing * density_candidate
                + (1.0 - config.thermal_branch.mixing) * density_reference
            )
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
        ),
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
) -> dict[str, Any]:
    if matsubara_branch is None:
        return {
            "thermal_branch_enabled": False,
            "thermal_branch_correlated": False,
            "mixed_components_included": False,
            "thermal_branch_factorized_difference": 0.0,
        }

    density_reference = _thermal_branch_density_reference(matsubara_branch)
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
    }


def _build_factorized_mixed_branch(
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> MixedBranchContainer | None:
    if matsubara_branch is None:
        return None

    sample_count = len(dynamics.times)
    tau_count = len(matsubara_branch.tau)
    nambu_dimension = matsubara_branch.green.shape[1]
    right = np.zeros((sample_count, tau_count, nambu_dimension, nambu_dimension), dtype=np.complex128)
    left = np.zeros_like(right)
    mirrored_matsubara = matsubara_branch.green[::-1]

    for time_index, propagator in enumerate(dynamics.cumulative_propagators):
        propagator_dagger = propagator.conjugate().T
        for tau_index, matsubara_value in enumerate(matsubara_branch.green):
            right[time_index, tau_index] = -1j * propagator @ matsubara_value
            left[time_index, tau_index] = 1j * mirrored_matsubara[tau_index].conjugate().T @ propagator_dagger

    return MixedBranchContainer(
        times=dynamics.times,
        tau=matsubara_branch.tau,
        right=right,
        left=left,
    )


def _build_mixed_branch(
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
            diagnostics={"mixed_components_included": False, "mixed_branch_factorized_difference": 0.0},
        )

    if factorized_branch is None:
        factorized_branch = _build_factorized_mixed_branch(dynamics, matsubara_branch)
    if factorized_branch is None:
        return MixedBranchBuildResult(
            branch=None,
            factorized_branch=None,
            diagnostics={"mixed_components_included": False, "mixed_branch_factorized_difference": 0.0},
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
        mixed_envelope = np.abs(np.diagonal(_tau_average_matrix(matsubara_branch.tau, right[time_index])[:site_count, :site_count]))
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
        right[time_index] = factorized_branch.right[time_index] + step_dt * _dissipative_collision(
            gamma_matrix,
            right[time_index] - right_reference,
        )
        left[time_index] = factorized_branch.left[time_index] + step_dt * _dissipative_collision(
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
    )
    diagnostics["mixed_branch_memory_norm_history"] = memory_norm_history
    diagnostics["max_mixed_branch_memory_norm"] = float(max(memory_norm_history)) if memory_norm_history else 0.0
    return MixedBranchBuildResult(
        branch=branch,
        factorized_branch=factorized_branch,
        diagnostics=diagnostics,
    )


def _mixed_branch_diagnostics(
    *,
    matsubara_branch: MatsubaraBranchContainer | None,
    mixed_branch: MixedBranchContainer | None,
    factorized_branch: MixedBranchContainer | None,
) -> dict[str, Any]:
    if matsubara_branch is None or mixed_branch is None:
        return {"mixed_components_included": False, "mixed_branch_factorized_difference": 0.0}

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
    }
