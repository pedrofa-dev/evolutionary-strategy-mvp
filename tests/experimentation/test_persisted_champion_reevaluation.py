import json
import sqlite3
from pathlib import Path

import pytest

from evo_system.domain.genome import Genome
from evo_system.experimentation.dataset_roots import DEFAULT_DATASET_ROOT
from evo_system.experimentation.persisted_champion_reevaluation import (
    build_reevaluation_rows,
    filter_champions,
    normalize_persisted_champion,
    reevaluate_persisted_champions,
    resolve_reevaluation_sources,
    resolve_evaluation_dataset_source,
)
from evo_system.storage.persistence_store import PersistenceStore


def write_dataset_csv(dataset_path: Path) -> None:
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


def build_config_snapshot() -> dict:
    return {
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


def seed_persistence_database(
    database_path: Path,
    *,
    run_id: str = "run-001",
    config_name: str = "config_a.json",
    champion_type: str = "robust",
    config_snapshot: dict | None = None,
) -> int:
    snapshot = config_snapshot or build_config_snapshot()
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
        runs_failed=0,
        champions_found=True,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )
    run_execution_id = store.save_run_execution(
        run_execution_uid=f"execution-{run_id}",
        multiseed_run_id=multiseed_run_id,
        run_id=run_id,
        config_name=config_name,
        config_json_snapshot=snapshot,
        effective_seed=42,
        dataset_catalog_id=snapshot["dataset_catalog_id"],
        dataset_signature=f"sig-{run_id}",
        dataset_context_json={
            "train_dataset_paths": ["core_1h_spot/train/window_a/candles.csv"],
            "validation_dataset_paths": ["core_1h_spot/validation/window_b/candles.csv"],
            "train_count": 1,
            "validation_count": 1,
        },
        status="completed",
    )
    return store.save_champion(
        champion_uid=f"champion-{run_id}",
        run_execution_id=run_execution_id,
        run_id=run_id,
        config_name=config_name,
        config_json_snapshot=snapshot,
        generation_number=5,
        mutation_seed=42,
        champion_type=champion_type,
        genome_json_snapshot=Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        ).to_dict(),
        dataset_catalog_id=snapshot["dataset_catalog_id"],
        dataset_signature=f"sig-{run_id}",
        train_metrics_json={
            "selection_score": 1.9,
            "median_profit": 0.03,
            "median_drawdown": 0.01,
            "median_trades": 10,
            "dataset_scores": [1.9],
            "dataset_profits": [0.03],
            "dataset_drawdowns": [0.01],
            "violations": [],
            "is_valid": True,
        },
        validation_metrics_json={
            "selection_score": 1.7,
            "median_profit": 0.02,
            "median_drawdown": 0.01,
            "median_trades": 12,
            "dispersion": 0.0,
            "dataset_scores": [1.7],
            "dataset_profits": [0.02],
            "dataset_drawdowns": [0.01],
            "violations": [],
            "is_valid": True,
        },
        champion_metrics_json={
            "champion_type": champion_type,
            "validation_selection": 1.7,
            "validation_profit": 0.02,
            "validation_drawdown": 0.01,
            "validation_trades": 12,
            "selection_gap": 0.2,
        },
    )


def test_filter_champions_supports_config_run_and_type_filters() -> None:
    champions = [
        {
            "id": 2,
            "run_id": "run-b",
            "config_name": "config_b.json",
            "champion_type": "specialist",
            "metrics": {"champion_type": "specialist"},
        },
        {
            "id": 1,
            "run_id": "run-a",
            "config_name": "config_a.json",
            "champion_type": "robust",
            "metrics": {"champion_type": "robust"},
        },
    ]

    filtered = filter_champions(
        champions,
        config_name="config_a.json",
        run_id="run-a",
        champion_type="robust",
    )

    assert [champion["id"] for champion in filtered] == [1]


def test_filter_champions_supports_multiple_run_ids() -> None:
    champions = [
        {"id": 1, "run_id": "run-a", "config_name": "config_a.json", "metrics": {}},
        {"id": 2, "run_id": "run-b", "config_name": "config_b.json", "metrics": {}},
        {"id": 3, "run_id": "run-c", "config_name": "config_c.json", "metrics": {}},
    ]

    filtered = filter_champions(champions, run_ids=["run-a", "run-c"])

    assert [champion["id"] for champion in filtered] == [1, 3]


