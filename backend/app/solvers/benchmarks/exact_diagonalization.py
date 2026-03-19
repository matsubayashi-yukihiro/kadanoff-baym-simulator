from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import SimulationConfig
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian
from backend.app.solvers.lattice import SquareLattice, build_square_lattice
from backend.app.solvers.observables import average_current, particle_density_statistics


ComplexMatrix = NDArray[np.complex128]


@dataclass(slots=True)
class ExactDiagonalizationBenchmarkResult:
    times: NDArray[np.float64]
    density_matrices: list[ComplexMatrix]
    density_mean: NDArray[np.float64]
    density_min: NDArray[np.float64]
    density_max: NDArray[np.float64]
    current_x: NDArray[np.float64]
    current_y: NDArray[np.float64]
    total_energy: NDArray[np.float64]


@dataclass(slots=True)
class _OperatorCache:
    transfer_operators: tuple[tuple[ComplexMatrix, ...], ...]
    interaction_matrix: ComplexMatrix


def run_exact_diagonalization_benchmark(
    config: SimulationConfig,
    *,
    integration_dt: float | None = None,
) -> ExactDiagonalizationBenchmarkResult:
    lattice = build_square_lattice(config.lattice)
    if lattice.site_count > 4:
        raise ValueError("exact diagonalization benchmark currently supports up to four lattice sites")

    particle_number = _physical_particle_number(config, lattice)
    integration_dt = config.time.dt if integration_dt is None else float(integration_dt)
    if integration_dt <= 0.0:
        raise ValueError("integration_dt must be positive")
    substeps = config.time.dt / integration_dt
    if abs(substeps - round(substeps)) > 1e-9:
        raise ValueError("integration_dt must evenly divide config.time.dt")
    substep_count = int(round(substeps))

    cache = _build_operator_cache(config, lattice, particle_number)
    state_density = _initial_state_density(config, lattice, cache)
    sample_times = np.asarray(config.time.time_points(), dtype=np.float64)

    density_matrices: list[ComplexMatrix] = []
    density_mean: list[float] = []
    density_min: list[float] = []
    density_max: list[float] = []
    current_x: list[float] = []
    current_y: list[float] = []
    total_energy: list[float] = []

    _record_observables(
        config=config,
        lattice=lattice,
        cache=cache,
        time=0.0,
        state_density=state_density,
        density_matrices=density_matrices,
        density_mean=density_mean,
        density_min=density_min,
        density_max=density_max,
        current_x=current_x,
        current_y=current_y,
        total_energy=total_energy,
    )

    current_time = 0.0
    for step in range(config.time.n_steps):
        for _ in range(substep_count):
            midpoint = current_time + 0.5 * integration_dt
            midpoint_hamiltonian = _build_many_body_hamiltonian(config, lattice, midpoint, cache)
            state_density = _propagate_density_operator(state_density, midpoint_hamiltonian, integration_dt)
            current_time += integration_dt
        _record_observables(
            config=config,
            lattice=lattice,
            cache=cache,
            time=float(sample_times[step + 1]),
            state_density=state_density,
            density_matrices=density_matrices,
            density_mean=density_mean,
            density_min=density_min,
            density_max=density_max,
            current_x=current_x,
            current_y=current_y,
            total_energy=total_energy,
        )

    return ExactDiagonalizationBenchmarkResult(
        times=sample_times,
        density_matrices=density_matrices,
        density_mean=np.asarray(density_mean, dtype=np.float64),
        density_min=np.asarray(density_min, dtype=np.float64),
        density_max=np.asarray(density_max, dtype=np.float64),
        current_x=np.asarray(current_x, dtype=np.float64),
        current_y=np.asarray(current_y, dtype=np.float64),
        total_energy=np.asarray(total_energy, dtype=np.float64),
    )


def _physical_particle_number(config: SimulationConfig, lattice: SquareLattice) -> int:
    target = 2.0 * config.initial_state.filling * lattice.site_count
    particle_number = int(round(target))
    if abs(target - particle_number) > 1e-9:
        raise ValueError("exact diagonalization benchmark requires an integer total particle number")
    return particle_number


def _build_operator_cache(
    config: SimulationConfig,
    lattice: SquareLattice,
    particle_number: int,
) -> _OperatorCache:
    mode_count = 2 * lattice.site_count
    basis_states = _fixed_particle_basis(mode_count, particle_number)
    basis_index = {state: idx for idx, state in enumerate(basis_states)}
    dimension = len(basis_states)
    transfer_operators = [
        [np.zeros((dimension, dimension), dtype=np.complex128) for _ in range(mode_count)]
        for _ in range(mode_count)
    ]

    for ket_index, state in enumerate(basis_states):
        for annihilator in range(mode_count):
            if ((state >> annihilator) & 1) == 0:
                continue
            intermediate = state ^ (1 << annihilator)
            sign_annihilation = _fermion_sign(state, annihilator)
            for creator in range(mode_count):
                if ((intermediate >> creator) & 1) == 1:
                    continue
                bra_state = intermediate | (1 << creator)
                bra_index = basis_index[bra_state]
                sign_creation = _fermion_sign(intermediate, creator)
                transfer_operators[creator][annihilator][bra_index, ket_index] = sign_creation * sign_annihilation

    interaction_diagonal = np.zeros(dimension, dtype=np.float64)
    if abs(config.interaction.onsite_u) > 1e-12 or abs(config.interaction.nearest_neighbor_v) > 1e-12:
        for basis_index_value, state in enumerate(basis_states):
            onsite_energy = 0.0
            bond_energy = 0.0
            for site in range(lattice.site_count):
                onsite_energy += config.interaction.onsite_u * _occupation(state, site) * _occupation(
                    state, lattice.site_count + site
                )
            if abs(config.interaction.nearest_neighbor_v) > 1e-12:
                for bond in lattice.bonds:
                    source_density = _occupation(state, bond.source) + _occupation(state, lattice.site_count + bond.source)
                    target_density = _occupation(state, bond.target) + _occupation(
                        state, lattice.site_count + bond.target
                    )
                    bond_energy += config.interaction.nearest_neighbor_v * source_density * target_density
            interaction_diagonal[basis_index_value] = onsite_energy + bond_energy

    return _OperatorCache(
        transfer_operators=tuple(tuple(row) for row in transfer_operators),
        interaction_matrix=np.diag(interaction_diagonal.astype(np.complex128)),
    )


