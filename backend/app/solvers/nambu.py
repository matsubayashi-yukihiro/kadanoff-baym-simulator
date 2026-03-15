from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import PairingChannel, SimulationConfig
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian
from backend.app.solvers.lattice import Bond, SquareLattice


ComplexMatrix = NDArray[np.complex128]
FloatVector = NDArray[np.float64]


@dataclass(slots=True)
class PairingProjections:
    primary: complex
    s_wave: complex
    d_wave: complex
    onsite: complex
    bond_x: complex
    bond_y: complex


@dataclass(slots=True)
class HFBEquilibriumState:
    generalized_density: ComplexMatrix
    normal_hamiltonian: ComplexMatrix
    pairing_field: ComplexMatrix
    hartree_potential: FloatVector
    effective_chemical_potential: float
    iterations: int
    converged: bool
    self_consistency_error: float
    stationarity_residual: float


def saved_step_indices(config: SimulationConfig) -> NDArray[np.int64]:
    indices = np.arange(0, config.time.n_steps + 1, config.time.save_every, dtype=np.int64)
    if indices[-1] != config.time.n_steps:
        indices = np.append(indices, config.time.n_steps)
    return indices


def extract_density_blocks(generalized_density: ComplexMatrix, site_count: int) -> tuple[ComplexMatrix, ComplexMatrix]:
    normal_density = generalized_density[:site_count, :site_count]
    pairing_tensor = generalized_density[:site_count, site_count:]
    return normal_density, pairing_tensor


def thermal_generalized_density(bdg_hamiltonian: ComplexMatrix, temperature: float) -> ComplexMatrix:
    eigenvalues, eigenvectors = np.linalg.eigh(bdg_hamiltonian)
    if temperature <= 1e-12:
        occupation = np.zeros_like(eigenvalues, dtype=np.float64)
        occupation[eigenvalues < -1e-10] = 1.0
        occupation[np.abs(eigenvalues) <= 1e-10] = 0.5
    else:
        argument = np.clip(eigenvalues / temperature, -100.0, 100.0)
        occupation = 1.0 / (np.exp(argument) + 1.0)
    weighted_vectors = eigenvectors * occupation[np.newaxis, :]
    generalized_density = weighted_vectors @ eigenvectors.conjugate().T
    return 0.5 * (generalized_density + generalized_density.conjugate().T)


def propagator_from_hamiltonian(hamiltonian: ComplexMatrix, dt: float) -> ComplexMatrix:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    phase = np.exp(-1j * eigenvalues * dt)
    return eigenvectors @ np.diag(phase) @ eigenvectors.conjugate().T


def propagate_generalized_density(
    generalized_density: ComplexMatrix,
    bdg_hamiltonian: ComplexMatrix,
    dt: float,
) -> tuple[ComplexMatrix, ComplexMatrix]:
    propagator = propagator_from_hamiltonian(bdg_hamiltonian, dt)
    propagated = propagator @ generalized_density @ propagator.conjugate().T
    return 0.5 * (propagated + propagated.conjugate().T), propagator


def pairing_channel(config: SimulationConfig) -> PairingChannel:
    return config.interaction.pairing_channel


def build_seed_pairing_tensor(config: SimulationConfig, lattice: SquareLattice) -> ComplexMatrix:
    site_count = lattice.site_count
    channel = pairing_channel(config)
    if channel == PairingChannel.NONE:
        return np.zeros((site_count, site_count), dtype=np.complex128)

    seed_value = config.initial_state.seed_pairing
    if abs(seed_value) <= 1e-12:
        seed_value = 1e-6

    pairing_seed = np.zeros((site_count, site_count), dtype=np.complex128)
    if channel == PairingChannel.ONSITE:
        np.fill_diagonal(pairing_seed, seed_value)
        return pairing_seed

    for bond in lattice.bonds:
        sign = 1.0
        if channel == PairingChannel.BOND_D and bond.direction == "y":
            sign = -1.0
        pairing_seed[bond.source, bond.target] = sign * seed_value
        pairing_seed[bond.target, bond.source] = sign * seed_value
    return pairing_seed


def build_effective_normal_hamiltonian(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
    hartree_potential: FloatVector,
    effective_chemical_potential: float,
) -> ComplexMatrix:
    one_body = build_one_body_hamiltonian(config, lattice, time)
    one_body -= effective_chemical_potential * np.eye(lattice.site_count, dtype=np.complex128)
    return one_body + np.diag(hartree_potential.astype(np.complex128))


def compute_hartree_potential(
    config: SimulationConfig,
    lattice: SquareLattice,
    normal_density: ComplexMatrix,
) -> FloatVector:
    density = np.real(np.diag(normal_density)).astype(np.float64, copy=False)
    hartree = config.interaction.onsite_u * density

    if abs(config.interaction.nearest_neighbor_v) <= 1e-12:
        return hartree.astype(np.float64)

    nearest_neighbor = config.interaction.nearest_neighbor_v
    for bond in lattice.bonds:
        hartree[bond.source] += nearest_neighbor * density[bond.target]
        hartree[bond.target] += nearest_neighbor * density[bond.source]
    return hartree.astype(np.float64)


