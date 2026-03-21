from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from backend.app.schemas import DriveConfig, DriveKind, SimulationConfig
from backend.app.solvers.lattice import SquareLattice


def _envelope_and_derivative(drive: DriveConfig, time: float) -> tuple[float, float]:
    """Return (envelope, d_envelope/dt) for the current drive_type."""
    s = time - drive.center
    w = drive.width

    if drive.drive_type == DriveKind.GAUSSIAN:
        env = math.exp(-0.5 * (s / w) ** 2)
        d_env = env * (-s / w**2)
        return env, d_env

    if drive.drive_type == DriveKind.SECH2:
        cosh_val = math.cosh(s / w)
        env = 1.0 / (cosh_val**2)
        d_env = -2.0 * env * math.tanh(s / w) / w
        return env, d_env

    if drive.drive_type == DriveKind.TRAPEZOID:
        # Smooth trapezoid via tanh: plateau in [center-w, center+w],
        # ramp sharpness k=4 (relative to w).
        k = 4.0
        t1 = math.tanh(k * (s / w + 1.0))
        t2 = math.tanh(k * (s / w - 1.0))
        env = 0.5 * (t1 - t2)
        sech2_1 = 1.0 - t1**2
        sech2_2 = 1.0 - t2**2
        d_env = 0.5 * (k / w) * (sech2_1 - sech2_2)
        return env, d_env

    # DriveKind.SINE: no envelope (pure sinusoidal)
    return 1.0, 0.0


def vector_potential(drive: DriveConfig, time: float) -> tuple[float, float]:
    if drive.amplitude_x == 0.0 and drive.amplitude_y == 0.0:
        return 0.0, 0.0

    if drive.drive_type == DriveKind.SINE:
        carrier = math.sin(drive.frequency * time + drive.phase)
        return drive.amplitude_x * carrier, drive.amplitude_y * carrier

    shifted_time = time - drive.center
    envelope, _ = _envelope_and_derivative(drive, time)
    carrier = math.sin(drive.frequency * shifted_time + drive.phase)
    return (
        drive.amplitude_x * envelope * carrier,
        drive.amplitude_y * envelope * carrier,
    )


def vector_potential_derivative(drive: DriveConfig, time: float) -> tuple[float, float]:
    if drive.amplitude_x == 0.0 and drive.amplitude_y == 0.0:
        return 0.0, 0.0

    if drive.drive_type == DriveKind.SINE:
        carrier_deriv = drive.frequency * math.cos(drive.frequency * time + drive.phase)
        return drive.amplitude_x * carrier_deriv, drive.amplitude_y * carrier_deriv

    shifted_time = time - drive.center
    envelope, d_envelope = _envelope_and_derivative(drive, time)
    carrier = math.sin(drive.frequency * shifted_time + drive.phase)
    carrier_deriv = drive.frequency * math.cos(drive.frequency * shifted_time + drive.phase)
    prefactor_deriv = d_envelope * carrier + envelope * carrier_deriv
    return (
        drive.amplitude_x * prefactor_deriv,
        drive.amplitude_y * prefactor_deriv,
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


def build_one_body_momentum_diagonal(
    config: SimulationConfig,
    *,
    kx: NDArray[np.float64],
    ky: NDArray[np.float64],
    time: float,
) -> NDArray[np.float64]:
    ax, ay = vector_potential(config.drive, time)
    return (
        -config.lattice.chemical_potential
        - 2.0 * config.lattice.hopping * np.cos(kx - ax)
        - 2.0 * config.lattice.hopping * np.cos(ky - ay)
    ).astype(np.float64)


def build_one_body_momentum_diagonal_derivative(
    config: SimulationConfig,
    *,
    kx: NDArray[np.float64],
    ky: NDArray[np.float64],
    time: float,
) -> NDArray[np.float64]:
    dax_dt, day_dt = vector_potential_derivative(config.drive, time)
    if dax_dt == 0.0 and day_dt == 0.0:
        return np.zeros_like(kx, dtype=np.float64)
    ax, ay = vector_potential(config.drive, time)
    return (
        -2.0 * config.lattice.hopping * np.sin(kx - ax) * dax_dt
        - 2.0 * config.lattice.hopping * np.sin(ky - ay) * day_dt
    ).astype(np.float64)
