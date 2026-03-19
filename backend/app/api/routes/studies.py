from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import StudyCreate, StudyRecord
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/studies", tags=["studies"])


@router.post("", response_model=StudyRecord, status_code=status.HTTP_201_CREATED)
def create_study(
    payload: StudyCreate,
    service: RunService = Depends(get_run_service),
) -> StudyRecord:
    return service.create_study(payload)


@router.get("", response_model=list[StudyRecord])
def list_studies(service: RunService = Depends(get_run_service)) -> list[StudyRecord]:
    return service.list_studies()


@router.get("/{study_id}", response_model=StudyRecord)
def get_study(study_id: str, service: RunService = Depends(get_run_service)) -> StudyRecord:
    try:
        return service.get_study(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found") from exc
