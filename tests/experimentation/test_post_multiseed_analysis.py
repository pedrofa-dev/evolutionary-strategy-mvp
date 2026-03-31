import json
import sqlite3
from pathlib import Path

from evo_system.domain.genome import Genome
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.post_multiseed_analysis import (
    CHAMPIONS_ANALYSIS_DIRNAME,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
    run_post_multiseed_analysis,
)
from evo_system.storage.persistence_store import PersistenceStore
from evo_system.storage.sqlite_store import SQLiteStore


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


def seed_champion(
    database_path: Path,
    *,
    run_id: str,
    config_name: str,
    champion_type: str = "robust",
) -> None:
    store = SQLiteStore(str(database_path))
    store.initialize()
    store.save_champion(
        run_id=run_id,
        generation_number=5,
        mutation_seed=42,
        config_name=config_name,
        genome=Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        ),
        metrics={
            "champion_type": champion_type,
            "validation_selection": 1.5,
            "validation_profit": 0.02,
            "validation_drawdown": 0.01,
            "validation_trades": 12,
            "selection_gap": 0.2,
        },
    )


def seed_new_persistence_context(
    database_path: Path,
    *,
    multiseed_run_uid: str,
    run_id: str,
    config_name: str,
) -> int:
    store = PersistenceStore(database_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=multiseed_run_uid,
        configs_dir_snapshot={"configs": [config_name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
        runs_planned=1,
        runs_completed=1,
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
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
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
    db_path = tmp_path / "evolution.db"
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
    multiseed_run_id = seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid=multiseed_dir.name,
        run_id="run-001",
        config_name="run_a.json",
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
        db_path=db_path,
        persistence_db_path=persistence_db_path,
        multiseed_run_id=multiseed_run_id,
        external_validation_dir=external_dir,
        audit_dir=audit_dir,
        failures=[],
        seeds_planned=1,
    )

    assert result.summary_path == summary_path
    assert result.quick_summary_path == multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    assert result.champions_summary_path == multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
    assert (multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv").exists()
    assert (
        multiseed_dir
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "reevaluated_champions.csv"
    ).exists()
    assert (
        multiseed_dir
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "audit"
        / "reevaluated_champions.csv"
    ).exists()
    assert (
        multiseed_dir
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
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "reevaluated_champions.json"
    ).read_text(encoding="utf-8")
    assert "Seeds planned: 1" in quick_summary
    assert "Seeds completed: 1" in quick_summary
    assert "Seeds failed: 0" in quick_summary
    assert '"external_dataset_root"' in external_json
    assert '"external_evaluation_type": "external"' in external_json
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
    db_path = tmp_path / "evolution.db"
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
        db_path=db_path,
        persistence_db_path=persistence_db_path,
        multiseed_run_id=multiseed_run_id,
        external_validation_dir=tmp_path / "missing_external",
        audit_dir=tmp_path / "missing_audit",
        failures=["seed 102: boom"],
        seeds_planned=2,
    )

    quick_summary = (
        multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    champions_summary = (
        multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    external_report = (
        multiseed_dir
        / POST_MULTISEED_VALIDATION_DIRNAME
        / "external"
        / "reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "seed 102: boom" in quick_summary
    assert "Seeds planned: 2" in quick_summary
    assert "Seeds completed: 1" in quick_summary
    assert "Seeds failed: 1" in quick_summary
    assert "No persisted champions were produced by this multiseed execution." in champions_summary
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
    db_path = tmp_path / "evolution.db"
    persistence_db_path = tmp_path / "evolution_v2.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
    seed_champion(db_path, run_id="run-999", config_name="run_a.json")
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-001",
        run_id="run-001",
        config_name="run_a.json",
    )
    seed_new_persistence_context(
        persistence_db_path,
        multiseed_run_uid="multiseed-run-999",
        run_id="run-999",
        config_name="run_a.json",
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
        db_path=db_path,
        persistence_db_path=persistence_db_path,
        external_validation_dir=tmp_path / "missing_external",
        audit_dir=tmp_path / "missing_audit",
        failures=[],
        seeds_planned=1,
    )

    champions_csv = (
        multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv"
    ).read_text(encoding="utf-8")
    assert "run-001" in champions_csv
    assert "run-999" not in champions_csv
