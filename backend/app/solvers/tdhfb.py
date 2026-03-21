from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.base import ObservableData, SeriesData, SimulationArtifacts, TwoTimeGreenFunctionData
from backend.app.solvers.equilibrium_solvers import solve_equilibrium
from backend.app.solvers.green_functions import build_two_time_green_functions
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian_derivative, vector_potential
from backend.app.solvers.lattice import SquareLattice, build_square_lattice
from backend.app.solvers.nambu import (
    ComplexMatrix,
    HFBEquilibriumState,
    PairingProjections,
    build_bdg_hamiltonian,
    effective_energy,
    extract_density_blocks,
    pairing_channel,
    pairing_projections,
    propagate_generalized_density,
    saved_step_indices,
    saved_step_indices_from_count,
)
from backend.app.solvers.observables import average_current, particle_density_statistics
from backend.app.solvers.observables import site_current_divergence, site_density_time_derivative
from backend.app.solvers.stationarity import stationarity_diagnostics
from backend.app.jobs.progress import SolverProgressUpdate


@dataclass(slots=True)
class HFBDynamicsResult:
    lattice: SquareLattice
    times: NDArray[np.float64]
    saved_indices: NDArray[np.int64]
    generalized_densities: list[ComplexMatrix]
    cumulative_propagators: list[ComplexMatrix]
    equilibrium: HFBEquilibriumState
    observables: dict[str, ObservableData]
    diagnostics: dict[str, Any]
    summary_excerpt: dict[str, Any]


