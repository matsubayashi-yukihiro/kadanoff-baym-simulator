from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from backend.app.solvers.numerics import solve_bracketed_root


def fermi_dirac(
    eigenvalues: NDArray[np.float64],
    chemical_potential: float,
    temperature: float,
) -> NDArray[np.float64]:
    argument = np.clip((eigenvalues - chemical_potential) / temperature, -100.0, 100.0)
    return 1.0 / (np.exp(argument) + 1.0)


def occupation_numbers(
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
    lower_residual = float(np.sum(fermi_dirac(eigenvalues, lower_mu, temperature)) - particle_target)
    upper_residual = float(np.sum(fermi_dirac(eigenvalues, upper_mu, temperature)) - particle_target)
    if lower_residual >= 0.0:
        return fermi_dirac(eigenvalues, lower_mu, temperature)
    if upper_residual <= 0.0:
        return fermi_dirac(eigenvalues, upper_mu, temperature)

    chemical_potential = solve_bracketed_root(
        lambda chemical_potential: float(np.sum(fermi_dirac(eigenvalues, chemical_potential, temperature)) - particle_target),
        lower=lower_mu,
        upper=upper_mu,
    )
    return fermi_dirac(eigenvalues, chemical_potential, temperature)
