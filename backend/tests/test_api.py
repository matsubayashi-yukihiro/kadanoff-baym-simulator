from copy import deepcopy

import numpy as np


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


def test_schema_and_presets_endpoints(client):
    schema_response = client.get("/api/v1/schema/simulation")
    assert schema_response.status_code == 200
    assert "properties" in schema_response.json()

    presets_response = client.get("/api/v1/presets")
    assert presets_response.status_code == 200
    preset_solvers = {preset["solver"] for preset in presets_response.json()}
    assert preset_solvers == {"noninteracting", "tdhfb", "kbe_hfb"}


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
