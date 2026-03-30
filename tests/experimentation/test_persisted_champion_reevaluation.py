import json
from pathlib import Path

import pytest

from evo_system.domain.genome import Genome
from evo_system.experimentation.dataset_roots import DEFAULT_MANIFEST_DATASET_ROOT
from evo_system.experimentation.persisted_champion_reevaluation import (
    filter_champions,
    reevaluate_persisted_champions,
    resolve_evaluation_dataset_source,
)
from evo_system.storage.sqlite_store import SQLiteStore


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


def write_run_config(config_path: Path) -> None:
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


def seed_database(database_path: Path) -> None:
    store = SQLiteStore(str(database_path))
    store.initialize()
    store.save_champion(
        run_id="run-001",
        generation_number=5,
        mutation_seed=42,
        config_name="config_a.json",
        genome=Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        ),
        metrics={
            "champion_type": "robust",
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
            "metrics": {"champion_type": "specialist"},
        },
        {
            "id": 1,
            "run_id": "run-a",
            "config_name": "config_a.json",
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


def test_reevaluate_persisted_champions_exports_direct_external_and_audit_outputs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    external_dir = tmp_path / "external_validation"
    audit_dir = tmp_path / "audit"
    output_dir = tmp_path / "out"

    write_run_config(config_path)
    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    write_dataset_csv(audit_dir / "set_b" / "candles.csv")
    seed_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        config_path=config_path,
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

    row = result["rows"][0]
    assert row["external_source_type"] == "directory"
    assert row["external_dataset_mode"] is None
    assert row["external_dataset_catalog_id"] is None
    assert row["external_dataset_count"] == 1
    assert row["audit_source_type"] == "directory"
    assert row["audit_dataset_count"] == 1
    assert row["external_validation_selection"] is not None
    assert row["audit_selection"] is not None


def test_reevaluate_persisted_champions_supports_manifest_external(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    dataset_root = tmp_path / "data" / "datasets"
    output_dir = tmp_path / "out"

    write_run_config(config_path)
    write_dataset_csv(
        dataset_root / "ext_catalog" / "external" / "window_a" / "candles.csv"
    )
    seed_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        config_path=config_path,
        dataset_root=dataset_root,
        config_name="config_a.json",
        external_dataset_catalog_id="ext_catalog",
        output_dir=output_dir,
    )

    row = result["rows"][0]
    assert row["external_source_type"] == "catalog"
    assert row["external_dataset_mode"] == "manifest"
    assert row["external_dataset_catalog_id"] == "ext_catalog"
    assert row["external_dataset_count"] == 1
    assert row["external_validation_selection"] is not None


def test_reevaluate_persisted_champions_supports_different_manifest_catalogs_for_external_and_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    dataset_root = tmp_path / "datasets"
    output_dir = tmp_path / "out"

    write_run_config(config_path)
    write_dataset_csv(
        dataset_root / "external_catalog" / "external" / "window_a" / "candles.csv"
    )
    write_dataset_csv(
        dataset_root / "audit_catalog" / "audit" / "window_b" / "candles.csv"
    )
    seed_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        config_path=config_path,
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
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"

    write_run_config(config_path)
    seed_database(database_path)

    with pytest.raises(
        ValueError,
        match="No datasets available for reevaluation",
    ):
        reevaluate_persisted_champions(
            db_path=database_path,
            config_path=config_path,
            config_name="config_a.json",
        )


def test_resolve_evaluation_dataset_source_uses_main_flow_manifest_root_resolution() -> None:
    source = resolve_evaluation_dataset_source(
        dataset_dir=None,
        dataset_root=None,
        dataset_mode="manifest",
        dataset_catalog_id="ext_catalog",
        dataset_layer="external",
        fail_on_missing_datasets=False,
    )

    assert source["source_type"] == "catalog"
    assert source["dataset_mode"] == "manifest"
    assert source["dataset_catalog_id"] == "ext_catalog"
    assert source["dataset_root"] == DEFAULT_MANIFEST_DATASET_ROOT
