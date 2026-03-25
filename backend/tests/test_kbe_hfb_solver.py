import pytest
import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.noninteracting import solve as solve_noninteracting
from backend.app.solvers.tdhfb import solve as solve_tdhfb

pytestmark = pytest.mark.physics_invariant


def _k_space_second_born_reference_full_contour_config(*, adaptive: dict[str, float | bool] | None = None):
    payload: dict[str, object] = {
        "solver": "kbe_hfb",
        "representation": "k_space",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.2,
            "amplitude_y": 0.0,
            "frequency": 1.0,
            "center": 0.2,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-5,
            "mixing": 0.5,
        },
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
        "observables": ["density", "energy"],
    }
    if adaptive is not None:
        payload["adaptive"] = adaptive
    return SimulationConfig.model_validate(payload)


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
        "adaptive": {"enabled": False},
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
        "adaptive": {"enabled": False},
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
    assert len(second_born.diagnostics["particle_conservation_residual_history"]) == second_born.diagnostics["time_steps"] + 1
    assert len(second_born.diagnostics["energy_work_mismatch_history"]) == second_born.diagnostics["time_steps"] + 1
    assert second_born.diagnostics["max_particle_conservation_residual"] == pytest.approx(
        second_born.diagnostics["particle_number_drift"],
        abs=1e-12,
    )
    for observable_name in ("density", "current_x", "current_y", "energy"):
        for hfb_series, second_born_series in zip(
            hfb.observables[observable_name].series,
            second_born.observables[observable_name].series,
            strict=True,
        ):
            assert hfb_series.values.tolist() == pytest.approx(second_born_series.values.tolist(), abs=1e-12)


def test_kbe_second_born_reference_reduces_to_hfb_when_onsite_u_zero():
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
        "adaptive": {"enabled": False},
    }

    hfb = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    reference = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **base_config,
                "kbe": {
                    "self_energy": "second_born_reference",
                    "max_fixed_point_iterations": 8,
                    "tolerance": 1e-8,
                    "mixing": 0.5,
                },
            }
        )
    )

    assert reference.diagnostics["second_born_enabled"] is True
    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert reference.diagnostics["second_born_solver_mode"] == "hfb_limit"
    assert reference.diagnostics["max_second_born_memory_norm"] == 0.0
    assert reference.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-12
    for observable_name in ("density", "current_x", "current_y", "energy"):
        for hfb_series, reference_series in zip(
            hfb.observables[observable_name].series,
            reference.observables[observable_name].series,
            strict=True,
        ):
            assert hfb_series.values.tolist() == pytest.approx(reference_series.values.tolist(), abs=1e-12)


def test_kbe_second_born_reference_k_space_representation_reduces_to_hfb_when_onsite_u_zero():
    base_config = {
        "solver": "kbe_hfb",
        "representation": "k_space",
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
        "adaptive": {"enabled": False},
    }

    hfb = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "kbe": {"self_energy": "hfb"}}))
    reference = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **base_config,
                "kbe": {
                    "self_energy": "second_born_reference",
                    "max_fixed_point_iterations": 8,
                    "tolerance": 1e-8,
                    "mixing": 0.5,
                },
            }
        )
    )

    assert reference.diagnostics["solver_representation"] == "k_space"
    assert reference.diagnostics["second_born_enabled"] is True
    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert reference.diagnostics["second_born_solver_mode"] == "hfb_limit"
    assert reference.diagnostics["max_second_born_memory_norm"] == 0.0
    assert reference.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-12
    for observable_name in ("density", "current_x", "current_y", "energy"):
        for hfb_series, reference_series in zip(
            hfb.observables[observable_name].series,
            reference.observables[observable_name].series,
            strict=True,
        ):
            assert hfb_series.values.tolist() == pytest.approx(reference_series.values.tolist(), abs=1e-12)