def simulate_hfb_dynamics(
    config: SimulationConfig,
    progress_callback: ProgressCallback | None = None,
) -> HFBDynamicsResult:
    lattice = build_square_lattice(config.lattice)
    if progress_callback is not None:
        progress_callback(
            SolverProgressUpdate(
                phase=RunProgressPhase.EQUILIBRIUM,
                status_line="solving HFB equilibrium",
                physical_time_current=0.0,
                physical_time_final=float(config.time.t_final),
                physical_progress_fraction=0.0,
                accepted_steps=0,
                requested_steps=int(config.time.n_steps),
                saved_samples_written=0,
                solver_metrics={},
            ),
            force=True,
        )
    equilibrium = solve_equilibrium(config, lattice)
    if progress_callback is not None:
        progress_callback(
            SolverProgressUpdate(
                phase=RunProgressPhase.PROPAGATING,
                status_line="propagating generalized density",
                physical_time_current=0.0,
                physical_time_final=float(config.time.t_final),
                physical_progress_fraction=0.0,
                accepted_steps=0,
                requested_steps=int(config.time.n_steps),
                saved_samples_written=1,
                solver_metrics={},
            ),
            force=True,
        )
    if config.representation.value == "k_space":
        (
            times,
            saved_indices,
            generalized_densities,
            cumulative_propagators,
            propagation_diagnostics,
        ) = _propagate_generalized_densities_kspace(config, equilibrium, progress_callback=progress_callback)
    else:
        (
            times,
            saved_indices,
            generalized_densities,
            cumulative_propagators,
            propagation_diagnostics,
        ) = _propagate_generalized_densities(
            config,
            lattice,
            equilibrium,
            progress_callback=progress_callback,
        )

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
    continuity_residual_norm: list[float] = []
    pairing_values: list[PairingProjections] = []
    continuity_residual_supported = pairing_channel(config).value == "none"
    cumulative_external_work = 0.0
    previous_time: float | None = None
    previous_external_power: float | None = None
    max_continuity_residual_so_far = 0.0
    max_energy_work_mismatch_so_far = 0.0

    for time, generalized_density in zip(times, generalized_densities, strict=True):
        normal_hamiltonian, pairing_field, _, bdg_hamiltonian = build_bdg_hamiltonian(
            config,
            lattice,
            time,
            generalized_density,
            equilibrium.effective_chemical_potential,
        )
        normal_density, _ = extract_density_blocks(generalized_density, lattice.site_count)
        density_stats = particle_density_statistics(normal_density)
        density_mean.append(density_stats[0])
        density_min.append(density_stats[1])
        density_max.append(density_stats[2])
        current_x.append(average_current(lattice.bonds_x, normal_hamiltonian, normal_density))
        current_y.append(average_current(lattice.bonds_y, normal_hamiltonian, normal_density))
        energy.append(effective_energy(generalized_density, bdg_hamiltonian))
        if continuity_residual_supported:
            continuity_residual = site_density_time_derivative(normal_hamiltonian, normal_density) + site_current_divergence(
                lattice,
                normal_hamiltonian,
                normal_density,
            )
            continuity_value = float(np.max(np.abs(continuity_residual)))
            continuity_residual_norm.append(continuity_value)
            max_continuity_residual_so_far = max(max_continuity_residual_so_far, continuity_value)
        ax, ay = vector_potential(config.drive, time)
        vector_ax.append(ax)
        vector_ay.append(ay)
        particle_trace.append(float(np.real(np.trace(normal_density))))
        hermiticity_error.append(float(np.max(np.abs(generalized_density - generalized_density.conjugate().T))))
        site_density = np.real(np.diag(normal_density))
        density_bound_violation.append(float(np.max(np.maximum(site_density - 1.0, 0.0) + np.maximum(-site_density, 0.0))))
        pairing_values.append(pairing_projections(config, lattice, pairing_field))
        external_power = _nambu_expectation_value(_explicit_bdg_hamiltonian_derivative(config, lattice, time), generalized_density)
        if previous_time is not None and previous_external_power is not None:
            cumulative_external_work += 0.5 * (previous_external_power + external_power) * float(time - previous_time)
        energy_work_mismatch = energy[-1] - energy[0] - cumulative_external_work
        max_energy_work_mismatch_so_far = max(max_energy_work_mismatch_so_far, abs(energy_work_mismatch))
        previous_time = float(time)
        previous_external_power = external_power
        if progress_callback is not None:
            accepted_steps = max(int(np.searchsorted(times, time, side="left")), 0)
            latest_dt = propagation_diagnostics.get("time_step_history", [])
            latest_error_history = propagation_diagnostics.get("adaptive_error_estimate_history", [])
            progress_callback(
                SolverProgressUpdate(
                    phase=RunProgressPhase.PROPAGATING,
                    status_line=f"propagating generalized density at t={float(time):.3f}",
                    physical_time_current=float(time),
                    physical_time_final=float(config.time.t_final),
                    physical_progress_fraction=(float(time) / float(config.time.t_final)) if config.time.t_final > 0 else 1.0,
                    accepted_steps=accepted_steps,
                    requested_steps=int(config.time.n_steps),
                    rejected_steps=int(propagation_diagnostics.get("rejected_time_steps", 0)),
                    saved_samples_written=int(np.count_nonzero(saved_indices <= accepted_steps)),
                    solver_metrics={
                        "current_dt": float(latest_dt[accepted_steps - 1]) if accepted_steps > 0 and accepted_steps - 1 < len(latest_dt) else float(config.time.dt),
                        "latest_adaptive_error_estimate": (
                            float(latest_error_history[accepted_steps - 1])
                            if accepted_steps > 0 and accepted_steps - 1 < len(latest_error_history)
                            else 0.0
                        ),
                        "max_continuity_residual_so_far": max_continuity_residual_so_far,
                        "max_energy_work_mismatch_so_far": max_energy_work_mismatch_so_far,
                    },
                )
            )

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
    continuity_residual_norm_array = np.asarray(continuity_residual_norm, dtype=np.float64)
    pairing_primary_array = np.asarray([value.primary for value in pairing_values], dtype=np.complex128)
    pairing_s_array = np.asarray([value.s_wave for value in pairing_values], dtype=np.complex128)
    pairing_d_array = np.asarray([value.d_wave for value in pairing_values], dtype=np.complex128)

    observables = _build_observables(
        config=config,
        saved_times=times[saved_indices],
        saved_indices=saved_indices,
        density_mean=density_mean_array,
        density_min=density_min_array,
        density_max=density_max_array,
        current_x=current_x_array,
        current_y=current_y_array,
        energy=energy_array,
        vector_ax=vector_ax_array,
        vector_ay=vector_ay_array,
        pairing_primary=pairing_primary_array,
        pairing_s=pairing_s_array,
        pairing_d=pairing_d_array,
    )

    diagnostics = {
        "site_count": lattice.site_count,
        "time_steps": int(len(times) - 1),
        "saved_samples": int(len(saved_indices)),
        "particle_target": float(config.initial_state.filling * lattice.site_count),
        "effective_chemical_potential": float(equilibrium.effective_chemical_potential),
        "pairing_channel": pairing_channel(config).value,
        "hfb_iterations": equilibrium.iterations,
        "hfb_converged": equilibrium.converged,
        "hfb_self_consistency_error": float(equilibrium.self_consistency_error),
        "hfb_fixed_point_accelerator": "anderson_diis",
        "equilibrium_solver_method": equilibrium.method,
        "equilibrium_method_requested": equilibrium.requested_method,
        "equilibrium_method_resolved": equilibrium.method,
        "equilibrium_matches_runtime_approximation": equilibrium.matches_runtime_approximation,
        "equilibrium_mismatch_allowed": equilibrium.mismatch_allowed,
        "equilibrium_solver_mode": equilibrium.solver_mode,
        "equilibrium_density_update_residual": float(equilibrium.density_update_residual),
        "equilibrium_stationarity_residual": float(equilibrium.stationarity_residual),
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_trace_array[0]))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_generalized_hermiticity_error": float(np.max(hermiticity_error_array)),
        "max_density_bound_violation": float(np.max(density_bound_violation_array)),
        "max_pairing_magnitude": float(np.max(np.abs(pairing_primary_array))),
        "max_pairing_s_magnitude": float(np.max(np.abs(pairing_s_array))),
        "max_pairing_d_magnitude": float(np.max(np.abs(pairing_d_array))),
        "final_pairing_magnitude": float(np.abs(pairing_primary_array[-1])),
        "continuity_residual_supported": continuity_residual_supported,
        "continuity_residual_history": continuity_residual_norm_array.tolist(),
        "max_continuity_residual": (
            float(np.max(continuity_residual_norm_array)) if continuity_residual_supported else None
        ),
        "final_continuity_residual": (
            float(continuity_residual_norm_array[-1]) if continuity_residual_supported else None
        ),
        "solver_representation": config.representation.value,
        "representation_equivalence_reference": "real_space",
    }
    diagnostics.update(
        stationarity_diagnostics(
            generalized_densities=generalized_densities,
            density_mean=density_mean_array,
            energy=energy_array,
            pairing_primary=pairing_primary_array,
            pairing_d=pairing_d_array,
        )
    )
    diagnostics.update(propagation_diagnostics)
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean_array[-1]),
        "final_pairing_magnitude": diagnostics["final_pairing_magnitude"],
        "pairing_s_final": float(np.abs(pairing_s_array[-1])),
        "pairing_d_final": float(np.abs(pairing_d_array[-1])),
        "particle_number_drift": diagnostics["particle_number_drift"],
        "max_stationarity_residual": diagnostics["max_stationarity_residual"],
        "time_grid_mode": diagnostics["time_grid_mode"],
    }
    if continuity_residual_supported:
        summary_excerpt["max_continuity_residual"] = diagnostics["max_continuity_residual"]
    return HFBDynamicsResult(
        lattice=lattice,
        times=times,
        saved_indices=saved_indices,
        generalized_densities=generalized_densities,
        cumulative_propagators=cumulative_propagators,
        equilibrium=equilibrium,
        observables={name: observables[name] for name in config.observables},
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
    )


