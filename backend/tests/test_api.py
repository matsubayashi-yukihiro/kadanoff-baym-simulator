from copy import deepcopy


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