def _fixed_particle_basis(mode_count: int, particle_number: int) -> tuple[int, ...]:
    if particle_number < 0 or particle_number > mode_count:
        raise ValueError("particle number must lie within the available spin-orbital count")
    basis_states: list[int] = []
    for occupied_modes in combinations(range(mode_count), particle_number):
        state = 0
        for mode in occupied_modes:
            state |= 1 << mode
        basis_states.append(state)
    return tuple(basis_states)


def _occupation(state: int, mode: int) -> int:
    return (state >> mode) & 1


def _fermion_sign(state: int, mode: int) -> int:
    return -1 if (state & ((1 << mode) - 1)).bit_count() % 2 else 1


def _initial_state_density(
    config: SimulationConfig,
    lattice: SquareLattice,
    cache: _OperatorCache,
) -> ComplexMatrix:
    hamiltonian = _build_many_body_hamiltonian(config, lattice, 0.0, cache)
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)

    if config.initial_state.temperature <= 1e-12:
        ground_energy = float(np.min(eigenvalues))
        tolerance = 1e-10 * max(1.0, abs(ground_energy))
        mask = np.abs(eigenvalues - ground_energy) <= tolerance
        projector = eigenvectors[:, mask] @ eigenvectors[:, mask].conjugate().T
        return projector / float(np.count_nonzero(mask))

    shifted = eigenvalues - float(np.min(eigenvalues))
    weights = np.exp(-shifted / config.initial_state.temperature)
    weighted_vectors = eigenvectors * weights[np.newaxis, :]
    state_density = weighted_vectors @ eigenvectors.conjugate().T
    state_density /= float(np.sum(weights))
    return 0.5 * (state_density + state_density.conjugate().T)


def _build_many_body_hamiltonian(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
    cache: _OperatorCache,
) -> ComplexMatrix:
    site_hamiltonian = build_one_body_hamiltonian(config, lattice, time)
    many_body = cache.interaction_matrix.copy()

    for spin in range(2):
        offset = spin * lattice.site_count
        for row in range(lattice.site_count):
            for column in range(lattice.site_count):
                coefficient = site_hamiltonian[row, column]
                if abs(coefficient) <= 1e-14:
                    continue
                many_body += coefficient * cache.transfer_operators[offset + row][offset + column]

    return many_body


def _propagate_density_operator(
    state_density: ComplexMatrix,
    hamiltonian: ComplexMatrix,
    dt: float,
) -> ComplexMatrix:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    phase = np.exp(-1j * eigenvalues * dt)
    propagator = eigenvectors @ np.diag(phase) @ eigenvectors.conjugate().T
    propagated = propagator @ state_density @ propagator.conjugate().T
    return 0.5 * (propagated + propagated.conjugate().T)


def _record_observables(
    *,
    config: SimulationConfig,
    lattice: SquareLattice,
    cache: _OperatorCache,
    time: float,
    state_density: ComplexMatrix,
    density_matrices: list[ComplexMatrix],
    density_mean: list[float],
    density_min: list[float],
    density_max: list[float],
    current_x: list[float],
    current_y: list[float],
    total_energy: list[float],
) -> None:
    site_hamiltonian = build_one_body_hamiltonian(config, lattice, time)
    one_body_density = _spin_averaged_density_matrix(state_density, lattice, cache)
    density_matrices.append(one_body_density)
    density_statistics = particle_density_statistics(one_body_density)
    density_mean.append(density_statistics[0])
    density_min.append(density_statistics[1])
    density_max.append(density_statistics[2])
    current_x.append(average_current(lattice.bonds_x, site_hamiltonian, one_body_density))
    current_y.append(average_current(lattice.bonds_y, site_hamiltonian, one_body_density))
    total_energy.append(
        _many_body_expectation(
            state_density,
            _build_many_body_hamiltonian(config, lattice, time, cache),
        )
    )


def _spin_averaged_density_matrix(
    state_density: ComplexMatrix,
    lattice: SquareLattice,
    cache: _OperatorCache,
) -> ComplexMatrix:
    site_count = lattice.site_count
    spin_density = np.zeros((2, site_count, site_count), dtype=np.complex128)

    for spin in range(2):
        offset = spin * site_count
        for row in range(site_count):
            for column in range(site_count):
                spin_density[spin, row, column] = _many_body_matrix_element(
                    state_density,
                    cache.transfer_operators[offset + column][offset + row],
                )

    averaged_density = 0.5 * (spin_density[0] + spin_density[1])
    return 0.5 * (averaged_density + averaged_density.conjugate().T)


def _many_body_expectation(
    state_density: ComplexMatrix,
    operator: ComplexMatrix,
) -> float:
    return float(np.real(np.trace(state_density @ operator)))


def _many_body_matrix_element(
    state_density: ComplexMatrix,
    operator: ComplexMatrix,
) -> complex:
    return complex(np.trace(state_density @ operator))