def solve(config: SimulationConfig, progress_callback: ProgressCallback | None = None) -> SimulationArtifacts:
    dynamics = simulate_hfb_dynamics(config, progress_callback=progress_callback)
    two_time = build_two_time_green_functions(dynamics)
    return SimulationArtifacts(
        observables=dynamics.observables,
        diagnostics=dynamics.diagnostics,
        summary_excerpt=dynamics.summary_excerpt,
        two_time_green_functions=TwoTimeGreenFunctionData(
            times=two_time.times,
            components={
                "retarded": two_time.retarded,
                "lesser": two_time.lesser,
            },
        ),
    )


def _propagate_generalized_densities(
    config: SimulationConfig,
    lattice: SquareLattice,
    equilibrium: HFBEquilibriumState,
    progress_callback: ProgressCallback | None = None,
    ) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    list[ComplexMatrix],
    list[ComplexMatrix],
    dict[str, Any],
]:
    if not config.adaptive.enabled:
        times = np.asarray(config.time.time_points(), dtype=np.float64)
        generalized_densities = [equilibrium.generalized_density]
        cumulative_propagators = [np.eye(2 * lattice.site_count, dtype=np.complex128)]
        for time in times[:-1]:
            next_density, propagator = _advance_generalized_density_step(
                config=config,
                lattice=lattice,
                equilibrium=equilibrium,
                current_density=generalized_densities[-1],
                time=float(time),
                dt=config.time.dt,
            )
            generalized_densities.append(next_density)
            cumulative_propagators.append(propagator @ cumulative_propagators[-1])
            if progress_callback is not None:
                accepted_steps = len(generalized_densities) - 1
                current_time = float(times[accepted_steps])
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"propagating generalized density at t={current_time:.3f}",
                        physical_time_current=current_time,
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=current_time / float(config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=accepted_steps,
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=0,
                        saved_samples_written=int(np.count_nonzero(saved_step_indices(config) <= accepted_steps)),
                        solver_metrics={
                            "current_dt": float(config.time.dt),
                            "latest_adaptive_error_estimate": 0.0,
                        },
                    )
                )
        return (
            times,
            saved_step_indices(config),
            generalized_densities,
            cumulative_propagators,
            {
                "requested_time_steps": config.time.n_steps,
                "accepted_time_steps": config.time.n_steps,
                "rejected_time_steps": 0,
                "time_grid_mode": "uniform",
                "adaptive_enabled": False,
                "time_step_history": [float(config.time.dt)] * config.time.n_steps,
                "adaptive_error_estimate_history": [],
                "adaptive_max_error_estimate": 0.0,
            },
        )

    times = [0.0]
    generalized_densities = [equilibrium.generalized_density]
    cumulative_propagators = [np.eye(2 * lattice.site_count, dtype=np.complex128)]
    error_estimates: list[float] = []
    time_step_history: list[float] = []
    rejected_steps = 0
    current_time = 0.0
    min_dt = config.adaptive.min_dt if config.adaptive.min_dt is not None else config.time.dt / 32.0
    max_dt = config.adaptive.max_dt if config.adaptive.max_dt is not None else config.time.dt
    next_dt = min(config.time.dt, max_dt, config.time.t_final)

    while current_time < config.time.t_final - 1e-12:
        current_density = generalized_densities[-1]
        trial_dt = min(next_dt, config.time.t_final - current_time)
        if trial_dt <= 0.0:
            break

        full_density, _ = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=current_density,
            time=current_time,
            dt=trial_dt,
        )
        half_density, half_propagator_left = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=current_density,
            time=current_time,
            dt=0.5 * trial_dt,
        )
        accepted_density, half_propagator_right = _advance_generalized_density_step(
            config=config,
            lattice=lattice,
            equilibrium=equilibrium,
            current_density=half_density,
            time=current_time + 0.5 * trial_dt,
            dt=0.5 * trial_dt,
        )
        accepted_propagator = half_propagator_right @ half_propagator_left

        scale = config.adaptive.atol + config.adaptive.rtol * max(
            1.0,
            float(np.max(np.abs(current_density))),
            float(np.max(np.abs(accepted_density))),
        )
        error_estimate = float(np.max(np.abs(accepted_density - full_density)) / scale)

        if error_estimate <= 1.0 or trial_dt <= min_dt * (1.0 + 1e-12):
            current_time += trial_dt
            times.append(float(current_time))
            generalized_densities.append(accepted_density)
            cumulative_propagators.append(accepted_propagator @ cumulative_propagators[-1])
            time_step_history.append(float(trial_dt))
            error_estimates.append(error_estimate)
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"accepted adaptive step to t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = min(
                max_dt,
                max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config)),
            )
        else:
            rejected_steps += 1
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"rejected adaptive step at t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config))

    times_array = np.asarray(times, dtype=np.float64)
    return (
        times_array,
        saved_step_indices_from_count(len(times_array), config.time.save_every),
        generalized_densities,
        cumulative_propagators,
        {
            "requested_time_steps": config.time.n_steps,
            "accepted_time_steps": int(len(times_array) - 1),
            "rejected_time_steps": rejected_steps,
            "time_grid_mode": "adaptive",
            "adaptive_enabled": True,
            "time_step_history": time_step_history,
            "adaptive_error_estimate_history": error_estimates,
            "adaptive_max_error_estimate": float(max(error_estimates)) if error_estimates else 0.0,
            "adaptive_min_dt_used": float(min(time_step_history)) if time_step_history else 0.0,
            "adaptive_max_dt_used": float(max(time_step_history)) if time_step_history else 0.0,
        },
    )


