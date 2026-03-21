import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.tdhfb import solve as solve_tdhfb

pytestmark = pytest.mark.physics_invariant


def test_tdhfb_hfb_equilibrium_remains_stationary_source_free(paired_config):
    artifacts = solve_tdhfb(SimulationConfig.model_validate(paired_config))

    assert artifacts.diagnostics["equilibrium_solver_method"] == "hfb"
    assert artifacts.diagnostics["equilibrium_matches_runtime_approximation"] is True
    assert artifacts.diagnostics["particle_number_drift"] < 1e-8
    assert artifacts.diagnostics["energy_drift"] < 1e-8
    assert artifacts.diagnostics["max_stationarity_residual"] < 1e-8


def test_second_born_reference_hfb_seed_source_free_shows_initial_slip():
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
            "time": {"t_final": 0.3, "dt": 0.05},
            "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            "interaction": {"onsite_u": -1.2, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
            "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
            "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
            "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 10, "tolerance": 1e-6, "mixing": 0.5},
            "observables": ["density", "energy", "pairing", "pairing_d"],
        }
    )

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["equilibrium_solver_method"] == "hfb"
    assert artifacts.diagnostics["equilibrium_matches_runtime_approximation"] is False
    assert artifacts.diagnostics["equilibrium_mismatch_allowed"] is True
    assert artifacts.diagnostics["max_stationarity_residual"] > 1e-3
    assert artifacts.diagnostics["max_density_initial_slip"] > 1e-4
    assert artifacts.diagnostics["max_energy_initial_slip"] > 1e-3


def test_second_born_reference_correlated_contour_changes_source_free_stationarity_metrics():
    factorized = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                "solver": "kbe_hfb",
                "lattice": {
                    "nx": 2,
                    "ny": 2,
                    "boundary": "periodic",
                    "hopping": 1.0,
                    "chemical_potential": 0.0,
                },
                "time": {"t_final": 0.3, "dt": 0.05},
                "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
                "interaction": {"onsite_u": -1.2, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
                "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
                "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
                "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 10, "tolerance": 1e-6, "mixing": 0.5},
                "observables": ["density", "energy"],
            }
        )
    )
    correlated = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                "solver": "kbe_hfb",
                "lattice": {
                    "nx": 2,
                    "ny": 2,
                    "boundary": "periodic",
                    "hopping": 1.0,
                    "chemical_potential": 0.0,
                },
                "time": {"t_final": 0.3, "dt": 0.05},
                "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
                "interaction": {"onsite_u": -1.2, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
                "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
                "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
                "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 10, "tolerance": 1e-6, "mixing": 0.5},
                "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
                "observables": ["density", "energy"],
            }
        )
    )

    assert correlated.diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert correlated.diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert correlated.diagnostics["stationarity_residual_history"] != pytest.approx(
        factorized.diagnostics["stationarity_residual_history"]
    )
    assert correlated.diagnostics["density_initial_slip_history"] != pytest.approx(
        factorized.diagnostics["density_initial_slip_history"]
    )


def test_second_born_reference_equilibrium_seed_is_more_stationary_than_hfb_seed():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
        "interaction": {"onsite_u": -1.2, "nearest_neighbor_v": 0.0, "pairing_channel": "none"},
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "kbe": {"self_energy": "second_born_reference", "max_fixed_point_iterations": 10, "tolerance": 1e-6, "mixing": 0.5},
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
        "observables": ["density", "energy", "pairing", "pairing_d"],
    }

    hfb_seed = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **base_config,
                "equilibrium": {"method": "hfb", "allow_approximation_mismatch": True},
            }
        )
    )
    reference_seed = solve_kbe_hfb(SimulationConfig.model_validate(base_config))

    assert reference_seed.diagnostics["equilibrium_solver_method"] == "second_born_reference"
    assert reference_seed.diagnostics["equilibrium_matches_runtime_approximation"] is True
    assert reference_seed.diagnostics["max_stationarity_residual"] < hfb_seed.diagnostics["max_stationarity_residual"]
    assert reference_seed.diagnostics["max_density_initial_slip"] < hfb_seed.diagnostics["max_density_initial_slip"]
    assert reference_seed.diagnostics["max_energy_initial_slip"] < hfb_seed.diagnostics["max_energy_initial_slip"]
    assert reference_seed.diagnostics["particle_number_drift"] < hfb_seed.diagnostics["particle_number_drift"]
    assert reference_seed.diagnostics["equilibrium_density_update_residual"] >= 0.0
    assert np.isfinite(reference_seed.diagnostics["equilibrium_stationarity_residual"])
