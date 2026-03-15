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


def vector_potential_derivative(drive: DriveConfig, time: float) -> tuple[float, float]:
    if drive.amplitude_x == 0.0 and drive.amplitude_y == 0.0:
        return 0.0, 0.0
    shifted_time = time - drive.center
    envelope = math.exp(-0.5 * (shifted_time / drive.width) ** 2)
    carrier = math.sin(drive.frequency * shifted_time + drive.phase)
    carrier_derivative = drive.frequency * math.cos(drive.frequency * shifted_time + drive.phase)
    envelope_derivative = envelope * (-shifted_time / (drive.width**2))
    prefactor_derivative = envelope_derivative * carrier + envelope * carrier_derivative
    return (
        drive.amplitude_x * prefactor_derivative,
        drive.amplitude_y * prefactor_derivative,
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


def build_one_body_hamiltonian_derivative(
    config: SimulationConfig,
    lattice: SquareLattice,
    time: float,
) -> NDArray[np.complex128]:
    size = lattice.site_count
    hamiltonian_derivative = np.zeros((size, size), dtype=np.complex128)

    dax_dt, day_dt = vector_potential_derivative(config.drive, time)
    if dax_dt == 0.0 and day_dt == 0.0:
        return hamiltonian_derivative

    ax, ay = vector_potential(config.drive, time)
    for bond in lattice.bonds:
        phase = ax if bond.direction == "x" else ay
        phase_derivative = dax_dt if bond.direction == "x" else day_dt
        forward = -config.lattice.hopping * np.exp(-1j * phase)
        derivative = -1j * forward * phase_derivative
        hamiltonian_derivative[bond.source, bond.target] += derivative
        hamiltonian_derivative[bond.target, bond.source] += np.conjugate(derivative)

    return hamiltonian_derivative