def _advance_generalized_density_step(
    *,
    config: SimulationConfig,
    lattice: SquareLattice,
    equilibrium: HFBEquilibriumState,
    current_density: ComplexMatrix,
    time: float,
    dt: float,
) -> tuple[ComplexMatrix, ComplexMatrix]:
    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time,
        current_density,
        equilibrium.effective_chemical_potential,
    )
    predicted_density, _ = propagate_generalized_density(current_density, bdg_hamiltonian, dt)
    midpoint_density = 0.5 * (current_density + predicted_density)
    midpoint_density = 0.5 * (midpoint_density + midpoint_density.conjugate().T)
    _, _, _, midpoint_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time + 0.5 * dt,
        midpoint_density,
        equilibrium.effective_chemical_potential,
    )
    return propagate_generalized_density(current_density, midpoint_hamiltonian, dt)


def _adaptive_step_factor(error_estimate: float, config: SimulationConfig) -> float:
    if error_estimate <= 1e-16:
        return config.adaptive.max_growth
    proposed = 0.9 * error_estimate ** (-1.0 / 3.0)
    return min(config.adaptive.max_growth, max(config.adaptive.min_shrink, proposed))


def _propagate_generalized_densities_kspace(
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    progress_callback: ProgressCallback | None = None,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    list[ComplexMatrix],
    list[ComplexMatrix],
    dict[str, Any],
]:
    context = equilibrium.momentum_context
    current_density_k = equilibrium.momentum_generalized_density
    assert context is not None
    assert current_density_k is not None

    if not config.adaptive.enabled:
        times = np.asarray(config.time.time_points(), dtype=np.float64)
        generalized_densities = [equilibrium.generalized_density]
        cumulative_propagators = [np.eye(2 * context.site_count, dtype=np.complex128)]
        for time in times[:-1]:
            next_density_k, propagator_k = _advance_generalized_density_step_kspace(
                config=config,
                equilibrium=equilibrium,
                context=context,
                current_density_k=current_density_k,
                time=float(time),
                dt=config.time.dt,
            )
            generalized_densities.append(context.nambu_momentum_to_site @ next_density_k @ context.nambu_site_to_momentum)
            cumulative_propagators.append(
                (context.nambu_momentum_to_site @ propagator_k @ context.nambu_site_to_momentum) @ cumulative_propagators[-1]
            )
            current_density_k = next_density_k
            if progress_callback is not None:
                accepted_steps = len(generalized_densities) - 1
                current_time = float(times[accepted_steps])
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"propagating generalized density at t={current_time:.3f}",
                        physical_time_current=current_time,
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=current_time / float(config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=accepted_steps,
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=0,
                        saved_samples_written=int(np.count_nonzero(saved_step_indices(config) <= accepted_steps)),
                        solver_metrics={
                            "current_dt": float(config.time.dt),
                            "latest_adaptive_error_estimate": 0.0,
                        },
                    )
                )
        return (
            times,
            saved_step_indices(config),
            generalized_densities,
            cumulative_propagators,
            {
                "requested_time_steps": config.time.n_steps,
                "accepted_time_steps": config.time.n_steps,
                "rejected_time_steps": 0,
                "time_grid_mode": "uniform",
                "adaptive_enabled": False,
                "time_step_history": [float(config.time.dt)] * config.time.n_steps,
                "adaptive_error_estimate_history": [],
                "adaptive_max_error_estimate": 0.0,
            },
        )

    times = [0.0]
    generalized_densities = [equilibrium.generalized_density]
    cumulative_propagators = [np.eye(2 * context.site_count, dtype=np.complex128)]
    error_estimates: list[float] = []
    time_step_history: list[float] = []
    rejected_steps = 0
    current_time = 0.0
    min_dt = config.adaptive.min_dt if config.adaptive.min_dt is not None else config.time.dt / 32.0
    max_dt = config.adaptive.max_dt if config.adaptive.max_dt is not None else config.time.dt
    next_dt = min(config.time.dt, max_dt, config.time.t_final)

    while current_time < config.time.t_final - 1e-12:
        trial_dt = min(next_dt, config.time.t_final - current_time)
        if trial_dt <= 0.0:
            break

        full_density, _ = _advance_generalized_density_step_kspace(
            config=config,
            equilibrium=equilibrium,
            context=context,
            current_density_k=current_density_k,
            time=current_time,
            dt=trial_dt,
        )
        half_density, half_propagator_left = _advance_generalized_density_step_kspace(
            config=config,
            equilibrium=equilibrium,
            context=context,
            current_density_k=current_density_k,
            time=current_time,
            dt=0.5 * trial_dt,
        )
        accepted_density, half_propagator_right = _advance_generalized_density_step_kspace(
            config=config,
            equilibrium=equilibrium,
            context=context,
            current_density_k=half_density,
            time=current_time + 0.5 * trial_dt,
            dt=0.5 * trial_dt,
        )
        accepted_propagator = half_propagator_right @ half_propagator_left

        scale = config.adaptive.atol + config.adaptive.rtol * max(
            1.0,
            float(np.max(np.abs(current_density_k))),
            float(np.max(np.abs(accepted_density))),
        )
        error_estimate = float(np.max(np.abs(accepted_density - full_density)) / scale)

        if error_estimate <= 1.0 or trial_dt <= min_dt * (1.0 + 1e-12):
            current_time += trial_dt
            times.append(float(current_time))
            generalized_densities.append(
                context.nambu_momentum_to_site @ accepted_density @ context.nambu_site_to_momentum
            )
            cumulative_propagators.append(
                (context.nambu_momentum_to_site @ accepted_propagator @ context.nambu_site_to_momentum)
                @ cumulative_propagators[-1]
            )
            time_step_history.append(float(trial_dt))
            error_estimates.append(error_estimate)
            current_density_k = accepted_density
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"accepted adaptive step to t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = min(
                max_dt,
                max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config)),
            )
        else:
            rejected_steps += 1
            if progress_callback is not None:
                progress_callback(
                    SolverProgressUpdate(
                        phase=RunProgressPhase.PROPAGATING,
                        status_line=f"rejected adaptive step at t={current_time:.3f}",
                        physical_time_current=float(current_time),
                        physical_time_final=float(config.time.t_final),
                        physical_progress_fraction=float(current_time / config.time.t_final) if config.time.t_final > 0 else 1.0,
                        accepted_steps=int(len(times) - 1),
                        requested_steps=int(config.time.n_steps),
                        rejected_steps=rejected_steps,
                        saved_samples_written=int(
                            np.count_nonzero(saved_step_indices_from_count(len(times), config.time.save_every) <= len(times) - 1)
                        ),
                        solver_metrics={
                            "current_dt": float(trial_dt),
                            "latest_adaptive_error_estimate": error_estimate,
                        },
                    )
                )
            next_dt = max(min_dt, trial_dt * _adaptive_step_factor(error_estimate, config))

    times_array = np.asarray(times, dtype=np.float64)
    return (
        times_array,
        saved_step_indices_from_count(len(times_array), config.time.save_every),
        generalized_densities,
        cumulative_propagators,
        {
            "requested_time_steps": config.time.n_steps,
            "accepted_time_steps": int(len(times_array) - 1),
            "rejected_time_steps": rejected_steps,
            "time_grid_mode": "adaptive",
            "adaptive_enabled": True,
            "time_step_history": time_step_history,
            "adaptive_error_estimate_history": error_estimates,
            "adaptive_max_error_estimate": float(max(error_estimates)) if error_estimates else 0.0,
            "adaptive_min_dt_used": float(min(time_step_history)) if time_step_history else 0.0,
            "adaptive_max_dt_used": float(max(time_step_history)) if time_step_history else 0.0,
        },
    )


