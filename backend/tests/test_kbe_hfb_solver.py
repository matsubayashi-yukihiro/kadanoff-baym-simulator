import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.noninteracting import solve as solve_noninteracting
from backend.app.solvers.tdhfb import solve as solve_tdhfb


@pytest.mark.parametrize("observable_name,series_index", [("density", 0), ("pairing_d", 2), ("energy", 0)])
def test_kbe_hfb_matches_tdhfb_equal_time_observables(paired_config, observable_name, series_index):
    tdhfb_config = SimulationConfig.model_validate(paired_config)
    kbe_config = SimulationConfig.model_validate({**paired_config, "solver": "kbe_hfb"})

    tdhfb = solve_tdhfb(tdhfb_config)
    kbe = solve_kbe_hfb(kbe_config)

    assert kbe.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-10
    assert kbe.diagnostics["max_lesser_hermiticity_error"] < 1e-10
    assert kbe.diagnostics["max_retarded_equal_time_error"] < 1e-10
    assert kbe.diagnostics["max_retarded_causality_error"] == 0.0
    assert kbe.diagnostics["two_time_grid_shape"] == [3, 3, 32, 32]

    assert tdhfb.observables[observable_name].time.tolist() == kbe.observables[observable_name].time.tolist()
    assert tdhfb.observables[observable_name].series[series_index].values.tolist() == pytest.approx(
        kbe.observables[observable_name].series[series_index].values.tolist(),
        abs=1e-10,
    )


def test_kbe_hfb_matches_exact_noninteracting_limit_under_drive():
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
    kbe = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "solver": "kbe_hfb"}))

    assert kbe.diagnostics["two_time_grid_shape"] == [7, 7, 8, 8]
    assert kbe.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-12
    assert kbe.diagnostics["max_lesser_hermiticity_error"] < 1e-12
    assert kbe.diagnostics["max_retarded_equal_time_error"] < 1e-12
    assert kbe.diagnostics["max_retarded_causality_error"] == 0.0

    assert exact.observables["density"].time.tolist() == kbe.observables["density"].time.tolist()
    assert exact.observables["density"].series[0].values.tolist() == pytest.approx(
        kbe.observables["density"].series[0].values.tolist(),
        abs=1e-12,
    )
    for observable_name in ("current_x", "current_y", "energy", "vector_potential"):
        for exact_series, kbe_series in zip(
            exact.observables[observable_name].series,
            kbe.observables[observable_name].series,
            strict=True,
        ):
            assert exact_series.values.tolist() == pytest.approx(kbe_series.values.tolist(), abs=1e-12)

    for observable_name in ("pairing", "pairing_s", "pairing_d"):
        for series in kbe.observables[observable_name].series:
            assert series.values.tolist() == pytest.approx([0.0] * len(series.values), abs=1e-12)


def test_kbe_second_born_reduces_to_hfb_when_onsite_u_zero():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.25,
            "amplitude_y": 0.1,
            "frequency": 2.0,
            "phase": 0.2,
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
            "temperature": 0.1,
            "seed_pairing": 0.0,
        },
        "observables": ["density", "current_x", "current_y", "energy"],
    }

    hfb = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    second_born = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **base_config,
                "kbe": {
                    "self_energy": "second_born",
                    "max_fixed_point_iterations": 8,
                    "tolerance": 1e-8,
                    "mixing": 0.5,
                },
            }
        )
    )

    assert second_born.diagnostics["second_born_enabled"] is True
    assert second_born.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-12
    assert second_born.diagnostics["max_second_born_memory_norm"] == 0.0
    for observable_name in ("density", "current_x", "current_y", "energy"):
        for hfb_series, second_born_series in zip(
            hfb.observables[observable_name].series,
            second_born.observables[observable_name].series,
            strict=True,
        ):
            assert hfb_series.values.tolist() == pytest.approx(second_born_series.values.tolist(), abs=1e-12)


def test_kbe_second_born_reports_memory_diagnostics_under_drive():
    hfb_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.5,
            "amplitude_y": 0.25,
            "frequency": 2.0,
            "center": 0.2,
            "width": 0.1,
        },
        "interaction": {
            "onsite_u": -2.0,
            "nearest_neighbor_v": -2.5,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.2,
        },
        "observables": ["density", "energy", "pairing_d"],
    }

    hfb = solve_kbe_hfb(SimulationConfig.model_validate(hfb_config))
    second_born = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **hfb_config,
                "kbe": {
                    "self_energy": "second_born",
                    "max_fixed_point_iterations": 12,
                    "tolerance": 1e-7,
                    "mixing": 0.5,
                },
            }
        )
    )

    assert second_born.diagnostics["second_born_enabled"] is True
    assert second_born.diagnostics["second_born_converged"] is True
    assert second_born.diagnostics["max_second_born_memory_norm"] > 0.0
    assert second_born.diagnostics["max_second_born_collision_norm"] > 0.0
    assert second_born.diagnostics["max_equal_time_tdhfb_mismatch"] > 1e-6
    assert len(second_born.diagnostics["second_born_iteration_history"]) == second_born.diagnostics["time_steps"]
    assert abs(
        second_born.observables["pairing_d"].series[2].values[-1]
        - hfb.observables["pairing_d"].series[2].values[-1]
    ) > 1e-8


def test_kbe_hfb_supports_adaptive_grid_and_matsubara_diagnostics():
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
            "time": {"t_final": 0.4, "dt": 0.1},
            "interaction": {
                "onsite_u": -1.5,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {"filling": 0.5, "temperature": 0.2},
            "adaptive": {"enabled": True, "rtol": 1e-4, "atol": 1e-6, "min_dt": 0.025, "max_dt": 0.1},
            "thermal_branch": {"enabled": True, "n_tau": 8},
            "observables": ["density", "energy"],
        }
    )

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["time_grid_mode"] == "adaptive"
    assert artifacts.diagnostics["accepted_time_steps"] > 0
    assert len(artifacts.diagnostics["time_step_history"]) == artifacts.diagnostics["accepted_time_steps"]
    assert artifacts.diagnostics["thermal_branch_enabled"] is True
    assert artifacts.diagnostics["matsubara_grid_shape"] == [9, 8, 8]
    assert artifacts.diagnostics["matsubara_zero_plus_error"] < 1e-8
    assert artifacts.diagnostics["matsubara_beta_minus_error"] < 1e-7
