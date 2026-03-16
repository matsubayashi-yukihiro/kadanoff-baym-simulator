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


def test_simulation_config_normalizes_legacy_pairing_channel_aliases():
    config = SimulationConfig(
        solver="tdhfb",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        interaction={"nearest_neighbor_v": -1.0, "pairing_channel": "d"},
        initial_state={"seed_pairing": 0.1},
        observables=["density", "pairing_d"],
    )

    assert config.interaction.pairing_channel.value == "bond_d"


def test_simulation_config_accepts_phase_e_extensions():
    config = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        interaction={"onsite_u": -2.0},
        initial_state={"temperature": 0.2},
        kbe={"self_energy": "second_born", "max_fixed_point_iterations": 8, "mixing": 0.5},
        adaptive={"enabled": True, "min_dt": 0.05, "max_dt": 0.1},
        thermal_branch={"enabled": True, "n_tau": 8},
        observables=["density", "energy"],
    )

    assert config.kbe.self_energy.value == "second_born"
    assert config.adaptive.enabled is True
    assert config.thermal_branch.n_tau == 8


def test_simulation_config_requires_positive_temperature_for_thermal_branch():
    with pytest.raises(ValidationError):
        SimulationConfig(
            solver="kbe_hfb",
            lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
            thermal_branch={"enabled": True, "n_tau": 8},
        )
