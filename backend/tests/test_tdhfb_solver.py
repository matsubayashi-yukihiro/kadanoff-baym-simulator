import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.nambu import extract_density_blocks
from backend.app.solvers.noninteracting import solve as solve_noninteracting
from backend.app.solvers.tdhfb import simulate_hfb_dynamics, solve

pytestmark = pytest.mark.physics_invariant


def test_tdhfb_solver_emits_pairing_projections_and_preserves_stationary_state(paired_config):
    config = SimulationConfig.model_validate(paired_config)

    artifacts = solve(config)

    assert set(artifacts.observables) == {"density", "energy", "pairing", "pairing_s", "pairing_d"}
    assert artifacts.diagnostics["hfb_converged"] is True
    assert artifacts.diagnostics["particle_number_drift"] < 1e-8
    assert artifacts.diagnostics["energy_drift"] < 1e-8

    pairing = artifacts.observables["pairing"]
    pairing_s = artifacts.observables["pairing_s"]
    pairing_d = artifacts.observables["pairing_d"]

    assert [series.label for series in pairing.series] == ["real", "imag", "magnitude"]
    assert pairing.time.tolist() == [0.0, 0.1, 0.2]
    assert pairing_d.series[2].values[-1] > 0.05
    assert pairing_d.series[2].values[-1] > 5.0 * pairing_s.series[2].values[-1]


def test_tdhfb_matches_exact_noninteracting_limit_under_drive():
    base_config = {
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.3,
            "amplitude_y": 0.15,
            "frequency": 2.0,
            "phase": 0.25,
            "center": 0.15,
            "width": 0.08,
        },
        "interaction": {
            "onsite_u": 0.0,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "observables": [
            "density",
            "current_x",
            "current_y",
            "energy",
            "vector_potential",
            "pairing",
            "pairing_s",
            "pairing_d",
        ],
    }

    exact = solve_noninteracting(SimulationConfig.model_validate({**base_config, "solver": "noninteracting"}))
    tdhfb = solve(SimulationConfig.model_validate({**base_config, "solver": "tdhfb"}))

    assert exact.observables["density"].time.tolist() == tdhfb.observables["density"].time.tolist()
    assert exact.observables["density"].series[0].values.tolist() == pytest.approx(
        tdhfb.observables["density"].series[0].values.tolist(),
        abs=1e-12,
    )
    for observable_name in ("current_x", "current_y", "energy", "vector_potential"):
        for exact_series, tdhfb_series in zip(
            exact.observables[observable_name].series,
            tdhfb.observables[observable_name].series,
            strict=True,
        ):
            assert exact_series.values.tolist() == pytest.approx(tdhfb_series.values.tolist(), abs=1e-12)

    for observable_name in ("pairing", "pairing_s", "pairing_d"):
        for series in tdhfb.observables[observable_name].series:
            assert series.values.tolist() == pytest.approx([0.0] * len(series.values), abs=1e-12)

    assert tdhfb.diagnostics["particle_number_drift"] < 1e-12
    assert tdhfb.diagnostics["equilibrium_stationarity_residual"] < 1e-10
    assert tdhfb.diagnostics["max_generalized_hermiticity_error"] == 0.0
    assert tdhfb.diagnostics["max_density_bound_violation"] == 0.0


def test_tdhfb_preserves_generalized_density_constraints_over_time(paired_config):
    dynamics = simulate_hfb_dynamics(SimulationConfig.model_validate(paired_config))

    idempotency_residual = 0.0
    occupation_bound_violation = 0.0

    for generalized_density in dynamics.generalized_densities:
        idempotency_residual = max(
            idempotency_residual,
            float(np.max(np.abs(generalized_density @ generalized_density - generalized_density))),
        )
        normal_density, _ = extract_density_blocks(generalized_density, dynamics.lattice.site_count)
        site_density = np.real(np.diag(normal_density))
        occupation_bound_violation = max(
            occupation_bound_violation,
            float(np.max(np.maximum(site_density - 1.0, 0.0) + np.maximum(-site_density, 0.0))),
        )

    assert dynamics.diagnostics["equilibrium_stationarity_residual"] < 5e-8
    assert dynamics.diagnostics["max_generalized_hermiticity_error"] == 0.0
    assert dynamics.diagnostics["max_density_bound_violation"] == 0.0
    assert idempotency_residual < 1e-10
    assert occupation_bound_violation == 0.0