def compute_pairing_field(
    config: SimulationConfig,
    lattice: SquareLattice,
    pairing_tensor: ComplexMatrix,
) -> ComplexMatrix:
    site_count = lattice.site_count
    channel = pairing_channel(config)
    pairing_field = np.zeros((site_count, site_count), dtype=np.complex128)

    if channel == PairingChannel.NONE:
        return pairing_field

    pairing_field += build_seed_pairing_tensor(config, lattice)

    if channel == PairingChannel.ONSITE:
        if abs(config.interaction.onsite_u) <= 1e-12:
            return pairing_field
        onsite_pairing = -config.interaction.onsite_u * np.diag(pairing_tensor)
        diagonal = np.diag_indices(site_count)
        pairing_field[diagonal] += onsite_pairing
        return pairing_field

    if abs(config.interaction.nearest_neighbor_v) <= 1e-12:
        return pairing_field

    nearest_neighbor = config.interaction.nearest_neighbor_v
    for bond in lattice.bonds:
        amplitude = 0.5 * (pairing_tensor[bond.source, bond.target] + pairing_tensor[bond.target, bond.source])
        pairing_field[bond.source, bond.target] += -nearest_neighbor * amplitude
        pairing_field[bond.target, bond.source] += -nearest_neighbor * amplitude
    return pairing_field


def assemble_bdg_hamiltonian(normal_hamiltonian: ComplexMatrix, pairing_field: ComplexMatrix) -> ComplexMatrix:
    return np.block(
        [
            [normal_hamiltonian, pairing_field],
            [pairing_field.conjugate().T, -normal_hamiltonian.conjugate()],
        ]
    )


def build_bdg_hamiltonian(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
    generalized_density: ComplexMatrix,
    effective_chemical_potential: float,
) -> tuple[ComplexMatrix, ComplexMatrix, FloatVector, ComplexMatrix]:
    normal_density, pairing_tensor = extract_density_blocks(generalized_density, lattice.site_count)
    hartree_potential = compute_hartree_potential(config, lattice, normal_density)
    normal_hamiltonian = build_effective_normal_hamiltonian(
        config,
        lattice,
        time,
        hartree_potential,
        effective_chemical_potential,
    )
    pairing_field = compute_pairing_field(config, lattice, pairing_tensor)
    return normal_hamiltonian, pairing_field, hartree_potential, assemble_bdg_hamiltonian(normal_hamiltonian, pairing_field)


def pairing_projections(config: SimulationConfig, lattice: SquareLattice, pairing_field: ComplexMatrix) -> PairingProjections:
    onsite = complex(np.mean(np.diag(pairing_field))) if lattice.site_count else 0.0j
    bond_x = _bond_average(lattice.bonds_x, pairing_field)
    bond_y = _bond_average(lattice.bonds_y, pairing_field)
    s_wave = onsite if pairing_channel(config) == PairingChannel.ONSITE else 0.5 * (bond_x + bond_y)
    d_wave = 0.0j if pairing_channel(config) == PairingChannel.ONSITE else 0.5 * (bond_x - bond_y)

    if pairing_channel(config) == PairingChannel.ONSITE:
        primary = onsite
    elif pairing_channel(config) == PairingChannel.BOND_D:
        primary = d_wave
    else:
        primary = s_wave

    return PairingProjections(
        primary=primary,
        s_wave=s_wave,
        d_wave=d_wave,
        onsite=onsite,
        bond_x=bond_x,
        bond_y=bond_y,
    )


def effective_energy(generalized_density: ComplexMatrix, bdg_hamiltonian: ComplexMatrix) -> float:
    return float(0.5 * np.real(np.trace(generalized_density @ bdg_hamiltonian)))


