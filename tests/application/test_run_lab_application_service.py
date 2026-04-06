from __future__ import annotations

import json
import time
from pathlib import Path

from application.execution_queue import ExecutionQueueService
from application.run_lab import RunLabApplicationService
from evo_system.storage import PersistenceStore


def _write_manifest(path: Path, *, catalog_id: str = "core_1h_spot") -> None:
    path.write_text(
        "\n".join(
            [
                f"catalog_id: {catalog_id}",
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
                "  - id: BTCUSDT_1h_validation",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2023-03-01",
                "    end: 2023-03-15",
                "    layer: validation",
                "    regime_primary: range",
                "    regime_secondary: mean_reversion",
                "    volatility: low",
                "    event_tag: test_validation",
                "    notes: Validation window.",
            ]
        ),
        encoding="utf-8",
    )


def _write_template(path: Path) -> None:
    payload = {
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
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_run_lab_bootstrap_exposes_canonical_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    bootstrap = service.get_bootstrap()

    assert bootstrap.defaults["template_config_name"] == "balanced_baseline.json"
    assert bootstrap.defaults["dataset_catalog_id"] == "core_1h_spot"
    assert bootstrap.defaults["signal_pack_name"] == "policy_v21_default"
    assert bootstrap.defaults["genome_schema_name"] == "policy_v2_default"
    assert bootstrap.defaults["decision_policy_name"] == "policy_v2_default"
    assert bootstrap.defaults["mutation_profile_name"] == "default_runtime_profile"
    assert bootstrap.defaults["experiment_preset_name"] == "standard"
    assert bootstrap.dataset_catalogs[0].split_summary == {"train": 1, "validation": 1}
    assert any(option.id == "policy_v2_default" for option in bootstrap.decision_policies)
    assert [
        option.id for option in bootstrap.signal_pack_authoring.signal_options
    ] == [
        "trend_strength_medium",
        "trend_strength_long",
        "momentum_short",
        "momentum_persistence",
        "breakout_strength_medium",
        "range_position_medium",
        "realized_volatility_medium",
        "volatility_ratio_short_long",
    ]
    assert [
        option.id for option in bootstrap.genome_schema_authoring.gene_catalog_options
    ] == ["modular_genome_v1_gene_catalog"]
    assert [
        option.id for option in bootstrap.genome_schema_authoring.gene_type_options
    ] == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]
    assert [
        module.to_dict()
        for module in bootstrap.genome_schema_authoring.suggested_modules
    ] == [
        {"name": "entry_context", "gene_type": "entry_context", "required": True},
        {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
        {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
        {"name": "trade_control", "gene_type": "trade_control", "required": True},
    ]


def test_run_lab_save_run_config_writes_canonical_json(tmp_path: Path) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )

    result = service.save_run_config(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "bnb run lab probe",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
        }
    )

    saved_path = repo_root / result.config_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert result.config_name == "bnb run lab probe.json"
    assert saved_payload["dataset_catalog_id"] == "core_1h_spot"
    assert saved_payload["seed_start"] == 111
    assert saved_payload["seed_count"] == 8
    assert any(
        "Current executable mutation profile" in warning
        for warning in result.warnings
    )


def test_run_lab_save_and_execute_launches_canonical_script_in_isolated_dir(
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

    captured: dict[str, object] = {}

    class DummyProcess:
        pid = 12345

    def fake_launcher(command, cwd, stdout, stderr):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["stderr"] = stderr
        return DummyProcess()

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        launcher=fake_launcher,
    )

    result = service.save_and_execute(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "bnb run lab execute",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
            "experiment_preset_name": "standard",
            "parallel_workers": 3,
            "queue_concurrency_limit": 1,
        }
    )

    assert result.pid == 12345
    assert result.status == "running"
    assert result.job_id.startswith("queue_")
    assert captured["cwd"] == str(repo_root)
    assert "scripts/run_experiment.py" in captured["command"]
    assert "--preset" in captured["command"]
    assert "--multiseed-output-dir" in captured["command"]
    assert "--parallel-workers" in captured["command"]
    assert "3" in captured["command"]
    assert result.campaign_id is not None
    assert result.campaign_id.startswith("multiseed_")
    assert result.launch_log_path.endswith("launch.log")
    assert (repo_root / result.saved_config.config_path).exists()
    assert result.queue_concurrency_limit == 1


