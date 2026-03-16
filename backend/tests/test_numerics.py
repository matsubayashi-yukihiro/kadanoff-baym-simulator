import numpy as np
import pytest

from backend.app.solvers.equilibrium import occupation_numbers
from backend.app.solvers.numerics import cumulative_trapezoid, solve_bracketed_root


def test_cumulative_trapezoid_matches_linear_antiderivative_on_nonuniform_grid():
    times = np.asarray([0.0, 0.2, 0.5, 1.0], dtype=np.float64)
    values = 2.0 * times + 1.0

    integrated = cumulative_trapezoid(values, times)

    assert integrated.tolist() == pytest.approx((times**2 + times).tolist(), abs=1e-12)


def test_solve_bracketed_root_uses_scipy_brentq_backend():
    root = solve_bracketed_root(lambda value: value**3 - 2.0, lower=0.0, upper=2.0)

    assert root == pytest.approx(2.0 ** (1.0 / 3.0), abs=1e-10)


def test_occupation_numbers_match_particle_target_at_finite_temperature():
    eigenvalues = np.asarray([-1.0, -0.25, 0.75, 1.5], dtype=np.float64)

    occupation = occupation_numbers(eigenvalues, particle_target=1.7, temperature=0.3)

    assert occupation.sum() == pytest.approx(1.7, abs=1e-9)
    assert np.all(occupation >= 0.0)
    assert np.all(occupation <= 1.0)
