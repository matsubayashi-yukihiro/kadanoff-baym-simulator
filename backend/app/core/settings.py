from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


JobMode = Literal["process", "inline"]


@dataclass(frozen=True, slots=True)
class AppSettings:
    data_dir: Path = Path("backend/data/runs")
    job_mode: JobMode = "process"

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            data_dir=Path(os.getenv("TDKB_DATA_DIR", "backend/data/runs")),
            job_mode=os.getenv("TDKB_JOB_MODE", "process"),  # type: ignore[arg-type]
        )

    def resolved(self) -> "AppSettings":
        return replace(self, data_dir=self.data_dir.resolve())
