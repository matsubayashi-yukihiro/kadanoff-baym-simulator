from copy import deepcopy
import json
import subprocess
import sys
import time

import numpy as np
import pytest

from backend.app.core.settings import AppSettings
from backend.app.main import create_app
from backend.app.schemas import RunState, SimulationConfig
from backend.app.services.run_service import build_higgs_demo_preset

pytestmark = pytest.mark.workflow


class _NeverCancelRunner:
    def submit(self, run_id, config, data_dir, registry_db_path):
        return None

    def cancel(self, run_id):
        return False


def test_api_run_lifecycle(client, sample_config):
    create_response = client.post("/api/v1/runs", json=sample_config)
    assert create_response.status_code == 202

    run_payload = create_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["state"] == "succeeded"
    assert run_payload["available_observables"]

    list_response = client.get("/api/v1/runs")
    assert list_response.status_code == 200
    assert any(item["run_id"] == run_id for item in list_response.json())

    detail_response = client.get(f"/api/v1/runs/{run_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["diagnostics"]["site_count"] == 4

    observable_list = client.get(f"/api/v1/runs/{run_id}/observables")
    assert observable_list.status_code == 200
    assert "energy" in observable_list.json()["observables"]

    energy_response = client.get(f"/api/v1/runs/{run_id}/observables/energy")
    energy_payload = energy_response.json()
    assert energy_response.status_code == 200
    assert energy_payload["name"] == "energy"
    assert len(energy_payload["time"]) == 5
    assert energy_payload["series"][0]["label"] == "total"


def test_api_observable_response_respects_save_every(client, sample_config):
    config = deepcopy(sample_config)
    config["time"]["save_every"] = 2

    create_response = client.post("/api/v1/runs", json=config)
    run_id = create_response.json()["run_id"]

    energy_response = client.get(f"/api/v1/runs/{run_id}/observables/energy")
    energy_payload = energy_response.json()

    assert energy_response.status_code == 200
    assert energy_payload["time"] == [0.0, 0.2, 0.4]
    assert len(energy_payload["series"][0]["values"]) == 3


def test_api_exposes_run_progress_record(client, sample_config):
    create_response = client.post("/api/v1/runs", json=sample_config)
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]

    progress_response = client.get(f"/api/v1/runs/{run_id}/progress")
    assert progress_response.status_code == 200
    progress = progress_response.json()

    assert progress["run_id"] == run_id
    assert progress["state"] == "succeeded"
    assert progress["phase"] == "succeeded"
    assert progress["physical_time_final"] == pytest.approx(sample_config["time"]["t_final"])
    assert progress["requested_steps"] == 4
    assert progress["history"]
    assert progress["status_line"] == "simulation completed"


