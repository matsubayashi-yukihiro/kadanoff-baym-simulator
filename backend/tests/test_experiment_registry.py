from __future__ import annotations

import sqlite3
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


def test_existing_evidence_bundle_table_is_migrated_with_status_column(tmp_path):
    db_path = tmp_path / "experiment-registry.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE evidence_bundles (
                bundle_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                title TEXT NOT NULL,
                claim_candidate TEXT NOT NULL,
                artifact_refs_json TEXT NOT NULL,
                analysis_refs_json TEXT NOT NULL,
                validation_scope TEXT,
                reproduction_recipe TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    ExperimentRegistry(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence_bundles)").fetchall()}
    assert "status" in columns


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

    analysis_response = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "fft_preview",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [run_id],
        },
    )
    assert analysis_response.status_code == 201
    analysis_id = analysis_response.json()["analysis_id"]

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
            "analysis_refs": [analysis_id],
            "validation_scope": "Workbench metadata only; does not alter solver validation labels.",
            "reproduction_recipe": "Create study, run baseline, attach note, then bundle the run reference.",
            "status": "ready",
        },
    )
    assert bundle_response.status_code == 201
    bundle_payload = bundle_response.json()
    assert bundle_payload["artifact_refs"] == [{"artifact_kind": "run", "artifact_id": run_id}]
    assert bundle_payload["analysis_refs"] == [analysis_id]
    assert bundle_payload["status"] == "ready"

    list_bundles = client.get("/api/v1/evidence-bundles", params={"study_id": study_id})
    assert list_bundles.status_code == 200
    assert [item["bundle_id"] for item in list_bundles.json()] == [bundle_payload["bundle_id"]]

    ready_bundles = client.get("/api/v1/evidence-bundles", params={"status": "ready"})
    assert ready_bundles.status_code == 200
    assert [item["bundle_id"] for item in ready_bundles.json()] == [bundle_payload["bundle_id"]]

    get_analysis = client.get(f"/api/v1/derived-analyses/{analysis_id}")
    assert get_analysis.status_code == 200
    assert get_analysis.json()["supports_bundle_ids"] == [bundle_payload["bundle_id"]]

    resolved_bundle = client.get(f"/api/v1/evidence-bundles/{bundle_payload['bundle_id']}/resolved")
    assert resolved_bundle.status_code == 200
    resolved_payload = resolved_bundle.json()
    assert resolved_payload["bundle"]["status"] == "ready"
    assert resolved_payload["resolved_artifacts"][0]["artifact_kind"] == "run"
    assert resolved_payload["resolved_artifacts"][0]["artifact_id"] == run_id
    assert resolved_payload["resolved_artifacts"][0]["label"] == sample_config["name"]
    assert resolved_payload["resolved_artifacts"][0]["state"] == "succeeded"
    assert resolved_payload["resolved_analyses"][0]["analysis_id"] == analysis_id
    assert resolved_payload["resolved_analyses"][0]["analysis_type"] == "fft_preview"
    assert resolved_payload["resolved_analyses"][0]["supports_bundle_ids"] == [bundle_payload["bundle_id"]]

    get_study = client.get(f"/api/v1/studies/{study_id}")
    assert get_study.status_code == 200
    assert get_study.json()["title"] == "Numerical validation sweep prep"


def test_evidence_bundle_list_supports_status_and_study_filters(client):
    first_study = client.post(
        "/api/v1/studies",
        json={
            "title": "Bundle filter study A",
            "question": "Which bundles are ready in study A?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": ["ready bundle remains queryable"],
            "status": "active",
            "notes_on_scope": "Filter coverage.",
        },
    ).json()
    second_study = client.post(
        "/api/v1/studies",
        json={
            "title": "Bundle filter study B",
            "question": "Which bundles are ready in study B?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["pairing_d"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": ["draft bundle is excluded"],
            "status": "active",
            "notes_on_scope": "Filter coverage.",
        },
    ).json()

    ready_bundle = client.post(
        "/api/v1/evidence-bundles",
        json={
            "study_id": first_study["study_id"],
            "title": "Ready bundle",
            "claim_candidate": "Ready bundles should be queryable by status and study.",
            "artifact_refs": [],
            "analysis_refs": [],
            "validation_scope": "Metadata only.",
            "reproduction_recipe": "Create bundle.",
            "status": "ready",
        },
    )
    assert ready_bundle.status_code == 201

    draft_bundle = client.post(
        "/api/v1/evidence-bundles",
        json={
            "study_id": second_study["study_id"],
            "title": "Draft bundle",
            "claim_candidate": "Draft bundles should not leak into ready filter results.",
            "artifact_refs": [],
            "analysis_refs": [],
            "validation_scope": "Metadata only.",
            "reproduction_recipe": "Create bundle.",
            "status": "draft",
        },
    )
    assert draft_bundle.status_code == 201

    ready_list = client.get("/api/v1/evidence-bundles", params={"status": "ready"})
    assert ready_list.status_code == 200
    assert [item["bundle_id"] for item in ready_list.json()] == [ready_bundle.json()["bundle_id"]]

    study_scoped_ready_list = client.get(
        "/api/v1/evidence-bundles",
        params={"study_id": first_study["study_id"], "status": "ready"},
    )
    assert study_scoped_ready_list.status_code == 200
    assert [item["bundle_id"] for item in study_scoped_ready_list.json()] == [ready_bundle.json()["bundle_id"]]


