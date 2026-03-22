import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.benchmarks import (
    build_benchmark_trajectory,
    build_convergence_table,
    exact_diagonalization_trajectory,
    run_exact_diagonalization_benchmark,
    summarize_trajectory_error,
)
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.noninteracting import solve as solve_noninteracting
from backend.app.solvers.tdhfb import solve as solve_tdhfb

pytestmark = pytest.mark.physics_benchmark


def _normal_state_config(*, dt: float) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "noninteracting",
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "open",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.4, "dt": dt},
            "drive": {
                "amplitude_x": 0.6,
                "amplitude_y": 0.3,
                "frequency": 2.7,
                "phase": 0.35,
                "center": 0.18,
                "width": 0.09,
            },
            "interaction": {
                "onsite_u": 0.0,
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


def _weak_interaction_benchmark_config(
    *,
    solver: str,
    dt: float,
    t_final: float,
    onsite_u: float = -0.6,
    amplitude_x: float = 0.5,
    amplitude_y: float = 0.2,
) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": solver,
            "lattice": {
                "nx": 2,
                "ny": 2,
                "boundary": "open",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": t_final, "dt": dt},
            "drive": {
                "amplitude_x": amplitude_x,
                "amplitude_y": amplitude_y,
                "frequency": 2.6,
                "phase": 0.3,
                "center": 0.18,
                "width": 0.12,
            },
            "interaction": {
                "onsite_u": onsite_u,
                "nearest_neighbor_v": 0.0,
                "pairing_channel": "none",
            },
            "initial_state": {
                "filling": 0.25,
                "temperature": 0.0,
                "seed_pairing": 0.0,
            },
            "observables": ["density", "current_x", "current_y", "energy"],
            "adaptive": {"enabled": False},
        }
    )


def _second_born_short_window_config(
    *,
    dt: float,
    memory_window: int | None = None,
    adaptive: dict[str, float | bool] | None = None,
) -> SimulationConfig:
    payload: dict[str, object] = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "open",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": dt},
        "drive": {
            "amplitude_x": 0.4,
            "amplitude_y": 0.12,
            "frequency": 3.0,
            "phase": 0.35,
            "center": 0.2,
            "width": 0.1,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.25,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "kbe": {
            "self_energy": "second_born",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-7,
            "mixing": 0.5,
        },
        "observables": ["density", "current_x", "current_y"],
    }
    if memory_window is not None:
        payload["kbe"] = {**payload["kbe"], "memory_window": memory_window}
    payload["adaptive"] = adaptive if adaptive is not None else {"enabled": False}
    return SimulationConfig.model_validate(payload)


def _second_born_reference_short_window_config(
    *,
    dt: float,
    adaptive: dict[str, float | bool] | None = None,
) -> SimulationConfig:
    payload: dict[str, object] = {
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "open",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": dt},
        "drive": {
            "amplitude_x": 0.4,
            "amplitude_y": 0.12,
            "frequency": 3.0,
            "phase": 0.35,
            "center": 0.2,
            "width": 0.1,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.25,
            "temperature": 0.2,
            "seed_pairing": 0.0,
        },
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-6,
            "mixing": 0.5,
        },
        "thermal_branch": {
            "enabled": True,
            "n_tau": 8,
            "max_iterations": 12,
            "mixing": 0.4,
        },
        "observables": ["density", "current_x", "current_y"],
    }
    payload["adaptive"] = adaptive if adaptive is not None else {"enabled": False}
    return SimulationConfig.model_validate(payload)


def _second_born_thermal_branch_config() -> SimulationConfig:
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
            "initial_state": {
                "filling": 0.5,
                "temperature": 0.2,
                "seed_pairing": 0.0,
            },
            "kbe": {
                "self_energy": "second_born",
                "max_fixed_point_iterations": 12,
                "tolerance": 1e-4,
                "mixing": 0.5,
            },
            "thermal_branch": {
                "enabled": True,
                "n_tau": 8,
                "max_iterations": 10,
                "mixing": 0.4,
            },
            "observables": ["density", "current_x", "current_y"],
            "adaptive": {"enabled": False},
        }
    )