def test_api_accepts_k_space_runs_and_exposes_native_artifact_contract(client):
    config = {
        "name": "k-space-native-run",
        "solver": "tdhfb",
        "representation": "k_space",
        "lattice": {
            "nx": 4,
            "ny": 4,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.01,
            "frequency": 1.2,
            "phase": 0.1,
            "center": 0.12,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -1.0,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.2,
            "seed_pairing": 0.0,
        },
        "observables": ["density", "energy", "current_x", "current_y"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]
    run_dir = client.app.state.run_service.repository.storage.run_dir(run_id)

    detail = client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["diagnostics"]["solver_representation"] == "k_space"
    assert not (run_dir / "green_functions.json").exists()
    assert (run_dir / "kspace_native.json").exists()

    green_catalog = client.get(f"/api/v1/runs/{run_id}/green-functions")
    assert green_catalog.status_code == 409
    assert green_catalog.json()["detail"]["code"] == "k_space_full_matrix_artifact_disabled"

    native_catalog = client.get(f"/api/v1/runs/{run_id}/kspace-native/catalog")
    assert native_catalog.status_code == 200
    assert native_catalog.json()["components"] == ["lesser"]
    assert native_catalog.json()["nambu_dimension"] == 2


def test_api_accepts_k_space_second_born_reference_runs_and_exposes_native_artifact_contract(client):
    config = {
        "name": "k-space-reference-run",
        "solver": "kbe_hfb",
        "representation": "k_space",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.02,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -0.6,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.2,
            "seed_pairing": 0.0,
        },
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 8,
            "tolerance": 1e-6,
            "mixing": 0.35,
        },
        "thermal_branch": {
            "enabled": True,
            "n_tau": 8,
            "max_iterations": 8,
            "mixing": 0.4,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]
    run_dir = client.app.state.run_service.repository.storage.run_dir(run_id)

    detail = client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    diagnostics = detail.json()["diagnostics"]
    assert diagnostics["solver_representation"] == "k_space"
    assert diagnostics["second_born_reference_implementation"] is True
    assert not (run_dir / "green_functions.json").exists()
    assert (run_dir / "kspace_native.json").exists()

    green_catalog = client.get(f"/api/v1/runs/{run_id}/green-functions")
    assert green_catalog.status_code == 409
    assert green_catalog.json()["detail"]["code"] == "k_space_full_matrix_artifact_disabled"

    native_catalog = client.get(f"/api/v1/runs/{run_id}/kspace-native/catalog")
    assert native_catalog.status_code == 200
    native_slice = client.get(
        f"/api/v1/runs/{run_id}/kspace-native/lesser",
        params={
            "row_start": 0,
            "row_stop": 1,
            "col_start": 0,
            "col_stop": 1,
            "k_start": 0,
            "k_stop": 1,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert native_slice.status_code == 200
    assert native_slice.json()["shape"] == [1, 1, 1, 2, 2]


def test_api_launches_and_reuses_fft_derived_analysis_artifacts(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "FFT artifact study",
            "question": "Can backend FFT artifacts be cached and re-read?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["single-job"],
            "acceptance_checks": ["FFT payload is persisted and cacheable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for derived analysis lifecycle.",
        },
    ).json()["study_id"]

    run_id = client.post("/api/v1/runs", json=sample_config).json()["run_id"]

    launch_payload = {
        "study_id": study_id,
        "source_kind": "run",
        "source_id": run_id,
        "analysis_type": "fft_preview",
        "analysis_version": "v1",
        "parameters": {"observable": "energy"},
        "input_surface_ids": [run_id],
    }

    launch_response = client.post("/api/v1/derived-analyses/launch", json=launch_payload)
    assert launch_response.status_code == 201
    analysis = launch_response.json()
    assert analysis["status"] == "succeeded"
    assert analysis["data_refs"]
    assert analysis["result_metadata"]["observable"] == "energy"

    result_response = client.get(f"/api/v1/derived-analyses/{analysis['analysis_id']}/result")
    assert result_response.status_code == 200
    result = result_response.json()
    assert result["payload_kind"] == "observable"
    assert result["analysis"]["analysis_id"] == analysis["analysis_id"]
    assert result["payload"]["name"] == "energy_fft_preview"
    assert result["payload"]["metadata"]["source_observable"] == "energy"
    assert result["payload"]["metadata"]["axis"] == "frequency"

    cached_launch_response = client.post("/api/v1/derived-analyses/launch", json=launch_payload)
    assert cached_launch_response.status_code == 201
    cached_analysis = cached_launch_response.json()
    assert cached_analysis["analysis_id"] == analysis["analysis_id"]

    list_response = client.get(
        "/api/v1/derived-analyses",
        params={"study_id": study_id, "source_kind": "run", "source_id": run_id},
    )
    assert list_response.status_code == 200
    assert [item["analysis_id"] for item in list_response.json()] == [analysis["analysis_id"]]


def test_api_launches_group_and_sweep_fft_derived_analysis_artifacts(client, sample_config):
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "Compare and sweep FFT artifacts",
            "question": "Can compare and sweep artifacts reuse backend-generated FFT payloads?",
            "baseline_preset_id": "square-4x4-baseline",
            "target_observables": ["energy"],
            "primary_surfaces": ["compare-jobs", "parameter-sweep"],
            "acceptance_checks": ["group and sweep payloads remain re-fetchable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for compare/sweep derived analysis lifecycle.",
        },
    ).json()["study_id"]

    baseline_run_id = client.post("/api/v1/runs", json=sample_config).json()["run_id"]
    coarse_config = deepcopy(sample_config)
    coarse_config["name"] = "test-run-dt-0.2"
    coarse_config["time"]["dt"] = 0.2
    variant_run_id = client.post("/api/v1/runs", json=coarse_config).json()["run_id"]

    group_id = client.post(
        "/api/v1/job-groups",
        json={
            "study_id": study_id,
            "name": "energy dt compare",
            "comparison_kind": "numerical_validation",
            "baseline_run_id": baseline_run_id,
            "base_config": sample_config,
            "variants": [
                {"label": "dt=0.1", "config_patch": {"time": {"dt": 0.1}}, "run_id": baseline_run_id},
                {"label": "dt=0.2", "config_patch": {"time": {"dt": 0.2}}, "run_id": variant_run_id},
            ],
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["group_id"]

    sweep_id = client.post(
        "/api/v1/sweeps",
        json={
            "study_id": study_id,
            "name": "energy dt sweep",
            "parameter_kind": "numerical",
            "parameter_path": "time.dt",
            "parameter_label": "dt",
            "values": [0.1, 0.2],
            "baseline_value": 0.1,
            "fixed_axes": {"observable": "energy"},
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["sweep_id"]

    group_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "fft_compare",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [group_id],
        },
    )
    assert group_launch.status_code == 201
    group_analysis = group_launch.json()
    assert group_analysis["status"] == "succeeded"
    assert group_analysis["result_metadata"]["run_count"] == 2

    group_result = client.get(f"/api/v1/derived-analyses/{group_analysis['analysis_id']}/result")
    assert group_result.status_code == 200
    group_payload = group_result.json()["payload"]
    assert group_payload["name"] == "energy_fft_compare"
    assert [entry["label"] for entry in group_payload["entries"]] == ["dt=0.1", "dt=0.2"]
    assert group_payload["entries"][0]["is_baseline"] is True

    group_cached = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "fft_compare",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [group_id],
        },
    )
    assert group_cached.status_code == 201
    assert group_cached.json()["analysis_id"] == group_analysis["analysis_id"]

    sweep_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "sweep",
            "source_id": sweep_id,
            "analysis_type": "fft_heatmap",
            "parameters": {"observable": "energy"},
            "input_surface_ids": [sweep_id],
        },
    )
    assert sweep_launch.status_code == 201
    sweep_analysis = sweep_launch.json()
    assert sweep_analysis["status"] == "succeeded"
    assert sweep_analysis["result_metadata"]["sweep_point_count"] == 2

    sweep_result = client.get(f"/api/v1/derived-analyses/{sweep_analysis['analysis_id']}/result")
    assert sweep_result.status_code == 200
    sweep_payload = sweep_result.json()["payload"]
    assert sweep_payload["name"] == "energy_fft_heatmap"
    assert sweep_payload["parameter_values"] == [0.1, 0.2]
    assert len(sweep_payload["intensity"]) == 2
    assert len(sweep_payload["intensity"][0]) == len(sweep_payload["frequency"])
    assert sweep_payload["interpolated_to_common_grid"] is True


