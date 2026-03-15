from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import DriveConfig, SimulationConfig
from backend.app.solvers.lattice import SquareLattice


def vector_potential(drive: DriveConfig, time: float) -> tuple[float, float]:
    if drive.amplitude_x == 0.0 and drive.amplitude_y == 0.0:
        return 0.0, 0.0
    shifted_time = time - drive.center
    envelope = math.exp(-0.5 * (shifted_time / drive.width) ** 2)
    carrier = math.sin(drive.frequency * shifted_time + drive.phase)
    return (
        drive.amplitude_x * envelope * carrier,
        drive.amplitude_y * envelope * carrier,
    )


def build_one_body_hamiltonian(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
) -> NDArray[np.complex128]:
    size = lattice.site_count
    hamiltonian = np.zeros((size, size), dtype=np.complex128)
    np.fill_diagonal(hamiltonian, -config.lattice.chemical_potential)

    ax, ay = vector_potential(config.drive, time)
    for bond in lattice.bonds:
        phase = ax if bond.direction == "x" else ay
        hopping = -config.lattice.hopping * np.exp(-1j * phase)
        hamiltonian[bond.source, bond.target] += hopping
        hamiltonian[bond.target, bond.source] += np.conjugate(hopping)

    return hamiltonian
