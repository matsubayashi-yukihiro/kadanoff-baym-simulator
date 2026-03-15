import pytest

from backend.app.schemas import SimulationConfig
from backend.app.solvers.kbe_hfb import solve as solve_kbe_hfb
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
