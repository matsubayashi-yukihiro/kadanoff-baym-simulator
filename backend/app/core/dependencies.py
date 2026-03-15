from fastapi import Request

from backend.app.services.run_service import RunService


def get_run_service(request: Request) -> RunService:
    return request.app.state.run_service