def test_run_lab_save_and_execute_leaves_second_job_queued_when_concurrency_cap_is_reached(
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

    class DummyProcess:
        pid = 99999

    launch_count = 0

    def fake_launcher(command, cwd, stdout, stderr):
        nonlocal launch_count
        launch_count += 1
        return DummyProcess()

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        launcher=fake_launcher,
    )

    first = service.save_and_execute(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "queue-first",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 101,
            "seed_count": 4,
            "experiment_preset_name": "standard",
            "parallel_workers": 2,
            "queue_concurrency_limit": 1,
        }
    )
    second = service.save_and_execute(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "queue-second",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 201,
            "seed_count": 4,
            "experiment_preset_name": "standard",
            "parallel_workers": 2,
            "queue_concurrency_limit": 1,
        }
    )

    assert first.status == "running"
    assert second.status == "queued"
    assert second.pid is None
    assert launch_count == 1


def test_execution_queue_background_dispatcher_advances_queue_without_ui_polling(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()
    store.set_execution_queue_concurrency_limit(1)

    launched_job_ids: list[str] = []

    class DummyProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    def fake_launcher(command, cwd, stdout, stderr):
        launched_job_ids.append(str(command[3]))
        return DummyProcess(9000 + len(launched_job_ids))

    queue_service = ExecutionQueueService(
        database_path=database_path,
        repo_root=tmp_path,
        launcher=fake_launcher,
        process_exists_checker=lambda pid: pid in {9001, 9002},
    )

    store.save_execution_queue_job(
        queue_job_uid="queue-001",
        campaign_id="multiseed_one",
        config_name="queued_one.json",
        config_path="configs/runs/queued_one.json",
        config_payload_json={"seed_count": 1},
        parallel_workers=1,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/queued_one",
        launch_log_path="artifacts/ui_run_lab/config_sets/queued_one/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_one",
    )
    store.save_execution_queue_job(
        queue_job_uid="queue-002",
        campaign_id="multiseed_two",
        config_name="queued_two.json",
        config_path="configs/runs/queued_two.json",
        config_payload_json={"seed_count": 1},
        parallel_workers=1,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/queued_two",
        launch_log_path="artifacts/ui_run_lab/config_sets/queued_two/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_two",
    )

    dispatcher = queue_service.start_background_dispatcher(poll_interval_seconds=0.05)
    try:
        deadline = time.time() + 1.5
        while time.time() < deadline:
            first_job = store.load_execution_queue_job("queue-001")
            if first_job is not None and first_job["status"] == "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Expected first queued job to start running.")

        store.update_execution_queue_job(
            "queue-001",
            status="finished",
            completed_at="2099-01-01T00:00:00Z",
        )

        deadline = time.time() + 1.5
        while time.time() < deadline:
            second_job = store.load_execution_queue_job("queue-002")
            if second_job is not None and second_job["status"] == "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Expected second queued job to start without UI polling.")
    finally:
        dispatcher.stop()


