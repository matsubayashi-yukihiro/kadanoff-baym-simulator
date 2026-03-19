from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.decision_notes import router as decision_notes_router
from backend.app.api.routes.evidence_bundles import router as evidence_bundles_router
from backend.app.api.routes.presets import router as presets_router
from backend.app.api.routes.runs import router as runs_router
from backend.app.api.routes.schema import router as schema_router
from backend.app.api.routes.studies import router as studies_router
from backend.app.core.settings import AppSettings
from backend.app.jobs.runner import InlineJobRunner, JobRunner, ProcessJobRunner
from backend.app.services.run_service import RunService
from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.experiment_repository import ExperimentRepository
from backend.app.storage.file_storage import FileRunStorage


def _build_runner(settings: AppSettings) -> JobRunner:
    if settings.job_mode == "inline":
        return InlineJobRunner()
    return ProcessJobRunner()


def create_app(
    settings: AppSettings | None = None,
    runner: JobRunner | None = None,
) -> FastAPI:
    resolved_settings = (settings or AppSettings.from_env()).resolved()
    storage = FileRunStorage(resolved_settings.data_dir)
    registry = ExperimentRegistry(resolved_settings.registry_db_path)
    repository = ExperimentRepository(storage=storage, registry=registry)
    job_runner = runner or _build_runner(resolved_settings)
    run_service = RunService(repository=repository, runner=job_runner)

    app = FastAPI(title="TDKB Backend", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.run_service = run_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(schema_router, prefix="/api/v1")
    app.include_router(presets_router, prefix="/api/v1")
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(studies_router, prefix="/api/v1")
    app.include_router(decision_notes_router, prefix="/api/v1")
    app.include_router(evidence_bundles_router, prefix="/api/v1")
    return app


app = create_app()
