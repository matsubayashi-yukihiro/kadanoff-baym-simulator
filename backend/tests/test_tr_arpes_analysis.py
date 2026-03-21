import math

import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kspace_analysis import (
    build_momentum_selection,
    compute_k_resolved_trarpes,
    parse_energy_grid,
)
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
from backend.app.solvers.tdhfb import solve as solve_tdhfb

pytestmark = pytest.mark.physics_benchmark


def _periodic_kbe_config() -> SimulationConfig:
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
            "time": {"t_final": 2.0, "dt": 0.05},
        }
    )


def _momentum_mode(nx: int, ny: int, grid_index_x: int, grid_index_y: int) -> np.ndarray:
    coordinates = np.asarray([(index % nx, index // nx) for index in range(nx * ny)], dtype=np.float64)
    kx = 2.0 * math.pi * grid_index_x / nx
    ky = 2.0 * math.pi * grid_index_y / ny
    phase = coordinates[:, 0] * kx + coordinates[:, 1] * ky
    return np.exp(-1j * phase) / math.sqrt(nx * ny)


def _peak_energy(intensity: np.ndarray, energy_grid: np.ndarray, k_index: int) -> float:
    return float(energy_grid[int(np.argmax(intensity[k_index]))])


def _run_derived_hfb_config(*, representation: str) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "representation": representation,
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
            "kbe": {"self_energy": "hfb"},
            "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        }
    )


def _run_derived_second_born_reference_config(*, representation: str) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "representation": representation,
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
                "onsite_u": -0.6,
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
                "max_fixed_point_iterations": 8,
                "tolerance": 1e-6,
                "mixing": 0.35,
            },
            "thermal_branch": {
                "enabled": True,
                "n_tau": 8,
                "max_iterations": 8,
                "mixing": 0.4,
            },
            "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
        }
    )


def _run_derived_tdhfb_config(*, representation: str) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "solver": "tdhfb",
            "representation": representation,
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


def test_trarpes_probe_width_tradeoff_preserves_delay_resolution():
    config = _periodic_kbe_config()
    selection = build_momentum_selection(config, k_path=None, k_grid={"kind": "discrete_bz"})
    energy_grid = parse_energy_grid({"min": -2.0, "max": 0.2, "count": 177}, config=config)
    times = np.linspace(0.0, 2.0, 41, dtype=np.float64)

    site_count = config.lattice.nx * config.lattice.ny
    nambu_dimension = 2 * site_count
    lesser = np.zeros((times.size, times.size, nambu_dimension, nambu_dimension), dtype=np.complex128)

    gamma_mode = _momentum_mode(config.lattice.nx, config.lattice.ny, 0, 0)
    projector = np.outer(gamma_mode, gamma_mode.conjugate())
    packet_energy = -0.8
    packet_center = 0.7
    delayed_probe_center = 1.4
    packet_width = 0.12

    envelope = np.exp(-0.5 * ((times - packet_center) / packet_width) ** 2)
    for row_index, time_row in enumerate(times):
        for column_index, time_col in enumerate(times):
            lesser[row_index, column_index, :site_count, :site_count] = (
                1j
                * envelope[row_index]
                * envelope[column_index]
                * np.exp(-1j * packet_energy * (time_row - time_col))
                * projector
            )

    gamma_index = next(
        index
        for index, point in enumerate(selection.points)
        if point.grid_index_x == 0 and point.grid_index_y == 0
    )
    narrow_early = compute_k_resolved_trarpes(
        lesser=lesser,
        times=times,
        config=config,
        momentum_selection=selection,
        energy_grid=energy_grid,
        probe_center=packet_center,
        probe_width=0.12,
        broadening=0.05,
    )
    narrow_delayed = compute_k_resolved_trarpes(
        lesser=lesser,
        times=times,
        config=config,
        momentum_selection=selection,
        energy_grid=energy_grid,
        probe_center=delayed_probe_center,
        probe_width=0.12,
        broadening=0.05,
    )
    broad_early = compute_k_resolved_trarpes(
        lesser=lesser,
        times=times,
        config=config,
        momentum_selection=selection,
        energy_grid=energy_grid,
        probe_center=packet_center,
        probe_width=0.45,
        broadening=0.05,
    )
    broad_delayed = compute_k_resolved_trarpes(
        lesser=lesser,
        times=times,
        config=config,
        momentum_selection=selection,
        energy_grid=energy_grid,
        probe_center=delayed_probe_center,
        probe_width=0.45,
        broadening=0.05,
    )

    narrow_peak = _peak_energy(np.asarray(narrow_early["intensity"]), energy_grid, gamma_index)
    narrow_matched_weight = float(narrow_early["occupied_weight"][gamma_index])
    narrow_delayed_weight = float(narrow_delayed["occupied_weight"][gamma_index])
    broad_matched_weight = float(broad_early["occupied_weight"][gamma_index])
    broad_delayed_weight = float(broad_delayed["occupied_weight"][gamma_index])

    delay_axis_coverage = 1.0 - (narrow_delayed_weight / narrow_matched_weight)
    probe_width_resolution_tradeoff = (
        broad_delayed_weight / broad_matched_weight
    ) - (
        narrow_delayed_weight / narrow_matched_weight
    )

    assert narrow_peak == pytest.approx(0.125, abs=1e-12)
    assert delay_axis_coverage > 0.99
    assert probe_width_resolution_tradeoff > 0.05


