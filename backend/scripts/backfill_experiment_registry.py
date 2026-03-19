from __future__ import annotations

import argparse

from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.experiment_repository import ExperimentRepository
from backend.app.storage.file_storage import FileRunStorage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill filesystem run artifacts into the SQLite experiment registry.")
    parser.add_argument("--data-dir", default="backend/data/runs", help="Directory that contains run artifact folders.")
    parser.add_argument(
        "--registry-db",
        default="backend/data/experiment-registry.sqlite",
        help="SQLite database file for the experiment registry.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage = FileRunStorage(args.data_dir)
    registry = ExperimentRegistry(args.registry_db)
    repository = ExperimentRepository(storage=storage, registry=registry)
    imported = repository.backfill_existing_runs()
    print(f"backfilled {imported} run(s) into {registry.db_path}")


if __name__ == "__main__":
    main()
