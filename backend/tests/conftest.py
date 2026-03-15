from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import AppSettings
from backend.app.jobs.runner import InlineJobRunner
from backend.app.main import create_app


@pytest.fixture
def sample_config() -> dict:
    return {
        "name": "test-run",
        "solver": "noninteracting",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {"onsite_u": 0.0, "nearest_neighbor_v": 0.0},
        "initial_state": {"filling": 0.5, "temperature": 0.0},
        "observables": ["density", "current_x", "current_y", "energy", "vector_potential"],
    }


@pytest.fixture
def client(tmp_path):
    app = create_app(
        settings=AppSettings(data_dir=tmp_path / "runs", job_mode="inline"),
        runner=InlineJobRunner(),
    )
    with TestClient(app) as test_client:
        yield test_client