def test_kbe_hfb_k_space_representation_matches_real_space_in_hfb_mode():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.08,
            "amplitude_y": 0.04,
            "frequency": 1.7,
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
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        "adaptive": {"enabled": False},
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-8
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_second_born_reference_k_space_representation_matches_real_space():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.06,
            "amplitude_y": 0.02,
            "frequency": 1.6,
            "phase": 0.1,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -0.8,
            "nearest_neighbor_v": -0.4,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.2,
            "seed_pairing": 0.1,
        },
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 8,
            "tolerance": 1e-6,
            "mixing": 0.5,
        },
        "thermal_branch": {
            "enabled": True,
            "n_tau": 8,
            "max_iterations": 10,
            "mixing": 0.4,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        "adaptive": {"enabled": False},
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["second_born_reference_implementation"] is True
    assert k_space.diagnostics["second_born_contour_mode"] == "full_contour"
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_hfb_k_space_representation_matches_real_space_on_moderate_longer_window():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.08,
            "amplitude_y": 0.03,
            "frequency": 1.7,
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
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        "adaptive": {"enabled": False},
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-8
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_hfb_k_space_representation_matches_real_space_on_longer_window():
    base_config = {
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
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        "adaptive": {"enabled": False},
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-8
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_hfb_k_space_representation_matches_real_space_on_larger_lattice():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 5,
            "ny": 5,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.08,
            "amplitude_y": 0.03,
            "frequency": 1.6,
            "phase": 0.1,
            "center": 0.12,
            "width": 0.12,
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
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["max_equal_time_tdhfb_mismatch"] < 1e-8
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_second_born_reference_k_space_representation_matches_real_space_on_larger_system_longer_window():
    base_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 3,
            "ny": 3,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.3, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.03,
            "frequency": 1.4,
            "phase": 0.1,
            "center": 0.15,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -0.8,
            "nearest_neighbor_v": -0.4,
            "pairing_channel": "bond_d",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.2,
            "seed_pairing": 0.08,
        },
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 8,
            "tolerance": 1e-6,
            "mixing": 0.5,
        },
        "thermal_branch": {
            "enabled": True,
            "n_tau": 8,
            "max_iterations": 10,
            "mixing": 0.4,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    real_space = solve_kbe_hfb(SimulationConfig.model_validate(base_config))
    k_space = solve_kbe_hfb(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert k_space.diagnostics["second_born_reference_implementation"] is True
    assert k_space.diagnostics["second_born_contour_mode"] == "full_contour"
    assert k_space.diagnostics["max_lesser_hermiticity_error"] < 1e-8
    assert k_space.diagnostics["max_retarded_equal_time_error"] < 1e-8
    for observable_name in ("density", "energy", "pairing", "pairing_s", "pairing_d"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-8)


def test_kbe_hfb_tracks_local_continuity_equation_in_source_free_normal_state():
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
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

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["continuity_residual_supported"] is True
    assert len(artifacts.diagnostics["continuity_residual_history"]) == artifacts.diagnostics["time_steps"] + 1
    assert artifacts.diagnostics["max_continuity_residual"] == pytest.approx(
        max(artifacts.diagnostics["continuity_residual_history"])
    )
    assert artifacts.diagnostics["max_continuity_residual"] < 1e-11
    assert artifacts.diagnostics["final_continuity_residual"] < 1e-11


def test_kbe_second_born_tracks_conservation_residuals_for_stationary_state(paired_config):
    artifacts = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **paired_config,
                "solver": "kbe_hfb",
                "kbe": {
                    "self_energy": "second_born",
                    "max_fixed_point_iterations": 8,
                    "tolerance": 1e-8,
                    "mixing": 0.5,
                },
            }
        )
    )

    sample_count = artifacts.diagnostics["time_steps"] + 1
    assert len(artifacts.diagnostics["particle_conservation_residual_history"]) == sample_count
    assert len(artifacts.diagnostics["energy_work_mismatch_history"]) == sample_count
    assert len(artifacts.diagnostics["energy_conservation_residual_history"]) == sample_count
    assert artifacts.diagnostics["max_particle_conservation_residual"] < 1e-10
    assert artifacts.diagnostics["final_particle_conservation_residual"] < 1e-10
    assert artifacts.diagnostics["max_energy_work_mismatch"] < 1e-8
    assert artifacts.diagnostics["final_energy_work_mismatch"] < 1e-8


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
    assert second_born.diagnostics["second_born_solver_mode"] == "two_time_causal_marching"
    assert second_born.diagnostics["max_second_born_memory_norm"] > 0.0
    assert second_born.diagnostics["max_second_born_collision_norm"] > 0.0
    assert second_born.diagnostics["max_equal_time_tdhfb_mismatch"] > 1e-6
    assert second_born.diagnostics["kbe_two_time_reconstruction"] == "causal_marching"
    assert len(second_born.diagnostics["second_born_iteration_history"]) == second_born.diagnostics["time_steps"]
    assert len(second_born.diagnostics["particle_conservation_residual_history"]) == second_born.diagnostics["time_steps"] + 1
    assert len(second_born.diagnostics["energy_work_mismatch_history"]) == second_born.diagnostics["time_steps"] + 1
    assert second_born.diagnostics["max_equal_time_density_reconstruction_error"] < 1e-10
    assert second_born.diagnostics["max_particle_conservation_residual"] == pytest.approx(
        max(second_born.diagnostics["particle_conservation_residual_history"])
    )
    assert second_born.diagnostics["max_energy_work_mismatch"] == pytest.approx(
        max(second_born.diagnostics["energy_conservation_residual_history"])
    )
    assert second_born.summary_excerpt["max_energy_work_mismatch"] == pytest.approx(
        second_born.diagnostics["max_energy_work_mismatch"]
    )
    assert abs(
        second_born.observables["pairing_d"].series[2].values[-1]
        - hfb.observables["pairing_d"].series[2].values[-1]
    ) > 1e-9
    assert second_born.two_time_green_functions is not None
    assert hfb.two_time_green_functions is not None
    assert np.max(
        np.abs(
            second_born.two_time_green_functions.components["lesser"]
            - hfb.two_time_green_functions.components["lesser"]
        )
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
    assert artifacts.diagnostics["thermal_branch_reference_implementation"] is False
    assert artifacts.diagnostics["thermal_branch_implementation_kind"] == "factorized_hfb"
    assert artifacts.diagnostics["matsubara_grid_shape"] == [9, 8, 8]
    assert artifacts.diagnostics["matsubara_zero_plus_error"] < 1e-8
    assert artifacts.diagnostics["matsubara_beta_minus_error"] < 1e-7
    assert artifacts.diagnostics["mixed_components_included"] is True
    assert artifacts.diagnostics["mixed_grid_shape"][1:] == [9, 8, 8]
    assert artifacts.diagnostics["mixed_right_initial_error"] < 1e-12
    assert artifacts.diagnostics["mixed_left_initial_error"] < 1e-12
    assert artifacts.mixed_green_functions is not None
    assert set(artifacts.mixed_green_functions.components) == {"mixed_right", "mixed_left"}


def test_kbe_second_born_supports_adaptive_history_against_fixed_reference():
    fixed_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.2,
            "amplitude_y": 0.0,
            "frequency": 1.0,
            "center": 0.2,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "kbe": {
            "self_energy": "second_born",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-4,
            "mixing": 0.5,
        },
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 10, "mixing": 0.4},
        "observables": ["density", "energy"],
    }

    fixed = solve_kbe_hfb(SimulationConfig.model_validate(fixed_config))
    adaptive = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **fixed_config,
                "adaptive": {
                    "enabled": True,
                    "rtol": 1e-3,
                    "atol": 1e-5,
                    "min_dt": 0.025,
                    "max_dt": 0.1,
                },
            }
        )
    )

    assert adaptive.diagnostics["time_grid_mode"] == "adaptive"
    assert adaptive.diagnostics["accepted_time_steps"] < adaptive.diagnostics["requested_time_steps"]
    assert adaptive.diagnostics["second_born_solver_mode"] == "two_time_causal_marching"
    assert adaptive.diagnostics["second_born_contour_mode"] == "full_contour"
    assert adaptive.diagnostics["second_born_converged"] is True
    assert len(adaptive.diagnostics["second_born_history_integration_order_history"]) == adaptive.diagnostics["time_steps"]
    assert adaptive.diagnostics["second_born_history_integration_max_order"] >= 1
    assert adaptive.diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert adaptive.diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert adaptive.summary_excerpt["time_grid_mode"] == "adaptive"
    assert adaptive.summary_excerpt["mixed_branch_factorized_difference"] > 0.0

    assert adaptive.summary_excerpt["final_density"] == pytest.approx(
        fixed.summary_excerpt["final_density"],
        abs=5e-4,
    )
    assert adaptive.summary_excerpt["final_energy"] == pytest.approx(
        fixed.summary_excerpt["final_energy"],
        abs=2e-3,
    )


