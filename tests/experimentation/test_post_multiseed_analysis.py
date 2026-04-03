import json
import sqlite3
from pathlib import Path

import pytest
from evo_system.domain.genome import Genome
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.dataset_roots import DEFAULT_DATASET_ROOT
from evo_system.experimentation.post_multiseed_analysis import (
    ANALYSIS_DIRNAME,
    CHAMPIONS_ANALYSIS_DIRNAME,
    DEBUG_DIRNAME,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
    run_post_multiseed_analysis,
)
from evo_system.storage.persistence_store import PersistenceStore


def build_summary(
    tmp_path: Path,
    *,
    config_name: str,
    run_id: str,
    selection: float,
    profit: float,
) -> HistoricalRunSummary:
    return HistoricalRunSummary(
        config_name=config_name,
        run_id=run_id,
        log_file_path=tmp_path / f"{config_name}.txt",
        mutation_seed=42,
        best_train_selection_score=selection + 0.1,
        final_validation_selection_score=selection,
        final_validation_profit=profit,
        final_validation_drawdown=0.01,
        final_validation_trades=10.0,
        best_genome_repr="genome",
        generation_of_best=5,
        train_validation_selection_gap=0.1,
        train_validation_profit_gap=0.01,
        config_path=tmp_path / config_name,
        experimental_space_snapshot={
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "modular_genome_v1",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "experiment_preset_name": "standard",
        },
    )


def write_config(config_path: Path) -> None:
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "dataset_catalog_id": "core_1h_spot",
                "trade_cost_rate": 0.001,
                "cost_penalty_weight": 0.25,
                "trade_count_penalty_weight": 0.0,
                "regime_filter_enabled": False,
            }
        ),
        encoding="utf-8",
    )


def write_dataset(dataset_path: Path) -> None:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close",
                "1,100,100,100,100",
                "2,100,110,100,110",
                "3,110,120,110,120",
                "4,120,125,115,118",
            ]
        ),
        encoding="utf-8",
    )


def seed_new_persistence_context(
    database_path: Path,
    *,
    multiseed_run_uid: str,
    run_id: str,
    config_name: str,
    dataset_root: Path | None = None,
    include_dataset_root_context: bool = True,
) -> int:
    store = PersistenceStore(database_path)
    store.initialize()
    resolved_dataset_root = dataset_root or Path("data/datasets")
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=multiseed_run_uid,
        configs_dir_snapshot={"configs": [config_name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root=resolved_dataset_root,
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=True,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )
    config_snapshot = {
        "mutation_seed": 42,
        "population_size": 12,
        "target_population_size": 12,
        "survivors_count": 4,
        "generations_planned": 25,
        "dataset_catalog_id": "core_1h_spot",
        "trade_cost_rate": 0.001,
        "cost_penalty_weight": 0.25,
        "trade_count_penalty_weight": 0.0,
        "regime_filter_enabled": False,
    }
    run_execution_id = store.save_run_execution(
        run_execution_uid=f"execution-{run_id}",
        multiseed_run_id=multiseed_run_id,
        run_id=run_id,
        config_name=config_name,
        config_json_snapshot=config_snapshot,
        effective_seed=42,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={
            "train_count": 1,
            "validation_count": 1,
            **(
                {"resolved_dataset_root": str(resolved_dataset_root)}
                if include_dataset_root_context
                else {}
            ),
        },
        status="completed",
        requested_dataset_root=resolved_dataset_root if include_dataset_root_context else None,
        resolved_dataset_root=resolved_dataset_root if include_dataset_root_context else None,
    )
    store.save_champion(
        champion_uid=f"champion-{run_id}",
        run_execution_id=run_execution_id,
        run_id=run_id,
        config_name=config_name,
        config_json_snapshot=config_snapshot,
        generation_number=5,
        mutation_seed=42,
        champion_type="robust",
        genome_json_snapshot=Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        ).to_dict(),
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        train_metrics_json={"selection": 1.6},
        validation_metrics_json={"selection": 1.5},
        champion_metrics_json={
            "champion_type": "robust",
            "validation_selection": 1.5,
            "validation_profit": 0.02,
            "validation_drawdown": 0.01,
            "validation_trades": 12,
            "selection_gap": 0.2,
        },
    )
    return multiseed_run_id