def test_api_launches_k_space_and_trarpes_derived_analysis_artifacts(client):
    config = {
        "name": "k-space-preview-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "k-space preview study",
            "question": "Can backend derived analyses produce k-space and tr-ARPES preview payloads?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum", "tr_arpes"],
            "primary_surfaces": ["single-job", "k_spectrum", "tr_arpes"],
            "acceptance_checks": ["run-backed k-space payloads are cacheable and re-readable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for k-space derived-analysis lifecycle.",
        },
    ).json()["study_id"]
    run_id = client.post("/api/v1/runs", json=config).json()["run_id"]

    k_space_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "k_spectral_preview",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.2,
                "probe_width": 0.12,
                "broadening": 0.08,
                "observable_scope": "occupied_spectrum",
            },
            "input_surface_ids": [run_id],
        },
    )
    assert k_space_launch.status_code == 201
    analysis = k_space_launch.json()
    assert analysis["status"] == "succeeded"
    assert analysis["result_metadata"]["observable_scope"] == "occupied_spectrum"
    assert analysis["result_metadata"]["k_surface_kind"] == "k_path"

    k_space_result = client.get(f"/api/v1/derived-analyses/{analysis['analysis_id']}/result")
    assert k_space_result.status_code == 200
    payload = k_space_result.json()["payload"]
    assert payload["analysis_type"] == "k_spectral_preview"
    assert payload["observable_scope"] == "occupied_spectrum"
    assert payload["measurement_model"] == "minimal_matrix_element_free_tr_arpes"
    assert payload["source_self_energy"] == "hfb"
    assert payload["k_surface"]["kind"] == "k_path"
    assert payload["k_surface"]["tick_labels"] == ["Gamma", "X", "M", "Gamma"]
    assert len(payload["intensity"]) == len(payload["k_surface"]["points"])
    assert len(payload["intensity"][0]) == len(payload["energy"])
    assert payload["gap_indicator"]["minimum_gap_energy"] >= 0.0

    cached_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "k_spectral_preview",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.2,
                "probe_width": 0.12,
                "broadening": 0.08,
                "observable_scope": "occupied_spectrum",
            },
            "input_surface_ids": [run_id],
        },
    )
    assert cached_launch.status_code == 201
    assert cached_launch.json()["analysis_id"] == analysis["analysis_id"]

    tr_arpes_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "tr_arpes_preview",
            "parameters": {
                "k_grid": {"kind": "discrete_bz"},
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_center": 0.1,
                "probe_width": 0.08,
                "broadening": 0.08,
                "observable_scope": "tr_arpes_intensity",
            },
            "input_surface_ids": [run_id],
        },
    )
    assert tr_arpes_launch.status_code == 201
    tr_arpes_analysis = tr_arpes_launch.json()
    assert tr_arpes_analysis["result_metadata"]["observable_scope"] == "tr_arpes_intensity"
    assert tr_arpes_analysis["result_metadata"]["k_surface_kind"] == "k_grid"
    tr_arpes_result = client.get(f"/api/v1/derived-analyses/{tr_arpes_analysis['analysis_id']}/result")
    assert tr_arpes_result.status_code == 200
    tr_arpes_payload = tr_arpes_result.json()["payload"]
    assert tr_arpes_payload["analysis_type"] == "tr_arpes_preview"
    assert tr_arpes_payload["observable_scope"] == "tr_arpes_intensity"
    assert tr_arpes_payload["k_surface"]["kind"] == "k_grid"


def test_api_launches_k_space_preview_from_second_born_reference_source(client):
    config = {
        "name": "k-space-reference-preview-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.02,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -0.6,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 8,
            "tolerance": 1e-7,
            "mixing": 0.35,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "reference-source k-space preview study",
            "question": "Can backend derived analyses reuse second_born_reference runs as real-space sources?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum"],
            "primary_surfaces": ["single-job", "k_spectrum"],
            "acceptance_checks": ["second_born_reference source is preserved in the derived-analysis payload"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for correlated real-space source reuse.",
        },
    ).json()["study_id"]
    run_id = client.post("/api/v1/runs", json=config).json()["run_id"]

    launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "k_spectral_preview",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.2,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [run_id],
        },
    )
    assert launch.status_code == 201

    result = client.get(f"/api/v1/derived-analyses/{launch.json()['analysis_id']}/result")
    assert result.status_code == 200
    payload = result.json()["payload"]

    assert payload["source_run_solver"] == "kbe_hfb"
    assert payload["source_self_energy"] == "second_born_reference"
    assert payload["measurement_model"] == "minimal_matrix_element_free_tr_arpes"
    assert payload["k_surface"]["kind"] == "k_path"
    assert len(payload["intensity"]) == len(payload["k_surface"]["points"])
    assert len(payload["intensity"][0]) == len(payload["energy"])
    assert min(min(row) for row in payload["intensity"]) >= 0.0


def test_api_launches_run_derived_analysis_with_placeholder_study_id(client):
    config = {
        "name": "k-space-placeholder-study-run",
        "solver": "kbe_hfb",
        "representation": "k_space",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.0,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    run_id = client.post("/api/v1/runs", json=config).json()["run_id"]

    launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": "__none__",
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "tr_arpes_preview",
            "parameters": {},
            "input_surface_ids": [run_id],
        },
    )
    assert launch.status_code == 201
    launch_payload = launch.json()
    assert launch_payload["study_id"] != "__none__"

    studies = client.get("/api/v1/studies")
    assert studies.status_code == 200
    assert any(study["study_id"] == launch_payload["study_id"] for study in studies.json())

    result = client.get(f"/api/v1/derived-analyses/{launch_payload['analysis_id']}/result")
    assert result.status_code == 200
    assert result.json()["payload"]["analysis_type"] == "tr_arpes_preview"


def test_api_launches_k_space_compare_and_trarpes_heatmap_artifacts(client):
    config = {
        "name": "k-space-compare-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.1,
            "amplitude_y": 0.0,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.2,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "kbe": {"self_energy": "hfb"},
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "k-space compare and heatmap study",
            "question": "Can job-group and sweep artifacts reuse k-space derived analyses?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum", "tr_arpes"],
            "primary_surfaces": ["compare-jobs", "parameter-sweep"],
            "acceptance_checks": ["compare and heatmap payloads remain re-fetchable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for k-space compare/sweep lifecycle.",
        },
    ).json()["study_id"]

    baseline_run_id = client.post("/api/v1/runs", json=config).json()["run_id"]
    variant_config = deepcopy(config)
    variant_config["name"] = "k-space-compare-run-variant"
    variant_config["drive"]["amplitude_x"] = 0.2
    variant_run_id = client.post("/api/v1/runs", json=variant_config).json()["run_id"]

    group_id = client.post(
        "/api/v1/job-groups",
        json={
            "study_id": study_id,
            "name": "k-space compare",
            "comparison_kind": "physics_hypothesis",
            "baseline_run_id": baseline_run_id,
            "base_config": config,
            "variants": [
                {"label": "baseline", "config_patch": {"drive": {"amplitude_x": 0.1}}, "run_id": baseline_run_id},
                {"label": "pump-x2", "config_patch": {"drive": {"amplitude_x": 0.2}}, "run_id": variant_run_id},
            ],
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["group_id"]

    sweep_id = client.post(
        "/api/v1/sweeps",
        json={
            "study_id": study_id,
            "name": "tr-arpes delay sweep",
            "parameter_kind": "analysis",
            "parameter_path": "probe_center",
            "parameter_label": "probe_delay",
            "values": [0.05, 0.15],
            "baseline_value": 0.05,
            "fixed_axes": {"analysis_type": "tr_arpes_heatmap"},
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["sweep_id"]

    compare_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "k_spectral_compare",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.1,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [group_id],
        },
    )
    assert compare_launch.status_code == 201
    compare_analysis = compare_launch.json()
    assert compare_analysis["result_metadata"]["run_count"] == 2
    compare_result = client.get(f"/api/v1/derived-analyses/{compare_analysis['analysis_id']}/result")
    assert compare_result.status_code == 200
    compare_payload = compare_result.json()["payload"]
    assert compare_payload["source_kind"] == "job_group"
    assert compare_payload["k_surface"]["kind"] == "k_path"
    assert [entry["label"] for entry in compare_payload["entries"]] == ["baseline", "pump-x2"]
    assert compare_payload["entries"][0]["is_baseline"] is True
    assert len(compare_payload["entries"][0]["intensity"]) == len(compare_payload["k_surface"]["points"])

    heatmap_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "sweep",
            "source_id": sweep_id,
            "analysis_type": "tr_arpes_heatmap",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_width": 0.08,
                "broadening": 0.08,
            },
            "input_surface_ids": [sweep_id],
        },
    )
    assert heatmap_launch.status_code == 201
    heatmap_analysis = heatmap_launch.json()
    assert heatmap_analysis["result_metadata"]["sweep_point_count"] == 2
    assert heatmap_analysis["result_metadata"]["selected_k_index"] >= 0
    heatmap_result = client.get(f"/api/v1/derived-analyses/{heatmap_analysis['analysis_id']}/result")
    assert heatmap_result.status_code == 200
    heatmap_payload = heatmap_result.json()["payload"]
    assert heatmap_payload["source_kind"] == "sweep"
    assert heatmap_payload["parameter_label"] == "probe_delay"
    assert heatmap_payload["parameter_values"] == [0.05, 0.15]
    assert heatmap_payload["probe_centers"] == [0.05, 0.15]
    assert len(heatmap_payload["intensity"]) == 2
    assert len(heatmap_payload["intensity"][0]) == len(heatmap_payload["energy"])


