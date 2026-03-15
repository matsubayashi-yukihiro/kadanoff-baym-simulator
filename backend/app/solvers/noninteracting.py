from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.base import ObservableData, SeriesData, SimulationArtifacts
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian, vector_potential
from backend.app.solvers.lattice import SquareLattice, build_square_lattice
from backend.app.solvers.observables import average_current, particle_density_statistics, total_energy


def _fermi_dirac(eigenvalues: NDArray[np.float64], mu: float, temperature: float) -> NDArray[np.float64]:
    argument = np.clip((eigenvalues - mu) / temperature, -100.0, 100.0)
    return 1.0 / (np.exp(argument) + 1.0)


def _occupation_numbers(
    eigenvalues: NDArray[np.float64],
    particle_target: float,
    temperature: float,
) -> NDArray[np.float64]:
    orbital_count = len(eigenvalues)
    particle_target = min(max(particle_target, 0.0), float(orbital_count))
    if temperature <= 1e-12:
        occupation = np.zeros(orbital_count, dtype=np.float64)
        lower = int(np.floor(particle_target))
        occupation[:lower] = 1.0
        if lower < orbital_count:
            occupation[lower] = particle_target - lower
        return occupation

    lower_mu = float(eigenvalues.min() - 50.0 * temperature - 1.0)
    upper_mu = float(eigenvalues.max() + 50.0 * temperature + 1.0)
    for _ in range(200):
        mid_mu = 0.5 * (lower_mu + upper_mu)
        occupation = _fermi_dirac(eigenvalues, mid_mu, temperature)
        if occupation.sum() > particle_target:
            upper_mu = mid_mu
        else:
            lower_mu = mid_mu
    return _fermi_dirac(eigenvalues, 0.5 * (lower_mu + upper_mu), temperature)


def _initial_density_matrix(
    config: SimulationConfig,
    lattice: SquareLattice,
) -> NDArray[np.complex128]:
    h0 = build_one_body_hamiltonian(config, lattice, time=0.0)
    eigenvalues, eigenvectors = np.linalg.eigh(h0)
    occupation = _occupation_numbers(
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


def solve(config: SimulationConfig) -> SimulationArtifacts:
    lattice = build_square_lattice(config.lattice)
    times = np.asarray(config.time.time_points(), dtype=np.float64)
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

        if index == len(times) - 1:
            continue

        midpoint = time + 0.5 * config.time.dt
        h_mid = build_one_body_hamiltonian(config, lattice, midpoint)
        density_matrix = _propagate_density_matrix(density_matrix, h_mid, config.time.dt)

    observables = {
        "density": ObservableData(
            name="density",
            time=times,
            series=[
                SeriesData(label="mean", values=np.asarray(density_mean, dtype=np.float64)),
                SeriesData(label="min", values=np.asarray(density_min, dtype=np.float64)),
                SeriesData(label="max", values=np.asarray(density_max, dtype=np.float64)),
            ],
            metadata={"solver": config.solver.value},
        ),
        "current_x": ObservableData(
            name="current_x",
            time=times,
            series=[SeriesData(label="total", values=np.asarray(current_x, dtype=np.float64))],
            metadata={"solver": config.solver.value},
        ),
        "current_y": ObservableData(
            name="current_y",
            time=times,
            series=[SeriesData(label="total", values=np.asarray(current_y, dtype=np.float64))],
            metadata={"solver": config.solver.value},
        ),
        "energy": ObservableData(
            name="energy",
            time=times,
            series=[SeriesData(label="total", values=np.asarray(energy, dtype=np.float64))],
            metadata={"solver": config.solver.value},
        ),
        "vector_potential": ObservableData(
            name="vector_potential",
            time=times,
            series=[
                SeriesData(label="ax", values=np.asarray(vector_ax, dtype=np.float64)),
                SeriesData(label="ay", values=np.asarray(vector_ay, dtype=np.float64)),
            ],
            metadata={"solver": config.solver.value},
        ),
    }

    filtered_observables = {name: observables[name] for name in config.observables}
    energy_array = np.asarray(energy, dtype=np.float64)
    particle_trace_array = np.asarray(particle_trace, dtype=np.float64)
    diagnostics = {
        "site_count": lattice.site_count,
        "time_steps": config.time.n_steps,
        "particle_target": particle_target,
        "particle_number_drift": float(np.max(np.abs(particle_trace_array - particle_target))),
        "energy_drift": float(np.max(np.abs(energy_array - energy_array[0]))),
        "max_hermiticity_error": float(np.max(np.asarray(hermiticity_error, dtype=np.float64))),
    }
    summary_excerpt = {
        "final_energy": float(energy_array[-1]),
        "final_density": float(density_mean[-1]),
        "particle_number_drift": diagnostics["particle_number_drift"],
        "energy_drift": diagnostics["energy_drift"],
    }
    return SimulationArtifacts(
        observables=filtered_observables,
        diagnostics=diagnostics,
        summary_excerpt=summary_excerpt,
    )
