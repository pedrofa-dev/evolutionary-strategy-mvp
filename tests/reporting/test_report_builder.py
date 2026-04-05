import csv
import json
import sqlite3
from pathlib import Path

from evo_system.domain.genome import Genome
from evo_system.reporting.report_builder import analyze_champions, export_flat_csv
from evo_system.storage.persistence_store import PersistenceStore


def test_export_flat_csv_supports_rows_with_new_genome_weights(tmp_path) -> None:
    csv_path = tmp_path / "champions_flat.csv"
    rows = [
        {
            "id": 1,
            "config_name": "legacy",
            "weight_ret_short": 0.5,
        },
        {
            "id": 2,
            "config_name": "new",
            "weight_ret_short": 0.7,
            "weight_trend_strength": 0.2,
            "weight_realized_volatility": -0.1,
            "weight_trend_long": 0.3,
            "weight_breakout": -0.4,
        },
    ]

    export_flat_csv(rows, csv_path)

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        exported_rows = list(reader)

    assert "weight_trend_strength" in reader.fieldnames
    assert "weight_realized_volatility" in reader.fieldnames
    assert "weight_trend_long" in reader.fieldnames
    assert "weight_breakout" in reader.fieldnames
    assert exported_rows[0]["weight_trend_strength"] == ""
    assert exported_rows[0]["weight_realized_volatility"] == ""
    assert exported_rows[0]["weight_trend_long"] == ""
    assert exported_rows[0]["weight_breakout"] == ""
    assert exported_rows[1]["weight_trend_strength"] == "0.2"
    assert exported_rows[1]["weight_realized_volatility"] == "-0.1"
    assert exported_rows[1]["weight_trend_long"] == "0.3"
    assert exported_rows[1]["weight_breakout"] == "-0.4"


def seed_champion(
    database_path: Path,
    *,
    run_id: str,
    config_name: str,
    experimental_space_snapshot_json: dict | None = None,
) -> int:
    store = PersistenceStore(database_path)
    store.initialize()
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=f"multiseed-{run_id}",
        configs_dir_snapshot={"configs": [config_name]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
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
    }
    run_execution_id = store.save_run_execution(
        run_execution_uid=f"execution-{run_id}",
        multiseed_run_id=multiseed_run_id,
        run_id=run_id,
        config_name=config_name,
        config_json_snapshot=config_snapshot,
        effective_seed=42,
        dataset_catalog_id="core_1h_spot",
        dataset_signature=f"sig-{run_id}",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
    )
    return store.save_champion(
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
        dataset_signature=f"sig-{run_id}",
        train_metrics_json={"selection_score": 1.9, "median_profit": 0.03},
        validation_metrics_json={
            "selection_score": 1.7,
            "median_profit": 0.02,
            "median_drawdown": 0.01,
            "median_trades": 12,
            "dataset_scores": [1.7],
            "dataset_profits": [0.02],
            "dataset_drawdowns": [0.01],
            "is_valid": True,
            "violations": [],
            "dispersion": 0.0,
        },
        champion_metrics_json={
            "champion_type": "robust",
            "validation_selection": 1.7,
            "validation_profit": 0.02,
            "validation_drawdown": 0.01,
            "validation_trades": 12,
            "selection_gap": 0.2,
        },
        experimental_space_snapshot_json=experimental_space_snapshot_json,
    )


def test_analyze_champions_reads_from_new_store_and_persists_manual_analysis(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    output_dir = tmp_path / "analysis"
    champion_id = seed_champion(
        database_path,
        run_id="run-001",
        config_name="config_a.json",
    )

    result = analyze_champions(
        db_path=database_path,
        output_dir=output_dir,
        run_id="run-001",
    )

    assert result is not None
    assert result["champion_count"] == 1
    assert result["csv_path"].exists()
    assert result["report_path"].exists()
    assert result["champion_analysis_id"] is not None

    with sqlite3.connect(database_path) as connection:
        analysis_row = connection.execute(
            "SELECT analysis_type, champion_count FROM champion_analyses"
        ).fetchone()
        member_rows = connection.execute(
            "SELECT champion_id FROM champion_analysis_members"
        ).fetchall()

    assert analysis_row == ("manual_cross_run", 1)
    assert member_rows == [(champion_id,)]


def test_analyze_champions_supports_multiple_run_ids_and_champion_type(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    output_dir = tmp_path / "analysis"
    seed_champion(database_path, run_id="run-001", config_name="config_a.json")
    seed_champion(database_path, run_id="run-002", config_name="config_b.json")

    result = analyze_champions(
        db_path=database_path,
        output_dir=output_dir,
        run_ids=["run-001", "run-002"],
        champion_type="robust",
    )

    assert result is not None
    assert result["champion_count"] == 2


def test_analyze_champions_surfaces_modular_identity_and_legacy_fallback(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evolution_v2.db"
    output_dir = tmp_path / "analysis"
    seed_champion(
        database_path,
        run_id="run-001",
        config_name="config_a.json",
        experimental_space_snapshot_json={
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "modular_genome_v1",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "standard",
        },
    )
    seed_champion(
        database_path,
        run_id="run-002",
        config_name="config_b.json",
        experimental_space_snapshot_json=None,
    )

    result = analyze_champions(
        db_path=database_path,
        output_dir=output_dir,
        run_ids=["run-001", "run-002"],
        persist_analysis=False,
    )

    assert result is not None
    report_text = result["report_path"].read_text(encoding="utf-8")
    champion_card = result["champion_card"]
    csv_text = result["csv_path"].read_text(encoding="utf-8")

    assert "Modular identity summary" in report_text
    assert "modules=mixed_stacks | signal_pack=policy_v21_default" in report_text
    assert "signal_pack_name" in csv_text
    assert "modular_stack_label" in csv_text
    assert "primary_stack_label" in json.dumps(result["report_data"]["modular_identity_summary"])
    assert champion_card["modular_identity"]["stack_label"] in {
        "signal_pack=policy_v21_default | genome_schema=modular_genome_v1 | gene_catalog=modular_genome_v1_gene_catalog | decision_policy=policy_v2_default | mutation_profile=default_runtime_profile | market_mode=spot | leverage=1.0 | preset=standard",
        "unknown",
    }
