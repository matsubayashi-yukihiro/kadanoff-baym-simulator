from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import JobGroupCreate, JobGroupRecord
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/job-groups", tags=["job-groups"])


@router.post("", response_model=JobGroupRecord, status_code=status.HTTP_201_CREATED)
def create_job_group(
    payload: JobGroupCreate,
    service: RunService = Depends(get_run_service),
) -> JobGroupRecord:
    try:
        return service.create_job_group(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[JobGroupRecord])
def list_job_groups(
    study_id: str | None = Query(default=None),
    service: RunService = Depends(get_run_service),
) -> list[JobGroupRecord]:
    return service.list_job_groups(study_id=study_id)


@router.get("/{group_id}", response_model=JobGroupRecord)
def get_job_group(group_id: str, service: RunService = Depends(get_run_service)) -> JobGroupRecord:
    try:
        return service.get_job_group(group_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job group not found") from exc