def _second_born_reference_thermal_branch_config() -> SimulationConfig:
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
            "initial_state": {
                "filling": 0.5,
                "temperature": 0.2,
                "seed_pairing": 0.0,
            },
            "equilibrium": {
                "method": "hfb",
                "allow_approximation_mismatch": True,
            },
            "kbe": {
                "self_energy": "second_born_reference",
                "max_fixed_point_iterations": 10,
                "tolerance": 1e-6,
                "mixing": 0.5,
            },
            "thermal_branch": {
                "enabled": True,
                "n_tau": 8,
                "max_iterations": 12,
                "mixing": 0.4,
            },
            "observables": ["density", "current_x", "current_y"],
            "adaptive": {"enabled": False},
        }
    )


def _observable_trajectory(artifacts, observable_name: str, *, label: str, series_index: int = 0):
    observable = artifacts.observables[observable_name]
    return build_benchmark_trajectory(
        label,
        times=observable.time,
        values=observable.series[series_index].values,
    )


def test_exact_diagonalization_matches_noninteracting_solver_in_normal_limit():
    config = _normal_state_config(dt=0.05)

    exact = run_exact_diagonalization_benchmark(config)
    artifacts = solve_noninteracting(config)

    assert exact.times.tolist() == artifacts.observables["density"].time.tolist()
    assert artifacts.observables["density"].series[0].values.tolist() == pytest.approx(exact.density_mean.tolist(), abs=1e-12)
    assert artifacts.observables["density"].series[1].values.tolist() == pytest.approx(exact.density_min.tolist(), abs=1e-12)
    assert artifacts.observables["density"].series[2].values.tolist() == pytest.approx(exact.density_max.tolist(), abs=1e-12)
    assert artifacts.observables["current_x"].series[0].values.tolist() == pytest.approx(exact.current_x.tolist(), abs=1e-12)
    assert artifacts.observables["current_y"].series[0].values.tolist() == pytest.approx(exact.current_y.tolist(), abs=1e-12)


def test_noninteracting_solver_shows_dt_convergence_against_exact_diagonalization_reference():
    coarse_config = _normal_state_config(dt=0.1)
    fine_config = _normal_state_config(dt=0.05)

    coarse_artifacts = solve_noninteracting(coarse_config)
    fine_artifacts = solve_noninteracting(fine_config)
    coarse_reference = run_exact_diagonalization_benchmark(coarse_config, integration_dt=0.0125)
    fine_reference = run_exact_diagonalization_benchmark(fine_config, integration_dt=0.0125)

    coarse_error = np.max(
        np.abs(np.asarray(coarse_artifacts.observables["current_x"].series[0].values) - coarse_reference.current_x)
    )
    fine_error = np.max(
        np.abs(np.asarray(fine_artifacts.observables["current_x"].series[0].values) - fine_reference.current_x)
    )

    assert coarse_error > 1e-6
    assert fine_error < coarse_error
    assert fine_error < 0.3 * coarse_error


def test_tdhfb_and_kbe_hfb_track_exact_diagonalization_for_short_time_weak_interaction():
    tdhfb_config = SimulationConfig.model_validate(
        {
            "solver": "tdhfb",
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
            "observables": ["density", "current_x", "current_y", "energy"],
            "adaptive": {"enabled": False},
        }
    )
    kbe_config = SimulationConfig.model_validate({**tdhfb_config.model_dump(mode="json"), "solver": "kbe_hfb"})

    exact = run_exact_diagonalization_benchmark(tdhfb_config, integration_dt=0.0125)
    tdhfb = solve_tdhfb(tdhfb_config)
    kbe = solve_kbe_hfb(kbe_config)

    tdhfb_current_x_error = np.max(
        np.abs(np.asarray(tdhfb.observables["current_x"].series[0].values) - exact.current_x)
    )
    tdhfb_current_y_error = np.max(
        np.abs(np.asarray(tdhfb.observables["current_y"].series[0].values) - exact.current_y)
    )
    kbe_current_x_error = np.max(
        np.abs(np.asarray(kbe.observables["current_x"].series[0].values) - exact.current_x)
    )
    kbe_current_y_error = np.max(
        np.abs(np.asarray(kbe.observables["current_y"].series[0].values) - exact.current_y)
    )

    assert np.asarray(tdhfb.observables["density"].series[0].values).tolist() == pytest.approx(
        exact.density_mean.tolist(),
        abs=1e-12,
    )
    assert np.asarray(kbe.observables["density"].series[0].values).tolist() == pytest.approx(
        exact.density_mean.tolist(),
        abs=1e-12,
    )
    assert tdhfb_current_x_error < 1e-3
    assert tdhfb_current_y_error < 1e-3
    assert kbe_current_x_error < 1e-3
    assert kbe_current_y_error < 1e-3


