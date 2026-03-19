from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_run_service
from backend.app.schemas.simulation import PresetEntry
from backend.app.services.run_service import RunService


router = APIRouter(tags=["presets"])


@router.get("/presets", response_model=list[PresetEntry])
def get_presets(service: RunService = Depends(get_run_service)) -> list[PresetEntry]:
    return service.get_presets()
