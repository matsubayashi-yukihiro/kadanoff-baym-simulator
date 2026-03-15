from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.lattice import Bond


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


def total_energy(
    hamiltonian: NDArray[np.complex128],
    density_matrix: NDArray[np.complex128],
) -> float:
    return float(np.real(np.trace(density_matrix @ hamiltonian)))
