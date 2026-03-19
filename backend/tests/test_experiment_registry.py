from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import AppSettings
from backend.app.jobs.runner import InlineJobRunner
from backend.app.main import create_app
from backend.app.schemas import (
    ArtifactLifecycleState,
    ComparisonKind,
    JobGroupCreate,
    RunState,
    SimulationConfig,
    StudyCreate,
    SweepCreate,
)
from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.experiment_repository import ExperimentRepository
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


def test_job_groups_sweeps_and_derived_analyses_api(client, sample_config):
    study_response = client.post(
        "/api/v1/studies",
        json={
            "title": "Compare and sweep foundation",
            "question": "Can compare and sweep artifacts be persisted before dedicated launchers exist?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["density", "energy"],
            "primary_surfaces": ["compare-jobs", "parameter-sweep"],
            "acceptance_checks": ["child runs remain traceable from parent artifacts"],
            "status": "active",
            "notes_on_scope": "Metadata and lineage only.",
        },
    )
    study_id = study_response.json()["study_id"]

    baseline_run = client.post("/api/v1/runs", json=sample_config).json()
    variant_run = client.post(
        "/api/v1/runs",
        json={**sample_config, "name": "variant-run", "time": {**sample_config["time"], "dt": 0.2}},
    ).json()

    group_response = client.post(
        "/api/v1/job-groups",
        json={
            "study_id": study_id,
            "name": "dt comparison",
            "comparison_kind": "numerical_validation",
            "baseline_run_id": baseline_run["run_id"],
            "base_config": sample_config,
            "variants": [
                {
                    "label": "dt=0.1",
                    "description": "baseline",
                    "config_patch": {"time": {"dt": 0.1}},
                    "run_id": baseline_run["run_id"],
                },
                {
                    "label": "dt=0.2",
                    "description": "coarser step",
                    "config_patch": {"time": {"dt": 0.2}},
                    "run_id": variant_run["run_id"],
                },
            ],
            "child_run_ids": [baseline_run["run_id"], variant_run["run_id"]],
        },
    )
    assert group_response.status_code == 201
    group_payload = group_response.json()
    assert group_payload["comparison_kind"] == "numerical_validation"
    assert group_payload["state"] == "succeeded"
    assert group_payload["child_run_ids"] == [baseline_run["run_id"], variant_run["run_id"]]

    list_groups = client.get("/api/v1/job-groups", params={"study_id": study_id})
    assert list_groups.status_code == 200
    assert [item["group_id"] for item in list_groups.json()] == [group_payload["group_id"]]

    get_group = client.get(f"/api/v1/job-groups/{group_payload['group_id']}")
    assert get_group.status_code == 200
    assert get_group.json()["baseline_run_id"] == baseline_run["run_id"]

    sweep_response = client.post(
        "/api/v1/sweeps",
        json={
            "study_id": study_id,
            "name": "dt sweep",
            "parameter_kind": "numerical",
            "parameter_path": "time.dt",
            "parameter_label": "dt",
            "values": [0.1, 0.2],
            "baseline_value": 0.1,
            "fixed_axes": {"solver": "noninteracting", "observable": "energy"},
            "child_run_ids": [baseline_run["run_id"], variant_run["run_id"]],
        },
    )
    assert sweep_response.status_code == 201
    sweep_payload = sweep_response.json()
    assert sweep_payload["parameter_kind"] == "numerical"
    assert sweep_payload["state"] == "succeeded"
    assert sweep_payload["values"] == [0.1, 0.2]

    list_sweeps = client.get("/api/v1/sweeps", params={"study_id": study_id})
    assert list_sweeps.status_code == 200
    assert [item["sweep_id"] for item in list_sweeps.json()] == [sweep_payload["sweep_id"]]

    baseline_detail = client.get(f"/api/v1/runs/{baseline_run['run_id']}").json()
    variant_detail = client.get(f"/api/v1/runs/{variant_run['run_id']}").json()
    assert baseline_detail["research_metadata"]["group_id"] == group_payload["group_id"]
    assert variant_detail["research_metadata"]["group_id"] == group_payload["group_id"]
    assert baseline_detail["research_metadata"]["sweep_id"] == sweep_payload["sweep_id"]
    assert variant_detail["research_metadata"]["sweep_id"] == sweep_payload["sweep_id"]

    analysis_response = client.post(
        "/api/v1/derived-analyses",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": baseline_run["run_id"],
            "analysis_type": "fft_preview",
            "analysis_version": "v1",
            "cache_key": f"fft:{baseline_run['run_id']}:pairing_d",
            "status": "succeeded",
            "parameters": {"observable": "pairing_d", "mode": "magnitude"},
            "input_surface_ids": [baseline_run["run_id"]],
            "result_metadata": {"peak_frequency": 2.0},
            "data_refs": ["analysis/fft-preview.json"],
            "supports_bundle_ids": [],
        },
    )
    assert analysis_response.status_code == 201
    analysis_payload = analysis_response.json()
    assert analysis_payload["source_kind"] == "run"
    assert analysis_payload["status"] == "succeeded"

    list_analyses = client.get(
        "/api/v1/derived-analyses",
        params={"study_id": study_id, "source_kind": "run", "source_id": baseline_run["run_id"]},
    )
    assert list_analyses.status_code == 200
    assert [item["analysis_id"] for item in list_analyses.json()] == [analysis_payload["analysis_id"]]

    get_analysis = client.get(f"/api/v1/derived-analyses/{analysis_payload['analysis_id']}")
    assert get_analysis.status_code == 200
    assert get_analysis.json()["cache_key"] == f"fft:{baseline_run['run_id']}:pairing_d"