def test_tdhfb_and_kbe_hfb_track_exact_diagonalization_on_longer_window_weak_interaction():
    tdhfb_config = _weak_interaction_benchmark_config(solver="tdhfb", dt=0.05, t_final=0.4)
    kbe_config = _weak_interaction_benchmark_config(solver="kbe_hfb", dt=0.05, t_final=0.4)

    exact = run_exact_diagonalization_benchmark(tdhfb_config, integration_dt=0.01)
    tdhfb = solve_tdhfb(tdhfb_config)
    kbe = solve_kbe_hfb(kbe_config)

    density_reference = exact_diagonalization_trajectory(exact, "density")
    current_x_reference = exact_diagonalization_trajectory(exact, "current_x")
    current_y_reference = exact_diagonalization_trajectory(exact, "current_y")

    tdhfb_density_error = summarize_trajectory_error(
        density_reference,
        _observable_trajectory(tdhfb, "density", label="tdhfb"),
    )
    tdhfb_current_x_error = summarize_trajectory_error(
        current_x_reference,
        _observable_trajectory(tdhfb, "current_x", label="tdhfb"),
    )
    tdhfb_current_y_error = summarize_trajectory_error(
        current_y_reference,
        _observable_trajectory(tdhfb, "current_y", label="tdhfb"),
    )
    kbe_density_error = summarize_trajectory_error(
        density_reference,
        _observable_trajectory(kbe, "density", label="kbe_hfb"),
    )
    kbe_current_x_error = summarize_trajectory_error(
        current_x_reference,
        _observable_trajectory(kbe, "current_x", label="kbe_hfb"),
    )
    kbe_current_y_error = summarize_trajectory_error(
        current_y_reference,
        _observable_trajectory(kbe, "current_y", label="kbe_hfb"),
    )

    assert tdhfb_density_error.max_abs_error < 1e-12
    assert kbe_density_error.max_abs_error < 1e-12
    assert tdhfb_current_x_error.max_abs_error < 2e-3
    assert tdhfb_current_y_error.max_abs_error < 1e-3
    assert kbe_current_x_error.max_abs_error < 2e-3
    assert kbe_current_y_error.max_abs_error < 1e-3