def test_execution_queue_reconciles_stale_running_campaign_and_unblocks_queue(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()
    store.set_execution_queue_concurrency_limit(1)

    launched_job_ids: list[str] = []

    class DummyProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    def fake_launcher(command, cwd, stdout, stderr):
        launched_job_ids.append(str(command[3]))
        return DummyProcess(9100 + len(launched_job_ids))

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed_stale",
        configs_dir_snapshot={"configs": [{"config_name": "stale_probe.json"}]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=tmp_path / "data" / "datasets",
        runs_planned=2,
        runs_completed=0,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="not_run",
        external_evaluation_status="not_run",
        audit_evaluation_status="not_run",
        status="running",
    )
    store.save_run_execution(
        run_execution_uid="execution-stale-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-stale-001",
        config_name="stale_probe.json",
        config_json_snapshot={"dataset_catalog_id": "core_1h_spot"},
        effective_seed=100,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-stale-001",
        dataset_context_json={"train_count": 1},
        status="running",
    )
    store.save_execution_queue_job(
        queue_job_uid="queue-stale",
        campaign_id="multiseed_stale",
        config_name="stale_probe.json",
        config_path="configs/runs/stale_probe.json",
        config_payload_json={"seed_count": 2},
        parallel_workers=1,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/stale_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/stale_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_stale",
        status="running",
        started_at="2026-04-06T15:00:00Z",
        pid=77777,
    )
    store.save_execution_queue_job(
        queue_job_uid="queue-next",
        campaign_id="multiseed_next",
        config_name="next_probe.json",
        config_path="configs/runs/next_probe.json",
        config_payload_json={"seed_count": 1},
        parallel_workers=1,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/next_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/next_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_next",
        status="queued",
    )

    queue_service = ExecutionQueueService(
        database_path=database_path,
        repo_root=tmp_path,
        launcher=fake_launcher,
        process_exists_checker=lambda pid: False,
    )

    queue_service.reconcile_and_dispatch()

    stale_job = store.load_execution_queue_job("queue-stale")
    next_job = store.load_execution_queue_job("queue-next")
    assert stale_job is not None
    assert next_job is not None
    assert stale_job["status"] == "failed"
    assert "no longer has a live process" in str(stale_job["failure_message"])
    assert next_job["status"] == "running"

    with store.connect() as connection:
        campaign_row = connection.execute(
            """
            SELECT status, runs_failed
            FROM multiseed_runs
            WHERE multiseed_run_uid = 'multiseed_stale'
            LIMIT 1
            """
        ).fetchone()
        run_row = connection.execute(
            """
            SELECT status, failure_reason
            FROM run_executions
            WHERE run_execution_uid = 'execution-stale-001'
            LIMIT 1
            """
        ).fetchone()

    assert campaign_row is not None
    assert campaign_row["status"] == "failed"
    assert int(campaign_row["runs_failed"]) == 1
    assert run_row is not None
    assert run_row["status"] == "failed"
    assert "no live process" in str(run_row["failure_reason"])


def test_run_lab_save_run_config_allows_reusing_identical_existing_config(
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )
    payload = {
        "template_config_name": "balanced_baseline.json",
        "config_name": "repeatable probe",
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "decision_policy_name": "policy_v2_default",
        "seed_mode": "range",
        "seed_start": 111,
        "seed_count": 8,
    }

    first_result = service.save_run_config(payload)
    second_result = service.save_run_config(payload)

    assert first_result.config_name == "repeatable probe.json"
    assert second_result.config_name == "repeatable probe.json"
    assert first_result.config_payload == second_result.config_payload


def test_run_lab_save_run_config_blocks_reusing_name_with_different_content(
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
    )
    base_payload = {
        "template_config_name": "balanced_baseline.json",
        "config_name": "collision probe",
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "decision_policy_name": "policy_v2_default",
        "seed_mode": "range",
        "seed_start": 111,
        "seed_count": 8,
    }
    service.save_run_config(base_payload)

    try:
        service.save_run_config(
            {
                **base_payload,
                "seed_count": 12,
            }
        )
    except ValueError as exc:
        assert "already exists with different content" in str(exc)
    else:
        raise AssertionError("Expected name collision with different content to fail.")


def test_run_lab_save_mutation_profile_asset_writes_canonical_json(
    tmp_path: Path,
) -> None:
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )

    result = service.save_mutation_profile_asset(
        {
            "id": "authoring_profile_v1",
            "description": "Authored in Run Lab.",
            "strong_mutation_probability": 0.12,
            "numeric_delta_scale": 1.3,
            "flag_flip_probability": 0.04,
            "weight_delta": 0.18,
            "window_step_mode": "small",
        }
    )

    saved_path = repo_root / result.asset_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert result.asset_id == "authoring_profile_v1"
    assert saved_payload["profile"]["numeric_delta_scale"] == 1.3
    assert saved_payload["description"] == "Authored in Run Lab."


def test_run_lab_save_mutation_profile_asset_allows_identical_reuse(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    mutation_profile_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "mutation_profiles"
    )
    mutation_profile_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )
    payload = {
        "id": "authoring_profile_v1",
        "description": "Authored in Run Lab.",
        "strong_mutation_probability": 0.12,
        "numeric_delta_scale": 1.3,
        "flag_flip_probability": 0.04,
        "weight_delta": 0.18,
        "window_step_mode": "small",
    }

    first_result = service.save_mutation_profile_asset(payload)
    second_result = service.save_mutation_profile_asset(payload)

    assert first_result.asset_id == second_result.asset_id
    assert first_result.asset_payload == second_result.asset_payload


