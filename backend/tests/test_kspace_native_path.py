from __future__ import annotations

from time import perf_counter

import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.equilibrium_solvers import solve_equilibrium
from backend.app.solvers.lattice import build_square_lattice
from backend.app.solvers.nambu import solve_hfb_equilibrium
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.tdhfb import _propagate_generalized_densities_kspace, solve as solve_tdhfb


def _native_kspace_config() -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "tdhfb",
            "representation": "k_space",
            "lattice": {
                "nx": 4,
                "ny": 4,
                "boundary": "periodic",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.3, "dt": 0.1},
            "drive": {
                "amplitude_x": 0.05,
                "amplitude_y": 0.01,
                "frequency": 1.2,
                "phase": 0.1,
                "center": 0.12,
                "width": 0.12,
            },
            "interaction": {
                "onsite_u": -1.0,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {
                "filling": 0.5,
                "temperature": 0.2,
                "seed_pairing": 0.0,
            },
            "adaptive": {"enabled": False},
            "observables": ["density", "energy", "current_x", "current_y"],
        }
    )


@pytest.mark.physics_unit
def test_kspace_native_hfb_equilibrium_path_is_reachable():
    config = _native_kspace_config()
    lattice = build_square_lattice(config.lattice)

    equilibrium = solve_hfb_equilibrium(config, lattice)

    assert equilibrium.solver_mode == "hfb_kspace_native"
    assert equilibrium.momentum_density_blocks is not None
    assert equilibrium.momentum_generalized_density is not None
    assert np.all(np.isfinite(equilibrium.momentum_density_blocks))