def test_kbe_second_born_builds_correlated_thermal_and_mixed_branches():
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
            "drive": {
                "amplitude_x": 0.0,
                "amplitude_y": 0.0,
                "frequency": 0.0,
                "center": 0.0,
                "width": 1.0,
            },
            "interaction": {
                "onsite_u": -1.5,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
            "kbe": {
                "self_energy": "second_born",
                "max_fixed_point_iterations": 12,
                "tolerance": 1e-4,
                "mixing": 0.5,
            },
            "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 10, "mixing": 0.4},
            "observables": ["density", "energy"],
        }
    )

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["thermal_branch_enabled"] is True
    assert artifacts.diagnostics["thermal_branch_correlated"] is True
    assert artifacts.diagnostics["kbe_reference_solver_available"] is False
    assert artifacts.diagnostics["second_born_reference_implementation"] is False
    assert artifacts.diagnostics["second_born_implementation_kind"] == "heuristic_prototype"
    assert artifacts.diagnostics["thermal_branch_converged"] is True
    assert artifacts.diagnostics["thermal_branch_iterations"] > 1
    assert artifacts.diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert artifacts.diagnostics["thermal_branch_density_shift"] >= 0.0
    assert artifacts.diagnostics["thermal_branch_reference_implementation"] is False
    assert artifacts.diagnostics["thermal_branch_implementation_kind"] == "heuristic_prototype"
    assert artifacts.diagnostics["matsubara_zero_plus_error"] < 1e-12
    assert artifacts.diagnostics["matsubara_beta_minus_error"] < 1e-12
    assert artifacts.diagnostics["mixed_components_included"] is True
    assert artifacts.diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert artifacts.diagnostics["mixed_right_factorized_difference"] > 0.0
    assert artifacts.diagnostics["mixed_left_factorized_difference"] > 0.0
    assert artifacts.diagnostics["max_mixed_branch_memory_norm"] > 0.0
    assert artifacts.diagnostics["mixed_branch_reference_implementation"] is False
    assert artifacts.diagnostics["mixed_branch_implementation_kind"] == "heuristic_prototype"
    assert artifacts.diagnostics["second_born_contour_terms_included"] is True
    assert artifacts.diagnostics["second_born_contour_mode"] == "full_contour"
    assert artifacts.diagnostics["second_born_converged"] is True
    assert artifacts.thermal_branch_green_functions is not None
    assert artifacts.mixed_green_functions is not None