def test_run_lab_save_mutation_profile_asset_rejects_different_content_same_id(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    mutation_profile_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "mutation_profiles"
    )
    mutation_profile_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )

    service.save_mutation_profile_asset(
        {
            "id": "authoring_profile_v1",
            "description": "Authored in Run Lab.",
            "strong_mutation_probability": 0.12,
            "numeric_delta_scale": 1.3,
            "flag_flip_probability": 0.04,
            "weight_delta": 0.18,
            "window_step_mode": "small",
        }
    )

    try:
        service.save_mutation_profile_asset(
            {
                "id": "authoring_profile_v1",
                "description": "Changed.",
                "strong_mutation_probability": 0.15,
                "numeric_delta_scale": 1.3,
                "flag_flip_probability": 0.04,
                "weight_delta": 0.18,
                "window_step_mode": "small",
            }
        )
    except ValueError as exc:
        assert "already exists with different content" in str(exc)
    else:
        raise AssertionError("Expected authored mutation profile collision to fail.")


def test_run_lab_bootstrap_lists_saved_authored_mutation_profile_as_selectable(
    tmp_path: Path,
) -> None:
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )
    service.save_mutation_profile_asset(
        {
            "id": "authoring_profile_v1",
            "description": "Authored in Run Lab.",
            "strong_mutation_probability": 0.12,
            "numeric_delta_scale": 1.3,
            "flag_flip_probability": 0.04,
            "weight_delta": 0.18,
            "window_step_mode": "small",
        }
    )

    bootstrap = service.get_bootstrap()
    authored_option = next(
        option
        for option in bootstrap.mutation_profiles
        if option.id == "authoring_profile_v1"
    )

    assert authored_option.selectable is True
    assert authored_option.origin == "asset"


def test_run_lab_save_run_config_accepts_authored_mutation_profile_asset(
    tmp_path: Path,
) -> None:
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )
    service.save_mutation_profile_asset(
        {
            "id": "authoring_profile_v1",
            "description": "Authored in Run Lab.",
            "strong_mutation_probability": 0.12,
            "numeric_delta_scale": 1.3,
            "flag_flip_probability": 0.04,
            "weight_delta": 0.18,
            "window_step_mode": "small",
        }
    )

    result = service.save_run_config(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "authored mutation profile run",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "authoring_profile_v1",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
        }
    )

    assert result.config_payload["mutation_profile_name"] == "authoring_profile_v1"


def test_run_lab_save_signal_pack_asset_writes_canonical_json(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    signal_pack_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "signal_packs"
    )
    signal_pack_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=repo_root
        / "src"
        / "evo_system"
        / "experimental_space"
        / "assets"
        / "mutation_profiles",
    )

    result = service.save_signal_pack_asset(
        {
            "id": "authoring_signal_pack_v1",
            "description": "Authored signal pack.",
            "signals": "trend_strength_medium\ntrend_strength_long\nmomentum_short",
        }
    )

    saved_path = repo_root / result.asset_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert result.asset_id == "authoring_signal_pack_v1"
    assert len(saved_payload["signals"]) == 3
    assert [entry["signal_id"] for entry in saved_payload["signals"]] == [
        "trend_strength_medium",
        "trend_strength_long",
        "momentum_short",
    ]
    assert saved_payload["signals"][0]["params"]["source"] == "trend_strength_medium"


