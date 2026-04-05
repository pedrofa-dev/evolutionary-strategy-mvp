from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import api.main
from application.run_lab import RunLabApplicationService
from api.main import create_app


def _write_manifest(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "catalog_id: core_1h_spot",
                "description: Core test catalog.",
                "market_type: spot",
                "timeframe: 1h",
                "datasets:",
                "  - id: BTCUSDT_1h_train",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2023-01-01",
                "    end: 2023-02-01",
                "    layer: train",
                "    regime_primary: trend",
                "    regime_secondary: breakout",
                "    volatility: medium",
                "    event_tag: test_train",
                "    notes: Train window.",
            ]
        ),
        encoding="utf-8",
    )


def _write_template(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "seed_start": 100,
                "seed_count": 6,
                "population_size": 18,
                "target_population_size": 18,
                "survivors_count": 4,
                "generations_planned": 25,
                "mutation_seed": 42,
                "trade_cost_rate": 0.0005,
                "cost_penalty_weight": 0.0,
                "dataset_catalog_id": "core_1h_spot",
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "policy_v2_default",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "mutation_profile": {
                    "strong_mutation_probability": 0.055,
                    "numeric_delta_scale": 0.75,
                    "flag_flip_probability": 0.025,
                    "weight_delta": 0.145,
                    "window_step_mode": "default",
                },
            }
        ),
        encoding="utf-8",
    )


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    run_lab_service: RunLabApplicationService | None = None,
) -> tuple[int, dict]:
    app = create_app(run_lab_service=run_lab_service)
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if body is not None:
        raw_body = json.dumps(body).encode("utf-8")
        environ["CONTENT_LENGTH"] = str(len(raw_body))
        environ["CONTENT_TYPE"] = "application/json"
        environ["wsgi.input"] = BytesIO(raw_body)

    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app(environ, start_response))
    status_code = int(str(captured["status"]).split()[0])
    return status_code, json.loads(body.decode("utf-8"))


def test_health_endpoint_returns_ok() -> None:
    status_code, payload = _request("GET", "/health")

    assert status_code == 200
    assert payload == {"status": "ok"}


def test_catalog_endpoint_returns_application_catalog_payload() -> None:
    status_code, payload = _request("GET", "/catalog")

    assert status_code == 200
    assert "signal_packs" in payload
    assert "experiment_presets" in payload
    assert any(item["id"] == "btc_1h_probe_v1" for item in payload["experiment_presets"])


def test_catalog_category_endpoint_returns_requested_category_only() -> None:
    status_code, payload = _request("GET", "/catalog/signal_packs")

    assert status_code == 200
    assert payload["category"] == "signal_packs"
    assert any(item["id"] == "core_policy_v21_signals_v1" for item in payload["items"])


def test_catalog_category_endpoint_returns_404_for_unknown_category() -> None:
    status_code, payload = _request("GET", "/catalog/unknown")

    assert status_code == 404
    assert payload["error"] == "unknown_catalog_category"


def test_api_rejects_non_get_methods() -> None:
    status_code, payload = _request("POST", "/catalog")

    assert status_code == 405
    assert payload["error"] == "method_not_allowed"


def test_create_dev_server_uses_localhost_8000_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyServer:
        pass

    def fake_make_server(host: str, port: int, application):
        captured["host"] = host
        captured["port"] = port
        captured["application"] = application
        return DummyServer()

    monkeypatch.setattr(api.main, "make_server", fake_make_server)

    server = api.main.create_dev_server()

    assert isinstance(server, DummyServer)
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000
    assert captured["application"] is api.main.app


def test_run_lab_bootstrap_endpoint_returns_operational_payload(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")
    run_lab_service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    status_code, payload = _request(
        "GET",
        "/run-lab",
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["defaults"]["dataset_catalog_id"] == "core_1h_spot"
    assert payload["defaults"]["experiment_preset_name"] == "standard"
    assert payload["dataset_catalogs"][0]["id"] == "core_1h_spot"


def test_run_lab_save_config_endpoint_writes_config(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")
    run_lab_service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    status_code, payload = _request(
        "POST",
        "/run-lab/configs",
        body={
            "template_config_name": "balanced_baseline.json",
            "config_name": "api run lab save",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 101,
            "seed_count": 6,
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["config_name"] == "api run lab save.json"
    assert (repo_root / payload["config_path"]).exists()


def test_run_lab_execution_endpoint_launches_canonical_process(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    class DummyProcess:
        pid = 43210

    def fake_launcher(command, cwd, stdout, stderr):
        return DummyProcess()

    run_lab_service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        launcher=fake_launcher,
    )

    status_code, payload = _request(
        "POST",
        "/run-lab/executions",
        body={
            "template_config_name": "balanced_baseline.json",
            "config_name": "api run lab execute",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 201,
            "seed_count": 4,
            "experiment_preset_name": "standard",
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["pid"] == 43210
    assert payload["saved_config"]["config_name"] == "api run lab execute.json"
    assert payload["preset_name"] == "standard"