def test_api_launches_second_born_reference_k_space_compare_and_heatmap_with_analysis_override(client):
    config = {
        "name": "k-space-reference-compare-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.02,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -0.6,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.2,
            "seed_pairing": 0.0,
        },
        "equilibrium": {
            "method": "hfb",
            "allow_approximation_mismatch": True,
        },
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 8,
            "tolerance": 1e-6,
            "mixing": 0.35,
        },
        "thermal_branch": {
            "enabled": True,
            "n_tau": 8,
            "max_iterations": 8,
            "mixing": 0.4,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "reference compare and heatmap study",
            "question": "Can compare/sweep payloads reuse second_born_reference runs across real/k representations?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum", "tr_arpes"],
            "primary_surfaces": ["compare-jobs", "parameter-sweep"],
            "acceptance_checks": ["payload parity and analysis override stay stable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for second_born_reference source consistency.",
        },
    ).json()["study_id"]

    real_run_id = client.post("/api/v1/runs", json=config).json()["run_id"]
    k_space_run_id = client.post("/api/v1/runs", json={**config, "name": "k-space-reference-compare-run-k", "representation": "k_space"}).json()["run_id"]

    group_id = client.post(
        "/api/v1/job-groups",
        json={
            "study_id": study_id,
            "name": "reference compare",
            "comparison_kind": "physics_hypothesis",
            "baseline_run_id": real_run_id,
            "base_config": config,
            "variants": [
                {"label": "real", "config_patch": {}, "run_id": real_run_id},
                {"label": "k-space", "config_patch": {"representation": "k_space"}, "run_id": k_space_run_id},
            ],
            "child_run_ids": [real_run_id, k_space_run_id],
        },
    ).json()["group_id"]

    sweep_id = client.post(
        "/api/v1/sweeps",
        json={
            "study_id": study_id,
            "name": "reference tr-arpes delay sweep",
            "parameter_kind": "analysis",
            "parameter_path": "probe_center",
            "parameter_label": "probe_delay",
            "values": [0.05, 0.15],
            "baseline_value": 0.05,
            "fixed_axes": {"analysis_type": "tr_arpes_heatmap"},
            "child_run_ids": [real_run_id, k_space_run_id],
        },
    ).json()["sweep_id"]

    compare_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "k_spectral_compare",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.1,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [group_id],
        },
    )
    assert compare_launch.status_code == 201
    compare_analysis = compare_launch.json()
    compare_result = client.get(f"/api/v1/derived-analyses/{compare_analysis['analysis_id']}/result")
    assert compare_result.status_code == 200
    compare_payload = compare_result.json()["payload"]

    assert [entry["label"] for entry in compare_payload["entries"]] == ["real", "k-space"]
    assert {entry["source_self_energy"] for entry in compare_payload["entries"]} == {"second_born_reference"}
    assert compare_payload["k_surface"]["kind"] == "k_path"
    real_intensity = np.asarray(compare_payload["entries"][0]["intensity"], dtype=float)
    k_space_intensity = np.asarray(compare_payload["entries"][1]["intensity"], dtype=float)
    assert np.max(np.abs(real_intensity - k_space_intensity)) < 1e-12

    compare_launch_with_different_grid = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "k_spectral_compare",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_center": 0.1,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [group_id],
        },
    )
    assert compare_launch_with_different_grid.status_code == 201
    assert compare_launch_with_different_grid.json()["analysis_id"] != compare_analysis["analysis_id"]
    compare_result_coarse = client.get(
        f"/api/v1/derived-analyses/{compare_launch_with_different_grid.json()['analysis_id']}/result"
    )
    assert compare_result_coarse.status_code == 200
    assert len(compare_payload["energy"]) == 81
    assert len(compare_result_coarse.json()["payload"]["energy"]) == 61

    heatmap_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "sweep",
            "source_id": sweep_id,
            "analysis_type": "tr_arpes_heatmap",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_width": 0.08,
                "broadening": 0.08,
            },
            "input_surface_ids": [sweep_id],
        },
    )
    assert heatmap_launch.status_code == 201
    heatmap_analysis = heatmap_launch.json()
    heatmap_result = client.get(f"/api/v1/derived-analyses/{heatmap_analysis['analysis_id']}/result")
    assert heatmap_result.status_code == 200
    heatmap_payload = heatmap_result.json()["payload"]

    assert heatmap_payload["source_kind"] == "sweep"
    assert heatmap_payload["parameter_values"] == [0.05, 0.15]
    assert heatmap_payload["probe_centers"] == [0.05, 0.15]
    assert len(heatmap_payload["intensity"]) == 2
    assert len(heatmap_payload["intensity"][0]) == len(heatmap_payload["energy"])
    assert float(np.min(np.asarray(heatmap_payload["intensity"], dtype=float))) >= 0.0


