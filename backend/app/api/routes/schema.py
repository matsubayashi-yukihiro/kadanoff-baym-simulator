from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_run_service
from backend.app.services.run_service import RunService


router = APIRouter(tags=["schema"])


@router.get("/schema/simulation")
def get_simulation_schema(service: RunService = Depends(get_run_service)) -> dict:
    return service.get_schema()
