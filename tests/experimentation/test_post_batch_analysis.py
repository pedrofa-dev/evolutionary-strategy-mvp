import json
from pathlib import Path

from evo_system.domain.genome import Genome
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.post_batch_analysis import (
    BATCH_CHAMPIONS_SUMMARY_NAME,
    BATCH_QUICK_SUMMARY_NAME,
    BATCH_RUN_SUMMARY_NAME,
    CHAMPIONS_ANALYSIS_DIRNAME,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_BATCH_VALIDATION_DIRNAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
    run_post_batch_analysis,
    run_post_multiseed_analysis,
)
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


def test_run_post_batch_analysis_generates_expected_artifacts(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_20260330_120000"
    batch_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"

    write_config(config_path)
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
    write_dataset(external_dir / "set_a" / "candles.csv")
    write_dataset(audit_dir / "set_b" / "candles.csv")

    result = run_post_batch_analysis(
        batch_dir=batch_dir,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        config_paths=[config_path],
        dataset_root_label="data\\processed",
        db_path=db_path,
        external_validation_dir=external_dir,
        audit_dir=audit_dir,
        failures=[],
    )

    assert result.batch_summary_path == batch_dir / BATCH_RUN_SUMMARY_NAME
    assert result.quick_summary_path == batch_dir / BATCH_QUICK_SUMMARY_NAME
    assert result.champions_summary_path == batch_dir / BATCH_CHAMPIONS_SUMMARY_NAME
    assert (batch_dir / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv").exists()
    assert (
        batch_dir / POST_BATCH_VALIDATION_DIRNAME / "external" / "reevaluated_champions.csv"
    ).exists()
    assert (
        batch_dir / POST_BATCH_VALIDATION_DIRNAME / "audit" / "reevaluated_champions.csv"
    ).exists()
    assert (
        batch_dir
        / POST_BATCH_VALIDATION_DIRNAME
        / "external"
        / "champions"
        / "champion_1.json"
    ).exists()
    quick_summary = (batch_dir / BATCH_QUICK_SUMMARY_NAME).read_text(encoding="utf-8")
    external_json = (
        batch_dir / POST_BATCH_VALIDATION_DIRNAME / "external" / "reevaluated_champions.json"
    ).read_text(encoding="utf-8")
    assert "Runs planned: 1" in quick_summary
    assert "Runs completed: 1" in quick_summary
    assert "Runs failed: 0" in quick_summary
    assert '"external_dataset_root"' in external_json
    assert '"external_evaluation_type": "external"' in external_json


def test_run_post_batch_analysis_filters_only_batch_run_ids(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_20260330_120000"
    batch_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"

    write_config(config_path)
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
    seed_champion(db_path, run_id="run-999", config_name="run_a.json")

    run_post_batch_analysis(
        batch_dir=batch_dir,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        config_paths=[config_path],
        dataset_root_label="data\\processed",
        db_path=db_path,
        external_validation_dir=tmp_path / "missing_external",
        audit_dir=tmp_path / "missing_audit",
        failures=[],
    )

    champions_csv = (
        batch_dir / CHAMPIONS_ANALYSIS_DIRNAME / "champions_flat.csv"
    ).read_text(encoding="utf-8")
    assert "run-001" in champions_csv
    assert "run-999" not in champions_csv


def test_run_post_batch_analysis_handles_no_champions_and_missing_datasets(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_20260330_120000"
    batch_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"
    write_config(config_path)

    run_post_batch_analysis(
        batch_dir=batch_dir,
        run_summaries=[
            build_summary(
                tmp_path,
                config_name="run_a.json",
                run_id="run-001",
                selection=1.2,
                profit=0.03,
            )
        ],
        config_paths=[config_path],
        dataset_root_label="data\\processed",
        db_path=db_path,
        external_validation_dir=tmp_path / "missing_external",
        audit_dir=tmp_path / "missing_audit",
        failures=["run_b.json: boom"],
    )

    quick_summary = (batch_dir / BATCH_QUICK_SUMMARY_NAME).read_text(encoding="utf-8")
    champions_summary = (
        batch_dir / BATCH_CHAMPIONS_SUMMARY_NAME
    ).read_text(encoding="utf-8")
    external_report = (
        batch_dir / POST_BATCH_VALIDATION_DIRNAME / "external" / "reevaluation_report.txt"
    ).read_text(encoding="utf-8")

    assert "run_b.json: boom" in quick_summary
    assert "Runs planned: 1" in quick_summary
    assert "Runs completed: 1" in quick_summary
    assert "Runs failed: 1" in quick_summary
    assert "No persisted champions were produced by this batch." in champions_summary
    assert "No persisted champions were found for this batch." in external_report


def test_run_post_multiseed_analysis_generates_expected_artifacts(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
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
        dataset_root_label="data\\processed",
        db_path=db_path,
        external_validation_dir=external_dir,
        audit_dir=audit_dir,
        failures=[],
        seeds_planned=1,
    )

    assert result.batch_summary_path == summary_path
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


def test_run_post_multiseed_analysis_handles_no_champions_and_missing_datasets(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"
    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")

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
        dataset_root_label="data\\processed",
        db_path=db_path,
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
    assert "No persisted champions were found for this multiseed." in external_report


def test_run_post_multiseed_analysis_filters_only_multiseed_run_ids(tmp_path: Path) -> None:
    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "evolution.db"
    config_path = tmp_path / "run_a.json"
    summary_path = multiseed_dir / "multiseed_run_summary.txt"

    write_config(config_path)
    summary_path.write_text("summary", encoding="utf-8")
    seed_champion(db_path, run_id="run-001", config_name="run_a.json")
    seed_champion(db_path, run_id="run-999", config_name="run_a.json")

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
        dataset_root_label="data\\processed",
        db_path=db_path,
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