def test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_sources():
    params = {"min": -4.0, "max": 4.0, "count": 61}
    results: dict[str, dict[str, object]] = {}
    for representation in ("real_space", "k_space"):
        config = _run_derived_hfb_config(representation=representation)
        artifacts = solve_kbe_hfb(config)
        assert artifacts.two_time_green_functions is not None

        lesser = artifacts.two_time_green_functions.components["lesser"]
        times = artifacts.two_time_green_functions.times
        selection = build_momentum_selection(config, k_path=None, k_grid={"kind": "discrete_bz"})
        energy_grid = parse_energy_grid(params, config=config)
        payload = compute_k_resolved_trarpes(
            lesser=lesser,
            times=times,
            config=config,
            momentum_selection=selection,
            energy_grid=energy_grid,
            probe_center=0.1,
            probe_width=0.08,
            broadening=0.08,
        )
        results[representation] = {
            "selection": selection,
            "intensity": np.asarray(payload["intensity"], dtype=float),
            "occupied_weight": np.asarray(payload["occupied_weight"], dtype=float),
        }

    real_intensity = results["real_space"]["intensity"]
    k_intensity = results["k_space"]["intensity"]
    real_weight = results["real_space"]["occupied_weight"]
    k_weight = results["k_space"]["occupied_weight"]
    selection = results["real_space"]["selection"]

    assert len(selection.points) == 4
    assert np.max(np.abs(real_intensity - k_intensity)) < 1e-12
    assert np.max(np.abs(real_weight - k_weight)) < 1e-12
    assert float(np.min(real_intensity)) >= -1e-14
    assert float(np.min(real_weight)) >= -1e-14


def test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_second_born_reference_sources():
    params = {"min": -4.0, "max": 4.0, "count": 61}
    results: dict[str, dict[str, object]] = {}
    for representation in ("real_space", "k_space"):
        config = _run_derived_second_born_reference_config(representation=representation)
        artifacts = solve_kbe_hfb(config)
        assert artifacts.two_time_green_functions is not None

        lesser = artifacts.two_time_green_functions.components["lesser"]
        times = artifacts.two_time_green_functions.times
        selection = build_momentum_selection(config, k_path=None, k_grid={"kind": "discrete_bz"})
        energy_grid = parse_energy_grid(params, config=config)
        payload = compute_k_resolved_trarpes(
            lesser=lesser,
            times=times,
            config=config,
            momentum_selection=selection,
            energy_grid=energy_grid,
            probe_center=0.1,
            probe_width=0.08,
            broadening=0.08,
        )
        results[representation] = {
            "selection": selection,
            "intensity": np.asarray(payload["intensity"], dtype=float),
            "occupied_weight": np.asarray(payload["occupied_weight"], dtype=float),
        }

    real_intensity = results["real_space"]["intensity"]
    k_intensity = results["k_space"]["intensity"]
    real_weight = results["real_space"]["occupied_weight"]
    k_weight = results["k_space"]["occupied_weight"]
    selection = results["real_space"]["selection"]

    assert len(selection.points) == 4
    assert np.max(np.abs(real_intensity - k_intensity)) < 1e-12
    assert np.max(np.abs(real_weight - k_weight)) < 1e-12
    assert float(np.min(real_intensity)) >= -1e-14
    assert float(np.min(real_weight)) >= -1e-14


def test_run_derived_trarpes_preview_matches_between_real_space_and_k_space_tdhfb_sources():
    params = {"min": -4.0, "max": 4.0, "count": 61}
    results: dict[str, dict[str, object]] = {}
    for representation in ("real_space", "k_space"):
        config = _run_derived_tdhfb_config(representation=representation)
        artifacts = solve_tdhfb(config)
        assert artifacts.two_time_green_functions is not None

        lesser = artifacts.two_time_green_functions.components["lesser"]
        times = artifacts.two_time_green_functions.times
        selection = build_momentum_selection(config, k_path=None, k_grid={"kind": "discrete_bz"})
        energy_grid = parse_energy_grid(params, config=config)
        payload = compute_k_resolved_trarpes(
            lesser=lesser,
            times=times,
            config=config,
            momentum_selection=selection,
            energy_grid=energy_grid,
            probe_center=0.1,
            probe_width=0.08,
            broadening=0.08,
        )
        results[representation] = {
            "selection": selection,
            "intensity": np.asarray(payload["intensity"], dtype=float),
            "occupied_weight": np.asarray(payload["occupied_weight"], dtype=float),
        }

    real_intensity = results["real_space"]["intensity"]
    k_intensity = results["k_space"]["intensity"]
    real_weight = results["real_space"]["occupied_weight"]
    k_weight = results["k_space"]["occupied_weight"]
    selection = results["real_space"]["selection"]

    assert len(selection.points) == 4
    assert np.max(np.abs(real_intensity - k_intensity)) < 1e-12
    assert np.max(np.abs(real_weight - k_weight)) < 1e-12
    assert float(np.min(real_intensity)) >= -1e-14
    assert float(np.min(real_weight)) >= -1e-14
