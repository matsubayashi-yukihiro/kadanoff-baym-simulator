from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


JobMode = Literal["process", "inline"]
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True, slots=True)
class AppSettings:
    data_dir: Path = Path("backend/data/runs")
    registry_db_path: Path | None = None
    job_mode: JobMode = "process"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            data_dir=Path(os.getenv("TDKB_DATA_DIR", "backend/data/runs")),
            registry_db_path=_parse_optional_path(os.getenv("TDKB_REGISTRY_DB_PATH")),
            job_mode=os.getenv("TDKB_JOB_MODE", "process"),  # type: ignore[arg-type]
            cors_origins=_parse_cors_origins(os.getenv("TDKB_CORS_ORIGINS")),
        )

    def resolved(self) -> "AppSettings":
        resolved_data_dir = self.data_dir.resolve()
        resolved_registry_db_path = self.registry_db_path.resolve() if self.registry_db_path is not None else None
        if resolved_registry_db_path is None:
            resolved_registry_db_path = resolved_data_dir.parent / "experiment-registry.sqlite"
        return replace(
            self,
            data_dir=resolved_data_dir,
            registry_db_path=resolved_registry_db_path,
        )


def _parse_cors_origins(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_CORS_ORIGINS
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value)
