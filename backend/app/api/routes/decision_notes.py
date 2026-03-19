from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import ArtifactSourceKind, DecisionNoteCreate, DecisionNoteRecord
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/decision-notes", tags=["decision-notes"])


@router.post("", response_model=DecisionNoteRecord, status_code=status.HTTP_201_CREATED)
def create_decision_note(
    payload: DecisionNoteCreate,
    service: RunService = Depends(get_run_service),
) -> DecisionNoteRecord:
    try:
        return service.create_decision_note(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[DecisionNoteRecord])
def list_decision_notes(
    study_id: str | None = Query(default=None),
    source_kind: ArtifactSourceKind | None = Query(default=None),
    source_id: str | None = Query(default=None),
    service: RunService = Depends(get_run_service),
) -> list[DecisionNoteRecord]:
    return service.list_decision_notes(
        study_id=study_id,
        source_kind=source_kind.value if source_kind is not None else None,
        source_id=source_id,
    )


@router.get("/{note_id}", response_model=DecisionNoteRecord)
def get_decision_note(note_id: str, service: RunService = Depends(get_run_service)) -> DecisionNoteRecord:
    try:
        return service.get_decision_note(note_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="decision note not found") from exc
