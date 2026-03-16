from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.base import ObservableData, SeriesData, SimulationArtifacts
from backend.app.solvers.equilibrium import occupation_numbers
from backend.app.solvers.hamiltonian import (
    build_one_body_hamiltonian,
    build_one_body_hamiltonian_derivative,
    vector_potential,
)
from backend.app.solvers.lattice import SquareLattice, build_square_lattice
from backend.app.solvers.numerics import cumulative_trapezoid
from backend.app.solvers.observables import average_current, particle_density_statistics, total_energy


def _initial_density_matrix(
    config: SimulationConfig,
    lattice: SquareLattice,
) -> NDArray[np.complex128]:
    h0 = build_one_body_hamiltonian(config, lattice, time=0.0)
    eigenvalues, eigenvectors = np.linalg.eigh(h0)
    occupation = occupation_numbers(
        eigenvalues=eigenvalues,
        particle_target=config.initial_state.filling * lattice.site_count,
        temperature=config.initial_state.temperature,
    )
    weighted_vectors = eigenvectors * occupation[np.newaxis, :]
    density_matrix = weighted_vectors @ eigenvectors.conjugate().T
    return 0.5 * (density_matrix + density_matrix.conjugate().T)


def _propagate_density_matrix(
    density_matrix: NDArray[np.complex128],
    h_mid: NDArray[np.complex128],
    dt: float,
) -> NDArray[np.complex128]:
    eigenvalues, eigenvectors = np.linalg.eigh(h_mid)
    phase = np.exp(-1j * eigenvalues * dt)
    propagator = eigenvectors @ np.diag(phase) @ eigenvectors.conjugate().T
    propagated = propagator @ density_matrix @ propagator.conjugate().T
    return 0.5 * (propagated + propagated.conjugate().T)


def _saved_step_indices(config: SimulationConfig) -> NDArray[np.int64]:
    indices = np.arange(0, config.time.n_steps + 1, config.time.save_every, dtype=np.int64)
    if indices[-1] != config.time.n_steps:
        indices = np.append(indices, config.time.n_steps)
    return indices


