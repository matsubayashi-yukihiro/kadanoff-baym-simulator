from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import (
    ObservableCatalogResponse,
    ObservableResponse,
    RunDetail,
    RunSummary,
    SimulationConfig,
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


@router.post("/{run_id}/cancel", response_model=RunDetail)
def cancel_run(run_id: str, service: RunService = Depends(get_run_service)) -> RunDetail:
    try:
        return service.cancel_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found") from exc


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