def test_kbe_second_born_reference_supports_adaptive_history_against_fixed_reference():
    fixed_config = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.2,
            "amplitude_y": 0.0,
            "frequency": 1.0,
            "center": 0.2,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-5,
            "mixing": 0.5,
        },
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
        "observables": ["density", "energy"],
    }

    fixed = solve_kbe_hfb(SimulationConfig.model_validate(fixed_config))
    adaptive = solve_kbe_hfb(
        SimulationConfig.model_validate(
            {
                **fixed_config,
                "adaptive": {
                    "enabled": True,
                    "rtol": 1e-3,
                    "atol": 1e-5,
                    "min_dt": 0.025,
                    "max_dt": 0.1,
                },
            }
        )
    )

    assert adaptive.diagnostics["time_grid_mode"] == "adaptive"
    assert adaptive.diagnostics["accepted_time_steps"] < adaptive.diagnostics["requested_time_steps"]
    assert adaptive.diagnostics["second_born_solver_mode"] == "gkba_causal_marching"
    assert adaptive.diagnostics["second_born_contour_mode"] == "full_contour"
    assert adaptive.diagnostics["second_born_reference_scope"] == "equal_time_gkba_full_contour"
    assert adaptive.diagnostics["second_born_converged"] is True
    assert adaptive.diagnostics["thermal_branch_reference_implementation"] is True
    assert adaptive.diagnostics["mixed_branch_reference_implementation"] is True
    assert adaptive.diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert adaptive.diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert adaptive.summary_excerpt["time_grid_mode"] == "adaptive"
    assert adaptive.summary_excerpt["thermal_branch_factorized_difference"] > 0.0
    assert adaptive.summary_excerpt["mixed_branch_factorized_difference"] > 0.0

    assert adaptive.summary_excerpt["final_density"] == pytest.approx(
        fixed.summary_excerpt["final_density"],
        abs=2e-3,
    )
    assert adaptive.summary_excerpt["final_energy"] == pytest.approx(
        fixed.summary_excerpt["final_energy"],
        abs=5e-3,
    )


def test_kbe_second_born_reference_k_space_supports_adaptive_history_against_fixed_reference():
    fixed = solve_kbe_hfb(_k_space_second_born_reference_full_contour_config())
    adaptive = solve_kbe_hfb(
        _k_space_second_born_reference_full_contour_config(
            adaptive={
                "enabled": True,
                "rtol": 1e-3,
                "atol": 1e-5,
                "min_dt": 0.025,
                "max_dt": 0.1,
            },
        )
    )

    assert adaptive.diagnostics["solver_representation"] == "k_space"
    assert adaptive.diagnostics["time_grid_mode"] == "adaptive"
    assert adaptive.diagnostics["accepted_time_steps"] < adaptive.diagnostics["requested_time_steps"]
    assert adaptive.diagnostics["second_born_reference_implementation"] is True
    assert adaptive.diagnostics["second_born_contour_mode"] == "full_contour"
    assert adaptive.diagnostics["second_born_reference_scope"] == "equal_time_gkba_full_contour"
    assert adaptive.diagnostics["second_born_kspace_block_path"] is True
    assert adaptive.diagnostics["second_born_solver_mode"] == "gkba_causal_marching_kspace_blocks"
    assert adaptive.diagnostics["second_born_converged"] is True
    assert adaptive.diagnostics["thermal_branch_reference_implementation"] is True
    assert adaptive.diagnostics["mixed_branch_reference_implementation"] is True
    assert adaptive.diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert adaptive.diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert adaptive.summary_excerpt["time_grid_mode"] == "adaptive"
    assert adaptive.summary_excerpt["thermal_branch_factorized_difference"] > 0.0
    assert adaptive.summary_excerpt["mixed_branch_factorized_difference"] > 0.0

    assert adaptive.summary_excerpt["final_density"] == pytest.approx(
        fixed.summary_excerpt["final_density"],
        abs=2e-3,
    )
    assert adaptive.summary_excerpt["final_energy"] == pytest.approx(
        fixed.summary_excerpt["final_energy"],
        abs=5e-3,
    )


