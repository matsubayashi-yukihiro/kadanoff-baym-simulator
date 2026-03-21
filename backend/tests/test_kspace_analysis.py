import numpy as np
import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kspace_analysis import (
    build_momentum_selection,
    compute_k_resolved_trarpes,
    parse_energy_grid,
)

pytestmark = pytest.mark.physics_unit


def test_build_high_symmetry_k_path_includes_expected_labels():
    config = SimulationConfig.model_validate(
        {
            "solver": "kbe_hfb",
            "lattice": {
                "nx": 4,
                "ny": 4,
                "boundary": "periodic",
                "hopping": 1.0,
                "chemical_potential": 0.0,
            },
            "time": {"t_final": 0.4, "dt": 0.1},
        }
    )

    selection = build_momentum_selection(config, k_path="gamma_x_m_gamma", k_grid=None)

    assert selection.kind == "k_path"
    assert selection.tick_labels == ("Gamma", "X", "M", "Gamma")
    assert len(selection.points) >= 4


def test_k_space_trarpes_reconstructs_peak_for_single_momentum_mode():
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
            "time": {"t_final": 2.0, "dt": 0.05},
        }
    )
    selection = build_momentum_selection(config, k_path=None, k_grid={"kind": "discrete_bz"})
    energy_grid = parse_energy_grid({"min": -2.0, "max": 2.0, "count": 161}, config=config)
    times = np.linspace(0.0, 2.0, 41, dtype=np.float64)

    site_count = config.lattice.nx * config.lattice.ny
    nambu_dimension = 2 * site_count
    lesser = np.zeros((times.size, times.size, nambu_dimension, nambu_dimension), dtype=np.complex128)

    gamma_mode = np.ones(site_count, dtype=np.complex128) / np.sqrt(site_count)
    energy = -0.8
    for row_index, time_row in enumerate(times):
        for column_index, time_col in enumerate(times):
            temporal_phase = np.exp(-1j * energy * (time_row - time_col))
            lesser[row_index, column_index, :site_count, :site_count] = (
                1j * temporal_phase * np.outer(gamma_mode, gamma_mode.conjugate())
            )

    payload = compute_k_resolved_trarpes(
        lesser=lesser,
        times=times,
        config=config,
        momentum_selection=selection,
        energy_grid=energy_grid,
        probe_center=1.0,
        probe_width=0.4,
        broadening=0.05,
    )

    intensity = payload["intensity"]
    assert intensity.shape == (len(selection.points), len(energy_grid))
    gamma_index = next(index for index, point in enumerate(selection.points) if point.grid_index_x == 0 and point.grid_index_y == 0)
    peak_energy = energy_grid[int(np.argmax(intensity[gamma_index]))]
    assert peak_energy == pytest.approx(energy, abs=0.1)
    assert np.max(intensity[gamma_index]) > np.max(intensity[(gamma_index + 1) % len(selection.points)])