def _advance_generalized_density_step_kspace(
    *,
    config: SimulationConfig,
    equilibrium: HFBEquilibriumState,
    context,
    current_density_k: ComplexMatrix,
    time: float,
    dt: float,
) -> tuple[ComplexMatrix, ComplexMatrix]:
    site_current_density = context.nambu_momentum_to_site @ current_density_k @ context.nambu_site_to_momentum
    _, _, _, bdg_site = build_bdg_hamiltonian(
        config,
        context.lattice,
        time,
        site_current_density,
        equilibrium.effective_chemical_potential,
    )
    bdg_k = context.nambu_site_to_momentum @ bdg_site @ context.nambu_momentum_to_site
    predicted_density, _ = propagate_generalized_density(current_density_k, bdg_k, dt)
    midpoint_density = 0.5 * (current_density_k + predicted_density)
    midpoint_density = 0.5 * (midpoint_density + midpoint_density.conjugate().T)
    site_midpoint_density = context.nambu_momentum_to_site @ midpoint_density @ context.nambu_site_to_momentum
    _, _, _, midpoint_site_hamiltonian = build_bdg_hamiltonian(
        config,
        context.lattice,
        time + 0.5 * dt,
        site_midpoint_density,
        equilibrium.effective_chemical_potential,
    )
    midpoint_hamiltonian = context.nambu_site_to_momentum @ midpoint_site_hamiltonian @ context.nambu_momentum_to_site
    return propagate_generalized_density(current_density_k, midpoint_hamiltonian, dt)


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