def solve_hfb_equilibrium(config: SimulationConfig, lattice: SquareLattice) -> HFBEquilibriumState:
    site_count = lattice.site_count
    particle_target = config.initial_state.filling * site_count
    normal_density = _initial_normal_density(config, lattice)
    pairing_tensor = build_seed_pairing_tensor(config, lattice)
    generalized_density = _assemble_generalized_density(normal_density, pairing_tensor)

    effective_chemical_potential = 0.0
    self_consistency_error = float("inf")
    converged = False
    normal_hamiltonian = np.zeros((site_count, site_count), dtype=np.complex128)
    pairing_field = np.zeros((site_count, site_count), dtype=np.complex128)
    hartree_potential = np.zeros(site_count, dtype=np.float64)
    max_iterations = 192
    mixing = 0.22

    for iteration in range(1, max_iterations + 1):
        effective_chemical_potential, next_density = _solve_thermal_state_for_particle_target(
            config=config,
            lattice=lattice,
            generalized_density=generalized_density,
            particle_target=particle_target,
        )

        self_consistency_error = float(np.max(np.abs(next_density - generalized_density)))
        mixed_density = mixing * next_density + (1.0 - mixing) * generalized_density
        mixed_density = 0.5 * (mixed_density + mixed_density.conjugate().T)
        generalized_density = mixed_density
        if self_consistency_error < 1e-8:
            converged = True
            break

    effective_chemical_potential, generalized_density = _solve_thermal_state_for_particle_target(
        config=config,
        lattice=lattice,
        generalized_density=generalized_density,
        particle_target=particle_target,
    )

    normal_hamiltonian, pairing_field, hartree_potential, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time=0.0,
        generalized_density=generalized_density,
        effective_chemical_potential=effective_chemical_potential,
    )
    stationarity_residual = float(
        np.max(np.abs(bdg_hamiltonian @ generalized_density - generalized_density @ bdg_hamiltonian))
    )
    return HFBEquilibriumState(
        generalized_density=generalized_density,
        normal_hamiltonian=normal_hamiltonian,
        pairing_field=pairing_field,
        hartree_potential=hartree_potential,
        effective_chemical_potential=effective_chemical_potential,
        iterations=iteration,
        converged=converged,
        self_consistency_error=self_consistency_error,
        stationarity_residual=stationarity_residual,
    )


def _solve_thermal_state_for_particle_target(
    *,
    config: SimulationConfig,
    lattice: SquareLattice,
    generalized_density: ComplexMatrix,
    particle_target: float,
) -> tuple[float, ComplexMatrix]:
    target = min(max(particle_target, 0.0), float(lattice.site_count))
    search_span = max(
        2.0,
        8.0 * config.lattice.hopping + 4.0 * abs(config.interaction.onsite_u) + 8.0 * abs(config.interaction.nearest_neighbor_v),
    )
    lower_shift = -search_span
    upper_shift = search_span
    lower_state = _thermal_state_for_shift(config, lattice, generalized_density, lower_shift)
    upper_state = _thermal_state_for_shift(config, lattice, generalized_density, upper_shift)

    for _ in range(18):
        if lower_state[1] <= target <= upper_state[1]:
            break
        search_span *= 2.0
        lower_shift = -search_span
        upper_shift = search_span
        lower_state = _thermal_state_for_shift(config, lattice, generalized_density, lower_shift)
        upper_state = _thermal_state_for_shift(config, lattice, generalized_density, upper_shift)

    if target <= lower_state[1]:
        return lower_state[0], lower_state[2]
    if target >= upper_state[1]:
        return upper_state[0], upper_state[2]

    chosen_state = upper_state
    for _ in range(80):
        mid_shift = 0.5 * (lower_shift + upper_shift)
        mid_state = _thermal_state_for_shift(config, lattice, generalized_density, mid_shift)
        chosen_state = mid_state
        if abs(mid_state[1] - target) < 1e-9:
            break
        if mid_state[1] < target:
            lower_shift = mid_shift
            lower_state = mid_state
        else:
            upper_shift = mid_shift
            upper_state = mid_state
    return chosen_state[0], chosen_state[2]


def _thermal_state_for_shift(
    config: SimulationConfig,
    lattice: SquareLattice,
    generalized_density: ComplexMatrix,
    effective_chemical_potential: float,
) -> tuple[float, float, ComplexMatrix]:
    _, _, _, bdg_hamiltonian = build_bdg_hamiltonian(
        config,
        lattice,
        time=0.0,
        generalized_density=generalized_density,
        effective_chemical_potential=effective_chemical_potential,
    )
    candidate_density = thermal_generalized_density(bdg_hamiltonian, config.initial_state.temperature)
    normal_density, _ = extract_density_blocks(candidate_density, lattice.site_count)
    particle_number = float(np.real(np.trace(normal_density)))
    return (
        effective_chemical_potential,
        particle_number,
        candidate_density,
    )


def _assemble_generalized_density(normal_density: ComplexMatrix, pairing_tensor: ComplexMatrix) -> ComplexMatrix:
    site_count = normal_density.shape[0]
    return np.block(
        [
            [normal_density, pairing_tensor],
            [pairing_tensor.conjugate().T, np.eye(site_count, dtype=np.complex128) - normal_density.conjugate()],
        ]
    )


def _initial_normal_density(config: SimulationConfig, lattice: SquareLattice) -> ComplexMatrix:
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


def _fermi_dirac(eigenvalues: NDArray[np.float64], mu: float, temperature: float) -> NDArray[np.float64]:
    argument = np.clip((eigenvalues - mu) / temperature, -100.0, 100.0)
    return 1.0 / (np.exp(argument) + 1.0)


def _bond_average(bonds: tuple[Bond, ...], matrix: ComplexMatrix) -> complex:
    if not bonds:
        return 0.0j
    return complex(
        np.mean(
            np.asarray([matrix[bond.source, bond.target] for bond in bonds], dtype=np.complex128)
        )
    )
