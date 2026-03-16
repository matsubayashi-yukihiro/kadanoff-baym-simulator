from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.base import ObservableData, SeriesData, SimulationArtifacts
from backend.app.solvers.hamiltonian import vector_potential
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

    if config.kbe.self_energy == KBESelfEnergyMode.SECOND_BORN:
        reference_densities, second_born_diagnostics = _apply_second_born_corrections(
            config=config,
            dynamics=dynamics,
            hfb_green_functions=hfb_green_functions,
        )
        observables, trajectory_diagnostics, summary_excerpt = _analyze_trajectory(
            config=config,
            dynamics=dynamics,
            generalized_densities=reference_densities,
        )
        diagnostics.update(trajectory_diagnostics)
        diagnostics.update(second_born_diagnostics)
        green_function_reference = build_two_time_green_functions(
            dynamics,
            generalized_densities=reference_densities,
        )
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
            }
        )

    diagnostics.update(
        _green_function_diagnostics(
            dynamics=dynamics,
            green_functions=green_function_reference,
            reference_densities=reference_densities,
            tdhfb_reference_densities=dynamics.generalized_densities,
        )
    )

    matsubara_branch = _build_matsubara_branch(config, dynamics)
    diagnostics.update(_matsubara_diagnostics(config, dynamics, matsubara_branch))
    summary_excerpt["max_equal_time_tdhfb_mismatch"] = diagnostics["max_equal_time_tdhfb_mismatch"]
    if matsubara_branch is not None:
        summary_excerpt["matsubara_beta"] = diagnostics["matsubara_beta"]
    return SimulationArtifacts(
        observables=observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
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
        "kbe_two_time_reconstruction": "exact_hfb" if equal_time_tdhfb_mismatch == 0.0 else "equal_time_average",
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
) -> tuple[list[ComplexMatrix], dict[str, Any]]:
    onsite_strength = abs(config.interaction.onsite_u)
    corrected = [density.copy() for density in dynamics.generalized_densities[:1]]
    sample_count = len(dynamics.times)
    site_count = dynamics.lattice.site_count
    if sample_count <= 1 or onsite_strength <= 1e-12:
        return corrected + [density.copy() for density in dynamics.generalized_densities[1:]], {
            "second_born_enabled": True,
            "second_born_converged": True,
            "second_born_iteration_history": [1] * max(sample_count - 1, 0),
            "second_born_residual_history": [0.0] * max(sample_count - 1, 0),
            "second_born_memory_norm_history": [0.0] * max(sample_count - 1, 0),
            "second_born_collision_norm_history": [0.0] * max(sample_count - 1, 0),
            "max_second_born_memory_norm": 0.0,
            "max_second_born_collision_norm": 0.0,
            "second_born_memory_window": int(config.kbe.memory_window or max(sample_count - 1, 0)),
        }

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
) -> tuple[dict[str, ObservableData], dict[str, float], dict[str, float | str]]:
    density_mean: list[float] = []
    density_min: list[float] = []
    density_max: list[float] = []
    current_x: list[float] = []
    current_y: list[float] = []
    energy: list[float] = []
    vector_ax: list[float] = []
    vector_ay: list[float] = []
    particle_trace: list[float] = []
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
    hermiticity_error_array = np.asarray(hermiticity_error, dtype=np.float64)
    density_bound_violation_array = np.asarray(density_bound_violation, dtype=np.float64)
    pairing_primary_array = np.asarray(pairing_primary, dtype=np.complex128)
    pairing_s_array = np.asarray(pairing_s, dtype=np.complex128)
    pairing_d_array = np.asarray(pairing_d, dtype=np.complex128)

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
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean_array[-1]),
        "final_pairing_magnitude": diagnostics["final_pairing_magnitude"],
        "pairing_s_final": float(np.abs(pairing_s_array[-1])),
        "pairing_d_final": float(np.abs(pairing_d_array[-1])),
        "particle_number_drift": diagnostics["particle_number_drift"],
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


def _build_matsubara_branch(
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


def _matsubara_diagnostics(
    config: SimulationConfig,
    dynamics: HFBDynamicsResult,
    matsubara_branch: MatsubaraBranchContainer | None,
) -> dict[str, Any]:
    if matsubara_branch is None:
        return {
            "thermal_branch_enabled": False,
            "mixed_components_included": False,
        }

    identity = np.eye(dynamics.equilibrium.generalized_density.shape[0], dtype=np.complex128)
    zero_plus_error = float(
        np.max(np.abs(matsubara_branch.green[0] + (identity - dynamics.equilibrium.generalized_density)))
    )
    beta_minus_error = float(
        np.max(np.abs(matsubara_branch.green[-1] + dynamics.equilibrium.generalized_density))
    )
    return {
        "thermal_branch_enabled": True,
        "mixed_components_included": False,
        "matsubara_beta": float(1.0 / config.initial_state.temperature),
        "matsubara_grid_shape": [
            int(matsubara_branch.green.shape[0]),
            int(matsubara_branch.green.shape[1]),
            int(matsubara_branch.green.shape[2]),
        ],
        "matsubara_zero_plus_error": zero_plus_error,
        "matsubara_beta_minus_error": beta_minus_error,
        "thermal_branch_converged": True,
        "thermal_branch_iterations": 1,
    }
