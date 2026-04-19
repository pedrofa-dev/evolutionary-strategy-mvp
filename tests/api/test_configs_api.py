from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from api.main import create_app
from application.configs import RunConfigBrowserApplicationService


def _write_config(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _base_payload() -> dict:
    return {
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
        "entry_trigger": {"entry_score_threshold": 0.75},
        "exit_policy": {"exit_on_signal_reversal": True},
        "trade_control": {"cooldown_bars": 2},
        "entry_trigger_constraints": {"min_trend_weight": -0.5},
        "mutation_profile": {
            "strong_mutation_probability": 0.055,
            "numeric_delta_scale": 0.75,
            "flag_flip_probability": 0.025,
            "weight_delta": 0.145,
            "window_step_mode": "default",
        },
    }


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    config_browser_service: RunConfigBrowserApplicationService | None = None,
) -> tuple[int, dict]:
    app = create_app(config_browser_service=config_browser_service)
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

    response_body = b"".join(app(environ, start_response))
    status_code = int(str(captured["status"]).split()[0])
    return status_code, json.loads(response_body.decode("utf-8"))


def test_configs_list_endpoint_returns_canonical_configs(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
        database_path=repo_root / "data" / "evolution_v2.db",
    )

    status_code, payload = _request(
        "GET",
        "/api/configs",
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["items"][0]["config_name"] == "alpha.json"
    assert payload["items"][0]["dataset_catalog_id"] == "core_1h_spot"


def test_configs_detail_endpoint_returns_normalized_editor_dto(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
        database_path=repo_root / "data" / "evolution_v2.db",
    )

    status_code, payload = _request(
        "GET",
        "/api/configs/alpha.json",
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["identity"]["config_name"] == "alpha.json"
    assert payload["research_stack"]["signal_pack_name"] == "policy_v21_default"
    assert payload["evolution_budget"]["population_size"] == 18


def test_configs_duplicate_endpoint_creates_copy(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/duplicate",
        body={
            "source_config_name": "alpha.json",
            "new_config_name": "alpha copy",
        },
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["config_name"] == "alpha copy.json"
    assert (run_configs_dir / "alpha copy.json").exists()


def test_configs_rename_endpoint_renames_config(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/rename",
        body={
            "source_config_name": "alpha.json",
            "new_config_name": "renamed_alpha",
        },
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["config_name"] == "renamed_alpha.json"
    assert (run_configs_dir / "renamed_alpha.json").exists()


def test_configs_duplicate_collision_returns_bad_request(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/duplicate",
        body={
            "source_config_name": "alpha.json",
            "new_config_name": "beta.json",
        },
        config_browser_service=service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_config_request"
    assert "already exists" in payload["message"]


def test_configs_rename_collision_returns_bad_request(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/rename",
        body={
            "source_config_name": "alpha.json",
            "new_config_name": "beta.json",
        },
        config_browser_service=service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_config_request"
    assert "already exists" in payload["message"]


def test_configs_detail_missing_returns_not_found(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "GET",
        "/api/configs/missing.json",
        config_browser_service=service,
    )

    assert status_code == 404
    assert payload["error"] == "unknown_config"


def test_configs_operation_invalid_payload_returns_bad_request(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/duplicate",
        body={"source_config_name": "alpha.json"},
        config_browser_service=service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_config_request"


def test_configs_save_endpoint_updates_existing_config(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["evolution_budget"]["generations_planned"] = 60
    editor["seed_plan"] = {
        "mode": "explicit",
        "seed_start": None,
        "seed_count": None,
        "explicit_seeds": [7, 8],
        "summary": "7, 8",
    }

    status_code, payload = _request(
        "POST",
        "/api/configs/save",
        body={
            "source_config_name": "alpha.json",
            "config": editor,
        },
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["identity"]["config_name"] == "alpha.json"
    persisted = json.loads((run_configs_dir / "alpha.json").read_text(encoding="utf-8"))
    assert persisted["generations_planned"] == 60
    assert persisted["seeds"] == [7, 8]


def test_configs_save_as_new_endpoint_creates_new_config(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["identity"]["config_name"] = "beta.json"

    status_code, payload = _request(
        "POST",
        "/api/configs/save-as-new",
        body={"config": editor},
        config_browser_service=service,
    )

    assert status_code == 200
    assert payload["identity"]["config_name"] == "beta.json"
    assert (run_configs_dir / "beta.json").exists()


def test_configs_save_missing_source_returns_not_found(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    status_code, payload = _request(
        "POST",
        "/api/configs/save",
        body={
            "source_config_name": "missing.json",
            "config": {
                "identity": {"config_name": "missing.json"},
                "research_stack": {},
                "evolution_budget": {},
                "seed_plan": {},
                "evaluation_trading": {},
                "advanced_overrides": {},
            },
        },
        config_browser_service=service,
    )

    assert status_code == 404
    assert payload["error"] == "unknown_config"


def test_configs_save_as_new_collision_returns_bad_request(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["identity"]["config_name"] = "beta.json"

    status_code, payload = _request(
        "POST",
        "/api/configs/save-as-new",
        body={"config": editor},
        config_browser_service=service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_config_request"
    assert "already exists" in payload["message"]


def test_configs_save_invalid_payload_returns_bad_request(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["identity"]["config_name"] = "renamed.json"

    status_code, payload = _request(
        "POST",
        "/api/configs/save",
        body={
            "source_config_name": "alpha.json",
            "config": editor,
        },
        config_browser_service=service,
    )

    assert status_code == 400
    assert payload["error"] == "invalid_config_request"
    assert "cannot rename files implicitly" in payload["message"]
