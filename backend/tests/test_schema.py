import pytest
from pydantic import ValidationError

from backend.app.schemas import SimulationConfig, TimeGridConfig


def test_time_grid_requires_commensurate_dt():
    with pytest.raises(ValidationError):
        TimeGridConfig(t_final=1.0, dt=0.3)


def test_simulation_config_rejects_duplicate_observables():
    with pytest.raises(ValidationError):
        SimulationConfig(
            lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
            observables=["density", "density"],
        )