def test_evidence_bundle_rejects_cross_study_analysis_reference(client, sample_config):
    study_a_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Study A",
            "question": "A",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": [],
            "status": "active",
        },
    ).json()["study_id"]
    study_b_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Study B",
            "question": "B",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": [],
            "status": "active",
        },
    ).json()["study_id"]

    run_id = client.post("/api/v1/runs", json=sample_config).json()["run_id"]
    client.patch(f"/api/v1/runs/{run_id}/metadata", json={"study_id": study_a_id})
    analysis_id = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_a_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "fft_preview",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [run_id],
        },
    ).json()["analysis_id"]

    bundle_response = client.post(
        "/api/v1/evidence-bundles",
        json={
            "study_id": study_b_id,
            "title": "Invalid cross-study bundle",
            "claim_candidate": "Should fail.",
            "artifact_refs": [],
            "analysis_refs": [analysis_id],
            "validation_scope": "workflow",
            "reproduction_recipe": "n/a",
        },
    )
    assert bundle_response.status_code == 422
    assert bundle_response.json()["detail"] == "evidence bundle references must belong to the same study"


def test_evidence_bundle_patch_updates_status_and_analysis_support_links(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Bundle patch study",
            "question": "Can bundle patch update analysis provenance links?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": [],
            "status": "active",
        },
    ).json()["study_id"]

    first_run_id = client.post("/api/v1/runs", json=sample_config).json()["run_id"]
    second_config = {**sample_config, "name": "bundle-patch-second"}
    second_run_id = client.post("/api/v1/runs", json=second_config).json()["run_id"]

    first_analysis_id = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": first_run_id,
            "analysis_type": "fft_preview",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [first_run_id],
        },
    ).json()["analysis_id"]
    second_analysis_id = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": second_run_id,
            "analysis_type": "fft_preview",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [second_run_id],
        },
    ).json()["analysis_id"]

    bundle_id = client.post(
        "/api/v1/evidence-bundles",
        json={
            "study_id": study_id,
            "title": "Patchable bundle",
            "claim_candidate": "Initial draft.",
            "artifact_refs": [{"artifact_kind": "run", "artifact_id": first_run_id}],
            "analysis_refs": [first_analysis_id],
            "status": "draft",
        },
    ).json()["bundle_id"]

    patch_response = client.patch(
        f"/api/v1/evidence-bundles/{bundle_id}",
        json={
            "title": "Patched bundle",
            "claim_candidate": "Updated claim.",
            "analysis_refs": [second_analysis_id],
            "status": "superseded",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["title"] == "Patched bundle"
    assert patched["claim_candidate"] == "Updated claim."
    assert patched["analysis_refs"] == [second_analysis_id]
    assert patched["status"] == "superseded"

    first_analysis = client.get(f"/api/v1/derived-analyses/{first_analysis_id}").json()
    second_analysis = client.get(f"/api/v1/derived-analyses/{second_analysis_id}").json()
    assert first_analysis["supports_bundle_ids"] == []
    assert second_analysis["supports_bundle_ids"] == [bundle_id]

    resolved = client.get(f"/api/v1/evidence-bundles/{bundle_id}/resolved").json()
    assert resolved["bundle"]["status"] == "superseded"
    assert [item["analysis_id"] for item in resolved["resolved_analyses"]] == [second_analysis_id]


def test_derived_analysis_and_bundle_payloads_survive_repository_restart(tmp_path, sample_config):
    settings = AppSettings(
        data_dir=tmp_path / "runs",
        registry_db_path=tmp_path / "experiment-registry.sqlite",
        job_mode="inline",
    )
    app = create_app(settings=settings, runner=InlineJobRunner())

    with TestClient(app) as client:
        study_id = client.post(
            "/api/v1/studies",
            json={
                "title": "Restart persistence study",
                "question": "Do analysis payloads and bundles survive restart?",
                "baseline_preset_id": "square-4x4-baseline",
                "target_observables": ["energy"],
                "primary_surfaces": ["single-job"],
                "acceptance_checks": [],
                "status": "active",
            },
        ).json()["study_id"]
        run_id = client.post("/api/v1/runs", json=sample_config).json()["run_id"]
        analysis_id = client.post(
            "/api/v1/derived-analyses/launch",
            json={
                "study_id": study_id,
                "source_kind": "run",
                "source_id": run_id,
                "analysis_type": "fft_preview",
                "parameters": {"observable": "energy"},
                "input_surface_ids": [run_id],
            },
        ).json()["analysis_id"]
        bundle_id = client.post(
            "/api/v1/evidence-bundles",
            json={
                "study_id": study_id,
                "title": "Restart bundle",
                "claim_candidate": "Persisted artifact graph remains readable.",
                "artifact_refs": [{"artifact_kind": "run", "artifact_id": run_id}],
                "analysis_refs": [analysis_id],
                "status": "ready",
            },
        ).json()["bundle_id"]

    restarted_app = create_app(settings=settings, runner=InlineJobRunner())
    with TestClient(restarted_app) as client:
        analysis_result = client.get(f"/api/v1/derived-analyses/{analysis_id}/result")
        assert analysis_result.status_code == 200
        assert analysis_result.json()["payload"]["name"] == "energy_fft_preview"

        bundle = client.get(f"/api/v1/evidence-bundles/{bundle_id}")
        assert bundle.status_code == 200
        assert bundle.json()["status"] == "ready"

        resolved = client.get(f"/api/v1/evidence-bundles/{bundle_id}/resolved")
        assert resolved.status_code == 200
        resolved_payload = resolved.json()
        assert resolved_payload["bundle"]["bundle_id"] == bundle_id
        assert resolved_payload["resolved_artifacts"][0]["artifact_id"] == run_id
        assert resolved_payload["resolved_analyses"][0]["analysis_id"] == analysis_id
        assert resolved_payload["resolved_analyses"][0]["supports_bundle_ids"] == [bundle_id]


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


def test_job_group_launch_creates_child_runs_and_syncs_variant_labels(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Launched compare group",
            "question": "Can compare jobs launch child runs from a base config?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["compare-jobs"],
            "acceptance_checks": ["variant labels remain attached to child runs"],
            "status": "active",
            "notes_on_scope": "Backend launch semantics regression.",
        },
    ).json()["study_id"]

    launch_response = client.post(
        "/api/v1/job-groups/launch",
        json={
            "study_id": study_id,
            "name": "dt compare launch",
            "comparison_kind": "numerical_validation",
            "base_config": sample_config,
            "variants": [
                {
                    "label": "dt=0.1",
                    "description": "baseline timestep",
                    "config_patch": {"time": {"dt": 0.1}},
                },
                {
                    "label": "dt=0.2",
                    "description": "coarser timestep",
                    "config_patch": {"time": {"dt": 0.2, "t_final": 0.4}},
                },
            ],
        },
    )

    assert launch_response.status_code == 201
    payload = launch_response.json()
    assert payload["state"] == "succeeded"
    assert len(payload["child_run_ids"]) == 2
    assert payload["baseline_run_id"] == payload["child_run_ids"][0]
    assert [variant["run_id"] for variant in payload["variants"]] == payload["child_run_ids"]

    baseline_run = client.get(f"/api/v1/runs/{payload['child_run_ids'][0]}").json()
    coarse_run = client.get(f"/api/v1/runs/{payload['child_run_ids'][1]}").json()
    assert baseline_run["config"]["time"]["dt"] == 0.1
    assert coarse_run["config"]["time"]["dt"] == 0.2
    assert baseline_run["research_metadata"]["group_id"] == payload["group_id"]
    assert coarse_run["research_metadata"]["group_id"] == payload["group_id"]
    assert baseline_run["research_metadata"]["variant_label"] == "dt=0.1"
    assert coarse_run["research_metadata"]["variant_label"] == "dt=0.2"
    assert baseline_run["name"] == "dt compare launch [dt=0.1]"
    assert coarse_run["name"] == "dt compare launch [dt=0.2]"


def test_sweep_launch_creates_child_runs_from_parameter_path(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Launched sweep",
            "question": "Can parameter sweeps launch child runs from a base config?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["parameter-sweep"],
            "acceptance_checks": ["parameter path is reflected in child run configs"],
            "status": "active",
            "notes_on_scope": "Backend launch semantics regression.",
        },
    ).json()["study_id"]

    launch_response = client.post(
        "/api/v1/sweeps/launch",
        json={
            "study_id": study_id,
            "name": "dt sweep launch",
            "parameter_kind": "numerical",
            "parameter_path": "time.dt",
            "parameter_label": "dt",
            "values": [0.1, 0.2],
            "baseline_value": 0.1,
            "fixed_axes": {"solver": "noninteracting", "observable": "energy"},
            "base_config": sample_config,
        },
    )

    assert launch_response.status_code == 201
    payload = launch_response.json()
    assert payload["state"] == "succeeded"
    assert payload["values"] == [0.1, 0.2]
    assert len(payload["child_run_ids"]) == 2

    baseline_run = client.get(f"/api/v1/runs/{payload['child_run_ids'][0]}").json()
    coarse_run = client.get(f"/api/v1/runs/{payload['child_run_ids'][1]}").json()
    assert baseline_run["config"]["time"]["dt"] == 0.1
    assert coarse_run["config"]["time"]["dt"] == 0.2
    assert baseline_run["research_metadata"]["sweep_id"] == payload["sweep_id"]
    assert coarse_run["research_metadata"]["sweep_id"] == payload["sweep_id"]
    assert baseline_run["research_metadata"]["variant_label"] == "dt=0.1"
    assert coarse_run["research_metadata"]["variant_label"] == "dt=0.2"
    assert baseline_run["name"] == "dt sweep launch [dt=0.1]"
    assert coarse_run["name"] == "dt sweep launch [dt=0.2]"


