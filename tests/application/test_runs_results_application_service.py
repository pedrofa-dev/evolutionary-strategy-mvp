from __future__ import annotations

import json
from pathlib import Path

from application.runs_results import RunsResultsApplicationService
from evo_system.storage import PersistenceStore


def _summary_payload(
    *,
    run_id: str,
    validation_selection: float,
    validation_profit: float,
    train_selection: float,
) -> dict:
    return {
        "run_id": run_id,
        "config_name": "run_lab_probe.json",
        "mutation_seed": 101,
        "best_train_selection_score": train_selection,
        "final_validation_selection_score": validation_selection,
        "final_validation_profit": validation_profit,
        "final_validation_drawdown": 0.02,
        "final_validation_trades": 14.0,
        "generation_of_best": 7,
        "train_validation_selection_gap": train_selection - validation_selection,
        "train_validation_profit_gap": 0.01,
        "execution_status": "executed",
    }


def seed_campaign(repo_root: Path, database_path: Path) -> str:
    store = PersistenceStore(database_path)
    store.initialize()

    quick_summary_path = repo_root / "artifacts" / "multiseed" / "campaign_001" / "multiseed_quick_summary.txt"
    quick_summary_path.parent.mkdir(parents=True, exist_ok=True)
    quick_summary_path.write_text(
        "\n".join(
            [
                "Multiseed: campaign_001",
                "Final verdict: ROBUST_CANDIDATE",
                "Likely limit: NO_CLEAR_LIMIT",
                "Next action: Keep this config in the candidate set.",
            ]
        ),
        encoding="utf-8",
    )

    champions_json_path = repo_root / "artifacts" / "multiseed" / "campaign_001" / "external_reevaluated_champions.json"
    champions_json_path.write_text(
        json.dumps(
            [
                {
                    "champion_id": 1,
                    "run_id": "run-001",
                    "validation_selection": 1.4,
                    "external_validation_selection": 1.2,
                    "external_validation_profit": 0.03,
                    "external_validation_is_valid": True,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_001",
        configs_dir_snapshot={
            "configs": [
                {
                    "config_name": "run_lab_probe.json",
                    "config_path": "configs/runs/run_lab_probe.json",
                }
            ]
        },
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=str(repo_root / "data" / "datasets"),
        runs_planned=2,
        runs_completed=2,
        runs_reused=0,
        runs_failed=0,
        champions_found=True,
        champion_analysis_status="completed",
        external_evaluation_status="completed",
        audit_evaluation_status="not_run",
        preset_name="standard",
        status="completed",
        quick_summary_artifact_path=quick_summary_path,
        artifacts_root_path=quick_summary_path.parent,
    )

    config_snapshot = {
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "decision_policy_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
    }

    run_execution_id = store.save_run_execution(
        run_execution_uid="execution-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-001",
        config_name="run_lab_probe.json",
        config_json_snapshot=config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
        summary_json=_summary_payload(
            run_id="run-001",
            validation_selection=1.4,
            validation_profit=0.04,
            train_selection=1.7,
        ),
    )
    store.save_run_execution(
        run_execution_uid="execution-002",
        multiseed_run_id=multiseed_run_id,
        run_id="run-002",
        config_name="run_lab_probe.json",
        config_json_snapshot=config_snapshot,
        effective_seed=102,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-002",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
        summary_json=_summary_payload(
            run_id="run-002",
            validation_selection=0.8,
            validation_profit=-0.01,
            train_selection=1.1,
        ),
    )
    store.save_champion(
        champion_uid="champion-001",
        run_execution_id=run_execution_id,
        run_id="run-001",
        config_name="run_lab_probe.json",
        config_json_snapshot=config_snapshot,
        generation_number=7,
        mutation_seed=101,
        champion_type="robust",
        genome_json_snapshot={"threshold_open": 0.4},
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        train_metrics_json={"selection_score": 1.7, "median_profit": 0.05},
        validation_metrics_json={
            "selection_score": 1.4,
            "median_profit": 0.04,
            "median_drawdown": 0.02,
            "median_trades": 14.0,
        },
        champion_metrics_json={"selection_gap": 0.3},
    )
    store.save_champion_analysis(
        champion_analysis_uid="analysis-001",
        multiseed_run_id=multiseed_run_id,
        analysis_type="automatic_post_multiseed",
        champion_count=1,
        selection_scope_json={"run_ids": ["run-001", "run-002"]},
        analysis_summary_json={
            "champion_count": 1,
            "champion_card": {
                "champion_id": 1,
                "config_name": "run_lab_probe.json",
                "type": "robust",
                "scores": {
                    "validation_selection": 1.4,
                    "validation_profit": 0.04,
                    "validation_drawdown": 0.02,
                    "validation_trades": 14.0,
                },
                "modular_identity": {
                    "stack_label": "signal_pack=policy_v21_default | genome_schema=policy_v2_default",
                },
                "traceability": {
                    "logic_version": "v15",
                    "config_hash": "abc123",
                },
            },
        },
    )
    store.save_champion_evaluation(
        champion_evaluation_uid="evaluation-001",
        multiseed_run_id=multiseed_run_id,
        evaluation_type="external",
        evaluation_origin="automatic_post_multiseed",
        champion_count=1,
        dataset_source_type="catalog_scoped",
        dataset_set_name="external",
        dataset_signature="ext-sig-001",
        selection_scope_json={"run_ids": ["run-001", "run-002"]},
        evaluation_summary_json={
            "rows_generated": 1,
            "mean_summary": {
                "mean_validation_selection": 1.4,
                "mean_validation_profit": 0.04,
                "mean_post_selection": 1.2,
                "mean_post_profit": 0.03,
                "positive_profit_count": 1,
                "valid_count": 1,
            },
        },
        json_artifact_path=champions_json_path,
    )
    return "campaign_001"


def test_runs_results_application_service_lists_campaigns(tmp_path: Path) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    campaigns = service.list_campaigns()

    assert len(campaigns) == 1
    assert campaigns[0].campaign_id == campaign_id
    assert campaigns[0].config_name == "run_lab_probe.json"
    assert campaigns[0].dataset_label == "core_1h_spot"
    assert campaigns[0].preset_name == "standard"
    assert campaigns[0].mean_score == 1.1
    assert campaigns[0].champion_count == 1
    assert campaigns[0].verdict == "ROBUST_CANDIDATE"


def test_runs_results_application_service_reads_campaign_detail_and_compare(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    detail = service.get_campaign(campaign_id)

    assert detail is not None
    assert detail.summary.campaign_id == campaign_id
    assert detail.champion is not None
    assert detail.champion.classification == "robust"
    assert detail.champion.score == 1.4
    assert detail.champion.source == "champion_analysis"
    assert len(detail.executions) == 2
    assert detail.executions[0].run_id == "run-001"
    assert detail.executions[0].external_score == 1.2
    assert detail.evaluation.external_mean_score == 1.2
    assert detail.evaluation.external_valid_count == 1
    assert detail.evaluation.has_external_evaluation is True
    assert detail.evaluation.external_artifact_available is True
    assert detail.summary.has_quick_summary is True
    assert detail.summary.quick_summary_source == "persisted_quick_summary"
    assert detail.summary.has_external_evaluation is True
    assert detail.summary.external_artifact_available is True
    assert detail.summary.has_champion is True

    comparison = service.compare_campaigns([campaign_id])
    assert len(comparison) == 1
    assert comparison[0].campaign_id == campaign_id
    assert comparison[0].champion_classification == "robust"
    assert comparison[0].has_champion is True
    assert comparison[0].has_external_evaluation is True
    assert comparison[0].external_artifact_available is True


def test_runs_results_application_service_handles_incomplete_campaign_data(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_incomplete",
        configs_dir_snapshot={
            "configs": [
                {
                    "config_name": "incomplete_probe.json",
                    "config_path": "configs/runs/incomplete_probe.json",
                }
            ]
        },
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=str(tmp_path / "data" / "datasets"),
        runs_planned=3,
        runs_completed=1,
        runs_reused=0,
        runs_failed=1,
        champions_found=False,
        champion_analysis_status="not_run",
        external_evaluation_status="not_run",
        audit_evaluation_status="not_run",
        preset_name="quick",
        status="partial",
        quick_summary_artifact_path=None,
        artifacts_root_path=tmp_path / "artifacts" / "multiseed" / "campaign_incomplete",
    )

    store.save_run_execution(
        run_execution_uid="execution-incomplete-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-incomplete-001",
        config_name="incomplete_probe.json",
        config_json_snapshot={"dataset_catalog_id": "core_1h_spot"},
        effective_seed=303,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-incomplete",
        dataset_context_json={"train_count": 1},
        status="completed",
        summary_json={
            "run_id": "run-incomplete-001",
            "best_train_selection_score": 0.7,
        },
    )

    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    campaigns = service.list_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].campaign_id == "campaign_incomplete"
    assert campaigns[0].has_champion is False
    assert campaigns[0].has_external_evaluation is False
    assert campaigns[0].external_artifact_available is False
    assert campaigns[0].has_quick_summary is False
    assert campaigns[0].mean_score is None
    assert campaigns[0].validation_to_external_survival_rate is None

    detail = service.get_campaign("campaign_incomplete")
    assert detail is not None
    assert detail.champion is None
    assert detail.evaluation.has_external_evaluation is False
    assert detail.evaluation.external_artifact_available is False
    assert detail.evaluation.external_mean_score is None
    assert detail.executions[0].validation_score is None
    assert detail.executions[0].external_score is None


def test_runs_results_application_service_exposes_reuse_visibility(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()

    config_snapshot = {
        "dataset_catalog_id": "core_1h_spot",
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "policy_v2_default",
        "decision_policy_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
    }

    previous_multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_previous_failed",
        configs_dir_snapshot={"configs": [{"config_name": "reuse_probe.json"}]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=str(tmp_path / "data" / "datasets"),
        runs_planned=1,
        runs_completed=0,
        runs_reused=0,
        runs_failed=1,
        champions_found=False,
        champion_analysis_status="failed",
        external_evaluation_status="failed",
        audit_evaluation_status="failed",
        preset_name="standard",
        status="completed_with_failures",
        logic_version="v15",
    )
    store.save_run_execution(
        run_execution_uid="execution-previous-failed",
        multiseed_run_id=previous_multiseed_run_id,
        run_id="run-previous-failed",
        config_name="reuse_probe.json",
        config_json_snapshot=config_snapshot,
        effective_seed=100,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-reuse",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="failed",
        logic_version="v15",
        failure_reason="interrupted",
    )

    current_multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_reuse_probe",
        configs_dir_snapshot={"configs": [{"config_name": "reuse_probe.json"}]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=str(tmp_path / "data" / "datasets"),
        runs_planned=2,
        runs_completed=2,
        runs_reused=1,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="skipped_no_champions",
        external_evaluation_status="skipped_no_champions",
        audit_evaluation_status="skipped_no_champions",
        preset_name="standard",
        status="completed",
        logic_version="v15",
    )
    store.save_run_execution(
        run_execution_uid="execution-current-001",
        multiseed_run_id=current_multiseed_run_id,
        run_id="run-current-001",
        config_name="reuse_probe.json",
        config_json_snapshot=config_snapshot,
        effective_seed=100,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-reuse",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
        logic_version="v15",
        summary_json={
            "run_id": "run-current-001",
            "best_train_selection_score": 0.8,
            "final_validation_selection_score": 0.7,
            "train_validation_selection_gap": 0.1,
            "train_validation_profit_gap": 0.01,
            "final_validation_profit": 0.02,
            "final_validation_drawdown": 0.01,
            "final_validation_trades": 10.0,
            "best_genome_repr": "genome",
            "generation_of_best": 4,
            "execution_status": "executed",
        },
    )

    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    detail = service.get_campaign("campaign_reuse_probe")

    assert detail is not None
    assert detail.reuse_overview["reused_count"] == 1
    assert detail.reuse_overview["fresh_success_count"] == 1
    assert detail.executions[0].reuse_status == "fresh execution"
    assert detail.executions[0].reuse_reason == "Previous matching execution existed but was not completed."
    assert detail.executions[0].reuse_reason_source == "exact_prior_row"


def test_runs_results_application_service_returns_partial_detail_when_external_artifact_is_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    missing_artifact_path = (
        tmp_path
        / "artifacts"
        / "multiseed"
        / "campaign_001"
        / "external_reevaluated_champions.json"
    )
    missing_artifact_path.unlink()
    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    detail = service.get_campaign(campaign_id)

    assert detail is not None
    assert detail.summary.has_external_evaluation is True
    assert detail.summary.external_artifact_available is False
    assert detail.evaluation.has_external_evaluation is True
    assert detail.evaluation.external_artifact_available is False
    assert detail.executions[0].external_score is None


def test_runs_results_application_service_lists_active_monitor_items(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()

    progress_path = (
        tmp_path
        / "artifacts"
        / "multiseed"
        / "campaign_running"
        / "progress_probe_seed101.json"
    )
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "config_name": "running_probe.json",
                "mutation_seed": 101,
                "current_generation": 7,
                "total_generations": 25,
                "validation_selection": 0.82,
                "elapsed_seconds": 95.0,
            }
        ),
        encoding="utf-8",
    )

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_running",
        configs_dir_snapshot={
            "configs": [
                {
                    "config_name": "running_probe.json",
                    "config_path": "configs/runs/running_probe.json",
                }
            ]
        },
        requested_parallel_workers=4,
        effective_parallel_workers=2,
        dataset_root=str(tmp_path / "data" / "datasets"),
        runs_planned=6,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="not_run",
        external_evaluation_status="not_run",
        audit_evaluation_status="not_run",
        preset_name="screening",
        status="running",
        artifacts_root_path=progress_path.parent,
    )
    store.save_run_execution(
        run_execution_uid="execution-running-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-running-001",
        config_name="running_probe.json",
        config_json_snapshot={"dataset_catalog_id": "core_1h_spot"},
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-running-001",
        dataset_context_json={"train_count": 1},
        status="running",
        progress_snapshot_artifact_path=progress_path,
    )

    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)
    items = service.list_execution_monitor_items()

    assert len(items) == 1
    assert items[0].campaign_id == "campaign_running"
    assert items[0].is_active is True
    assert items[0].requested_parallel_workers == 4
    assert items[0].effective_parallel_workers == 2
    assert items[0].seeds_finished == 1
    assert items[0].seeds_remaining == 5
    assert items[0].generation_progress is not None