def test_run_lab_save_genome_schema_asset_writes_canonical_json(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    genome_schema_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "genome_schemas"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        genome_schema_assets_dir=genome_schema_assets_dir,
    )

    result = service.save_genome_schema_asset(
        {
            "id": "authored_schema_v1",
            "description": "Authored schema.",
            "gene_catalog": "modular_genome_v1_gene_catalog",
            "modules": [
                {"name": "entry_context", "gene_type": "entry_context", "required": True},
                {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
                {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                {"name": "trade_control", "gene_type": "trade_control", "required": True},
            ],
        }
    )

    saved_path = repo_root / result.asset_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert result.asset_id == "authored_schema_v1"
    assert saved_payload["gene_catalog"] == "modular_genome_v1_gene_catalog"
    assert [module["name"] for module in saved_payload["modules"]] == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]


def test_run_lab_save_genome_schema_asset_allows_identical_reuse(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    genome_schema_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "genome_schemas"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        genome_schema_assets_dir=genome_schema_assets_dir,
    )

    payload = {
        "id": "authored_schema_v1",
        "description": "Authored schema.",
        "gene_catalog": "modular_genome_v1_gene_catalog",
        "modules": [
            {"name": "entry_context", "gene_type": "entry_context", "required": True},
            {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
            {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
            {"name": "trade_control", "gene_type": "trade_control", "required": True},
        ],
    }

    first_result = service.save_genome_schema_asset(payload)
    second_result = service.save_genome_schema_asset(payload)

    assert first_result.asset_path == second_result.asset_path


def test_run_lab_save_genome_schema_asset_rejects_different_content_same_id(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    genome_schema_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "genome_schemas"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        genome_schema_assets_dir=genome_schema_assets_dir,
    )

    service.save_genome_schema_asset(
        {
            "id": "authored_schema_v1",
            "description": "Authored schema.",
            "gene_catalog": "modular_genome_v1_gene_catalog",
            "modules": [
                {"name": "entry_context", "gene_type": "entry_context", "required": True},
                {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
                {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                {"name": "trade_control", "gene_type": "trade_control", "required": True},
            ],
        }
    )

    try:
        service.save_genome_schema_asset(
            {
                "id": "authored_schema_v1",
                "description": "Different schema.",
                "gene_catalog": "modular_genome_v1_gene_catalog",
                "modules": [
                    {"name": "entry_context", "gene_type": "entry_context", "required": True},
                    {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
                    {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                    {"name": "trade_control", "gene_type": "trade_control", "required": True},
                ],
            }
        )
    except ValueError as exc:
        assert "different content" in str(exc)
    else:
        raise AssertionError("Expected authored genome schema collision to fail.")


def test_run_lab_save_genome_schema_asset_rejects_invalid_payload(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    dataset_configs_dir = repo_root / "configs" / "datasets"
    run_configs_dir = repo_root / "configs" / "runs"
    artifacts_dir = repo_root / "artifacts" / "ui_run_lab"
    genome_schema_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "genome_schemas"
    )
    dataset_configs_dir.mkdir(parents=True)
    run_configs_dir.mkdir(parents=True)
    _write_manifest(dataset_configs_dir / "core_1h_spot.yaml")
    _write_template(run_configs_dir / "balanced_baseline.json")

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        genome_schema_assets_dir=genome_schema_assets_dir,
    )

    invalid_payloads = (
        {
            "id": "invalid_catalog_schema",
            "description": "Bad catalog.",
            "gene_catalog": "missing_gene_catalog",
            "modules": [
                {"name": "entry_context", "gene_type": "entry_context", "required": True},
                {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
                {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                {"name": "trade_control", "gene_type": "trade_control", "required": True},
            ],
        },
        {
            "id": "invalid_gene_type_schema",
            "description": "Bad gene type.",
            "gene_catalog": "modular_genome_v1_gene_catalog",
            "modules": [
                {"name": "entry_context", "gene_type": "entry_context", "required": True},
                {"name": "entry_trigger", "gene_type": "missing_gene_type", "required": True},
                {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                {"name": "trade_control", "gene_type": "trade_control", "required": True},
            ],
        },
        {
            "id": "invalid_structure_schema",
            "description": "Bad structure.",
            "gene_catalog": "modular_genome_v1_gene_catalog",
            "modules": [
                {"name": "entry_trigger", "gene_type": "entry_trigger", "required": True},
                {"name": "entry_context", "gene_type": "entry_context", "required": True},
                {"name": "exit_policy", "gene_type": "exit_policy", "required": True},
                {"name": "trade_control", "gene_type": "trade_control", "required": True},
            ],
        },
    )

    for payload in invalid_payloads:
        try:
            service.save_genome_schema_asset(payload)
        except ValueError:
            continue
        raise AssertionError("Expected invalid authored genome schema to fail.")


def test_run_lab_save_signal_pack_asset_preserves_signal_order(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    signal_pack_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "signal_packs"
    )
    signal_pack_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=repo_root
        / "src"
        / "evo_system"
        / "experimental_space"
        / "assets"
        / "mutation_profiles",
    )

    result = service.save_signal_pack_asset(
        {
            "id": "ordered_signal_pack_v1",
            "description": "Order should stay intact.",
            "signals": "momentum_short\ntrend_strength_medium\nbreakout_strength_medium",
        }
    )

    saved_path = repo_root / result.asset_path
    saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))

    assert [entry["signal_id"] for entry in saved_payload["signals"]] == [
        "momentum_short",
        "trend_strength_medium",
        "breakout_strength_medium",
    ]


def test_run_lab_save_signal_pack_asset_allows_identical_reuse(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    signal_pack_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "signal_packs"
    )
    signal_pack_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=repo_root
        / "src"
        / "evo_system"
        / "experimental_space"
        / "assets"
        / "mutation_profiles",
    )
    payload = {
        "id": "authoring_signal_pack_v1",
        "description": "Authored signal pack.",
        "signals": "trend_strength_medium\ntrend_strength_long\nmomentum_short",
    }

    first_result = service.save_signal_pack_asset(payload)
    second_result = service.save_signal_pack_asset(payload)

    assert first_result.asset_id == second_result.asset_id
    assert first_result.asset_payload == second_result.asset_payload


def test_run_lab_save_signal_pack_asset_rejects_different_content_same_id(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    signal_pack_assets_dir = (
        repo_root / "src" / "evo_system" / "experimental_space" / "assets" / "signal_packs"
    )
    signal_pack_assets_dir.mkdir(parents=True)
    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=repo_root / "configs" / "datasets",
        run_configs_dir=repo_root / "configs" / "runs",
        run_lab_artifacts_dir=repo_root / "artifacts" / "ui_run_lab",
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=repo_root
        / "src"
        / "evo_system"
        / "experimental_space"
        / "assets"
        / "mutation_profiles",
    )

    service.save_signal_pack_asset(
        {
            "id": "authoring_signal_pack_v1",
            "description": "Authored signal pack.",
            "signals": "trend_strength_medium\ntrend_strength_long",
        }
    )

    try:
        service.save_signal_pack_asset(
            {
                "id": "authoring_signal_pack_v1",
                "description": "Changed.",
                "signals": "trend_strength_medium\nmomentum_short",
            }
        )
    except ValueError as exc:
        assert "already exists with different content" in str(exc)
    else:
        raise AssertionError("Expected authored signal pack collision to fail.")


def test_run_lab_bootstrap_lists_saved_authored_signal_pack_as_selectable(
    tmp_path: Path,
) -> None:
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )
    service.save_signal_pack_asset(
        {
            "id": "authoring_signal_pack_v1",
            "description": "Authored signal pack.",
            "signals": "trend_strength_medium\ntrend_strength_long\nmomentum_short",
        }
    )

    bootstrap = service.get_bootstrap()
    authored_option = next(
        option
        for option in bootstrap.signal_packs
        if option.id == "authoring_signal_pack_v1"
    )

    assert authored_option.selectable is True
    assert authored_option.origin == "asset"


def test_run_lab_save_run_config_accepts_authored_signal_pack_asset(
    tmp_path: Path,
) -> None:
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

    service = RunLabApplicationService(
        repo_root=repo_root,
        dataset_configs_dir=dataset_configs_dir,
        run_configs_dir=run_configs_dir,
        run_lab_artifacts_dir=artifacts_dir,
        signal_pack_assets_dir=signal_pack_assets_dir,
        mutation_profile_assets_dir=mutation_profile_assets_dir,
    )
    service.save_signal_pack_asset(
        {
            "id": "authoring_signal_pack_v1",
            "description": "Authored signal pack.",
            "signals": "trend_strength_medium\ntrend_strength_long\nmomentum_short",
        }
    )

    result = service.save_run_config(
        {
            "template_config_name": "balanced_baseline.json",
            "config_name": "authored signal pack run",
            "dataset_catalog_id": "core_1h_spot",
            "signal_pack_name": "authoring_signal_pack_v1",
            "genome_schema_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "decision_policy_name": "policy_v2_default",
            "seed_mode": "range",
            "seed_start": 111,
            "seed_count": 8,
        }
    )

    assert result.config_payload["signal_pack_name"] == "authoring_signal_pack_v1"
