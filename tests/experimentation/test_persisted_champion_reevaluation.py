import json
from pathlib import Path

import pytest

from evo_system.domain.genome import Genome
from evo_system.experimentation.dataset_roots import DEFAULT_MANIFEST_DATASET_ROOT
from evo_system.experimentation.persisted_champion_reevaluation import (
    build_reevaluation_rows,
    filter_champions,
    reevaluate_persisted_champions,
    resolve_reevaluation_sources,
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
    assert str(row["external_dataset_root"]).endswith("data\\datasets")
    assert row["external_dataset_set_name"] == "ext_catalog"
    assert row["external_evaluation_type"] == "external"
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


def test_reevaluate_persisted_champions_rejects_multi_run_without_config_mapping(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    external_dir = tmp_path / "external_validation"

    write_run_config(config_path)
    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    seed_database(database_path)

    with pytest.raises(
        ValueError,
        match="run_ids requires config_paths_by_run_id",
    ):
        reevaluate_persisted_champions(
            db_path=database_path,
            config_path=config_path,
            run_ids=["run-001"],
            external_validation_dir=external_dir,
        )


def test_build_reevaluation_rows_uses_run_id_mapping_over_config_name(
    tmp_path: Path,
) -> None:
    config_path_a = tmp_path / "config_a.json"
    config_path_b = tmp_path / "config_b.json"
    external_dir = tmp_path / "external_validation"
    write_run_config(config_path_a)
    write_run_config(config_path_b)
    write_dataset_csv(external_dir / "set_a" / "candles.csv")

    champions = [
        {
            "id": 1,
            "run_id": "run-001",
            "generation_number": 5,
            "mutation_seed": 42,
            "config_name": "shared.json",
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
        }
    ]

    rows, external_count, audit_count, skipped = build_reevaluation_rows(
        champions=champions,
        config_paths_by_run_id={"run-001": config_path_a},
        config_paths_by_name={"shared.json": config_path_b},
        external_validation_dir=external_dir,
    )

    assert len(rows) == 1
    assert external_count == 1
    assert audit_count == 0
    assert skipped == []
    assert rows[0]["external_source_type"] == "directory"


def test_build_reevaluation_rows_reports_skipped_champions_when_config_is_missing(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config_a.json"
    external_dir = tmp_path / "external_validation"
    write_run_config(config_path)
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
        },
        {
            "id": 2,
            "run_id": "run-002",
            "generation_number": 6,
            "mutation_seed": 43,
            "config_name": "config_b.json",
            "genome": Genome(
                threshold_open=0.01,
                threshold_close=0.0,
                position_size=0.1,
                stop_loss=0.5,
                take_profit=1.0,
            ).to_dict(),
            "metrics": {
                "champion_type": "robust",
                "validation_selection": 1.8,
                "validation_profit": 0.03,
                "validation_drawdown": 0.01,
                "validation_trades": 10,
                "selection_gap": 0.1,
            },
        },
    ]

    rows, external_count, audit_count, skipped = build_reevaluation_rows(
        champions=champions,
        config_paths_by_run_id={"run-001": config_path},
        external_validation_dir=external_dir,
    )

    assert len(rows) == 1
    assert external_count == 1
    assert audit_count == 0
    assert skipped == [
        {
            "champion_id": 2,
            "run_id": "run-002",
            "config_name": "config_b.json",
            "reason": "Config path not available for persisted champion.",
        }
    ]


def test_reevaluate_persisted_champions_supports_multi_run_without_single_config_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    external_dir = tmp_path / "external_validation"

    write_run_config(config_path)
    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    seed_database(database_path)

    result = reevaluate_persisted_champions(
        db_path=database_path,
        config_path=None,
        config_paths_by_run_id={"run-001": config_path},
        run_ids=["run-001"],
        external_validation_dir=external_dir,
        output_dir=tmp_path / "out",
    )

    assert result["matched_count"] == 1
    assert result["rows"][0]["external_source_type"] == "directory"


def test_reevaluate_persisted_champions_reports_skipped_champions_in_report(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_evolution.db"
    config_path = tmp_path / "run_config.json"
    external_dir = tmp_path / "external_validation"
    output_dir = tmp_path / "out"

    write_run_config(config_path)
    write_dataset_csv(external_dir / "set_a" / "candles.csv")
    seed_database(database_path)

    store = SQLiteStore(str(database_path))
    store.save_champion(
        run_id="run-002",
        generation_number=6,
        mutation_seed=43,
        config_name="config_b.json",
        genome=Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        ),
        metrics={"champion_type": "robust"},
    )

    result = reevaluate_persisted_champions(
        db_path=database_path,
        config_path=None,
        config_paths_by_run_id={"run-001": config_path},
        run_ids=["run-001", "run-002"],
        external_validation_dir=external_dir,
        output_dir=output_dir,
    )

    report_text = result["report_path"].read_text(encoding="utf-8")
    assert result["matched_count"] == 1
    assert "Champions matched for reevaluation: 2" in report_text
    assert "Rows generated: 1" in report_text
    assert "Skipped champions" in report_text
    assert "run_id=run-002" in report_text
    assert "Config path not available for persisted champion." in report_text


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
        external_dataset_mode=None,
        external_dataset_catalog_id=None,
        audit_dir=audit_dir,
        audit_dataset_mode=None,
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
        dataset_mode="manifest",
        dataset_catalog_id="ext_catalog",
        dataset_layer="external",
        fail_on_missing_datasets=False,
    )

    assert source["source_type"] == "catalog"
    assert source["dataset_mode"] == "manifest"
    assert source["dataset_catalog_id"] == "ext_catalog"
    assert source["dataset_root"] == DEFAULT_MANIFEST_DATASET_ROOT
