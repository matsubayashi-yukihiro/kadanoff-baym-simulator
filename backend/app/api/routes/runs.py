from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import (
    GreenFunctionCatalogResponse,
    GreenFunctionSliceResponse,
    MixedGreenFunctionCatalogResponse,
    MixedGreenFunctionSliceResponse,
    ObservableCatalogResponse,
    ObservableResponse,
    RunDetail,
    RunProgressRecord,
    RunResearchMetadataPatch,
    RunSummary,
    SimulationConfig,
    ThermalBranchCatalogResponse,
    ThermalBranchSliceResponse,
)
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunDetail, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    config: SimulationConfig,
    service: RunService = Depends(get_run_service),
) -> RunDetail:
    return service.create_run(config)


@router.get("", response_model=list[RunSummary])
def list_runs(service: RunService = Depends(get_run_service)) -> list[RunSummary]:
    return service.list_runs()


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: str, service: RunService = Depends(get_run_service)) -> RunDetail:
    try:
        return service.get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.get("/{run_id}/progress", response_model=RunProgressRecord)
def get_run_progress(run_id: str, service: RunService = Depends(get_run_service)) -> RunProgressRecord:
    try:
        return service.get_run_progress(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.post("/{run_id}/cancel", response_model=RunDetail)
def cancel_run(run_id: str, service: RunService = Depends(get_run_service)) -> RunDetail:
    try:
        return service.cancel_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.patch("/{run_id}/metadata", response_model=RunDetail)
def update_run_metadata(
    run_id: str,
    patch: RunResearchMetadataPatch,
    service: RunService = Depends(get_run_service),
) -> RunDetail:
    try:
        return service.update_run_metadata(run_id, patch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{run_id}/log")
def get_run_log(run_id: str, service: RunService = Depends(get_run_service)) -> PlainTextResponse:
    try:
        log_content = service.read_log(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc
    return PlainTextResponse(log_content)


@router.get("/{run_id}/observables", response_model=ObservableCatalogResponse)
def list_observables(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> ObservableCatalogResponse:
    try:
        return service.list_observables(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


@router.get("/{run_id}/observables/{name}", response_model=ObservableResponse)
def get_observable(
    run_id: str,
    name: str,
    service: RunService = Depends(get_run_service),
) -> ObservableResponse:
    try:
        return service.get_observable(run_id, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="observable not found") from exc


@router.get("/{run_id}/green-functions", response_model=GreenFunctionCatalogResponse)
def list_green_functions(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> GreenFunctionCatalogResponse:
    try:
        return service.list_green_functions(run_id)
    except FileNotFoundError as exc:
        _raise_missing_green_function_detail(run_id, service, exc)


@router.get("/{run_id}/green-functions/{component}", response_model=GreenFunctionSliceResponse)
def get_green_function_slice(
    run_id: str,
    component: str,
    row_start: int | None = Query(default=None, ge=0),
    row_stop: int | None = Query(default=None, ge=1),
    col_start: int | None = Query(default=None, ge=0),
    col_stop: int | None = Query(default=None, ge=1),
    nambu_start: int | None = Query(default=None, ge=0),
    nambu_stop: int | None = Query(default=None, ge=1),
    service: RunService = Depends(get_run_service),
) -> GreenFunctionSliceResponse:
    try:
        return service.get_green_function_slice(
            run_id,
            component,
            row_start=row_start,
            row_stop=row_stop,
            col_start=col_start,
            col_stop=col_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )
    except FileNotFoundError as exc:
        _raise_missing_green_function_detail(run_id, service, exc)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="green function component not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{run_id}/thermal-branch", response_model=ThermalBranchCatalogResponse)
def list_thermal_branch(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> ThermalBranchCatalogResponse:
    try:
        return service.list_thermal_branch(run_id)
    except FileNotFoundError as exc:
        _raise_missing_thermal_branch_detail(run_id, service, exc)


@router.get("/{run_id}/thermal-branch/{component}", response_model=ThermalBranchSliceResponse)
def get_thermal_branch_slice(
    run_id: str,
    component: str,
    tau_start: int | None = Query(default=None, ge=0),
    tau_stop: int | None = Query(default=None, ge=1),
    nambu_start: int | None = Query(default=None, ge=0),
    nambu_stop: int | None = Query(default=None, ge=1),
    service: RunService = Depends(get_run_service),
) -> ThermalBranchSliceResponse:
    try:
        return service.get_thermal_branch_slice(
            run_id,
            component,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )
    except FileNotFoundError as exc:
        _raise_missing_thermal_branch_detail(run_id, service, exc)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thermal branch component not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{run_id}/mixed-green-functions", response_model=MixedGreenFunctionCatalogResponse)
def list_mixed_green_functions(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> MixedGreenFunctionCatalogResponse:
    try:
        return service.list_mixed_green_functions(run_id)
    except FileNotFoundError as exc:
        _raise_missing_mixed_green_function_detail(run_id, service, exc)


@router.get("/{run_id}/mixed-green-functions/{component}", response_model=MixedGreenFunctionSliceResponse)
def get_mixed_green_function_slice(
    run_id: str,
    component: str,
    time_start: int | None = Query(default=None, ge=0),
    time_stop: int | None = Query(default=None, ge=1),
    tau_start: int | None = Query(default=None, ge=0),
    tau_stop: int | None = Query(default=None, ge=1),
    nambu_start: int | None = Query(default=None, ge=0),
    nambu_stop: int | None = Query(default=None, ge=1),
    service: RunService = Depends(get_run_service),
) -> MixedGreenFunctionSliceResponse:
    try:
        return service.get_mixed_green_function_slice(
            run_id,
            component,
            time_start=time_start,
            time_stop=time_stop,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )
    except FileNotFoundError as exc:
        _raise_missing_mixed_green_function_detail(run_id, service, exc)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mixed green function component not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _raise_missing_green_function_detail(run_id: str, service: RunService, exc: FileNotFoundError) -> None:
    try:
        service.get_run(run_id)
    except FileNotFoundError as missing_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from missing_run
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="green function data not found") from exc


def _raise_missing_thermal_branch_detail(run_id: str, service: RunService, exc: FileNotFoundError) -> None:
    try:
        service.get_run(run_id)
    except FileNotFoundError as missing_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from missing_run
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thermal branch data not found") from exc


def _raise_missing_mixed_green_function_detail(run_id: str, service: RunService, exc: FileNotFoundError) -> None:
    try:
        service.get_run(run_id)
    except FileNotFoundError as missing_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from missing_run
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mixed green function data not found") from exc
