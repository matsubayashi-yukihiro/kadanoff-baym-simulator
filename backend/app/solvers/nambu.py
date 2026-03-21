from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import PairingChannel, SimulationConfig, SolverRepresentation
from backend.app.solvers.equilibrium import occupation_numbers
from backend.app.solvers.fixed_point import AndersonMixer
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian
from backend.app.solvers.lattice import Bond, SquareLattice
from backend.app.solvers.numerics import solve_bracketed_root
from backend.app.solvers.representation import (
    MomentumSpaceContext,
    build_momentum_space_context,
    extract_k_blocks_from_generalized_density,
)


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
    momentum_density_blocks: NDArray[np.complex128] | None = None
    momentum_context: MomentumSpaceContext | None = None
    momentum_generalized_density: ComplexMatrix | None = None
    method: str = "hfb"
    requested_method: str = "auto"
    matches_runtime_approximation: bool = True
    mismatch_allowed: bool = False
    density_update_residual: float = 0.0
    solver_mode: str = "hfb"


def saved_step_indices(config: SimulationConfig) -> NDArray[np.int64]:
    return saved_step_indices_from_count(config.time.n_steps + 1, config.time.save_every)


def saved_step_indices_from_count(sample_count: int, save_every: int) -> NDArray[np.int64]:
    indices = np.arange(0, sample_count, save_every, dtype=np.int64)
    if len(indices) == 0 or indices[-1] != sample_count - 1:
        indices = np.append(indices, sample_count - 1)
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
    if config.representation == SolverRepresentation.K_SPACE:
        return _solve_hfb_equilibrium_kspace(config, lattice)
    return _solve_hfb_equilibrium_real_space(config, lattice)


def _solve_hfb_equilibrium_real_space(config: SimulationConfig, lattice: SquareLattice) -> HFBEquilibriumState:
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
    density_mixer = AndersonMixer(mixing=mixing, max_history=4)

    for iteration in range(1, max_iterations + 1):
        effective_chemical_potential, next_density = _solve_thermal_state_for_particle_target(
            config=config,
            lattice=lattice,
            generalized_density=generalized_density,
            particle_target=particle_target,
        )

        self_consistency_error = float(np.max(np.abs(next_density - generalized_density)))
        mixed_density = density_mixer.update(generalized_density, next_density)
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

    evaluated_states: dict[float, tuple[float, float, ComplexMatrix]] = {}

    def evaluate(shift: float) -> tuple[float, float, ComplexMatrix]:
        if shift not in evaluated_states:
            evaluated_states[shift] = _thermal_state_for_shift(config, lattice, generalized_density, shift)
        return evaluated_states[shift]

    lower_shift = -search_span
    upper_shift = search_span
    lower_state = evaluate(lower_shift)
    upper_state = evaluate(upper_shift)

    for _ in range(18):
        if lower_state[1] <= target <= upper_state[1]:
            break
        search_span *= 2.0
        lower_shift = -search_span
        upper_shift = search_span
        lower_state = evaluate(lower_shift)
        upper_state = evaluate(upper_shift)

    if target <= lower_state[1]:
        return lower_state[0], lower_state[2]
    if target >= upper_state[1]:
        return upper_state[0], upper_state[2]

    chosen_shift = solve_bracketed_root(
        lambda shift: evaluate(shift)[1] - target,
        lower=lower_shift,
        upper=upper_shift,
    )
    chosen_state = evaluate(chosen_shift)
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
    occupation = occupation_numbers(
        eigenvalues=eigenvalues,
        particle_target=config.initial_state.filling * lattice.site_count,
        temperature=config.initial_state.temperature,
    )
    weighted_vectors = eigenvectors * occupation[np.newaxis, :]
    density_matrix = weighted_vectors @ eigenvectors.conjugate().T
    return 0.5 * (density_matrix + density_matrix.conjugate().T)


def _bond_average(bonds: tuple[Bond, ...], matrix: ComplexMatrix) -> complex:
    if not bonds:
        return 0.0j
    return complex(
        np.mean(
            np.asarray([matrix[bond.source, bond.target] for bond in bonds], dtype=np.complex128)
        )
    )


def _solve_hfb_equilibrium_kspace(config: SimulationConfig, lattice: SquareLattice) -> HFBEquilibriumState:
    real_space_config = SimulationConfig.model_validate(
        {
            **config.model_dump(mode="json"),
            "representation": SolverRepresentation.REAL_SPACE.value,
        }
    )
    equilibrium = _solve_hfb_equilibrium_real_space(real_space_config, lattice)
    context = build_momentum_space_context(config)
    density_blocks = extract_k_blocks_from_generalized_density(context, equilibrium.generalized_density)
    momentum_generalized_density = context.nambu_site_to_momentum @ equilibrium.generalized_density @ context.nambu_momentum_to_site
    return HFBEquilibriumState(
        generalized_density=equilibrium.generalized_density,
        normal_hamiltonian=equilibrium.normal_hamiltonian,
        pairing_field=equilibrium.pairing_field,
        hartree_potential=equilibrium.hartree_potential,
        effective_chemical_potential=equilibrium.effective_chemical_potential,
        iterations=equilibrium.iterations,
        converged=equilibrium.converged,
        self_consistency_error=equilibrium.self_consistency_error,
        stationarity_residual=equilibrium.stationarity_residual,
        momentum_density_blocks=density_blocks,
        momentum_context=context,
        momentum_generalized_density=momentum_generalized_density,
    )