def test_parent_artifact_state_tracks_child_run_state_updates(tmp_path, sample_config):
    runs_dir = tmp_path / "runs"
    storage = FileRunStorage(runs_dir)
    registry = ExperimentRegistry(tmp_path / "experiment-registry.sqlite")
    repository = ExperimentRepository(storage=storage, registry=registry)

    study = repository.create_study(
        StudyCreate(
            title="Parent state aggregation",
            question="Do group and sweep states follow their child runs?",
            baseline_preset_id="square-4x4-baseline",
            target_observables=["density"],
            primary_surfaces=["compare-jobs", "parameter-sweep"],
            acceptance_checks=["parent artifacts aggregate child states"],
            status="planning",
            notes_on_scope="Workflow-only regression.",
        )
    )
    run_a = repository.create_run(SimulationConfig.model_validate(sample_config))
    run_b = repository.create_run(SimulationConfig.model_validate({**sample_config, "name": "queued-variant"}))

    group = repository.create_job_group(
        JobGroupCreate(
            study_id=study.study_id,
            name="queued compare",
            comparison_kind=ComparisonKind.REGRESSION,
            baseline_run_id=run_a.run_id,
            base_config=sample_config,
            child_run_ids=[run_a.run_id, run_b.run_id],
        )
    )
    sweep = repository.create_sweep(
        SweepCreate(
            study_id=study.study_id,
            name="queued dt sweep",
            parameter_kind="numerical",
            parameter_path="time.dt",
            parameter_label="dt",
            values=[0.1, 0.2],
            baseline_value=0.1,
            fixed_axes={"solver": "noninteracting"},
            child_run_ids=[run_a.run_id, run_b.run_id],
        )
    )

    assert group.state == ArtifactLifecycleState.QUEUED
    assert sweep.state == ArtifactLifecycleState.QUEUED

    repository.update_status(run_a.run_id, RunState.RUNNING, message="run a started")
    assert repository.get_job_group(group.group_id).state == ArtifactLifecycleState.RUNNING
    assert repository.get_sweep(sweep.sweep_id).state == ArtifactLifecycleState.RUNNING

    repository.update_status(run_a.run_id, RunState.SUCCEEDED, message="run a done")
    repository.update_status(run_b.run_id, RunState.FAILED, error="benchmark mismatch")
    assert repository.get_job_group(group.group_id).state == ArtifactLifecycleState.FAILED
    assert repository.get_sweep(sweep.sweep_id).state == ArtifactLifecycleState.FAILED