def test_api_launches_k_space_and_trarpes_derived_analysis_from_tdhfb_sources(client):
    config = {
        "name": "tdhfb-k-space-preview-run",
        "solver": "tdhfb",
        "representation": "k_space",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.02,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "tdhfb k-space preview study",
            "question": "Can derived k-space analyses read direct tdhfb sources?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum", "tr_arpes"],
            "primary_surfaces": ["single-job", "k_spectrum", "tr_arpes"],
            "acceptance_checks": ["tdhfb source payloads are launchable and re-readable"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for tdhfb direct-source contract.",
        },
    ).json()["study_id"]

    run_id = client.post("/api/v1/runs", json=config).json()["run_id"]

    k_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "k_spectral_preview",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.2,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [run_id],
        },
    )
    assert k_launch.status_code == 201
    k_result = client.get(f"/api/v1/derived-analyses/{k_launch.json()['analysis_id']}/result")
    assert k_result.status_code == 200
    k_payload = k_result.json()["payload"]
    assert k_payload["source_run_solver"] == "tdhfb"
    assert k_payload["source_self_energy"] is None
    assert k_payload["k_surface"]["kind"] == "k_path"
    assert min(min(row) for row in k_payload["intensity"]) >= 0.0

    tr_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "run",
            "source_id": run_id,
            "analysis_type": "tr_arpes_preview",
            "parameters": {
                "k_grid": {"kind": "discrete_bz"},
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_center": 0.1,
                "probe_width": 0.08,
                "broadening": 0.08,
            },
            "input_surface_ids": [run_id],
        },
    )
    assert tr_launch.status_code == 201
    tr_result = client.get(f"/api/v1/derived-analyses/{tr_launch.json()['analysis_id']}/result")
    assert tr_result.status_code == 200
    tr_payload = tr_result.json()["payload"]
    assert tr_payload["source_run_solver"] == "tdhfb"
    assert tr_payload["source_self_energy"] is None
    assert tr_payload["k_surface"]["kind"] == "k_grid"
    assert min(min(row) for row in tr_payload["intensity"]) >= 0.0


def test_api_launches_k_space_compare_and_trarpes_heatmap_from_tdhfb_sources(client):
    config = {
        "name": "tdhfb-k-space-compare-run",
        "solver": "tdhfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.05,
            "amplitude_y": 0.02,
            "frequency": 1.5,
            "center": 0.1,
            "width": 0.12,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {
            "filling": 0.5,
            "temperature": 0.0,
            "seed_pairing": 0.0,
        },
        "observables": ["density", "energy", "pairing", "pairing_s", "pairing_d"],
    }
    study_id = client.post(
        "/api/v1/studies",
        json={
            "title": "tdhfb k-space compare and heatmap study",
            "question": "Can compare/sweep artifacts reuse tdhfb direct k-space analyses?",
            "baseline_preset_id": "square-4x4-bond-d-kbe-hfb",
            "target_observables": ["k_spectrum", "tr_arpes"],
            "primary_surfaces": ["compare-jobs", "parameter-sweep"],
            "acceptance_checks": ["compare and heatmap payloads remain re-fetchable for tdhfb source"],
            "status": "active",
            "notes_on_scope": "Workflow-level regression for tdhfb compare/sweep derived-analysis lifecycle.",
        },
    ).json()["study_id"]

    baseline_run_id = client.post("/api/v1/runs", json=config).json()["run_id"]
    variant_config = deepcopy(config)
    variant_config["name"] = "tdhfb-k-space-compare-run-variant"
    variant_config["representation"] = "k_space"
    variant_run_id = client.post("/api/v1/runs", json=variant_config).json()["run_id"]

    group_id = client.post(
        "/api/v1/job-groups",
        json={
            "study_id": study_id,
            "name": "tdhfb k-space compare",
            "comparison_kind": "physics_hypothesis",
            "baseline_run_id": baseline_run_id,
            "base_config": config,
            "variants": [
                {"label": "real", "config_patch": {}, "run_id": baseline_run_id},
                {"label": "k-space", "config_patch": {"representation": "k_space"}, "run_id": variant_run_id},
            ],
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["group_id"]

    sweep_id = client.post(
        "/api/v1/sweeps",
        json={
            "study_id": study_id,
            "name": "tdhfb tr-arpes delay sweep",
            "parameter_kind": "analysis",
            "parameter_path": "probe_center",
            "parameter_label": "probe_delay",
            "values": [0.05, 0.15],
            "baseline_value": 0.05,
            "fixed_axes": {"analysis_type": "tr_arpes_heatmap"},
            "child_run_ids": [baseline_run_id, variant_run_id],
        },
    ).json()["sweep_id"]

    compare_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "job_group",
            "source_id": group_id,
            "analysis_type": "k_spectral_compare",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 81},
                "probe_center": 0.1,
                "probe_width": 0.12,
                "broadening": 0.08,
            },
            "input_surface_ids": [group_id],
        },
    )
    assert compare_launch.status_code == 201
    compare_result = client.get(f"/api/v1/derived-analyses/{compare_launch.json()['analysis_id']}/result")
    assert compare_result.status_code == 200
    compare_payload = compare_result.json()["payload"]
    assert compare_payload["k_surface"]["kind"] == "k_path"
    assert [entry["label"] for entry in compare_payload["entries"]] == ["real", "k-space"]
    assert {entry["source_run_solver"] for entry in compare_payload["entries"]} == {"tdhfb"}
    assert {entry["source_self_energy"] for entry in compare_payload["entries"]} == {None}

    heatmap_launch = client.post(
        "/api/v1/derived-analyses/launch",
        json={
            "study_id": study_id,
            "source_kind": "sweep",
            "source_id": sweep_id,
            "analysis_type": "tr_arpes_heatmap",
            "parameters": {
                "k_path": "gamma_x_m_gamma",
                "energy_grid": {"min": -4.0, "max": 4.0, "count": 61},
                "probe_width": 0.08,
                "broadening": 0.08,
            },
            "input_surface_ids": [sweep_id],
        },
    )
    assert heatmap_launch.status_code == 201
    heatmap_result = client.get(f"/api/v1/derived-analyses/{heatmap_launch.json()['analysis_id']}/result")
    assert heatmap_result.status_code == 200
    heatmap_payload = heatmap_result.json()["payload"]
    assert heatmap_payload["source_kind"] == "sweep"
    assert heatmap_payload["probe_centers"] == [0.05, 0.15]
    assert len(heatmap_payload["intensity"]) == 2


