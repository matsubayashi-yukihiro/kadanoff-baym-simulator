from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.nambu import ComplexMatrix


def stationarity_diagnostics(
    *,
    generalized_densities: list[ComplexMatrix],
    density_mean: NDArray[np.float64],
    energy: NDArray[np.float64],
    pairing_primary: NDArray[np.complex128],
    pairing_d: NDArray[np.complex128],
) -> dict[str, float | list[float]]:
    stationarity_residual_history = [
        float(np.max(np.abs(generalized_density - generalized_densities[0])))
        for generalized_density in generalized_densities
    ]
    density_initial_slip_history = np.abs(density_mean - density_mean[0]).astype(np.float64).tolist()
    pairing_initial_slip_history = np.abs(pairing_primary - pairing_primary[0]).astype(np.float64).tolist()
    pairing_d_initial_slip_history = np.abs(pairing_d - pairing_d[0]).astype(np.float64).tolist()
    energy_initial_slip_history = np.abs(energy - energy[0]).astype(np.float64).tolist()
    return {
        "stationarity_residual_history": stationarity_residual_history,
        "max_stationarity_residual": float(max(stationarity_residual_history, default=0.0)),
        "density_initial_slip_history": density_initial_slip_history,
        "max_density_initial_slip": float(max(density_initial_slip_history, default=0.0)),
        "pairing_initial_slip_history": pairing_initial_slip_history,
        "max_pairing_initial_slip": float(max(pairing_initial_slip_history, default=0.0)),
        "pairing_d_initial_slip_history": pairing_d_initial_slip_history,
        "max_pairing_d_initial_slip": float(max(pairing_d_initial_slip_history, default=0.0)),
        "energy_initial_slip_history": energy_initial_slip_history,
        "max_energy_initial_slip": float(max(energy_initial_slip_history, default=0.0)),
    }
