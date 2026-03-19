from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import SweepCreate, SweepLaunchRequest, SweepRecord
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/sweeps", tags=["sweeps"])


@router.post("", response_model=SweepRecord, status_code=status.HTTP_201_CREATED)
def create_sweep(
    payload: SweepCreate,
    service: RunService = Depends(get_run_service),
) -> SweepRecord:
    try:
        return service.create_sweep(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/launch", response_model=SweepRecord, status_code=status.HTTP_201_CREATED)
def launch_sweep(
    payload: SweepLaunchRequest,
    service: RunService = Depends(get_run_service),
) -> SweepRecord:
    try:
        return service.launch_sweep(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[SweepRecord])
def list_sweeps(
    study_id: str | None = Query(default=None),
    service: RunService = Depends(get_run_service),
) -> list[SweepRecord]:
    return service.list_sweeps(study_id=study_id)


@router.get("/{sweep_id}", response_model=SweepRecord)
def get_sweep(sweep_id: str, service: RunService = Depends(get_run_service)) -> SweepRecord:
    try:
        return service.get_sweep(sweep_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sweep not found") from exc
