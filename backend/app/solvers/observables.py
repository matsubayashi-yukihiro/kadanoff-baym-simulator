from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.lattice import Bond, SquareLattice


def particle_density_statistics(density_matrix: NDArray[np.complex128]) -> tuple[float, float, float]:
    density = np.real(np.diag(density_matrix))
    return float(density.mean()), float(density.min()), float(density.max())


def bond_current(
    bond: Bond,
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> float:
    return float(-2.0 * np.imag(hamiltonian[bond.source, bond.target] * density_matrix[bond.target, bond.source]))


def average_current(
    bonds: Iterable[Bond],
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> float:
    bond_values = [bond_current(bond, hamiltonian, density_matrix) for bond in bonds]
    if not bond_values:
        return 0.0
    return float(np.mean(np.asarray(bond_values, dtype=np.float64)))


def site_current_divergence(
    lattice: SquareLattice,
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> NDArray[np.float64]:
    divergence = np.zeros(lattice.site_count, dtype=np.float64)
    for bond in lattice.bonds:
        current = bond_current(bond, hamiltonian, density_matrix)
        divergence[bond.source] += current
        divergence[bond.target] -= current
    return divergence


def site_density_time_derivative(
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> NDArray[np.float64]:
    commutator = hamiltonian @ density_matrix - density_matrix @ hamiltonian
    return np.real(-1j * np.diag(commutator)).astype(np.float64, copy=False)


def total_energy(
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> float:
    return float(np.real(np.trace(density_matrix @ hamiltonian)))