def _initial_kspace_pairing_diagonal(
    config: SimulationConfig,
    context: MomentumSpaceContext,
) -> NDArray[np.complex128]:
    channel = pairing_channel(config)
    if channel == PairingChannel.NONE:
        return np.zeros(context.site_count, dtype=np.complex128)
    seed_value = config.initial_state.seed_pairing
    if abs(seed_value) <= 1e-12:
        seed_value = 1e-6
    if channel == PairingChannel.ONSITE:
        return np.full(context.site_count, seed_value, dtype=np.complex128)
    if channel == PairingChannel.BOND_D:
        return 2.0 * seed_value * (context.cos_kx - context.cos_ky)
    return 2.0 * seed_value * (context.cos_kx + context.cos_ky)


def _solve_kspace_thermal_state_for_particle_target(
    *,
    config: SimulationConfig,
    context: MomentumSpaceContext,
    density_blocks: NDArray[np.complex128],
    particle_target: float,
) -> tuple[float, NDArray[np.complex128]]:
    target = min(max(particle_target, 0.0), float(context.site_count))
    search_span = max(
        2.0,
        8.0 * config.lattice.hopping + 4.0 * abs(config.interaction.onsite_u) + 8.0 * abs(config.interaction.nearest_neighbor_v),
    )
    evaluated_states: dict[float, tuple[float, float, NDArray[np.complex128]]] = {}

    def evaluate(shift: float) -> tuple[float, float, NDArray[np.complex128]]:
        if shift not in evaluated_states:
            evaluated_states[shift] = _kspace_thermal_state_for_shift(config, context, density_blocks, shift)
        return evaluated_states[shift]

    lower_shift = -search_span
    upper_shift = search_span
    lower_state = evaluate(lower_shift)
    upper_state = evaluate(upper_shift)
    for _ in range(18):
        if lower_state[1] <= target <= upper_state[1]:
            break
        search_span *= 2.0
        lower_shift = -search_span
        upper_shift = search_span
        lower_state = evaluate(lower_shift)
        upper_state = evaluate(upper_shift)

    if target <= lower_state[1]:
        return lower_state[0], lower_state[2]
    if target >= upper_state[1]:
        return upper_state[0], upper_state[2]

    chosen_shift = solve_bracketed_root(
        lambda shift: evaluate(shift)[1] - target,
        lower=lower_shift,
        upper=upper_shift,
    )
    chosen_state = evaluate(chosen_shift)
    return chosen_state[0], chosen_state[2]


def _kspace_thermal_state_for_shift(
    config: SimulationConfig,
    context: MomentumSpaceContext,
    density_blocks: NDArray[np.complex128],
    effective_chemical_potential: float,
) -> tuple[float, float, NDArray[np.complex128]]:
    _, _, _, bdg_blocks = _build_kspace_bdg_blocks(
        config=config,
        context=context,
        density_blocks=density_blocks,
        effective_chemical_potential=effective_chemical_potential,
        time=0.0,
    )
    candidate_density = thermal_generalized_density(
        nambu_from_k_blocks(context, bdg_blocks),
        config.initial_state.temperature,
    )
    candidate_density_blocks = extract_k_blocks_from_k_nambu_matrix(candidate_density)
    particle_number = float(np.real(np.sum(candidate_density_blocks[:, 0, 0])))
    return effective_chemical_potential, particle_number, candidate_density_blocks


def _build_kspace_bdg_blocks(
    *,
    config: SimulationConfig,
    context: MomentumSpaceContext,
    density_blocks: NDArray[np.complex128],
    effective_chemical_potential: float,
    time: float,
) -> tuple[NDArray[np.float64], NDArray[np.complex128], float, NDArray[np.complex128]]:
    normal_diagonal = build_one_body_momentum_diagonal(config, kx=context.kx, ky=context.ky, time=time).astype(np.float64)
    density_mean = float(np.mean(np.real(density_blocks[:, 0, 0])))
    hartree_scalar = density_mean * (
        config.interaction.onsite_u + 4.0 * config.interaction.nearest_neighbor_v
    )
    normal_diagonal = normal_diagonal - effective_chemical_potential + hartree_scalar

    pairing_diagonal = np.zeros(context.site_count, dtype=np.complex128)
    channel = pairing_channel(config)
    if channel != PairingChannel.NONE:
        seed_value = config.initial_state.seed_pairing
        if abs(seed_value) <= 1e-12:
            seed_value = 1e-6
        anomalous = density_blocks[:, 0, 1]
        if channel == PairingChannel.ONSITE:
            pairing_diagonal = np.full(context.site_count, seed_value, dtype=np.complex128)
            if abs(config.interaction.onsite_u) > 1e-12:
                pairing_diagonal = pairing_diagonal - config.interaction.onsite_u * np.mean(anomalous)
        else:
            seed_x = seed_value
            seed_y = -seed_value if channel == PairingChannel.BOND_D else seed_value
            if abs(config.interaction.nearest_neighbor_v) <= 1e-12:
                delta_x = complex(seed_x)
                delta_y = complex(seed_y)
            else:
                delta_x = complex(seed_x - config.interaction.nearest_neighbor_v * np.mean(anomalous * context.cos_kx))
                delta_y = complex(seed_y - config.interaction.nearest_neighbor_v * np.mean(anomalous * context.cos_ky))
            pairing_diagonal = 2.0 * delta_x * context.cos_kx + 2.0 * delta_y * context.cos_ky

    bdg_blocks = np.zeros((context.site_count, 2, 2), dtype=np.complex128)
    bdg_blocks[:, 0, 0] = normal_diagonal.astype(np.complex128)
    bdg_blocks[:, 0, 1] = pairing_diagonal
    bdg_blocks[:, 1, 0] = pairing_diagonal.conjugate()
    bdg_blocks[:, 1, 1] = -normal_diagonal.astype(np.complex128)
    return normal_diagonal, pairing_diagonal, hartree_scalar, bdg_blocks
