from __future__ import annotations

from typing import Protocol

from backend.app.jobs.progress import SolverProgressUpdate


class ProgressCallback(Protocol):
    def __call__(self, update: SolverProgressUpdate, /, *, force: bool = False) -> None:
        ...