def test_tdhfb_and_kbe_hfb_show_dt_convergence_against_longer_window_exact_reference():
    coarse_tdhfb = _weak_interaction_benchmark_config(
        solver="tdhfb",
        dt=0.1,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )
    fine_tdhfb = _weak_interaction_benchmark_config(
        solver="tdhfb",
        dt=0.05,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )
    finer_tdhfb = _weak_interaction_benchmark_config(
        solver="tdhfb",
        dt=0.025,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )
    coarse_kbe = _weak_interaction_benchmark_config(
        solver="kbe_hfb",
        dt=0.1,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )
    fine_kbe = _weak_interaction_benchmark_config(
        solver="kbe_hfb",
        dt=0.05,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )
    finer_kbe = _weak_interaction_benchmark_config(
        solver="kbe_hfb",
        dt=0.025,
        t_final=0.2,
        onsite_u=-0.1,
        amplitude_x=0.4,
        amplitude_y=0.2,
    )

    coarse_exact = run_exact_diagonalization_benchmark(coarse_tdhfb, integration_dt=0.0125)
    fine_exact = run_exact_diagonalization_benchmark(fine_tdhfb, integration_dt=0.0125)
    finer_exact = run_exact_diagonalization_benchmark(finer_tdhfb, integration_dt=0.0125)
    coarse_reference = exact_diagonalization_trajectory(coarse_exact, "current_x")
    fine_reference = exact_diagonalization_trajectory(fine_exact, "current_x")
    finer_reference = exact_diagonalization_trajectory(finer_exact, "current_x")

    coarse_tdhfb_error = summarize_trajectory_error(
        coarse_reference,
        _observable_trajectory(solve_tdhfb(coarse_tdhfb), "current_x", label="tdhfb-coarse"),
    )
    fine_tdhfb_error = summarize_trajectory_error(
        fine_reference,
        _observable_trajectory(solve_tdhfb(fine_tdhfb), "current_x", label="tdhfb-fine"),
    )
    finer_tdhfb_error = summarize_trajectory_error(
        finer_reference,
        _observable_trajectory(solve_tdhfb(finer_tdhfb), "current_x", label="tdhfb-finer"),
    )
    coarse_kbe_error = summarize_trajectory_error(
        coarse_reference,
        _observable_trajectory(solve_kbe_hfb(coarse_kbe), "current_x", label="kbe-coarse"),
    )
    fine_kbe_error = summarize_trajectory_error(
        fine_reference,
        _observable_trajectory(solve_kbe_hfb(fine_kbe), "current_x", label="kbe-fine"),
    )
    finer_kbe_error = summarize_trajectory_error(
        finer_reference,
        _observable_trajectory(solve_kbe_hfb(finer_kbe), "current_x", label="kbe-finer"),
    )

    assert coarse_tdhfb_error.max_abs_error > 1e-4
    assert coarse_tdhfb_error.max_abs_error > fine_tdhfb_error.max_abs_error > finer_tdhfb_error.max_abs_error
    assert finer_tdhfb_error.max_abs_error < 0.25 * coarse_tdhfb_error.max_abs_error
    assert coarse_kbe_error.max_abs_error > 1e-4
    assert coarse_kbe_error.max_abs_error > fine_kbe_error.max_abs_error > finer_kbe_error.max_abs_error
    assert finer_kbe_error.max_abs_error < 0.25 * coarse_kbe_error.max_abs_error


def test_second_born_prototype_remains_comparable_to_exact_benchmark_on_short_window():
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
                "self_energy": "second_born",
                "max_fixed_point_iterations": 10,
                "tolerance": 1e-7,
                "mixing": 0.5,
            },
            "observables": ["density", "current_x", "current_y", "energy"],
            "adaptive": {"enabled": False},
        }
    )

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.0125)
    second_born = solve_kbe_hfb(config)

    current_x_error = np.max(np.abs(np.asarray(second_born.observables["current_x"].series[0].values) - exact.current_x))
    current_y_error = np.max(np.abs(np.asarray(second_born.observables["current_y"].series[0].values) - exact.current_y))
    density_error = np.max(np.abs(np.asarray(second_born.observables["density"].series[0].values) - exact.density_mean))

    assert second_born.diagnostics["second_born_enabled"] is True
    assert second_born.diagnostics["second_born_converged"] is True
    assert current_x_error < 1e-3
    assert current_y_error < 1e-3
    assert density_error < 1e-6


def test_second_born_reference_remains_comparable_to_exact_benchmark_on_short_window():
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
            "observables": ["density", "current_x", "current_y", "energy"],
            "adaptive": {"enabled": False},
        }
    )

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.0125)
    reference = solve_kbe_hfb(config)

    current_x_error = np.max(np.abs(np.asarray(reference.observables["current_x"].series[0].values) - exact.current_x))
    current_y_error = np.max(np.abs(np.asarray(reference.observables["current_y"].series[0].values) - exact.current_y))
    density_error = np.max(np.abs(np.asarray(reference.observables["density"].series[0].values) - exact.density_mean))

    assert reference.diagnostics["second_born_enabled"] is True
    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert current_x_error < 1e-3
    assert current_y_error < 1e-3
    assert density_error < 5e-4


