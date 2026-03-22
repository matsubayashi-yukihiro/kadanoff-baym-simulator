import pytest
import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers import kbe_hfb as kbe_hfb_solver
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.self_energy_second_born import (
    _build_gkba_row_data,
    _build_local_second_born_self_energy,
    _damping_collision,
)

pytestmark = pytest.mark.physics_unit


def test_local_second_born_self_energy_matches_manual_local_blocks():
    site_count = 3
    nambu_dimension = 2 * site_count
    onsite_strength = 1.7
    first = np.arange(1, nambu_dimension * nambu_dimension + 1, dtype=np.float64).reshape(nambu_dimension, nambu_dimension)
    second = (first + 2.0j).astype(np.complex128)
    third = (first.T - 3.0j).astype(np.complex128)

    sigma = _build_local_second_born_self_energy(
        onsite_strength=onsite_strength,
        first=first.astype(np.complex128),
        second=second,
        third=third,
        site_count=site_count,
    )

    expected = np.zeros_like(sigma)
    coupling = onsite_strength**2
    for site in range(site_count):
        indices = np.asarray([site, site_count + site], dtype=np.int64)
        expected[np.ix_(indices, indices)] = (
            coupling
            * first[np.ix_(indices, indices)]
            @ second[np.ix_(indices, indices)]
            @ third[np.ix_(indices, indices)]
        )

    assert np.allclose(sigma, expected)
    off_block_mask = np.ones_like(sigma, dtype=bool)
    for site in range(site_count):
        indices = np.asarray([site, site_count + site], dtype=np.int64)
        off_block_mask[np.ix_(indices, indices)] = False
    assert np.max(np.abs(sigma[off_block_mask])) == 0.0


def test_build_gkba_row_data_shapes_and_equal_time_values():
    """_build_gkba_row_data returns 4 lists of length time_index+1 with correct shapes,
    and equal-time entries satisfy the GKBA identities."""
    site_count = 2
    nambu_dim = 2 * site_count
    time_index = 2
    rng = np.random.default_rng(42)

    guess_density = rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
    corrected_densities = [
        rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
        for _ in range(time_index)
    ]
    cumulative_propagators = [
        rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
        for _ in range(time_index + 1)
    ]

    row_lesser, column_lesser, row_greater, column_greater = _build_gkba_row_data(
        time_index=time_index,
        guess_density=guess_density,
        corrected_densities=corrected_densities,
        cumulative_propagators=cumulative_propagators,
    )

    # Each list has exactly time_index + 1 elements of shape (nambu_dim, nambu_dim)
    for lst in (row_lesser, column_lesser, row_greater, column_greater):
        assert len(lst) == time_index + 1
        for mat in lst:
            assert mat.shape == (nambu_dim, nambu_dim)

    # Equal-time: G^<(t,t) = i * rho
    np.testing.assert_array_equal(row_lesser[time_index], 1j * guess_density)
    # Equal-time symmetry: G^<(t,t) row == column (diagonal time)
    np.testing.assert_array_equal(column_lesser[time_index], row_lesser[time_index])
    # Equal-time: G^>(t,t) = i * (rho - 1)
    identity = np.eye(nambu_dim, dtype=np.complex128)
    np.testing.assert_array_equal(row_greater[time_index], 1j * (guess_density - identity))


def test_build_gkba_row_data_antihermitian_relation():
    """For history indices, column_lesser[h] == -row_lesser[h].conj().T (GKBA anti-Hermitian relation)."""
    site_count = 2
    nambu_dim = 2 * site_count
    time_index = 2
    rng = np.random.default_rng(7)

    guess_density = rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
    corrected_densities = [
        rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
        for _ in range(time_index)
    ]
    cumulative_propagators = [
        rng.standard_normal((nambu_dim, nambu_dim)) + 1j * rng.standard_normal((nambu_dim, nambu_dim))
        for _ in range(time_index + 1)
    ]

    row_lesser, column_lesser, row_greater, column_greater = _build_gkba_row_data(
        time_index=time_index,
        guess_density=guess_density,
        corrected_densities=corrected_densities,
        cumulative_propagators=cumulative_propagators,
    )

    for h in range(time_index):
        np.testing.assert_allclose(
            column_lesser[h],
            -row_lesser[h].conjugate().T,
            atol=1e-14,
            err_msg=f"anti-Hermitian relation failed at history index {h}",
        )


