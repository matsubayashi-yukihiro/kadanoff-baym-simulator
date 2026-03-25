from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GreenFunctionCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    components: list[str]
    shape: list[int]
    time_point_count: int
    nambu_dimension: int


class GreenFunctionSliceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    times_row: list[float]
    times_col: list[float]
    nambu_start: int
    nambu_stop: int
    shape: list[int]
    real: list[list[list[list[float]]]]
    imag: list[list[list[list[float]]]]


class ThermalBranchCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    components: list[str]
    shape: list[int]
    tau_point_count: int
    nambu_dimension: int


class ThermalBranchSliceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    tau: list[float]
    nambu_start: int
    nambu_stop: int
    shape: list[int]
    real: list[list[list[float]]]
    imag: list[list[list[float]]]


class MixedGreenFunctionCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    components: list[str]
    shape: list[int]
    time_point_count: int
    tau_point_count: int
    nambu_dimension: int


class MixedGreenFunctionSliceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    times: list[float]
    tau: list[float]
    nambu_start: int
    nambu_stop: int
    shape: list[int]
    real: list[list[list[list[float]]]]
    imag: list[list[list[list[float]]]]


class KSpaceNativePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    grid_index_x: int
    grid_index_y: int
    kx: float
    ky: float


class KSpaceNativeCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    components: list[str]
    time_point_count: int
    k_point_count: int
    block_shape: list[int]
    nambu_dimension: int
    reconstruction_mode: str | None = None
    points: list[KSpaceNativePoint]


class KSpaceNativeLesserSliceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    times_row: list[float]
    times_col: list[float]
    k_start: int
    k_stop: int
    nambu_start: int
    nambu_stop: int
    shape: list[int]
    real: list[list[list[list[list[float]]]]]
    imag: list[list[list[list[list[float]]]]]