def test_run_post_multiseed_analysis_generates_expected_artifacts(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    dataset_root = tmp_path / "data" / "datasets"
    external_dir = dataset_root / "core_1h_spot" / "external"
    audit_dir = dataset_root / "core_1h_spot" / "audit"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    multiseed_run_id = seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid=multiseed_dir.name,
        run_id="run-001",
        config_name="run_a.json",
        dataset_root=dataset_root,
    )
    write_dataset(external_dir / "set_a" / "candles.csv")
    write_dataset(audit_dir / "set_b" / "candles.csv")

    result = run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        multiseed_run_id=multiseed_run_id,
        failures=[],
        seeds_planned=1,
        seeds_executed=1,
        seeds_reused=0,
    )

    assert result.summary_path == summary_path
    assert result.quick_summary_path == multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    assert result.champions_summary_path == multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME
    assert result.analysis_dir == multiseed_dir / ANALYSIS_DIRNAME
    assert result.debug_dir == multiseed_dir / DEBUG_DIRNAME
    assert (multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv").exists()
    assert (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluation_report.txt"
    ).exists()
    assert (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "audit"
        / "audit_reevaluation_report.txt"
    ).exists()
    assert not (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "reevaluated_champions.csv"
    ).exists()
    assert (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "champions"
        / "champion_1.json"
    ).exists()

    quick_summary = (
        multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    external_json = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluated_champions.json"
    ).read_text(encoding="utf-8")
    combined_summary = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "post_multiseed_reevaluation_summary.txt"
    ).read_text(encoding="utf-8")
    assert "Runs: planned=1 | completed=1 | executed=1 | reused=0 | failed=0" in quick_summary
    assert "Modules: single_stack | signal_pack=policy_v21_default" in quick_summary
    assert "Champions found: 1" in quick_summary
    assert "Final verdict:" in quick_summary
    assert "Next action:" in quick_summary
    assert '"external_dataset_root"' in external_json
    assert '"external_evaluation_type": "external"' in external_json
    assert '"external_dataset_catalog_id": "core_1h_spot"' in external_json
    assert "catalog_scope_mode=single_catalog" in combined_summary
    champions_summary = (
        multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    assert "Active modular components" in champions_summary
    assert "signal_pack=policy_v21_default" in champions_summary
    assert result.champion_count == 1
    assert result.champion_analysis_status == "completed"
    assert result.external_evaluation_status == "completed"
    assert result.audit_evaluation_status == "completed"

    with sqlite3.connect(persistence_db_path) as connection:
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM champion_analyses WHERE multiseed_run_id = ?",
            (multiseed_run_id,),
        ).fetchone()[0]
        analysis_member_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM champion_analysis_members
            """
        ).fetchone()[0]
        evaluation_rows = connection.execute(
            """
            SELECT evaluation_type
            FROM champion_evaluations
            WHERE multiseed_run_id = ?
            ORDER BY evaluation_type ASC
            """,
            (multiseed_run_id,),
        ).fetchall()
        evaluation_member_count = connection.execute(
            "SELECT COUNT(*) FROM champion_evaluation_members"
        ).fetchone()[0]

    assert analysis_count == 1
    assert analysis_member_count == 1
    assert [row[0] for row in evaluation_rows] == ["audit", "external"]
    assert evaluation_member_count == 2


def test_run_post_multiseed_analysis_handles_no_champions_and_missing_datasets(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    store = PersistenceStore(persistence_db_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=multiseed_dir.name,
        configs_dir_snapshot={"configs": ["run_a.json"]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )

    result = run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        multiseed_run_id=multiseed_run_id,
        external_validation_dir=tmp_path / "missing_external",
        audit_dir=tmp_path / "missing_audit",
        failures=["seed 102: boom"],
        seeds_planned=2,
        seeds_executed=1,
        seeds_reused=0,
    )

    quick_summary = (
        multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    champions_summary = (
        multiseed_dir / ANALYSIS_DIRNAME / MULTISEED_CHAMPIONS_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    external_report = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "seed 102: boom" in quick_summary
    assert "Runs: planned=2 | completed=1 | executed=1 | reused=0 | failed=1" in quick_summary
    assert "Champions found: 0" in quick_summary
    assert "Final verdict: NO_EDGE_DETECTED" in quick_summary
    assert "Verdict: NO_EDGE_DETECTED" in champions_summary
    assert "No persisted champions were found for this multiseed execution." in external_report
    assert result.champion_count == 0
    assert result.champion_analysis_status == "skipped_no_champions"
    assert result.external_evaluation_status == "skipped_no_champions"
    assert result.audit_evaluation_status == "skipped_no_champions"

    with sqlite3.connect(persistence_db_path) as connection:
        analysis_count = connection.execute(
            "SELECT COUNT(*) FROM champion_analyses"
        ).fetchone()[0]
        evaluation_count = connection.execute(
            "SELECT COUNT(*) FROM champion_evaluations"
        ).fetchone()[0]

    assert analysis_count == 0
    assert evaluation_count == 0


def test_run_post_multiseed_analysis_filters_only_multiseed_run_ids(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    dataset_root = tmp_path / "data" / "datasets"
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-001",
        run_id="run-001",
        config_name="run_a.json",
        dataset_root=dataset_root,
    )
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-999",
        run_id="run-999",
        config_name="run_a.json",
        dataset_root=dataset_root,
    )

    run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        failures=[],
        seeds_planned=1,
        seeds_executed=1,
        seeds_reused=0,
    )

    champions_csv = (
        multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv"
    ).read_text(encoding="utf-8")
    assert "run-001" in champions_csv
    assert "run-999" not in champions_csv


def test_run_post_multiseed_analysis_includes_champions_from_reused_summaries(
    tmp_path: Path,
) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_130000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    dataset_root = tmp_path / "data" / "datasets"
    external_dir = dataset_root / "core_1h_spot" / "external"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    write_dataset(external_dir / "set_a" / "candles.csv")
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-001",
        run_id="run-001",
        config_name="run_a.json",
        dataset_root=dataset_root,
    )

    reused_summary = build_summary(
        tmp_path,
        config_name="run_a.json",
        run_id="run-001",
        selection=1.2,
        profit=0.03,
    )
    reused_summary = HistoricalRunSummary(
        **{**reused_summary.__dict__, "execution_status": "reused"}
    )

    result = run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[reused_summary],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        failures=[],
        seeds_planned=1,
        seeds_executed=0,
        seeds_reused=1,
    )

    assert result.champion_count == 1
    champions_csv = (
        multiseed_dir / DEBUG_DIRNAME / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv"
    ).read_text(encoding="utf-8")
    assert "run-001" in champions_csv


def test_run_post_multiseed_analysis_reports_not_run_when_catalog_scoped_datasets_are_missing(
    tmp_path: Path,
) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_140000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    dataset_root = tmp_path / "data" / "datasets"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-002",
        run_id="run-002",
        config_name="run_a.json",
        dataset_root=dataset_root,
    )

    result = run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-002",
                selection=1.2,
                profit=0.03,
            )
        ],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        failures=[],
        seeds_planned=1,
        seeds_executed=1,
        seeds_reused=0,
    )

    quick_summary = (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).read_text(encoding="utf-8")
    external_report = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "External: NOT_RUN" in quick_summary
    assert "Audit: NOT_RUN" in quick_summary
    assert "Final verdict: WEAK_PROMISING" in quick_summary
    assert "No automatic catalog-scoped external datasets were found" in external_report
    assert result.external_evaluation_status == "not_run"
    assert result.audit_evaluation_status == "not_run"


def test_run_post_multiseed_analysis_reports_mixed_catalog_scope(
    tmp_path: Path,
) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_150000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    dataset_root_a = tmp_path / "data" / "datasets_a"
    dataset_root_b = tmp_path / "data" / "datasets_b"

    summary_path.write_text("summary", encoding="utf-8")
    write_dataset(dataset_root_a / "core_1h_spot" / "external" / "set_a" / "candles.csv")
    write_dataset(dataset_root_b / "alt_1h_spot" / "external" / "set_b" / "candles.csv")
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-a",
        run_id="run-101",
        config_name="run_a.json",
        dataset_root=dataset_root_a,
    )
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-b",
        run_id="run-202",
        config_name="run_b.json",
        dataset_root=dataset_root_b,
    )

    store = PersistenceStore(persistence_db_path)
    store.initialize()
    with store.connect() as connection:
        connection.execute(
            "UPDATE run_executions SET dataset_catalog_id = ? WHERE run_id = ?",
            ("alt_1h_spot", "run-202"),
        )
        connection.execute(
            "UPDATE champions SET dataset_catalog_id = ? WHERE run_id = ?",
            ("alt_1h_spot", "run-202"),
        )

    run_post_multiseed_analysis(
        multiseed_dir=multiseed_dir,
        summary_path=summary_path,
        run_summaries=[
            build_summary(tmp_path, config_name="run_a.json", run_id="run-101", selection=1.2, profit=0.03),
            build_summary(tmp_path, config_name="run_b.json", run_id="run-202", selection=1.1, profit=0.02),
        ],
        dataset_root_label="data\\datasets",
        persistence_db_path=persistence_db_path,
        failures=[],
        seeds_planned=2,
        seeds_executed=2,
        seeds_reused=0,
    )

    external_report = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "catalog_scope_mode=mixed_catalogs" in external_report
    assert "dataset_root_scope_mode=mixed_roots" in external_report
    assert "run_id=run-101 -> catalog_id=core_1h_spot" in external_report
    assert "run_id=run-202 -> catalog_id=alt_1h_spot" in external_report


def test_run_post_multiseed_analysis_warns_when_default_dataset_root_fallback_is_used(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_160000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    persistence_db_path = tmp_path / "evolution_v2.db"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    external_dir = DEFAULT_DATASET_ROOT / "core_1h_spot" / "external"

    summary_path.write_text("summary", encoding="utf-8")
    write_dataset(external_dir / "set_a" / "candles.csv")
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-fallback",
        run_id="run-303",
        config_name="run_fallback.json",
        include_dataset_root_context=False,
    )

    try:
        run_post_multiseed_analysis(
            multiseed_dir=multiseed_dir,
            summary_path=summary_path,
            run_summaries=[
                build_summary(tmp_path, config_name="run_fallback.json", run_id="run-303", selection=1.0, profit=0.02)
            ],
            dataset_root_label="data\\datasets",
            persistence_db_path=persistence_db_path,
            failures=[],
            seeds_planned=1,
            seeds_executed=1,
            seeds_reused=0,
        )
    finally:
        if external_dir.exists():
            for path in sorted((DEFAULT_DATASET_ROOT / "core_1h_spot").rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink(missing_ok=True)
                else:
                    path.rmdir()
            catalog_root = DEFAULT_DATASET_ROOT / "core_1h_spot"
            if catalog_root.exists():
                catalog_root.rmdir()

    captured = capsys.readouterr()
    external_report = (
        multiseed_dir
        / DEBUG_DIRNAME
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "external_reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "fell back to data\\datasets" in captured.out
    assert "dataset_resolution_fallback_used=true" in external_report
    assert "missing_persisted_dataset_root_context" in external_report