def test_reevaluate_persisted_champions_exports_direct_external_and_audit_outputs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution_v2.db"
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"
    output_dir = tmp_path / "out"

    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    write_dataset_csv(audit_dir / "set_b" / "candles.csv")
    champion_id = seed_persistence_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        dataset_root=tmp_path,
        config_name="config_a.json",
        external_validation_dir=external_dir,
        audit_dir=audit_dir,
        output_dir=output_dir,
    )

    assert result["matched_count"] == 1
    assert result["external_evaluations_run"] == 1
    assert result["audit_evaluations_run"] == 1
    assert result["csv_path"].exists()
    assert result["json_path"].exists()
    assert result["report_path"].exists()
    assert result["external_champion_evaluation_id"] is not None
    assert result["audit_champion_evaluation_id"] is not None

    row = result["rows"][0]
    assert row["champion_id"] == champion_id
    assert row["external_source_type"] == "directory"
    assert row["external_dataset_catalog_id"] is None
    assert row["external_dataset_count"] == 1
    assert row["audit_source_type"] == "directory"
    assert row["audit_dataset_count"] == 1
    assert row["external_validation_selection"] is not None
    assert row["audit_selection"] is not None

    with sqlite3.connect(database_path) as connection:
        evaluation_rows = connection.execute(
            """
            SELECT evaluation_type, evaluation_origin
            FROM champion_evaluations
            ORDER BY evaluation_type ASC
            """
        ).fetchall()
        member_count = connection.execute(
            "SELECT COUNT(*) FROM champion_evaluation_members"
        ).fetchone()[0]

    assert evaluation_rows == [
        ("audit", "manual"),
        ("external", "manual"),
    ]
    assert member_count == 2


def test_reevaluate_persisted_champions_supports_manifest_external(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution_v2.db"
    dataset_root = tmp_path / "data" / "datasets"
    output_dir = tmp_path / "out"

    write_dataset_csv(
        dataset_root / "ext_catalog" / "external" / "window_a" / "candles.csv"
    )
    seed_persistence_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        dataset_root=dataset_root,
        config_name="config_a.json",
        external_dataset_catalog_id="ext_catalog",
        output_dir=output_dir,
    )

    row = result["rows"][0]
    assert row["external_source_type"] == "catalog"
    assert row["external_dataset_catalog_id"] == "ext_catalog"
    assert row["external_dataset_count"] == 1
    assert str(row["external_dataset_root"]).endswith("data\\datasets")
    assert row["external_dataset_set_name"] == "ext_catalog"
    assert row["external_evaluation_type"] == "external"
    assert row["external_validation_selection"] is not None


def test_reevaluate_persisted_champions_supports_different_manifest_catalogs_for_external_and_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution_v2.db"
    dataset_root = tmp_path / "datasets"
    output_dir = tmp_path / "out"

    write_dataset_csv(
        dataset_root / "external_catalog" / "external" / "window_a" / "candles.csv"
    )
    write_dataset_csv(
        dataset_root / "audit_catalog" / "audit" / "window_b" / "candles.csv"
    )
    seed_persistence_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        dataset_root=dataset_root,
        config_name="config_a.json",
        external_dataset_catalog_id="external_catalog",
        audit_dataset_catalog_id="audit_catalog",
        output_dir=output_dir,
    )

    row = result["rows"][0]
    assert row["external_dataset_catalog_id"] == "external_catalog"
    assert row["audit_dataset_catalog_id"] == "audit_catalog"
    assert row["external_validation_selection"] is not None
    assert row["audit_selection"] is not None