def test_sweep_launch_rejects_unknown_parameter_path(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Invalid sweep",
            "question": "Does sweep launch reject unknown config paths?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["parameter-sweep"],
            "acceptance_checks": ["invalid parameter paths fail fast"],
            "status": "planning",
            "notes_on_scope": "Validation of launch payloads.",
        },
    ).json()["study_id"]

    launch_response = client.post(
        "/api/v1/sweeps/launch",
        json={
            "study_id": study_id,
            "name": "broken sweep launch",
            "parameter_kind": "numerical",
            "parameter_path": "time.unknown_dt",
            "parameter_label": "dt",
            "values": [0.1, 0.2],
            "baseline_value": 0.1,
            "fixed_axes": {"solver": "noninteracting"},
            "base_config": sample_config,
        },
    )

    assert launch_response.status_code == 422
    assert "parameter_path" in launch_response.json()["detail"]


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


def test_parent_artifact_state_treats_succeeded_with_warnings_as_succeeded(tmp_path, sample_config):
    runs_dir = tmp_path / "runs"
    storage = FileRunStorage(runs_dir)
    registry = ExperimentRegistry(tmp_path / "experiment-registry.sqlite")
    repository = ExperimentRepository(storage=storage, registry=registry)

    study = repository.create_study(
        StudyCreate(
            title="Parent state warning aggregation",
            question="Do parent artifacts remain succeeded when children are succeeded_with_warnings?",
            baseline_preset_id="square-4x4-baseline",
            target_observables=["density"],
            primary_surfaces=["compare-jobs", "parameter-sweep"],
            acceptance_checks=["succeeded_with_warnings is normalized for parent lifecycle state"],
            status="planning",
            notes_on_scope="Workflow-only regression.",
        )
    )
    run_a = repository.create_run(SimulationConfig.model_validate(sample_config))
    run_b = repository.create_run(SimulationConfig.model_validate({**sample_config, "name": "warning-variant"}))

    group = repository.create_job_group(
        JobGroupCreate(
            study_id=study.study_id,
            name="warning compare",
            comparison_kind=ComparisonKind.REGRESSION,
            baseline_run_id=run_a.run_id,
            base_config=sample_config,
            child_run_ids=[run_a.run_id, run_b.run_id],
        )
    )
    sweep = repository.create_sweep(
        SweepCreate(
            study_id=study.study_id,
            name="warning dt sweep",
            parameter_kind="numerical",
            parameter_path="time.dt",
            parameter_label="dt",
            values=[0.1, 0.2],
            baseline_value=0.1,
            fixed_axes={"solver": "noninteracting"},
            child_run_ids=[run_a.run_id, run_b.run_id],
        )
    )

    repository.update_status(run_a.run_id, RunState.SUCCEEDED_WITH_WARNINGS, message="run a warning")
    repository.update_status(run_b.run_id, RunState.SUCCEEDED, message="run b done")

    assert repository.get_job_group(group.group_id).state == ArtifactLifecycleState.SUCCEEDED
    assert repository.get_sweep(sweep.sweep_id).state == ArtifactLifecycleState.SUCCEEDED