def test_runs_results_application_service_deletes_completed_campaign_and_artifacts(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    campaign_id = seed_campaign(tmp_path, database_path)
    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    result = service.delete_campaign(campaign_id)

    assert result is not None
    assert result.campaign_id == campaign_id
    assert result.deleted_row_counts["multiseed_runs"] == 1
    assert service.get_campaign(campaign_id) is None
    assert not (tmp_path / "artifacts" / "multiseed" / "campaign_001").exists()


def test_runs_results_application_service_blocks_deleting_running_campaign(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="campaign_running",
        configs_dir_snapshot={"configs": [{"config_name": "running_probe.json"}]},
        requested_parallel_workers=2,
        effective_parallel_workers=2,
        dataset_root=str(tmp_path / "data" / "datasets"),
        runs_planned=4,
        runs_completed=0,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="not_run",
        external_evaluation_status="not_run",
        audit_evaluation_status="not_run",
        preset_name="standard",
        status="running",
    )
    store.save_run_execution(
        run_execution_uid="execution-running-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-running-001",
        config_name="running_probe.json",
        config_json_snapshot={"dataset_catalog_id": "core_1h_spot"},
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-running-001",
        dataset_context_json={"train_count": 1},
        status="running",
    )

    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    try:
        service.delete_campaign("campaign_running")
    except ValueError as exc:
        assert "still running" in str(exc)
    else:
        raise AssertionError("Expected deleting a running campaign to fail.")


def test_runs_results_application_service_lists_and_cancels_queued_jobs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    store = PersistenceStore(database_path)
    store.initialize()
    store.save_execution_queue_job(
        queue_job_uid="queue-running",
        campaign_id="multiseed_running",
        config_name="running_probe.json",
        config_path="configs/runs/running_probe.json",
        config_payload_json={"seed_count": 3},
        experiment_preset_name="standard",
        parallel_workers=2,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/running_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/running_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_running",
        status="running",
        started_at="2099-01-01T00:00:00Z",
        pid=12345,
    )
    store.save_execution_queue_job(
        queue_job_uid="queue-001",
        campaign_id="multiseed_queued",
        config_name="queued_probe.json",
        config_path="configs/runs/queued_probe.json",
        config_payload_json={"seed_count": 3},
        experiment_preset_name="standard",
        parallel_workers=2,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/queued_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/queued_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_queued",
    )
    service = RunsResultsApplicationService(database_path, repo_root=tmp_path)

    items = service.list_execution_monitor_items()

    queued_item = next(item for item in items if item.job_id == "queue-001")
    assert queued_item.status == "queued"
    assert queued_item.can_cancel is True
    assert queued_item.results_path is None

    cancelled = service.cancel_queued_job("queue-001")
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    refreshed = service.list_execution_monitor_items()
    refreshed_item = next(item for item in refreshed if item.job_id == "queue-001")
    assert refreshed_item.status == "cancelled"
