import numpy as np
import pytest

from backend.app.solvers.equilibrium import occupation_numbers
from backend.app.solvers.fixed_point import AndersonMixer, evaluate_fixed_point_solver
from backend.app.solvers.numerics import cumulative_trapezoid, solve_bracketed_root

pytestmark = pytest.mark.physics_unit


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


def test_anderson_mixer_accelerates_coupled_fixed_point_against_linear_mixing():
    operator = np.asarray([[0.55, 0.2], [0.15, 0.45]], dtype=np.float64)
    bias = np.asarray([0.2, -0.1], dtype=np.float64)
    exact_solution = np.linalg.solve(np.eye(2, dtype=np.float64) - operator, bias)

    def mapping(state: np.ndarray) -> np.ndarray:
        return operator @ state + bias

    tolerance = 1e-8
    linear_state = np.zeros(2, dtype=np.float64)
    linear_iterations = 0
    for iteration in range(1, 129):
        target = mapping(linear_state)
        linear_state = 0.45 * target + 0.55 * linear_state
        if np.max(np.abs(mapping(linear_state) - linear_state)) <= tolerance:
            linear_iterations = iteration
            break

    anderson_state = np.zeros(2, dtype=np.float64)
    anderson_mixer = AndersonMixer(mixing=0.45, max_history=4)
    anderson_iterations = 0
    for iteration in range(1, 129):
        target = mapping(anderson_state)
        anderson_state = anderson_mixer.update(anderson_state, target)
        if np.max(np.abs(mapping(anderson_state) - anderson_state)) <= tolerance:
            anderson_iterations = iteration
            break

    assert linear_iterations > 0
    assert anderson_iterations > 0
    assert np.max(np.abs(anderson_state - exact_solution)) < 1e-7
    assert anderson_iterations < linear_iterations


@pytest.mark.parametrize("method", ["anderson", "broyden1"])
def test_fixed_point_candidate_evaluation_converges_for_toy_residual(method: str):
    def mapping(state: np.ndarray) -> np.ndarray:
        return np.asarray(
            [
                np.cos(state[0]) * 0.5 + 0.1,
                np.sin(state[1]) * 0.25 - 0.2,
            ],
            dtype=np.float64,
        )

    result = evaluate_fixed_point_solver(mapping, initial=np.asarray([0.2, -0.3], dtype=np.float64), method=method)

    assert result.converged is True
    assert result.residual_norm < 1e-10
