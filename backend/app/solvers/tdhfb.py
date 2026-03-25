from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.schemas.progress import RunProgressPhase
from backend.app.solvers.base import (
    KSpaceNativeTrajectoryData,
    ObservableData,
    SeriesData,
    SimulationArtifacts,
    TwoTimeGreenFunctionData,
)
from backend.app.solvers.equilibrium_solvers import solve_equilibrium
from backend.app.solvers.green_functions import build_two_time_green_functions
from backend.app.solvers.hamiltonian import vector_potential
from backend.app.solvers.lattice import SquareLattice, build_square_lattice
from backend.app.solvers.nambu_observables import (
    build_complex_observable,
    explicit_bdg_hamiltonian_derivative,
    nambu_expectation_value,
)
from backend.app.solvers.progress import ProgressCallback
from backend.app.solvers.nambu import (
    ComplexMatrix,
    HFBEquilibriumState,
    PairingProjections,
    build_bdg_hamiltonian,
    effective_energy,
    extract_density_blocks,
    pairing_channel,
    pairing_projections,
)
from backend.app.solvers.observables import average_current, particle_density_statistics
from backend.app.solvers.observables import site_current_divergence, site_density_time_derivative
from backend.app.solvers.representation import MomentumSpaceContext
from backend.app.solvers.stationarity import stationarity_diagnostics
from backend.app.solvers.tdhfb_propagation import (
    _propagate_generalized_densities,
    _propagate_generalized_densities_kspace,
)
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
    density_blocks_history: list[NDArray[np.complex128]] | None = None
    cumulative_propagator_blocks: list[NDArray[np.complex128]] | None = None
    momentum_context: MomentumSpaceContext | None = None


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
    density_blocks_history: list[NDArray[np.complex128]] | None = None
    cumulative_propagator_blocks_result: list[NDArray[np.complex128]] | None = None
    momentum_context_result: MomentumSpaceContext | None = None
    if config.representation.value == "k_space":
        (
            times,
            saved_indices,
            generalized_densities,
            cumulative_propagators,
            propagation_diagnostics,
            density_blocks_history,
            cumulative_propagator_blocks_result,
            momentum_context_result,
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
        external_power = nambu_expectation_value(
            explicit_bdg_hamiltonian_derivative(config, lattice, time),
            generalized_density,
        )
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
        "equilibrium_convergence_failure_reason": equilibrium.convergence_failure_reason,
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_trace_array[0]))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_generalized_hermiticity_error": float(np.max(hermiticity_error_array)),
        "max_density_bound_violation": float(np.max(density_bound_violation_array)),
        "max_pairing_magnitude": float(np.max(np.abs(pairing_primary_array))),
        "max_pairing_s_magnitude": float(np.max(np.abs(pairing_s_array))),
        "max_pairing_d_magnitude": float(np.max(np.abs(pairing_d_array))),
        "final_pairing_magnitude": float(np.abs(pairing_primary_array[-1])),
        "equilibrium_pairing": float(np.abs(pairing_primary_array[0])),
        "equilibrium_pairing_s": float(np.abs(pairing_s_array[0])),
        "equilibrium_pairing_d": float(np.abs(pairing_d_array[0])),
        "equilibrium_density": float(density_mean_array[0]),
        "equilibrium_energy": float(energy_array[0]),
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
        "equilibrium_pairing": diagnostics["equilibrium_pairing"],
        "equilibrium_pairing_s": diagnostics["equilibrium_pairing_s"],
        "equilibrium_pairing_d": diagnostics["equilibrium_pairing_d"],
        "equilibrium_density": diagnostics["equilibrium_density"],
        "equilibrium_energy": diagnostics["equilibrium_energy"],
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
        density_blocks_history=density_blocks_history,
        cumulative_propagator_blocks=cumulative_propagator_blocks_result,
        momentum_context=momentum_context_result,
    )


def solve(config: SimulationConfig, progress_callback: ProgressCallback | None = None) -> SimulationArtifacts:
    """Run TDHFB propagation and return observables plus representation-specific artifacts."""
    dynamics = simulate_hfb_dynamics(config, progress_callback=progress_callback)
    kspace_native: KSpaceNativeTrajectoryData | None = None
    if (
        config.representation.value == "k_space"
        and dynamics.density_blocks_history is not None
        and dynamics.cumulative_propagator_blocks is not None
        and dynamics.momentum_context is not None
    ):
        kspace_native = KSpaceNativeTrajectoryData(
            times=np.asarray(dynamics.times, dtype=np.float64),
            density_blocks_history=np.asarray(dynamics.density_blocks_history, dtype=np.complex128),
            cumulative_propagator_blocks=np.asarray(dynamics.cumulative_propagator_blocks, dtype=np.complex128),
            kx=np.asarray(dynamics.momentum_context.kx, dtype=np.float64),
            ky=np.asarray(dynamics.momentum_context.ky, dtype=np.float64),
            reconstruction_mode="k_space_native_blocks",
        )
    two_time: TwoTimeGreenFunctionData | None = None
    if config.representation.value != "k_space":
        two_time_built = build_two_time_green_functions(dynamics)
        two_time = TwoTimeGreenFunctionData(
            times=two_time_built.times,
            components={
                "retarded": two_time_built.retarded,
                "lesser": two_time_built.lesser,
            },
        )
    return SimulationArtifacts(
        observables=dynamics.observables,
        diagnostics=dynamics.diagnostics,
        summary_excerpt=dynamics.summary_excerpt,
        two_time_green_functions=two_time,
        kspace_native_trajectory=kspace_native,
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
        "pairing": build_complex_observable("pairing", saved_times, pairing_primary[saved_indices], metadata),
        "pairing_s": build_complex_observable("pairing_s", saved_times, pairing_s[saved_indices], metadata),
        "pairing_d": build_complex_observable("pairing_d", saved_times, pairing_d[saved_indices], metadata),
    }