def test_api_cancel_falls_back_to_pid_when_runner_state_is_gone(tmp_path, sample_config):
    app = create_app(
        settings=AppSettings(data_dir=tmp_path / "runs", registry_db_path=tmp_path / "experiment-registry.sqlite", job_mode="inline"),
        runner=_NeverCancelRunner(),
    )
    repository = app.state.run_service.repository
    summary = repository.create_run(SimulationConfig.model_validate(sample_config))
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        repository.update_status(
            summary.run_id,
            RunState.RUNNING,
            message="simulation running",
            pid=sleeper.pid,
        )

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            cancel_response = client.post(f"/api/v1/runs/{summary.run_id}/cancel")
            progress_response = client.get(f"/api/v1/runs/{summary.run_id}/progress")

        assert cancel_response.status_code == 200
        assert cancel_response.json()["state"] == "cancelled"
        assert progress_response.status_code == 200
        assert progress_response.json()["state"] == "cancelled"
        assert progress_response.json()["phase"] == "cancelled"

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and sleeper.poll() is None:
            time.sleep(0.05)
        assert sleeper.poll() is not None
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
            sleeper.wait(timeout=5.0)


def test_api_reconciles_running_state_when_worker_pid_is_dead_and_progress_is_stale(client, sample_config):
    repository = client.app.state.run_service.repository
    summary = repository.create_run(SimulationConfig.model_validate(sample_config))
    repository.update_status(summary.run_id, RunState.RUNNING, message="simulation running", pid=999999)
    progress_path = repository.storage.run_dir(summary.run_id) / "progress.json"
    progress_payload = json.loads(progress_path.read_text(encoding="utf-8"))
    progress_payload["updated_at"] = "2000-01-01T00:00:00Z"
    progress_payload["state"] = "running"
    progress_payload["phase"] = "finalizing"
    progress_payload["status_line"] = "finalizing: writing artifacts"
    progress_path.write_text(json.dumps(progress_payload, indent=2), encoding="utf-8")

    progress_response = client.get(f"/api/v1/runs/{summary.run_id}/progress")
    detail_response = client.get(f"/api/v1/runs/{summary.run_id}")

    assert progress_response.status_code == 200
    assert progress_response.json()["state"] == "failed"
    assert progress_response.json()["phase"] == "failed"
    assert "worker process" in (progress_response.json()["status_line"] or "")
    assert detail_response.status_code == 200
    assert detail_response.json()["state"] == "failed"


def test_api_cancel_is_noop_for_succeeded_with_warnings_state(client, sample_config):
    repository = client.app.state.run_service.repository
    summary = repository.create_run(SimulationConfig.model_validate(sample_config))
    repository.update_status(summary.run_id, RunState.RUNNING, message="simulation running")
    repository.update_status(summary.run_id, RunState.SUCCEEDED_WITH_WARNINGS, message="simulation completed with warnings")

    cancel_response = client.post(f"/api/v1/runs/{summary.run_id}/cancel")
    assert cancel_response.status_code == 200
    payload = cancel_response.json()
    assert payload["state"] == "succeeded_with_warnings"
    assert payload["finished_at"] is not None
    assert payload["status_message"] == "simulation completed with warnings"


