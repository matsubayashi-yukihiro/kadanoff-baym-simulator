from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import (
    DerivedAnalysisArtifactCreate,
    DerivedAnalysisArtifactRecord,
    DerivedAnalysisSourceKind,
)
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/derived-analyses", tags=["derived-analyses"])


@router.post("", response_model=DerivedAnalysisArtifactRecord, status_code=status.HTTP_201_CREATED)
def create_derived_analysis(
    payload: DerivedAnalysisArtifactCreate,
    service: RunService = Depends(get_run_service),
) -> DerivedAnalysisArtifactRecord:
    try:
        return service.create_derived_analysis(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[DerivedAnalysisArtifactRecord])
def list_derived_analyses(
    study_id: str | None = Query(default=None),
    source_kind: DerivedAnalysisSourceKind | None = Query(default=None),
    source_id: str | None = Query(default=None),
    service: RunService = Depends(get_run_service),
) -> list[DerivedAnalysisArtifactRecord]:
    return service.list_derived_analyses(
        study_id=study_id,
        source_kind=None if source_kind is None else source_kind.value,
        source_id=source_id,
    )


@router.get("/{analysis_id}", response_model=DerivedAnalysisArtifactRecord)
def get_derived_analysis(
    analysis_id: str,
    service: RunService = Depends(get_run_service),
) -> DerivedAnalysisArtifactRecord:
    try:
        return service.get_derived_analysis(analysis_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="derived analysis not found") from exc
