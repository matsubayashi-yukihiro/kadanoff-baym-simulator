import pytest
from pydantic import ValidationError

from backend.app.schemas import SimulationConfig, TimeGridConfig

pytestmark = pytest.mark.physics_unit


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


def test_simulation_config_accepts_reference_second_born_mode():
    config = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        interaction={"onsite_u": -1.0},
        kbe={"self_energy": "second_born_reference", "max_fixed_point_iterations": 6},
        observables=["density", "current_x"],
    )

    assert config.kbe.self_energy.value == "second_born_reference"
    assert config.resolved_equilibrium_method().value == "second_born_reference"


def test_equilibrium_method_auto_resolves_consistently():
    tdhfb = SimulationConfig(
        solver="tdhfb",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
    )
    kbe_hfb = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        kbe={"self_energy": "hfb"},
    )
    reference = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        initial_state={"temperature": 0.2},
        interaction={"onsite_u": -1.0},
        kbe={"self_energy": "second_born_reference"},
    )
    prototype = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        interaction={"onsite_u": -1.0},
        kbe={"self_energy": "second_born"},
    )

    assert tdhfb.resolved_equilibrium_method().value == "hfb"
    assert kbe_hfb.resolved_equilibrium_method().value == "hfb"
    assert reference.resolved_equilibrium_method().value == "second_born_reference"
    assert prototype.resolved_equilibrium_method().value == "hfb"


def test_equilibrium_method_mismatch_requires_explicit_override():
    with pytest.raises(ValidationError):
        SimulationConfig(
            solver="kbe_hfb",
            lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
            initial_state={"temperature": 0.2},
            interaction={"onsite_u": -1.0},
            equilibrium={"method": "hfb"},
            kbe={"self_energy": "second_born_reference"},
        )

    config = SimulationConfig(
        solver="kbe_hfb",
        lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        initial_state={"temperature": 0.2},
        interaction={"onsite_u": -1.0},
        equilibrium={"method": "hfb", "allow_approximation_mismatch": True},
        kbe={"self_energy": "second_born_reference"},
    )

    assert config.resolved_equilibrium_method().value == "hfb"


def test_simulation_config_requires_positive_temperature_for_thermal_branch():
    with pytest.raises(ValidationError):
        SimulationConfig(
            solver="kbe_hfb",
            lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
            thermal_branch={"enabled": True, "n_tau": 8},
        )


def test_simulation_config_accepts_k_space_representation_for_periodic_square_lattice():
    config = SimulationConfig(
        solver="noninteracting",
        representation="k_space",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
    )

    assert config.representation.value == "k_space"


def test_simulation_config_rejects_invalid_k_space_combinations():
    with pytest.raises(ValidationError):
        SimulationConfig(
            solver="noninteracting",
            representation="k_space",
            lattice={"nx": 2, "ny": 2, "boundary": "open", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
        )

    with pytest.raises(ValidationError):
        SimulationConfig(
            solver="kbe_hfb",
            representation="k_space",
            lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
            time={"t_final": 0.2, "dt": 0.1},
            kbe={"self_energy": "second_born"},
        )


def test_simulation_config_accepts_k_space_second_born_reference_representation():
    config = SimulationConfig(
        solver="kbe_hfb",
        representation="k_space",
        lattice={"nx": 2, "ny": 2, "boundary": "periodic", "hopping": 1.0},
        time={"t_final": 0.2, "dt": 0.1},
        initial_state={"temperature": 0.2},
        interaction={"onsite_u": -1.0},
        kbe={"self_energy": "second_born_reference"},
        equilibrium={"method": "second_born_reference"},
    )

    assert config.representation.value == "k_space"
    assert config.kbe.self_energy.value == "second_born_reference"
    assert config.resolved_equilibrium_method().value == "second_born_reference"
