from __future__ import annotations

import json
from pathlib import Path

from application.configs import RunConfigBrowserApplicationService
from evo_system.storage import PersistenceStore


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


def test_list_configs_exposes_browser_summaries(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
        database_path=repo_root / "data" / "evolution_v2.db",
    )

    configs = service.list_configs()

    assert len(configs) == 1
    assert configs[0].config_name == "alpha.json"
    assert configs[0].dataset_catalog_id == "core_1h_spot"
    assert configs[0].signal_pack_name == "policy_v21_default"
    assert configs[0].genome_schema_name == "policy_v2_default"
    assert configs[0].decision_policy_name == "policy_v2_default"
    assert configs[0].mutation_profile_name == "default_runtime_profile"
    assert configs[0].seed_mode == "range"
    assert configs[0].seed_summary == "100-105 (6 seeds)"
    assert configs[0].recent_usage.campaign_usage_count == 0


def test_get_config_normalizes_to_explicit_editor_dto(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
        database_path=repo_root / "data" / "evolution_v2.db",
    )

    editor = service.get_config("alpha.json")

    assert editor.identity.config_name == "alpha.json"
    assert editor.research_stack.signal_pack_name == "policy_v21_default"
    assert editor.research_stack.market_mode_name == "spot"
    assert editor.research_stack.leverage == 1.0
    assert editor.evolution_budget.population_size == 18
    assert editor.seed_plan.mode == "range"
    assert editor.evaluation_trading.trade_cost_rate == 0.0005
    assert editor.advanced_overrides.entry_trigger == {"entry_score_threshold": 0.75}
    assert editor.advanced_overrides.exit_policy == {
        "exit_on_signal_reversal": True
    }
    assert editor.advanced_overrides.trade_control == {"cooldown_bars": 2}
    assert editor.advanced_overrides.entry_trigger_constraints == {
        "min_trend_weight": -0.5
    }