@pytest.mark.physics_invariant
def test_tdhfb_kspace_native_block_path_matches_real_space_for_supported_scope():
    config_k = _native_kspace_config()
    config_real = SimulationConfig.model_validate({**config_k.model_dump(mode="json"), "representation": "real_space"})

    real_space = solve_tdhfb(config_real)
    k_space = solve_tdhfb(config_k)

    assert k_space.diagnostics["k_space_path_mode"] == "block_diagonal"
    assert k_space.diagnostics["equilibrium_solver_mode"] == "hfb_kspace_native"
    for observable_name in ("density", "energy", "current_x", "current_y"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


@pytest.mark.physics_benchmark
def test_kspace_block_path_is_at_least_1p5x_as_fast_as_forced_full_matrix_path():
    config = SimulationConfig.model_validate(
        {
            **_native_kspace_config().model_dump(mode="json"),
            "lattice": {"nx": 6, "ny": 6, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
            "time": {"t_final": 0.3, "dt": 0.05},
        }
    )
    lattice = build_square_lattice(config.lattice)
    equilibrium = solve_equilibrium(config, lattice)
    assert equilibrium.solver_mode == "hfb_kspace_native"

    _propagate_generalized_densities_kspace(config, equilibrium)
    equilibrium.solver_mode = "hfb_kspace_fallback_forced"
    _propagate_generalized_densities_kspace(config, equilibrium)

    block_times: list[float] = []
    full_times: list[float] = []
    for _ in range(4):
        equilibrium.solver_mode = "hfb_kspace_native"
        start = perf_counter()
        _propagate_generalized_densities_kspace(config, equilibrium)
        block_times.append(perf_counter() - start)

        equilibrium.solver_mode = "hfb_kspace_fallback_forced"
        start = perf_counter()
        _propagate_generalized_densities_kspace(config, equilibrium)
        full_times.append(perf_counter() - start)

    block_median = float(np.median(np.asarray(block_times[1:], dtype=np.float64)))
    full_median = float(np.median(np.asarray(full_times[1:], dtype=np.float64)))
    assert full_median / block_median >= 1.5


@pytest.mark.physics_benchmark
def test_kspace_block_path_is_at_least_twice_as_fast_for_second_born_reference_propagation_kernel():
    config = SimulationConfig.model_validate(
        {
            **_native_kspace_config().model_dump(mode="json"),
            "solver": "kbe_hfb",
            "lattice": {"nx": 6, "ny": 6, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
            "time": {"t_final": 0.3, "dt": 0.05},
            "equilibrium": {"method": "second_born_reference"},
            "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 8, "tolerance": 1e-5, "mixing": 0.5},
            "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 10, "mixing": 0.4},
        }
    )
    lattice = build_square_lattice(config.lattice)
    equilibrium = solve_equilibrium(config, lattice)

    equilibrium.solver_mode = "hfb_kspace_native"
    _propagate_generalized_densities_kspace(config, equilibrium)
    equilibrium.solver_mode = "hfb_kspace_fallback_forced"
    _propagate_generalized_densities_kspace(config, equilibrium)

    block_times: list[float] = []
    full_times: list[float] = []
    for _ in range(4):
        equilibrium.solver_mode = "hfb_kspace_native"
        start = perf_counter()
        _propagate_generalized_densities_kspace(config, equilibrium)
        block_times.append(perf_counter() - start)

        equilibrium.solver_mode = "hfb_kspace_fallback_forced"
        start = perf_counter()
        _propagate_generalized_densities_kspace(config, equilibrium)
        full_times.append(perf_counter() - start)

    block_median = float(np.median(np.asarray(block_times[1:], dtype=np.float64)))
    full_median = float(np.median(np.asarray(full_times[1:], dtype=np.float64)))
    assert full_median / block_median >= 2.0


@pytest.mark.physics_invariant
def test_kbe_hfb_kspace_block_second_born_matches_real_space():
    base = {
        **_native_kspace_config().model_dump(mode="json"),
        "solver": "kbe_hfb",
        "lattice": {"nx": 4, "ny": 4, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
        "time": {"t_final": 0.3, "dt": 0.1},
        "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
        "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 10, "tolerance": 1e-6, "mixing": 0.5},
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
        "observables": ["density", "energy", "current_x"],
    }
    config_k = SimulationConfig.model_validate({**base, "representation": "k_space"})
    config_real = SimulationConfig.model_validate({**base, "representation": "real_space"})

    result_k = solve_kbe_hfb(config_k)
    result_real = solve_kbe_hfb(config_real)

    assert result_k.diagnostics.get("second_born_kspace_block_path") is True
    assert result_k.diagnostics.get("second_born_solver_mode") == "gkba_causal_marching_kspace_blocks"
    assert result_k.diagnostics.get("kbe_two_time_reconstruction") == "gkba_causal_marching"
    assert result_real.diagnostics.get("kbe_two_time_reconstruction") == "gkba_causal_marching"
    for obs_name in ("density", "energy", "current_x"):
        for k_series, real_series in zip(
            result_k.observables[obs_name].series,
            result_real.observables[obs_name].series,
            strict=True,
        ):
            assert k_series.values.tolist() == pytest.approx(real_series.values.tolist(), abs=1e-8)


@pytest.mark.physics_benchmark
def test_kbe_hfb_kspace_block_second_born_is_faster_than_real_space():
    """k-space block path should be significantly faster than real-space for kbe_hfb.

    Uses hfb equilibrium to isolate the second-Born correction + propagation performance
    (the second_born_reference equilibrium solver is not yet k-space-optimized and dominates
    otherwise, making both paths appear equally slow).
    """
    base = {
        **_native_kspace_config().model_dump(mode="json"),
        "solver": "kbe_hfb",
        "lattice": {"nx": 6, "ny": 6, "boundary": "periodic", "hopping": 1.0, "chemical_potential": 0.0},
        "time": {"t_final": 0.3, "dt": 0.05},
        "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
        "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 8, "tolerance": 1e-5, "mixing": 0.5},
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 10, "mixing": 0.4},
        "observables": ["density", "energy"],
    }
    config_k = SimulationConfig.model_validate({**base, "representation": "k_space"})
    config_real = SimulationConfig.model_validate({**base, "representation": "real_space"})

    solve_kbe_hfb(config_k)
    solve_kbe_hfb(config_real)

    k_times: list[float] = []
    real_times: list[float] = []
    for _ in range(3):
        start = perf_counter()
        solve_kbe_hfb(config_k)
        k_times.append(perf_counter() - start)

        start = perf_counter()
        solve_kbe_hfb(config_real)
        real_times.append(perf_counter() - start)

    k_median = float(np.median(np.asarray(k_times, dtype=np.float64)))
    real_median = float(np.median(np.asarray(real_times, dtype=np.float64)))
    assert real_median / k_median >= 2.0