def test_second_born_thermal_branch_remains_close_to_exact_density_benchmark():
    config = _second_born_thermal_branch_config()

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.01)
    second_born = solve_kbe_hfb(config)
    density_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "density"),
        _observable_trajectory(second_born, "density", label="second_born"),
    )
    current_x_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_x"),
        _observable_trajectory(second_born, "current_x", label="second_born"),
    )
    current_y_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_y"),
        _observable_trajectory(second_born, "current_y", label="second_born"),
    )

    assert second_born.diagnostics["thermal_branch_enabled"] is True
    assert second_born.diagnostics["thermal_branch_correlated"] is True
    assert second_born.diagnostics["mixed_components_included"] is True
    assert second_born.diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert second_born.diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert density_error.max_abs_error < 1e-8
    assert current_x_error.max_abs_error < 1e-12
    assert current_y_error.max_abs_error < 1e-12


def test_second_born_reference_thermal_branch_remains_close_to_exact_density_benchmark():
    config = _second_born_reference_thermal_branch_config()

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.01)
    reference = solve_kbe_hfb(config)
    density_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "density"),
        _observable_trajectory(reference, "density", label="second_born_reference"),
    )
    current_x_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_x"),
        _observable_trajectory(reference, "current_x", label="second_born_reference"),
    )
    current_y_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_y"),
        _observable_trajectory(reference, "current_y", label="second_born_reference"),
    )

    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert reference.diagnostics["thermal_branch_reference_implementation"] is True
    assert reference.diagnostics["mixed_branch_reference_implementation"] is True
    assert reference.diagnostics["second_born_contour_mode"] == "full_contour"
    assert density_error.max_abs_error < 5e-3
    assert current_x_error.max_abs_error < 5e-3
    assert current_y_error.max_abs_error < 5e-3


def test_second_born_reference_k_space_thermal_branch_remains_close_to_exact_density_benchmark():
    config = SimulationConfig.model_validate(
        {
            **_second_born_reference_thermal_branch_config().model_dump(mode="json"),
            "representation": "k_space",
        }
    )

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.01)
    reference = solve_kbe_hfb(config)
    density_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "density"),
        _observable_trajectory(reference, "density", label="second_born_reference_k_space"),
    )
    current_x_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_x"),
        _observable_trajectory(reference, "current_x", label="second_born_reference_k_space"),
    )
    current_y_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_y"),
        _observable_trajectory(reference, "current_y", label="second_born_reference_k_space"),
    )

    assert reference.diagnostics["solver_representation"] == "k_space"
    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert reference.diagnostics["thermal_branch_reference_implementation"] is True
    assert reference.diagnostics["mixed_branch_reference_implementation"] is True
    assert reference.diagnostics["second_born_contour_mode"] == "full_contour"
    assert density_error.max_abs_error < 5e-3
    assert current_x_error.max_abs_error < 5e-3
    assert current_y_error.max_abs_error < 5e-3


def test_second_born_reference_k_space_thermal_branch_longer_window_remains_close_to_exact_density_benchmark():
    config = SimulationConfig.model_validate(
        {
            **_second_born_reference_thermal_branch_config().model_dump(mode="json"),
            "representation": "k_space",
            "time": {"t_final": 0.3, "dt": 0.05},
        }
    )

    exact = run_exact_diagonalization_benchmark(config, integration_dt=0.01)
    reference = solve_kbe_hfb(config)
    density_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "density"),
        _observable_trajectory(reference, "density", label="second_born_reference_k_space_longer"),
    )
    current_x_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_x"),
        _observable_trajectory(reference, "current_x", label="second_born_reference_k_space_longer"),
    )
    current_y_error = summarize_trajectory_error(
        exact_diagonalization_trajectory(exact, "current_y"),
        _observable_trajectory(reference, "current_y", label="second_born_reference_k_space_longer"),
    )

    assert reference.diagnostics["solver_representation"] == "k_space"
    assert reference.diagnostics["second_born_reference_implementation"] is True
    assert reference.diagnostics["thermal_branch_reference_implementation"] is True
    assert reference.diagnostics["mixed_branch_reference_implementation"] is True
    assert reference.diagnostics["second_born_contour_mode"] == "full_contour"
    assert density_error.max_abs_error < 5e-3
    assert current_x_error.max_abs_error < 5e-3
    assert current_y_error.max_abs_error < 5e-3


