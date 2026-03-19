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


class KBESelfEnergyMode(str, Enum):
    HFB = "hfb"
    SECOND_BORN = "second_born"
    SECOND_BORN_REFERENCE = "second_born_reference"


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


class KBEConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_energy: KBESelfEnergyMode = KBESelfEnergyMode.HFB
    max_fixed_point_iterations: int = Field(default=6, ge=1, le=64)
    tolerance: float = Field(default=1e-7, gt=0.0)
    mixing: float = Field(default=0.35, gt=0.0, le=1.0)
    memory_window: int | None = Field(default=None, ge=1)


class AdaptiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    atol: float = Field(default=1e-7, gt=0.0)
    rtol: float = Field(default=1e-5, gt=0.0)
    min_dt: float | None = Field(default=None, gt=0.0)
    max_dt: float | None = Field(default=None, gt=0.0)
    max_growth: float = Field(default=2.0, gt=1.0, le=8.0)
    min_shrink: float = Field(default=0.25, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_step_bounds(self) -> "AdaptiveConfig":
        if self.min_dt is not None and self.max_dt is not None and self.min_dt > self.max_dt:
            raise ValueError("adaptive.min_dt must be <= adaptive.max_dt")
        return self


class ThermalBranchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    n_tau: int = Field(default=16, ge=4)
    max_iterations: int = Field(default=8, ge=1, le=64)
    mixing: float = Field(default=0.3, gt=0.0, le=1.0)


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    solver: SolverKind = SolverKind.NONINTERACTING
    lattice: LatticeConfig
    time: TimeGridConfig
    drive: DriveConfig = Field(default_factory=DriveConfig)
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    initial_state: InitialStateConfig = Field(default_factory=InitialStateConfig)
    kbe: KBEConfig = Field(default_factory=KBEConfig)
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)
    thermal_branch: ThermalBranchConfig = Field(default_factory=ThermalBranchConfig)
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

    @model_validator(mode="after")
    def validate_extended_kbe_options(self) -> "SimulationConfig":
        if self.thermal_branch.enabled and self.initial_state.temperature <= 0.0:
            raise ValueError("thermal_branch.enabled requires initial_state.temperature > 0")
        return self


class PresetCategory(str, Enum):
    DEMO = "demo"
    WORKING_BASELINE = "working_baseline"
    MEAN_FIELD = "mean_field"
    EXACT_BASELINE = "exact_baseline"


class PresetValidationStatus(str, Enum):
    VALIDATED = "validated"
    PARTIAL = "partial"
    PROTOTYPE = "prototype"


class PresetEntry(BaseModel):
    """Enriched preset: config + metadata for display and selection."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: PresetCategory
    validation_status: PresetValidationStatus
    summary: str
    scope_note: str
    primary_observable: str | None = None
    config: SimulationConfig
