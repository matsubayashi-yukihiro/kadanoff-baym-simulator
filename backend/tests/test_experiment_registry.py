from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import AppSettings
from backend.app.jobs.runner import InlineJobRunner
from backend.app.main import create_app
from backend.app.schemas import SimulationConfig
from backend.app.storage.file_storage import FileRunStorage

pytestmark = pytest.mark.workflow


def test_existing_run_directories_are_backfilled_into_registry(tmp_path, sample_config):
    runs_dir = tmp_path / "runs"
    storage = FileRunStorage(runs_dir)
    config = SimulationConfig.model_validate(sample_config)
    legacy_summary = storage.create_run(config)

    app = create_app(
        settings=AppSettings(
            data_dir=runs_dir,
            registry_db_path=tmp_path / "experiment-registry.sqlite",
            job_mode="inline",
        ),
        runner=InlineJobRunner(),
    )

    with TestClient(app) as client:
        list_response = client.get("/api/v1/runs")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert [item["run_id"] for item in payload] == [legacy_summary.run_id]
    metadata = payload[0]["research_metadata"]
    assert metadata["config_hash"]
    assert metadata["storage_uri"] == str((runs_dir / legacy_summary.run_id).resolve())


def test_run_metadata_patch_updates_registry_backed_runs_list(client, sample_config):
    study_response = client.post(
        "/api/v1/studies",
        json={
            "title": "Higgs baseline framing",
            "question": "Which run is the baseline for the current single-job read?",
            "baseline_preset_id": "square-4x4-higgs-demo-kbe-hfb",
            "target_observables": ["pairing_d"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": ["validation scope stays explicit"],
            "status": "active",
            "notes_on_scope": "Workbench metadata only.",
        },
    )
    study_id = study_response.json()["study_id"]

    create_response = client.post("/api/v1/runs", json=sample_config)
    run_id = create_response.json()["run_id"]

    patch_response = client.patch(
        f"/api/v1/runs/{run_id}/metadata",
        json={
            "study_id": study_id,
            "run_role": "baseline",
            "validation_status": "screening",
            "variant_label": "baseline-a",
            "tags": ["higgs", "single-job"],
        },
    )

    assert patch_response.status_code == 200
    metadata = patch_response.json()["research_metadata"]
    assert metadata["study_id"] == study_id
    assert metadata["run_role"] == "baseline"
    assert metadata["validation_status"] == "screening"
    assert metadata["variant_label"] == "baseline-a"
    assert metadata["tags"] == ["higgs", "single-job"]

    summary_path = Path(client.app.state.settings.data_dir) / run_id / "summary.json"
    summary_path.unlink()

    list_response = client.get("/api/v1/runs")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["run_id"] == run_id)
    assert listed["research_metadata"]["study_id"] == study_id
    assert listed["research_metadata"]["run_role"] == "baseline"


def test_studies_notes_and_bundles_api(client, sample_config):
    study_response = client.post(
        "/api/v1/studies",
        json={
            "title": "Numerical validation sweep prep",
            "question": "How should the baseline be documented before compare and sweep land?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job", "compare-jobs"],
            "acceptance_checks": ["negative results remain queryable"],
            "status": "planning",
            "notes_on_scope": "Foundation for registry-backed artifacts.",
        },
    )
    assert study_response.status_code == 201
    study_payload = study_response.json()
    study_id = study_payload["study_id"]

    run_response = client.post("/api/v1/runs", json=sample_config)
    run_id = run_response.json()["run_id"]

    note_response = client.post(
        "/api/v1/decision-notes",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "note_kind": "observation",
            "body": "Baseline run is stable enough for workbench framing tests.",
            "tags": ["baseline", "registry"],
        },
    )
    assert note_response.status_code == 201
    note_payload = note_response.json()
    assert note_payload["study_id"] == study_id
    assert note_payload["source_id"] == run_id

    listed_notes = client.get(
        "/api/v1/decision-notes",
        params={"study_id": study_id, "source_kind": "run", "source_id": run_id},
    )
    assert listed_notes.status_code == 200
    assert [item["note_id"] for item in listed_notes.json()] == [note_payload["note_id"]]

    bundle_response = client.post(
        "/api/v1/evidence-bundles",
        json={
            "study_id": study_id,
            "title": "Single-job framing bundle",
            "claim_candidate": "Registry foundation can anchor baseline evidence before compare APIs exist.",
            "artifact_refs": [{"artifact_kind": "run", "artifact_id": run_id}],
            "analysis_refs": [],
            "validation_scope": "Workbench metadata only; does not alter solver validation labels.",
            "reproduction_recipe": "Create study, run baseline, attach note, then bundle the run reference.",
        },
    )
    assert bundle_response.status_code == 201
    bundle_payload = bundle_response.json()
    assert bundle_payload["artifact_refs"] == [{"artifact_kind": "run", "artifact_id": run_id}]

    list_bundles = client.get("/api/v1/evidence-bundles", params={"study_id": study_id})
    assert list_bundles.status_code == 200
    assert [item["bundle_id"] for item in list_bundles.json()] == [bundle_payload["bundle_id"]]

    get_study = client.get(f"/api/v1/studies/{study_id}")
    assert get_study.status_code == 200
    assert get_study.json()["title"] == "Numerical validation sweep prep"
