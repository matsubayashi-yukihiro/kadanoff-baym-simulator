import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.noninteracting import solve

pytestmark = pytest.mark.physics_invariant


def test_noninteracting_solver_conserves_particle_number_without_drive():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.4, "dt": 0.1},
        drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "width": 1.0},
    )

    artifacts = solve(config)

    assert set(artifacts.observables) == {"density", "current_x", "current_y", "energy", "vector_potential"}
    assert artifacts.diagnostics["particle_number_drift"] < 1e-10
    assert artifacts.diagnostics["energy_drift"] < 1e-10
    assert artifacts.diagnostics["max_hermiticity_error"] < 1e-12


def test_noninteracting_solver_respects_save_every_and_keeps_final_point():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.5, "dt": 0.1, "save_every": 2},
        drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "width": 1.0},
    )

    artifacts = solve(config)
    density = artifacts.observables["density"]

    assert density.time.tolist() == [0.0, 0.2, 0.4, 0.5]
    assert artifacts.diagnostics["saved_samples"] == 4
    assert all(len(series.values) == 4 for series in density.series)


def test_noninteracting_solver_tracks_energy_work_balance_under_drive():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.6, "dt": 0.01},
        drive={
            "amplitude_x": 0.3,
            "amplitude_y": 0.15,
            "frequency": 2.0,
            "phase": 0.25,
            "center": 0.3,
            "width": 0.12,
        },
    )

    artifacts = solve(config)

    assert artifacts.diagnostics["energy_drift"] > 1e-3
    assert artifacts.diagnostics["max_energy_work_mismatch"] < 1e-4
    assert artifacts.diagnostics["final_energy_work_mismatch"] < 1e-5


def test_noninteracting_solver_tracks_local_continuity_equation_under_drive():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.4, "dt": 0.05},
        drive={
            "amplitude_x": 0.6,
            "amplitude_y": 0.3,
            "frequency": 2.7,
            "phase": 0.35,
            "center": 0.18,
            "width": 0.09,
        },
    )

    artifacts = solve(config)

    assert len(artifacts.diagnostics["continuity_residual_history"]) == artifacts.diagnostics["time_steps"] + 1
    assert artifacts.diagnostics["max_continuity_residual"] == pytest.approx(
        max(artifacts.diagnostics["continuity_residual_history"])
    )
    assert artifacts.diagnostics["max_continuity_residual"] < 1e-12
    assert artifacts.diagnostics["final_continuity_residual"] < 1e-12


def test_noninteracting_k_space_representation_matches_real_space_under_drive():
    base_config = {
        "solver": "noninteracting",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.25,
            "amplitude_y": 0.1,
            "frequency": 2.4,
            "phase": 0.15,
            "center": 0.2,
            "width": 0.1,
        },
        "observables": ["density", "current_x", "current_y", "energy", "vector_potential"],
    }

    real_space = solve(SimulationConfig.model_validate(base_config))
    k_space = solve(SimulationConfig.model_validate({**base_config, "representation": "k_space"}))

    assert k_space.diagnostics["solver_representation"] == "k_space"
    assert real_space.observables["density"].time.tolist() == k_space.observables["density"].time.tolist()
    for observable_name in ("density", "current_x", "current_y", "energy", "vector_potential"):
        for real_series, k_series in zip(
            real_space.observables[observable_name].series,
            k_space.observables[observable_name].series,
            strict=True,
        ):
            assert real_series.values.tolist() == pytest.approx(k_series.values.tolist(), abs=1e-10)