def test_api_process_mode_submit_and_cancel_workflow(tmp_path, sample_config, monkeypatch):
    monkeypatch.setenv("TDKB_WORKER_STARTUP_DELAY_SECONDS", "5.0")
    app = create_app(
        settings=AppSettings(
            data_dir=tmp_path / "runs",
            registry_db_path=tmp_path / "experiment-registry.sqlite",
            job_mode="process",
        ),
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        create_response = client.post("/api/v1/runs", json=sample_config)
        assert create_response.status_code == 202
        run_id = create_response.json()["run_id"]

        deadline = time.monotonic() + 10.0
        detail = create_response.json()
        while time.monotonic() < deadline:
            detail = client.get(f"/api/v1/runs/{run_id}").json()
            if detail["state"] == "running" and detail["status_message"] == "simulation running":
                break
            time.sleep(0.05)
        assert detail["state"] == "running"
        assert detail["started_at"] is not None
        assert detail["diagnostics"] == {}
        assert detail["status_message"] == "simulation running"
        assert detail["config"]["solver"] == sample_config["solver"]

        running_progress_response = client.get(f"/api/v1/runs/{run_id}/progress")
        assert running_progress_response.status_code == 200
        running_progress = running_progress_response.json()
        assert running_progress["state"] == "running"
        assert running_progress["phase"] in {"equilibrium", "propagating"}
        assert running_progress["started_at"] is not None
        assert running_progress["history"]
        assert running_progress["status_line"] == "simulation running"

        cancel_response = client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancel_response.status_code == 200
        cancelled = cancel_response.json()
        assert cancelled["state"] == "cancelled"
        assert cancelled["finished_at"] is not None
        assert cancelled["status_message"] == "run cancelled"

        progress_response = client.get(f"/api/v1/runs/{run_id}/progress")
        assert progress_response.status_code == 200
        progress = progress_response.json()
        assert progress["state"] == "cancelled"
        assert progress["phase"] == "cancelled"
        assert progress["started_at"] is not None

        log_response = client.get(f"/api/v1/runs/{run_id}/log")
        assert log_response.status_code == 200


def test_schema_and_presets_endpoints(client):
    schema_response = client.get("/api/v1/schema/simulation")
    assert schema_response.status_code == 200
    assert "properties" in schema_response.json()

    presets_response = client.get("/api/v1/presets")
    assert presets_response.status_code == 200
    presets = presets_response.json()
    preset_names = {p["name"] for p in presets}
    preset_solvers = {p["config"]["solver"] for p in presets}
    preset_categories = {p["category"] for p in presets}
    assert "square-4x4-higgs-demo-kbe-hfb" in preset_names
    assert preset_solvers == {"noninteracting", "tdhfb", "kbe_hfb"}
    assert preset_categories == {"demo", "working_baseline", "mean_field", "exact_baseline"}


def test_higgs_demo_preset_uses_long_window_gaussian_pulse():
    preset = build_higgs_demo_preset()

    assert preset.config.time.t_final == 20.0
    assert preset.config.time.dt == 0.05
    assert preset.config.time.save_every == 2
    assert preset.config.drive.amplitude_x == 0.25
    assert preset.config.drive.amplitude_y == 0.125
    assert preset.config.drive.frequency == 2.0
    assert preset.config.drive.center == 3.0
    assert preset.config.drive.width == 1.2
    assert preset.config.kbe.self_energy.value == "hfb"
    assert preset.config.observables == ["density", "energy", "vector_potential", "pairing", "pairing_s", "pairing_d"]
    assert preset.category.value == "demo"
    assert preset.validation_status.value == "prototype"
    assert preset.primary_observable == "pairing_d"


def test_cors_preflight_for_runs_endpoint(client):
    response = client.options(
        "/api/v1/runs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_api_supports_tdhfb_pairing_observables(client, paired_config):
    create_response = client.post("/api/v1/runs", json=paired_config)
    assert create_response.status_code == 202

    run_id = create_response.json()["run_id"]

    observable_list = client.get(f"/api/v1/runs/{run_id}/observables")
    assert observable_list.status_code == 200
    assert "pairing_d" in observable_list.json()["observables"]

    pairing_response = client.get(f"/api/v1/runs/{run_id}/observables/pairing_d")
    pairing_payload = pairing_response.json()
    assert pairing_response.status_code == 200
    assert pairing_payload["series"][2]["label"] == "magnitude"
    assert pairing_payload["series"][2]["values"][-1] > 0.05


def test_api_supports_kbe_green_function_slice_queries(client):
    config = {
        "name": "kbe-green-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]

    catalog_response = client.get(f"/api/v1/runs/{run_id}/green-functions")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert set(catalog_payload["components"]) == {"retarded", "lesser"}
    assert catalog_payload["shape"] == [3, 3, 8, 8]

    slice_response = client.get(
        f"/api/v1/runs/{run_id}/green-functions/retarded",
        params={
            "row_start": 1,
            "row_stop": 2,
            "col_start": 1,
            "col_stop": 2,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert slice_response.status_code == 200
    slice_payload = slice_response.json()
    assert slice_payload["component"] == "retarded"
    assert slice_payload["times_row"] == [0.1]
    assert slice_payload["times_col"] == [0.1]
    assert slice_payload["shape"] == [1, 1, 2, 2]
    assert slice_payload["nambu_start"] == 0
    assert slice_payload["nambu_stop"] == 2
    assert np.allclose(np.asarray(slice_payload["real"]), np.asarray([[[[0.0, 0.0], [0.0, 0.0]]]]), atol=1e-12)
    assert np.allclose(np.asarray(slice_payload["imag"]), np.asarray([[[[-1.0, 0.0], [0.0, -1.0]]]]), atol=1e-12)


def test_api_green_function_storage_respects_save_every_for_kbe_runs(client):
    config = {
        "name": "kbe-green-save-every-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.1, "save_every": 2},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_payload = create_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["diagnostics"]["two_time_grid_shape"] == [5, 5, 8, 8]

    catalog_response = client.get(f"/api/v1/runs/{run_id}/green-functions")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert set(catalog_payload["components"]) == {"retarded", "lesser"}
    assert catalog_payload["shape"] == [3, 3, 8, 8]
    assert catalog_payload["time_point_count"] == 3

    slice_response = client.get(
        f"/api/v1/runs/{run_id}/green-functions/retarded",
        params={
            "row_start": 1,
            "row_stop": 2,
            "col_start": 0,
            "col_stop": 1,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert slice_response.status_code == 200
    slice_payload = slice_response.json()
    assert slice_payload["times_row"] == [0.2]
    assert slice_payload["times_col"] == [0.0]
    assert slice_payload["shape"] == [1, 1, 2, 2]


def test_api_supports_kbe_thermal_branch_slice_queries(client):
    config = {
        "name": "kbe-thermal-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "thermal_branch": {"enabled": True, "n_tau": 8},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_payload = create_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["diagnostics"]["thermal_branch_enabled"] is True
    assert run_payload["diagnostics"]["matsubara_grid_shape"] == [9, 8, 8]

    catalog_response = client.get(f"/api/v1/runs/{run_id}/thermal-branch")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert catalog_payload["components"] == ["matsubara"]
    assert catalog_payload["shape"] == [9, 8, 8]
    assert catalog_payload["tau_point_count"] == 9
    assert catalog_payload["nambu_dimension"] == 8

    slice_response = client.get(
        f"/api/v1/runs/{run_id}/thermal-branch/matsubara",
        params={
            "tau_start": 0,
            "tau_stop": 2,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert slice_response.status_code == 200
    slice_payload = slice_response.json()
    assert slice_payload["component"] == "matsubara"
    assert slice_payload["tau"] == [0.0, 0.625]
    assert slice_payload["shape"] == [2, 2, 2]
    assert slice_payload["nambu_start"] == 0
    assert slice_payload["nambu_stop"] == 2
    assert np.isfinite(np.asarray(slice_payload["real"])).all()
    assert np.allclose(np.asarray(slice_payload["imag"]), 0.0, atol=1e-12)
    assert np.min(np.asarray(slice_payload["real"])) < -0.01


def test_api_supports_kbe_mixed_green_function_slice_queries(client):
    config = {
        "name": "kbe-mixed-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.2, "dt": 0.1},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "thermal_branch": {"enabled": True, "n_tau": 8},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_payload = create_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["diagnostics"]["mixed_components_included"] is True
    assert run_payload["diagnostics"]["mixed_grid_shape"] == [3, 9, 8, 8]

    catalog_response = client.get(f"/api/v1/runs/{run_id}/mixed-green-functions")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert set(catalog_payload["components"]) == {"mixed_right", "mixed_left"}
    assert catalog_payload["shape"] == [3, 9, 8, 8]
    assert catalog_payload["time_point_count"] == 3
    assert catalog_payload["tau_point_count"] == 9
    assert catalog_payload["nambu_dimension"] == 8

    slice_response = client.get(
        f"/api/v1/runs/{run_id}/mixed-green-functions/mixed_right",
        params={
            "time_start": 0,
            "time_stop": 1,
            "tau_start": 0,
            "tau_stop": 2,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert slice_response.status_code == 200
    slice_payload = slice_response.json()
    assert slice_payload["component"] == "mixed_right"
    assert slice_payload["times"] == [0.0]
    assert slice_payload["tau"] == [0.0, 0.625]
    assert slice_payload["shape"] == [1, 2, 2, 2]
    assert slice_payload["nambu_start"] == 0
    assert slice_payload["nambu_stop"] == 2
    assert np.allclose(np.asarray(slice_payload["real"]), 0.0, atol=1e-12)
    assert np.max(np.abs(np.asarray(slice_payload["imag"]))) > 0.01


def test_api_mixed_green_function_storage_respects_save_every(client):
    config = {
        "name": "kbe-mixed-save-every-run",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.1, "save_every": 2},
        "drive": {
            "amplitude_x": 0.0,
            "amplitude_y": 0.0,
            "frequency": 0.0,
            "center": 0.0,
            "width": 1.0,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "thermal_branch": {"enabled": True, "n_tau": 8},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    run_payload = create_response.json()
    run_id = run_payload["run_id"]
    assert run_payload["diagnostics"]["mixed_grid_shape"] == [5, 9, 8, 8]

    catalog_response = client.get(f"/api/v1/runs/{run_id}/mixed-green-functions")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert set(catalog_payload["components"]) == {"mixed_right", "mixed_left"}
    assert catalog_payload["shape"] == [3, 9, 8, 8]
    assert catalog_payload["time_point_count"] == 3

    slice_response = client.get(
        f"/api/v1/runs/{run_id}/mixed-green-functions/mixed_right",
        params={
            "time_start": 1,
            "time_stop": 2,
            "tau_start": 0,
            "tau_stop": 2,
            "nambu_start": 0,
            "nambu_stop": 2,
        },
    )
    assert slice_response.status_code == 200
    slice_payload = slice_response.json()
    assert slice_payload["times"] == [0.2]
    assert slice_payload["shape"] == [1, 2, 2, 2]


def test_api_exposes_phase_e_full_contour_diagnostics(client):
    config = {
        "name": "kbe-phase-e-full",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.2,
            "amplitude_y": 0.0,
            "frequency": 1.0,
            "center": 0.2,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -1.5,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "kbe": {
            "self_energy": "second_born",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-4,
            "mixing": 0.5,
        },
        "adaptive": {
            "enabled": True,
            "rtol": 1e-3,
            "atol": 1e-5,
            "min_dt": 0.025,
            "max_dt": 0.1,
        },
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 10, "mixing": 0.4},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    payload = create_response.json()

    diagnostics = payload["diagnostics"]
    summary = payload["diagnostics_excerpt"]
    assert diagnostics["time_grid_mode"] == "adaptive"
    assert diagnostics["second_born_solver_mode"] == "two_time_causal_marching"
    assert diagnostics["second_born_contour_mode"] == "full_contour"
    assert diagnostics["second_born_converged"] is True
    assert diagnostics["thermal_branch_correlated"] is True
    assert diagnostics["thermal_branch_converged"] is True
    assert diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert len(diagnostics["second_born_history_integration_order_history"]) == diagnostics["time_steps"]
    assert summary["time_grid_mode"] == "adaptive"
    assert summary["thermal_branch_factorized_difference"] > 0.0
    assert summary["mixed_branch_factorized_difference"] > 0.0


def test_api_exposes_phase_e_reference_contour_diagnostics(client):
    config = {
        "name": "kbe-phase-e-reference",
        "solver": "kbe_hfb",
        "lattice": {
            "nx": 2,
            "ny": 2,
            "boundary": "periodic",
            "hopping": 1.0,
            "chemical_potential": 0.0,
        },
        "time": {"t_final": 0.4, "dt": 0.05},
        "drive": {
            "amplitude_x": 0.2,
            "amplitude_y": 0.0,
            "frequency": 1.0,
            "center": 0.2,
            "width": 0.15,
        },
        "interaction": {
            "onsite_u": -1.2,
            "nearest_neighbor_v": 0.0,
            "pairing_channel": "none",
        },
        "initial_state": {"filling": 0.5, "temperature": 0.2, "seed_pairing": 0.0},
        "kbe": {
            "self_energy": "second_born_reference",
            "max_fixed_point_iterations": 10,
            "tolerance": 1e-5,
            "mixing": 0.5,
        },
        "adaptive": {
            "enabled": True,
            "rtol": 1e-3,
            "atol": 1e-5,
            "min_dt": 0.025,
            "max_dt": 0.1,
        },
        "thermal_branch": {"enabled": True, "n_tau": 8, "max_iterations": 12, "mixing": 0.4},
        "observables": ["density", "energy"],
    }

    create_response = client.post("/api/v1/runs", json=config)
    assert create_response.status_code == 202
    payload = create_response.json()

    diagnostics = payload["diagnostics"]
    summary = payload["diagnostics_excerpt"]
    assert diagnostics["time_grid_mode"] == "adaptive"
    assert diagnostics["second_born_solver_mode"] == "gkba_causal_marching"
    assert diagnostics["second_born_contour_mode"] == "full_contour"
    assert diagnostics["second_born_reference_scope"] == "equal_time_gkba_full_contour"
    assert diagnostics["second_born_converged"] is True
    assert diagnostics["thermal_branch_correlated"] is True
    assert diagnostics["thermal_branch_reference_implementation"] is True
    assert diagnostics["mixed_branch_reference_implementation"] is True
    assert diagnostics["thermal_branch_factorized_difference"] > 0.0
    assert diagnostics["mixed_branch_factorized_difference"] > 0.0
    assert diagnostics["max_second_born_mixed_memory_norm"] > 0.0
    assert diagnostics["max_second_born_thermal_memory_norm"] > 0.0
    assert len(diagnostics["second_born_history_integration_order_history"]) == diagnostics["time_steps"]
    assert summary["time_grid_mode"] == "adaptive"
    assert summary["thermal_branch_factorized_difference"] > 0.0
    assert summary["mixed_branch_factorized_difference"] > 0.0
