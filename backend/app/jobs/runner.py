from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Protocol

from backend.app.jobs.worker import execute_run
from backend.app.schemas import SimulationConfig


class JobRunner(Protocol):
    def submit(
        self,
        run_id: str,
        config: SimulationConfig,
        data_dir: Path,
        registry_db_path: Path,
    ) -> int | None:
        ...

    def cancel(self, run_id: str) -> bool:
        ...


class InlineJobRunner:
    def submit(
        self,
        run_id: str,
        config: SimulationConfig,
        data_dir: Path,
        registry_db_path: Path,
    ) -> int | None:
        execute_run(
            run_id=run_id,
            config_data=config.model_dump(mode="json"),
            data_dir=str(data_dir),
            registry_db_path=str(registry_db_path),
        )
        return None

    def cancel(self, run_id: str) -> bool:
        return False


class ProcessJobRunner:
    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._jobs: dict[str, mp.Process] = {}

    def submit(
        self,
        run_id: str,
        config: SimulationConfig,
        data_dir: Path,
        registry_db_path: Path,
    ) -> int | None:
        process = self._ctx.Process(
            target=execute_run,
            kwargs={
                "run_id": run_id,
                "config_data": config.model_dump(mode="json"),
                "data_dir": str(data_dir),
                "registry_db_path": str(registry_db_path),
            },
            daemon=True,
        )
        process.start()
        self._jobs[run_id] = process
        return process.pid

    def cancel(self, run_id: str) -> bool:
        process = self._jobs.get(run_id)
        if process is None or not process.is_alive():
            return False
        process.terminate()
        process.join(timeout=2.0)
        return True