def test_tdhfb_tracks_local_continuity_equation_in_source_free_normal_state():
    config = SimulationConfig.model_validate(
        {
            "solver": "tdhfb",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "open",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.3, "dt": 0.05},
            "drive": {
                "amplitude_x": 0.3,
                "amplitude_y": 0.15,
                "frequency": 2.4,
                "phase": 0.2,
                "center": 0.15,
                "width": 0.09,
            },
            "interaction": {
                "onsite_u": -0.8,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {
                "filling": 0.25,
                "temperature": 0.0,
                "seed_pairing": 0.0,
            },
            "observables": ["density", "current_x", "current_y", "energy"],
        }
    )

    artifacts = solve(config)

    assert artifacts.diagnostics["continuity_residual_supported"] is True
    assert len(artifacts.diagnostics["continuity_residual_history"]) == artifacts.diagnostics["time_steps"] + 1
    assert artifacts.diagnostics["max_continuity_residual"] == pytest.approx(
        max(artifacts.diagnostics["continuity_residual_history"])
    )
    assert artifacts.diagnostics["max_continuity_residual"] < 1e-11
    assert artifacts.diagnostics["final_continuity_residual"] < 1e-11


def test_tdhfb_k_space_representation_matches_real_space_for_periodic_drive():
    base_config = {
        "solver": "tdhfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.1,
            "amplitude_y": 0.0,
            "frequency": 1.8,
            "phase": 0.1,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -4.0,
            "nearest_neighbor_v": -2.5,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.2,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    real_space = solve(SimulationConfig.model_validate(base_config))
    k_space = solve(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_tdhfb_k_space_representation_matches_real_space_on_moderate_longer_window():
    base_config = {
        "solver": "tdhfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.1,
            "amplitude_y": 0.03,
            "frequency": 1.8,
            "phase": 0.1,
            "center": 0.12,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -3.5,
            "nearest_neighbor_v": -2.0,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.15,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    real_space = solve(SimulationConfig.model_validate(base_config))
    k_space = solve(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_tdhfb_k_space_representation_matches_real_space_on_longer_window():
    base_config = {
        "solver": "tdhfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.1,
            "amplitude_y": 0.03,
            "frequency": 1.8,
            "phase": 0.1,
            "center": 0.16,
            "width": 0.14,
        },
        "interaction": {
            "onsite_u": -3.5,
            "nearest_neighbor_v": -2.0,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.15,
        },
        "observables": [
            "density",
            "energy",
            "pairing",
            "pairing_s",
            "pairing_d",
        ],
    }

    real_space = solve(SimulationConfig.model_validate(base_config))
    k_space = solve(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    for observable_name in (
        "density",
        "energy",
        "pairing",
        "pairing_s",
        "pairing_d",
    ):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_tdhfb_k_space_representation_matches_real_space_on_larger_lattice():
    base_config = {
        "solver": "tdhfb",
        "lattice": {
            "nx": 6,
            "ny": 6,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.08,
            "amplitude_y": 0.04,
            "frequency": 1.5,
            "phase": 0.15,
            "center": 0.15,
            "width": 0.14,
        },
        "interaction": {
            "onsite_u": -2.8,
            "nearest_neighbor_v": -1.6,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.12,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    real_space = solve(SimulationConfig.model_validate(base_config))
    k_space = solve(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_tdhfb_writes_two_time_green_functions_for_derived_analysis_source():
    config = SimulationConfig.model_validate(
        {
            "solver": "tdhfb",
            "representation": "k_space",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "periodic",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.2, "dt": 0.1},
            "drive": {
                "amplitude_x": 0.05,
                "amplitude_y": 0.02,
                "frequency": 1.5,
                "center": 0.1,
                "width": 0.12,
            },
            "interaction": {
                "onsite_u": -1.2,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {
                "filling": 0.5,
                "temperature": 0.0,
                "seed_pairing": 0.0,
            },
            "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        }
    )

    artifacts = solve(config)
    assert artifacts.two_time_green_functions is not None
    times = artifacts.two_time_green_functions.times
    lesser = artifacts.two_time_green_functions.components["lesser"]
    retarded = artifacts.two_time_green_functions.components["retarded"]

    assert lesser.shape[0] == len(times)
    assert lesser.shape[1] == len(times)
    assert retarded.shape == lesser.shape
    assert np.max(np.abs(retarded[np.arange(len(times)), np.arange(len(times))] + 1j * np.eye(retarded.shape[2]))) < 1e-10
