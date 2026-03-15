import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian, build_one_body_hamiltonian_derivative
from backend.app.solvers.lattice import build_square_lattice


def test_hamiltonian_is_hermitian_and_has_expected_hopping():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
    )
    lattice = build_square_lattice(config.lattice)

    hamiltonian = build_one_body_hamiltonian(config, lattice, time=0.0)

    assert np.allclose(hamiltonian, hamiltonian.conjugate().T)
    assert hamiltonian[0, 1] == -1.0
    assert hamiltonian[0, 2] == -1.0


def test_hamiltonian_time_derivative_matches_finite_difference():
    config = SimulationConfig(
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        drive={
            "amplitude_x": 0.25,
            "amplitude_y": -0.1,
            "frequency": 1.3,
            "phase": 0.2,
            "center": 0.05,
            "width": 0.4,
        },
    )
    lattice = build_square_lattice(config.lattice)
    time = 0.07
    epsilon = 1e-6

    analytic = build_one_body_hamiltonian_derivative(config, lattice, time=time)
    finite_difference = (
        build_one_body_hamiltonian(config, lattice, time=time + epsilon)
        - build_one_body_hamiltonian(config, lattice, time=time - epsilon)
    ) / (2.0 * epsilon)

    assert np.allclose(analytic, finite_difference, atol=1e-6, rtol=1e-5)