def test_second_born_adaptive_tolerance_improves_final_error_against_fine_fixed_reference():
    reference = solve_kbe_hfb(_second_born_short_window_config(dt=0.0125))
    loose = solve_kbe_hfb(
        _second_born_short_window_config(
            dt=0.1,
            adaptive={
                "enabled": True,
                "rtol": 1e-2,
                "atol": 1e-4,
                "min_dt": 0.025,
                "max_dt": 0.1,
            },
        )
    )
    tight = solve_kbe_hfb(
        _second_born_short_window_config(
            dt=0.1,
            adaptive={
                "enabled": True,
                "rtol": 1e-4,
                "atol": 1e-6,
                "min_dt": 0.0125,
                "max_dt": 0.1,
            },
        )
    )

    reference_current_x = _observable_trajectory(reference, "current_x", label="reference")
    loose_error = summarize_trajectory_error(
        reference_current_x,
        _observable_trajectory(loose, "current_x", label="adaptive-loose"),
    )
    tight_error = summarize_trajectory_error(
        reference_current_x,
        _observable_trajectory(tight, "current_x", label="adaptive-tight"),
    )

    assert loose.diagnostics["time_grid_mode"] == "adaptive"
    assert tight.diagnostics["time_grid_mode"] == "adaptive"
    assert tight.diagnostics["accepted_time_steps"] > loose.diagnostics["accepted_time_steps"]
    assert tight_error.final_abs_error < loose_error.final_abs_error
    assert tight_error.final_abs_error < 0.5 * loose_error.final_abs_error


def test_second_born_reference_adaptive_tolerance_improves_final_error_against_fine_fixed_reference():
    reference = solve_kbe_hfb(_second_born_reference_short_window_config(dt=0.0125))
    loose = solve_kbe_hfb(
        _second_born_reference_short_window_config(
            dt=0.1,
            adaptive={
                "enabled": True,
                "rtol": 1e-2,
                "atol": 1e-4,
                "min_dt": 0.025,
                "max_dt": 0.1,
            },
        )
    )
    tight = solve_kbe_hfb(
        _second_born_reference_short_window_config(
            dt=0.1,
            adaptive={
                "enabled": True,
                "rtol": 1e-4,
                "atol": 1e-6,
                "min_dt": 0.0125,
                "max_dt": 0.1,
            },
        )
    )

    reference_current_x = _observable_trajectory(reference, "current_x", label="reference")
    loose_error = summarize_trajectory_error(
        reference_current_x,
        _observable_trajectory(loose, "current_x", label="adaptive-loose"),
    )
    tight_error = summarize_trajectory_error(
        reference_current_x,
        _observable_trajectory(tight, "current_x", label="adaptive-tight"),
    )

    assert loose.diagnostics["time_grid_mode"] == "adaptive"
    assert tight.diagnostics["time_grid_mode"] == "adaptive"
    assert tight.diagnostics["accepted_time_steps"] > loose.diagnostics["accepted_time_steps"]
    assert tight_error.final_abs_error < loose_error.final_abs_error


def test_second_born_memory_window_rows_converge_to_full_memory_reference():
    reference = solve_kbe_hfb(_second_born_short_window_config(dt=0.05))
    current_x_reference = _observable_trajectory(reference, "current_x", label="full-memory")
    rows = build_convergence_table(
        current_x_reference,
        [
            _observable_trajectory(
                solve_kbe_hfb(_second_born_short_window_config(dt=0.05, memory_window=window)),
                "current_x",
                label=f"memory_window={window}",
            )
            for window in (1, 2, 4, 8)
        ],
    )

    assert [row.label for row in rows] == [
        "memory_window=1",
        "memory_window=2",
        "memory_window=4",
        "memory_window=8",
    ]
    assert rows[0].max_abs_error > rows[1].max_abs_error > rows[2].max_abs_error > rows[3].max_abs_error
    assert rows[3].max_abs_error == pytest.approx(0.0, abs=1e-12)
