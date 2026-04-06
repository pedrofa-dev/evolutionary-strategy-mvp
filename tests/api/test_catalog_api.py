from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import api.main
from application.run_lab import RunLabApplicationService
from application.runs_results import RunsResultsApplicationService
from api.main import create_app
from tests.application.test_runs_results_application_service import seed_campaign


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
    runs_results_service: RunsResultsApplicationService | None = None,
) -> tuple[int, dict]:
    app = create_app(
        run_lab_service=run_lab_service,
        runs_results_service=runs_results_service,
    )
    path_info, _, query_string = path.partition("?")
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path_info
    if query_string:
        environ["QUERY_STRING"] = query_string
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
    assert captured["application"] is not None
    assert getattr(server, "_queue_service", None) is not None


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


def test_run_lab_save_config_endpoint_allows_reusing_identical_content(
    tmp_path: Path,
) -> None:
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
    body = {
        "template_config_name": "balanced_baseline.json",
        "config_name": "api run lab repeatable",
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "decision_policy_name": "policy_v2_default",
        "seed_mode": "range",
        "seed_start": 101,
        "seed_count": 6,
    }

    first_status, first_payload = _request(
        "POST",
        "/run-lab/configs",
        body=body,
        run_lab_service=run_lab_service,
    )
    second_status, second_payload = _request(
        "POST",
        "/run-lab/configs",
        body=body,
        run_lab_service=run_lab_service,
    )

    assert first_status == 200
    assert second_status == 200
    assert first_payload["config_payload"] == second_payload["config_payload"]


def test_run_lab_save_config_endpoint_rejects_different_content_under_same_name(
    tmp_path: Path,
) -> None:
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
    base_body = {
        "template_config_name": "balanced_baseline.json",
        "config_name": "api run lab collision",
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "decision_policy_name": "policy_v2_default",
        "seed_mode": "range",
        "seed_start": 101,
        "seed_count": 6,
    }
    _request(
        "POST",
        "/run-lab/configs",
        body=base_body,
        run_lab_service=run_lab_service,
    )

    status_code, payload = _request(
        "POST",
        "/run-lab/configs",
        body={
            **base_body,
            "seed_count": 12,
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_run_lab_request"
    assert "different content" in payload["message"]


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
            "parallel_workers": 3,
            "queue_concurrency_limit": 1,
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["pid"] == 43210
    assert payload["job_id"].startswith("queue_")
    assert payload["saved_config"]["config_name"] == "api run lab execute.json"
    assert payload["preset_name"] == "standard"
    assert payload["status"] == "running"
    assert payload["campaign_id"].startswith("multiseed_")
    assert payload["parallel_workers"] == 3
    assert payload["queue_concurrency_limit"] == 1


def test_run_lab_authoring_mutation_profile_endpoint_saves_asset(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    mutation_profile_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "mutation_profiles"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    mutation_profile_assets_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    run_lab_service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )

    status_code, payload = _request(
        "POST",
        "/run-lab/authoring/mutation-profiles",
        body={
            "id": "authoring_profile_v1",
            "description": "Authored in Run Lab.",
            "strong_mutation_probability": 0.12,
            "numeric_delta_scale": 1.3,
            "flag_flip_probability": 0.04,
            "weight_delta": 0.18,
            "window_step_mode": "small",
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["asset_id"] == "authoring_profile_v1"
    assert (repo_root / payload["asset_path"]).exists()


def test_run_lab_authoring_signal_pack_endpoint_saves_asset(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    signal_pack_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "signal_packs"
    )
    mutation_profile_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "mutation_profiles"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    signal_pack_assets_dir.mkdir(parents=True)
    mutation_profile_assets_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    run_lab_service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )

    status_code, payload = _request(
        "POST",
        "/run-lab/authoring/signal-packs",
        body={
            "id": "authoring_signal_pack_v1",
            "description": "Authored signal pack.",
            "signals": "trend_strength_medium\ntrend_strength_long\nmomentum_short",
        },
        run_lab_service=run_lab_service,
    )

    assert status_code == 200
    assert payload["asset_id"] == "authoring_signal_pack_v1"
    assert (repo_root / payload["asset_path"]).exists()


def test_runs_campaigns_endpoints_return_persisted_results(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    runs_results_service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    status_code, payload = _request(
        "GET",
        "/runs/campaigns",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["campaigns"][0]["campaign_id"] == campaign_id
    assert payload["campaigns"][0]["verdict"] == "ROBUST_CANDIDATE"

    status_code, payload = _request(
        "GET",
        f"/runs/campaign/{campaign_id}",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["summary"]["campaign_id"] == campaign_id
    assert payload["champion"]["classification"] == "robust"

    status_code, payload = _request(
        "GET",
        f"/runs/compare?ids={campaign_id}",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["items"][0]["campaign_id"] == campaign_id


def test_runs_monitor_endpoint_returns_active_campaigns(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    runs_results_service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    status_code, payload = _request(
        "GET",
        "/runs/monitor",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["items"][0]["campaign_id"] == campaign_id


def test_cancel_queued_job_endpoint_cancels_safe_queue_job(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    from evo_system.storage import PersistenceStore

    store = PersistenceStore(database_path)
    store.initialize()
    store.save_execution_queue_job(
        queue_job_uid="queue-001",
        campaign_id="multiseed_queued",
        config_name="queued_probe.json",
        config_path="configs/runs/queued_probe.json",
        config_payload_json={"seed_count": 2},
        parallel_workers=1,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/queued_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/queued_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_queued",
    )
    runs_results_service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    status_code, payload = _request(
        "POST",
        "/runs/jobs/queue-001/cancel",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["job_id"] == "queue-001"
    assert payload["status"] == "cancelled"


def test_delete_campaign_endpoint_removes_completed_campaign(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    runs_results_service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    status_code, payload = _request(
        "DELETE",
        f"/runs/campaign/{campaign_id}",
        runs_results_service=runs_results_service,
    )

    assert status_code == 200
    assert payload["campaign_id"] == campaign_id

    status_code, payload = _request(
        "GET",
        f"/runs/campaign/{campaign_id}",
        runs_results_service=runs_results_service,
    )

    assert status_code == 404
    assert payload["error"] == "unknown_campaign"
