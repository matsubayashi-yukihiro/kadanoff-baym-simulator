from backend.app.schemas import SimulationConfig
from backend.app.solvers.tdhfb import solve


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