def test_damping_collision_zero_input():
    """_damping_collision returns zero for zero input values (2D and 3D)."""
    n = 4
    kernel = np.random.default_rng(0).standard_normal((n, n)).astype(np.complex128)

    values_2d = np.zeros((n, n), dtype=np.complex128)
    result_2d = _damping_collision(kernel, values_2d)
    assert np.all(result_2d == 0.0)
    assert result_2d.shape == (n, n)

    k = 3
    values_3d = np.zeros((k, n, n), dtype=np.complex128)
    result_3d = _damping_collision(kernel, values_3d)
    assert np.all(result_3d == 0.0)
    assert result_3d.shape == (k, n, n)


@pytest.mark.physics_invariant
def test_second_born_convergence_criterion_key_in_diagnostics():
    """second_born_convergence_criterion must be present in diagnostics and have a valid value.
    Regression guard for the convergence_criterion diagnostic field (Item 2)."""
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "periodic",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.1, "dt": 0.1},
            "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            "interaction": {"onsite_u": -1.0, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
            "initial_state": {"filling": 0.5, "temperature": 0.1, "seed_pairing": 0.0},
            "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 5, "tolerance": 1e-6},
            "adaptive": {"enabled": False},
            "observables": ["density"],
        }
    )
    artifacts = solve_kbe_hfb(config)

    assert "second_born_convergence_criterion" in artifacts.diagnostics
    assert artifacts.diagnostics["second_born_convergence_criterion"] in ("strict", "relaxed_5x")


def _fallback_probe_config(*, mode: str) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "periodic",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.1, "dt": 0.1},
            "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            "interaction": {"onsite_u": 0.0, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
            "initial_state": {"filling": 0.5, "temperature": 0.1, "seed_pairing": 0.0},
            "kbe": {"self_energy": mode, "max_fixed_point_iterations": 4, "tolerance": 1e-7},
            "thermal_branch": {"enabled": True, "n_tau": 6, "max_iterations": 2, "mixing": 0.3},
            "adaptive": {"enabled": False},
            "observables": ["density", "energy"],
        }
    )


def test_reference_second_born_fallback_diagnostics_and_warning(caplog):
    config = _fallback_probe_config(mode="second_born_reference")
    with caplog.at_level("WARNING"):
        artifacts = solve_kbe_hfb(config)

    diagnostics = artifacts.diagnostics
    assert diagnostics["second_born_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert diagnostics["thermal_branch_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert diagnostics["mixed_branch_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert any(
        "real_time_reference" in record.getMessage() and "hfb_limit_onsite_u_zero" in record.getMessage()
        for record in caplog.records
    )


def test_prototype_second_born_fallback_diagnostics_and_warning(caplog):
    config = _fallback_probe_config(mode="second_born")
    with caplog.at_level("WARNING"):
        artifacts = solve_kbe_hfb(config)

    diagnostics = artifacts.diagnostics
    assert diagnostics["second_born_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert diagnostics["thermal_branch_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert diagnostics["mixed_branch_applied_fallback"] == "hfb_limit_onsite_u_zero"
    assert any(
        "real_time_prototype" in record.getMessage() and "hfb_limit_onsite_u_zero" in record.getMessage()
        for record in caplog.records
    )


def test_kbe_solver_raises_runtime_error_when_green_function_reference_missing(monkeypatch):
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
            "time": {"t_final": 0.1, "dt": 0.1},
            "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            "interaction": {"onsite_u": -1.0, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
            "initial_state": {"filling": 0.5, "temperature": 0.1, "seed_pairing": 0.0},
            "adaptive": {"enabled": False},
            "observables": ["density"],
        }
    )

    def _fake_second_born_path(**kwargs):
        dynamics = kwargs["dynamics"]
        return dynamics.generalized_densities, dynamics.observables, {}, None, None

    monkeypatch.setattr(kbe_hfb_solver, "_solve_second_born_path", _fake_second_born_path)
    with pytest.raises(RuntimeError, match="green_function_reference is None"):
        kbe_hfb_solver.solve(config)


def test_kbe_solver_raises_runtime_error_when_hfb_green_functions_missing(monkeypatch):
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
            "time": {"t_final": 0.1, "dt": 0.1},
            "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            "interaction": {"onsite_u": -1.0, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
            "initial_state": {"filling": 0.5, "temperature": 0.1, "seed_pairing": 0.0},
            "kbe": {"self_energy": "second_born"},
            "adaptive": {"enabled": False},
            "observables": ["density"],
        }
    )

    monkeypatch.setattr(kbe_hfb_solver, "_build_hfb_green_functions", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="self_energy=second_born"):
        kbe_hfb_solver.solve(config)
