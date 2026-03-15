import numpy as np

from backend.app.schemas import SimulationConfig
from backend.app.solvers.hamiltonian import build_one_body_hamiltonian
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
