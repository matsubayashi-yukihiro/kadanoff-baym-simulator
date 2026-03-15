from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoundaryCondition(str, Enum):
    PERIODIC = "periodic"
    OPEN = "open"


class SolverKind(str, Enum):
    NONINTERACTING = "noninteracting"
    TDHFB = "tdhfb"
    KBE_HFB = "kbe_hfb"


class PairingChannel(str, Enum):
    NONE = "none"
    ONSITE = "onsite"
    BOND_S = "bond_s"
    BOND_D = "bond_d"


class LatticeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "square"
    nx: int = Field(ge=2)
    ny: int = Field(ge=2)
    boundary: BoundaryCondition = BoundaryCondition.PERIODIC
    hopping: float = Field(default=1.0, gt=0.0)
    chemical_potential: float = 0.0


class TimeGridConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_final: float = Field(gt=0.0)
    dt: float = Field(gt=0.0)
    save_every: int = Field(default=1, ge=1)

    @property
    def n_steps(self) -> int:
        return int(round(self.t_final / self.dt))

    def time_points(self) -> list[float]:
        return [step * self.dt for step in range(self.n_steps + 1)]

    @model_validator(mode="after")
    def validate_commensurate_step(self) -> "TimeGridConfig":
        n_steps = self.t_final / self.dt
        if abs(n_steps - round(n_steps)) > 1e-9:
            raise ValueError("t_final must be an integer multiple of dt")
        return self


class DriveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amplitude_x: float = 0.0
    amplitude_y: float = 0.0
    frequency: float = Field(default=0.0, ge=0.0)
    phase: float = 0.0
    center: float = 0.0
    width: float = Field(default=1.0, gt=0.0)


class InteractionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onsite_u: float = 0.0
    nearest_neighbor_v: float = 0.0
    pairing_channel: PairingChannel = PairingChannel.NONE


class InitialStateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filling: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=0.0, ge=0.0)
    seed_pairing: float = 0.0


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    solver: SolverKind = SolverKind.NONINTERACTING
    lattice: LatticeConfig
    time: TimeGridConfig
    drive: DriveConfig = Field(default_factory=DriveConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    initial_state: InitialStateConfig = Field(default_factory=InitialStateConfig)
    observables: list[str] = Field(
        default_factory=lambda: [
            "density",
            "current_x",
            "current_y",
            "energy",
            "vector_potential",
        ]
    )

    @property
    def supported_observables(self) -> set[str]:
        return {
            "density",
            "current_x",
            "current_y",
            "energy",
            "vector_potential",
            "pairing",
            "pairing_s",
            "pairing_d",
        }

    @field_validator("observables")
    @classmethod
    def validate_observables(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("observables must be unique")
        supported = {
            "density",
            "current_x",
            "current_y",
            "energy",
            "vector_potential",
            "pairing",
            "pairing_s",
            "pairing_d",
        }
        unknown = sorted(set(value) - supported)
        if unknown:
            raise ValueError(f"unsupported observables: {', '.join(unknown)}")
        return value

    @field_validator("interaction", mode="before")
    @classmethod
    def normalize_pairing_channel(cls, value: InteractionConfig | dict[str, object]) -> InteractionConfig | dict[str, object]:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        pairing_channel = normalized.get("pairing_channel")
        aliases = {
            "s": PairingChannel.BOND_S,
            "bond": PairingChannel.BOND_S,
            "d": PairingChannel.BOND_D,
        }
        if isinstance(pairing_channel, str) and pairing_channel in aliases:
            normalized["pairing_channel"] = aliases[pairing_channel]
        return normalized