def test_kbe_second_born_reference_builds_correlated_thermal_and_mixed_branches():
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
            "drive": {
                "amplitude_x": 0.0,
                "amplitude_y": 0.0,
                "frequency": 0.0,
                "center": 0.0,
                "width": 1.0,
            },
            "interaction": {
                "onsite_u": -1.2,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
            "kbe": {
                "self_energy": "second_born_reference",
                "max_fixed_point_iterations": 10,
                "tolerance": 1e-5,
                "mixing": 0.5,
            },
            "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
            "observables": ["density", "energy"],
        }
    )

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["kbe_reference_solver_available"] is True
    assert artifacts.diagnostics["second_born_reference_implementation"] is True
    assert artifacts.diagnostics["second_born_implementation_kind"] == "gkba_local_nambu_reference"
    assert artifacts.diagnostics["second_born_contour_terms_included"] is True
    assert artifacts.diagnostics["second_born_contour_mode"] == "full_contour"
    assert artifacts.diagnostics["second_born_reference_scope"] == "equal_time_gkba_full_contour"
    assert artifacts.diagnostics["thermal_branch_enabled"] is True
    assert artifacts.diagnostics["thermal_branch_correlated"] is True
    assert artifacts.diagnostics["thermal_branch_converged"] is True
    assert artifacts.diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert artifacts.diagnostics["thermal_branch_reference_implementation"] is True
    assert artifacts.diagnostics["thermal_branch_implementation_kind"] == "gkba_local_nambu_reference"
    assert artifacts.diagnostics["mixed_components_included"] is True
    assert artifacts.diagnostics["mixed_branch_converged"] is True
    assert artifacts.diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert artifacts.diagnostics["mixed_branch_reference_implementation"] is True
    assert artifacts.diagnostics["mixed_branch_implementation_kind"] == "gkba_local_nambu_reference"
    assert artifacts.diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert artifacts.diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert artifacts.thermal_branch_green_functions is not None
    assert artifacts.mixed_green_functions is not None


def test_kbe_second_born_reference_reports_reference_diagnostics_under_drive():
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "open",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.2, "dt": 0.05},
            "drive": {
                "amplitude_x": 0.6,
                "amplitude_y": 0.3,
                "frequency": 2.7,
                "phase": 0.35,
                "center": 0.1,
                "width": 0.1,
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
            "kbe": {
                "self_energy": "second_born_reference",
                "max_fixed_point_iterations": 10,
                "tolerance": 1e-7,
                "mixing": 0.5,
            },
            "observables": ["density", "current_x", "current_y"],
        }
    )

    artifacts = solve_kbe_hfb(config)

    assert artifacts.diagnostics["kbe_reference_solver_available"] is True
    assert artifacts.diagnostics["second_born_reference_implementation"] is True
    assert artifacts.diagnostics["second_born_implementation_kind"] == "gkba_local_nambu_reference"
    assert artifacts.diagnostics["second_born_solver_mode"] == "gkba_causal_marching"
    assert artifacts.diagnostics["second_born_contour_mode"] == "keldysh_only"
    assert artifacts.diagnostics["second_born_explicit_self_energy"] is True
    assert artifacts.diagnostics["second_born_reference_scope"] == "equal_time_gkba"
    assert artifacts.diagnostics["max_second_born_memory_norm"] > 0.0
    assert artifacts.diagnostics["max_second_born_collision_norm"] > 0.0
    assert artifacts.diagnostics["kbe_two_time_reconstruction"] == "gkba_causal_marching"
    assert len(artifacts.diagnostics["second_born_iteration_history"]) == artifacts.diagnostics["time_steps"]
    assert artifacts.two_time_green_functions is not None
