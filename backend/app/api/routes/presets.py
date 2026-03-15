from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_run_service
from backend.app.schemas import SimulationConfig
from backend.app.services.run_service import RunService


router = APIRouter(tags=["presets"])


@router.get("/presets", response_model=list[SimulationConfig])
def get_presets(service: RunService = Depends(get_run_service)) -> list[SimulationConfig]:
    return service.get_presets()
