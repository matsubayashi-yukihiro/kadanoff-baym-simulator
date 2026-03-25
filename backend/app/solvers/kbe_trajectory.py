from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import KBESelfEnergyMode, SimulationConfig
from backend.app.solvers.base import ObservableData, SeriesData
from backend.app.solvers.hamiltonian import vector_potential
from backend.app.solvers.nambu import (
    ComplexMatrix,
    build_bdg_hamiltonian,
    effective_energy,
    extract_density_blocks,
    pairing_channel,
    pairing_projections,
)
from backend.app.solvers.nambu_observables import (
    build_complex_observable,
    explicit_bdg_hamiltonian_derivative,
    nambu_expectation_value,
)
from backend.app.solvers.numerics import cumulative_trapezoid
from backend.app.solvers.observables import average_current, particle_density_statistics
from backend.app.solvers.observables import site_current_divergence, site_density_time_derivative
from backend.app.solvers.stationarity import stationarity_diagnostics
from backend.app.solvers.tdhfb import HFBDynamicsResult


def analyze_kbe_trajectory(
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
    continuity_residual_norm: list[float] = []
    pairing_primary: list[complex] = []
    pairing_s: list[complex] = []
    pairing_d: list[complex] = []
    continuity_residual_supported = (
        pairing_channel(config).value == "none" and config.kbe.self_energy == KBESelfEnergyMode.HFB
    )

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
        if continuity_residual_supported:
            continuity_residual = site_density_time_derivative(normal_hamiltonian, normal_density) + site_current_divergence(
                dynamics.lattice,
                normal_hamiltonian,
                normal_density,
            )
            continuity_residual_norm.append(float(np.max(np.abs(continuity_residual))))
        ax, ay = vector_potential(config.drive, float(time))
        vector_ax.append(ax)
        vector_ay.append(ay)
        particle_trace.append(float(np.real(np.trace(normal_density))))
        external_power.append(
            nambu_expectation_value(
                explicit_bdg_hamiltonian_derivative(config, dynamics.lattice, float(time)),
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
    continuity_residual_norm_array = np.asarray(continuity_residual_norm, dtype=np.float64)
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
        "pairing": build_complex_observable("pairing", saved_times, pairing_primary_array[saved_indices], metadata),
        "pairing_s": build_complex_observable("pairing_s", saved_times, pairing_s_array[saved_indices], metadata),
        "pairing_d": build_complex_observable("pairing_d", saved_times, pairing_d_array[saved_indices], metadata),
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
    diagnostics.update(conservation_diagnostics)
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
        "max_particle_conservation_residual": diagnostics["max_particle_conservation_residual"],
        "max_energy_work_mismatch": diagnostics["max_energy_work_mismatch"],
        "time_grid_mode": dynamics.diagnostics["time_grid_mode"],
    }
    if continuity_residual_supported:
        summary_excerpt["max_continuity_residual"] = diagnostics["max_continuity_residual"]
    return {name: observables[name] for name in config.observables}, diagnostics, summary_excerpt


def _conservation_diagnostics(
    *,
    times: NDArray[np.float64],
    energy: NDArray[np.float64],
    particle_trace: NDArray[np.float64],
    external_power: NDArray[np.float64],
) -> dict[str, float | list[float]]:
    cumulative_external_work = cumulative_trapezoid(external_power, times)
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