def test_duplicate_config_creates_new_canonical_file(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    result = service.duplicate_config(
        source_config_name="alpha.json",
        new_config_name="alpha copy",
    )

    assert result.config_name == "alpha copy.json"
    assert (run_configs_dir / "alpha copy.json").exists()
    assert json.loads((run_configs_dir / "alpha copy.json").read_text(encoding="utf-8")) == _base_payload()


def test_duplicate_config_collision_fails_clearly(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    try:
        service.duplicate_config(
            source_config_name="alpha.json",
            new_config_name="beta.json",
        )
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate collision to fail.")


def test_rename_config_renames_canonical_file(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    result = service.rename_config(
        source_config_name="alpha.json",
        new_config_name="renamed_alpha",
    )

    assert result.config_name == "renamed_alpha.json"
    assert not (run_configs_dir / "alpha.json").exists()
    assert (run_configs_dir / "renamed_alpha.json").exists()


def test_rename_config_collision_fails_clearly(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    try:
        service.rename_config(
            source_config_name="alpha.json",
            new_config_name="beta.json",
        )
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected rename collision to fail.")


def test_missing_config_fails_clearly(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    try:
        service.get_config("missing.json")
    except ValueError as exc:
        assert "Unknown run config" in str(exc)
    else:
        raise AssertionError("Expected missing config to fail.")


def test_recent_usage_derives_from_existing_persistence(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())
    _write_config(run_configs_dir / "beta.json", _base_payload())

    database_path = repo_root / "data" / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed_alpha",
        started_at="2026-04-08T10:00:00Z",
        configs_dir_snapshot={
            "configs": [
                {"config_name": "alpha.json", "config_path": "configs/runs/alpha.json"}
            ]
        },
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=repo_root / "data" / "datasets",
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="not_run",
        external_evaluation_status="not_run",
        audit_evaluation_status="not_run",
        status="completed",
    )
    store.save_run_execution(
        run_execution_uid="exec-alpha-1",
        multiseed_run_id=multiseed_run_id,
        run_id="run_alpha_1",
        config_name="alpha.json",
        config_json_snapshot=_base_payload(),
        effective_seed=100,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-alpha",
        dataset_context_json={"train_count": 1},
        status="completed",
    )

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
        database_path=database_path,
    )

    configs = {item.config_name: item for item in service.list_configs()}

    alpha_usage = configs["alpha.json"].recent_usage
    beta_usage = configs["beta.json"].recent_usage

    assert alpha_usage.campaign_usage_count == 1
    assert alpha_usage.latest_campaign_id == "multiseed_alpha"
    assert alpha_usage.latest_campaign_started_at == "2026-04-08T10:00:00Z"
    assert alpha_usage.latest_campaign_status == "completed"
    assert alpha_usage.appears_in_persisted_executions is True
    assert beta_usage.campaign_usage_count == 0
    assert beta_usage.appears_in_persisted_executions is False


def test_save_config_updates_existing_canonical_file(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    _write_config(run_configs_dir / "alpha.json", _base_payload())

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["research_stack"]["signal_pack_name"] = "core_policy_v21_signals_v1"
    editor["evolution_budget"]["generations_planned"] = 40
    editor["seed_plan"] = {
        "mode": "explicit",
        "seed_start": None,
        "seed_count": None,
        "explicit_seeds": [101, 102, 103],
        "summary": "101, 102, 103",
    }

    saved = service.save_config(
        source_config_name="alpha.json",
        config_payload=editor,
    )

    assert saved.identity.config_name == "alpha.json"
    persisted = json.loads((run_configs_dir / "alpha.json").read_text(encoding="utf-8"))
    assert persisted["signal_pack_name"] == "core_policy_v21_signals_v1"
    assert persisted["generations_planned"] == 40
    assert persisted["seeds"] == [101, 102, 103]
    assert "seed_start" not in persisted
    assert "seed_count" not in persisted


def test_save_config_as_new_creates_new_canonical_file(tmp_path: Path) -> None:
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
    editor["research_stack"]["dataset_catalog_id"] = "alt_dataset"

    saved = service.save_config_as_new(config_payload=editor)

    assert saved.identity.config_name == "beta.json"
    persisted = json.loads((run_configs_dir / "beta.json").read_text(encoding="utf-8"))
    assert persisted["dataset_catalog_id"] == "alt_dataset"


def test_save_config_rejects_implicit_rename(tmp_path: Path) -> None:
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

    try:
        service.save_config(
            source_config_name="alpha.json",
            config_payload=editor,
        )
    except ValueError as exc:
        assert "cannot rename files implicitly" in str(exc)
    else:
        raise AssertionError("Expected implicit rename during save to fail.")


def test_save_config_as_new_collision_fails_clearly(tmp_path: Path) -> None:
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

    try:
        service.save_config_as_new(config_payload=editor)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected save-as-new collision to fail.")


def test_save_config_missing_source_fails_clearly(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    try:
        service.save_config(
            source_config_name="missing.json",
            config_payload={
                "identity": {"config_name": "missing.json"},
                "research_stack": {},
                "evolution_budget": {},
                "seed_plan": {},
                "evaluation_trading": {},
                "advanced_overrides": {},
            },
        )
    except ValueError as exc:
        assert "Unknown run config" in str(exc)
    else:
        raise AssertionError("Expected missing source save to fail.")


def test_save_config_invalid_payload_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    repo_root = tmp_path
    run_configs_dir = repo_root / "configs" / "runs"
    run_configs_dir.mkdir(parents=True)
    original_payload = _base_payload()
    _write_config(run_configs_dir / "alpha.json", original_payload)

    service = RunConfigBrowserApplicationService(
        repo_root=repo_root,
        run_configs_dir=run_configs_dir,
    )

    editor = service.get_config("alpha.json").to_dict()
    editor["seed_plan"] = {
        "mode": "explicit",
        "seed_start": None,
        "seed_count": None,
        "explicit_seeds": [],
        "summary": "",
    }

    try:
        service.save_config(
            source_config_name="alpha.json",
            config_payload=editor,
        )
    except ValueError as exc:
        assert "Explicit seed mode requires" in str(exc)
    else:
        raise AssertionError("Expected invalid payload save to fail.")

    persisted = json.loads((run_configs_dir / "alpha.json").read_text(encoding="utf-8"))
    assert persisted == original_payload