def test_reevaluate_persisted_champions_errors_when_no_directories_or_catalogs_are_provided(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution_v2.db"
    seed_persistence_database(database_path)

    with pytest.raises(
        ValueError,
        match="No datasets available for reevaluation",
    ):
        reevaluate_persisted_champions(
            db_path=database_path,
            config_name="config_a.json",
        )


def test_build_reevaluation_rows_prefers_persisted_config_snapshot(
    tmp_path: Path,
) -> None:
    external_dir = tmp_path / "external_validation"
    write_dataset_csv(external_dir / "set_a" / "candles.csv")

    champion = normalize_persisted_champion(
        {
            "id": 1,
            "run_id": "run-001",
            "generation_number": 5,
            "mutation_seed": 42,
            "config_name": "config_a.json",
            "genome_json_snapshot": Genome(
                threshold_open=0.01,
                threshold_close=0.0,
                position_size=0.1,
                stop_loss=0.5,
                take_profit=1.0,
            ).to_dict(),
            "config_json_snapshot": build_config_snapshot(),
            "champion_type": "robust",
            "dataset_catalog_id": "core_1h_spot",
            "dataset_signature": "sig-001",
            "train_metrics_json": {},
            "validation_metrics_json": {},
            "champion_metrics_json": {
                "champion_type": "robust",
                "validation_selection": 1.7,
                "validation_profit": 0.02,
                "validation_drawdown": 0.01,
                "validation_trades": 12,
                "selection_gap": 0.2,
            },
            "persisted_at": "2026-03-31T10:00:00Z",
        }
    )

    rows, external_count, audit_count, skipped = build_reevaluation_rows(
        champions=[champion],
        external_validation_dir=external_dir,
    )

    assert len(rows) == 1
    assert external_count == 1
    assert audit_count == 0
    assert skipped == []
    assert rows[0]["external_source_type"] == "directory"


def test_build_reevaluation_rows_reports_skipped_champions_when_config_snapshot_is_missing(
    tmp_path: Path,
) -> None:
    external_dir = tmp_path / "external_validation"
    write_dataset_csv(external_dir / "set_a" / "candles.csv")

    champions = [
        {
            "id": 1,
            "run_id": "run-001",
            "generation_number": 5,
            "mutation_seed": 42,
            "config_name": "config_a.json",
            "genome": Genome(
                threshold_open=0.01,
                threshold_close=0.0,
                position_size=0.1,
                stop_loss=0.5,
                take_profit=1.0,
            ).to_dict(),
            "metrics": {
                "champion_type": "robust",
                "validation_selection": 1.7,
                "validation_profit": 0.02,
                "validation_drawdown": 0.01,
                "validation_trades": 12,
                "selection_gap": 0.2,
            },
            "config_snapshot": {},
        }
    ]

    rows, external_count, audit_count, skipped = build_reevaluation_rows(
        champions=champions,
        external_validation_dir=external_dir,
    )

    assert len(rows) == 0
    assert external_count == 0
    assert audit_count == 0
    assert skipped == [
        {
            "champion_id": 1,
            "run_id": "run-001",
            "config_name": "config_a.json",
            "reason": "Config snapshot not available for persisted champion.",
        }
    ]


def test_reevaluate_persisted_champions_supports_cross_run_filtering_without_config_file(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution_v2.db"
    external_dir = tmp_path / "external_validation"
    output_dir = tmp_path / "out"

    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    seed_persistence_database(database_path, run_id="run-001", config_name="config_a.json")
    seed_persistence_database(database_path, run_id="run-002", config_name="config_b.json")

    result = reevaluate_persisted_champions(
        db_path=database_path,
        run_ids=["run-001", "run-002"],
        external_validation_dir=external_dir,
        output_dir=output_dir,
    )

    assert result["matched_count"] == 2
    assert {row["run_id"] for row in result["rows"]} == {"run-001", "run-002"}


def test_resolve_reevaluation_sources_provides_report_context_without_rows(
    tmp_path: Path,
) -> None:
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"
    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    write_dataset_csv(audit_dir / "set_b" / "candles.csv")

    external_source, audit_source = resolve_reevaluation_sources(
        dataset_root=tmp_path,
        external_validation_dir=external_dir,
        external_dataset_catalog_id=None,
        audit_dir=audit_dir,
        audit_dataset_catalog_id=None,
        fail_on_missing_datasets=False,
    )

    assert external_source["source_type"] == "directory"
    assert external_source["dataset_root"] == external_dir
    assert audit_source["source_type"] == "directory"
    assert audit_source["dataset_root"] == audit_dir


def test_resolve_evaluation_dataset_source_uses_main_flow_manifest_root_resolution() -> None:
    source = resolve_evaluation_dataset_source(
        dataset_dir=None,
        dataset_root=None,
        dataset_catalog_id="ext_catalog",
        dataset_layer="external",
        fail_on_missing_datasets=False,
    )

    assert source["source_type"] == "catalog"
    assert source["dataset_catalog_id"] == "ext_catalog"
    assert source["dataset_root"] == DEFAULT_DATASET_ROOT
