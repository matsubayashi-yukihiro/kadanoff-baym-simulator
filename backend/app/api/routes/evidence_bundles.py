from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import (
    EvidenceBundleCreate,
    EvidenceBundlePatch,
    EvidenceBundleRecord,
    EvidenceBundleResolvedRecord,
    EvidenceBundleStatus,
)
from backend.app.services.run_service import RunService


router = APIRouter(prefix="/evidence-bundles", tags=["evidence-bundles"])


@router.post("", response_model=EvidenceBundleRecord, status_code=status.HTTP_201_CREATED)
def create_evidence_bundle(
    payload: EvidenceBundleCreate,
    service: RunService = Depends(get_run_service),
) -> EvidenceBundleRecord:
    try:
        return service.create_evidence_bundle(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("", response_model=list[EvidenceBundleRecord])
def list_evidence_bundles(
    study_id: str | None = Query(default=None),
    status: EvidenceBundleStatus | None = Query(default=None),
    service: RunService = Depends(get_run_service),
) -> list[EvidenceBundleRecord]:
    return service.list_evidence_bundles(study_id=study_id, status=status)


@router.get("/{bundle_id}", response_model=EvidenceBundleRecord)
def get_evidence_bundle(bundle_id: str, service: RunService = Depends(get_run_service)) -> EvidenceBundleRecord:
    try:
        return service.get_evidence_bundle(bundle_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence bundle not found") from exc


@router.patch("/{bundle_id}", response_model=EvidenceBundleRecord)
def update_evidence_bundle(
    bundle_id: str,
    patch: EvidenceBundlePatch,
    service: RunService = Depends(get_run_service),
) -> EvidenceBundleRecord:
    try:
        return service.update_evidence_bundle(bundle_id, patch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence bundle not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/{bundle_id}/resolved", response_model=EvidenceBundleResolvedRecord)
def get_evidence_bundle_resolved(
    bundle_id: str,
    service: RunService = Depends(get_run_service),
) -> EvidenceBundleResolvedRecord:
    try:
        return service.get_evidence_bundle_resolved(bundle_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence bundle not found") from exc