def _build_observables(
    *,
    config: SimulationConfig,
    saved_times: NDArray[np.float64],
    saved_indices: NDArray[np.int64],
    density_mean: NDArray[np.float64],
    density_min: NDArray[np.float64],
    density_max: NDArray[np.float64],
    current_x: NDArray[np.float64],
    current_y: NDArray[np.float64],
    energy: NDArray[np.float64],
    vector_ax: NDArray[np.float64],
    vector_ay: NDArray[np.float64],
    pairing_primary: NDArray[np.complex128],
    pairing_s: NDArray[np.complex128],
    pairing_d: NDArray[np.complex128],
) -> dict[str, ObservableData]:
    solver_name = config.solver.value if hasattr(config.solver, "value") else str(config.solver)
    metadata = {
        "solver": solver_name,
        "pairing_channel": pairing_channel(config).value,
    }
    return {
        "density": ObservableData(
            name="density",
            time=saved_times,
            series=[
                SeriesData(label="mean", values=density_mean[saved_indices]),
                SeriesData(label="min", values=density_min[saved_indices]),
                SeriesData(label="max", values=density_max[saved_indices]),
            ],
            metadata=metadata,
        ),
        "current_x": ObservableData(
            name="current_x",
            time=saved_times,
            series=[SeriesData(label="total", values=current_x[saved_indices])],
            metadata=metadata,
        ),
        "current_y": ObservableData(
            name="current_y",
            time=saved_times,
            series=[SeriesData(label="total", values=current_y[saved_indices])],
            metadata=metadata,
        ),
        "energy": ObservableData(
            name="energy",
            time=saved_times,
            series=[SeriesData(label="total", values=energy[saved_indices])],
            metadata=metadata,
        ),
        "vector_potential": ObservableData(
            name="vector_potential",
            time=saved_times,
            series=[
                SeriesData(label="ax", values=vector_ax[saved_indices]),
                SeriesData(label="ay", values=vector_ay[saved_indices]),
            ],
            metadata=metadata,
        ),
        "pairing": _complex_observable("pairing", saved_times, pairing_primary[saved_indices], metadata),
        "pairing_s": _complex_observable("pairing_s", saved_times, pairing_s[saved_indices], metadata),
        "pairing_d": _complex_observable("pairing_d", saved_times, pairing_d[saved_indices], metadata),
    }


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
