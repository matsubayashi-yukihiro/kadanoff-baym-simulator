from backend.app.schemas import SimulationConfig
from backend.app.solvers.noninteracting import solve


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
