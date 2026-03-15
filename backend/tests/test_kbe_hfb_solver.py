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