def _expectation_value(
    operator: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> float:
    return float(np.real(np.trace(density_matrix @ operator)))


def solve(config: SimulationConfig) -> SimulationArtifacts:
    lattice = build_square_lattice(config.lattice)
    times = np.asarray(config.time.time_points(), dtype=np.float64)
    saved_indices = _saved_step_indices(config)
    density_matrix = _initial_density_matrix(config, lattice)
    particle_target = config.initial_state.filling * lattice.site_count

    density_mean: list[float] = []
    density_min: list[float] = []
    density_max: list[float] = []
    current_x: list[float] = []
    current_y: list[float] = []
    energy: list[float] = []
    vector_ax: list[float] = []
    vector_ay: list[float] = []
    hermiticity_error: list[float] = []
    particle_trace: list[float] = []
    external_power: list[float] = []

    for index, time in enumerate(times):
        hamiltonian = build_one_body_hamiltonian(config, lattice, time)
        mean_density, min_density, max_density = particle_density_statistics(density_matrix)
        density_mean.append(mean_density)
        density_min.append(min_density)
        density_max.append(max_density)
        current_x.append(average_current(lattice.bonds_x, hamiltonian, density_matrix))
        current_y.append(average_current(lattice.bonds_y, hamiltonian, density_matrix))
        energy.append(total_energy(hamiltonian, density_matrix))
        ax, ay = vector_potential(config.drive, time)
        vector_ax.append(ax)
        vector_ay.append(ay)
        hermiticity_error.append(float(np.max(np.abs(density_matrix - density_matrix.conjugate().T))))
        particle_trace.append(float(np.real(np.trace(density_matrix))))
        external_power.append(_expectation_value(build_one_body_hamiltonian_derivative(config, lattice, time), density_matrix))

        if index == len(times) - 1:
            continue

        midpoint = time + 0.5 * config.time.dt
        h_mid = build_one_body_hamiltonian(config, lattice, midpoint)
        density_matrix = _propagate_density_matrix(density_matrix, h_mid, config.time.dt)

    saved_times = times[saved_indices]
    density_mean_array = np.asarray(density_mean, dtype=np.float64)
    density_min_array = np.asarray(density_min, dtype=np.float64)
    density_max_array = np.asarray(density_max, dtype=np.float64)
    current_x_array = np.asarray(current_x, dtype=np.float64)
    current_y_array = np.asarray(current_y, dtype=np.float64)
    energy_array = np.asarray(energy, dtype=np.float64)
    vector_ax_array = np.asarray(vector_ax, dtype=np.float64)
    vector_ay_array = np.asarray(vector_ay, dtype=np.float64)
    hermiticity_error_array = np.asarray(hermiticity_error, dtype=np.float64)
    particle_trace_array = np.asarray(particle_trace, dtype=np.float64)
    external_power_array = np.asarray(external_power, dtype=np.float64)
    cumulative_external_work = cumulative_trapezoid(external_power_array, times)
    energy_change = energy_array - energy_array[0]
    energy_work_mismatch = energy_change - cumulative_external_work

    observables = {
        "density": ObservableData(
            name="density",
            time=saved_times,
            series=[
                SeriesData(label="mean", values=density_mean_array[saved_indices]),
                SeriesData(label="min", values=density_min_array[saved_indices]),
                SeriesData(label="max", values=density_max_array[saved_indices]),
            ],
            metadata={"solver": config.solver.value},
        ),
        "current_x": ObservableData(
            name="current_x",
            time=saved_times,
            series=[SeriesData(label="total", values=current_x_array[saved_indices])],
            metadata={"solver": config.solver.value},
        ),
        "current_y": ObservableData(
            name="current_y",
            time=saved_times,
            series=[SeriesData(label="total", values=current_y_array[saved_indices])],
            metadata={"solver": config.solver.value},
        ),
        "energy": ObservableData(
            name="energy",
            time=saved_times,
            series=[SeriesData(label="total", values=energy_array[saved_indices])],
            metadata={"solver": config.solver.value},
        ),
        "vector_potential": ObservableData(
            name="vector_potential",
            time=saved_times,
            series=[
                SeriesData(label="ax", values=vector_ax_array[saved_indices]),
                SeriesData(label="ay", values=vector_ay_array[saved_indices]),
            ],
            metadata={"solver": config.solver.value},
        ),
        "pairing": _zero_pairing_observable("pairing", saved_times, config.solver.value),
        "pairing_s": _zero_pairing_observable("pairing_s", saved_times, config.solver.value),
        "pairing_d": _zero_pairing_observable("pairing_d", saved_times, config.solver.value),
    }

    filtered_observables = {name: observables[name] for name in config.observables}
    diagnostics = {
        "site_count": lattice.site_count,
        "time_steps": config.time.n_steps,
        "saved_samples": int(len(saved_indices)),
        "particle_target": particle_target,
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_target))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_hermiticity_error": float(np.max(hermiticity_error_array)),
        "net_external_work": float(cumulative_external_work[-1]),
        "max_energy_work_mismatch": float(np.max(np.abs(energy_work_mismatch))),
        "final_energy_work_mismatch": float(abs(energy_work_mismatch[-1])),
    }
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean_array[-1]),
        "particle_number_drift": diagnostics["particle_number_drift"],
        "energy_drift": diagnostics["energy_drift"],
        "max_energy_work_mismatch": diagnostics["max_energy_work_mismatch"],
    }
    return SimulationArtifacts(
        observables=filtered_observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
    )


def _zero_pairing_observable(name: str, times: NDArray[np.float64], solver_name: str) -> ObservableData:
    zeros = np.zeros_like(times)
    return ObservableData(
        name=name,
        time=times,
        series=[
            SeriesData(label="real", values=zeros.copy()),
            SeriesData(label="imag", values=zeros.copy()),
            SeriesData(label="magnitude", values=zeros.copy()),
        ],
        metadata={"solver": solver_name, "pairing_channel": "none"},
    )
