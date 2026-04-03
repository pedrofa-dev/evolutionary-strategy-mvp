import sqlite3
from pathlib import Path

from evo_system.storage.persistence_store import (
    CURRENT_LOGIC_VERSION,
    PersistenceStore,
    build_execution_fingerprint,
    hash_config_snapshot,
    hash_genome_snapshot,
    utc_now_iso,
)


def build_config_snapshot(seed: int = 101) -> dict:
    return {
        "population_size": 18,
        "target_population_size": 18,
        "survivors_count": 4,
        "generations_planned": 40,
        "mutation_seed": seed,
        "dataset_catalog_id": "core_1h_spot",
    }


def build_genome_snapshot() -> dict:
    return {
        "threshold_open": 0.4,
        "threshold_close": 0.1,
        "position_size": 0.2,
        "stop_loss": 0.03,
        "take_profit": 0.08,
    }


def test_initialize_creates_redesigned_tables_and_indexes(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    with sqlite3.connect(database_path) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()
        index_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
            ORDER BY name
            """
        ).fetchall()

    table_names = {row[0] for row in table_rows}
    index_names = {row[0] for row in index_rows}

    assert {
        "multiseed_runs",
        "run_executions",
        "champions",
        "champion_analyses",
        "champion_analysis_members",
        "champion_evaluations",
        "champion_evaluation_members",
    }.issubset(table_names)

    assert "idx_run_executions_execution_fingerprint" in index_names
    assert "idx_run_executions_run_id" in index_names
    assert "idx_run_executions_config_hash" in index_names
    assert "idx_run_executions_logic_version" in index_names
    assert "idx_champions_run_execution_id" in index_names
    assert "idx_champions_run_id" in index_names
    assert "idx_champions_champion_type" in index_names
    assert "idx_champions_config_hash" in index_names
    assert "idx_champions_logic_version" in index_names
    assert "idx_champion_analyses_multiseed_run_id" in index_names
    assert "idx_champion_evaluations_multiseed_run_id" in index_names


def test_save_multiseed_run_stores_no_champion_status_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed-001",
        configs_dir_snapshot={"configs": ["a.json", "b.json"]},
        requested_parallel_workers=4,
        effective_parallel_workers=2,
        dataset_root="data/datasets",
        runs_planned=12,
        runs_completed=10,
        runs_reused=3,
        runs_failed=2,
        champions_found=False,
        champion_analysis_status="skipped_no_champions",
        external_evaluation_status="skipped_no_champions",
        audit_evaluation_status="skipped_no_champions",
        status="completed_with_failures",
        artifacts_root_path="artifacts/multiseed/multiseed_001",
    )

    assert multiseed_run_id == 1

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT champions_found, champion_analysis_status, external_evaluation_status, audit_evaluation_status
            FROM multiseed_runs
            WHERE id = ?
            """,
            (multiseed_run_id,),
        ).fetchone()

    assert row == (0, "skipped_no_champions", "skipped_no_champions", "skipped_no_champions")


def test_save_run_execution_and_find_by_fingerprint(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed-001",
        configs_dir_snapshot={"configs": ["a.json"]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
        runs_planned=1,
        runs_completed=0,
        runs_reused=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
    )

    config_snapshot = build_config_snapshot(seed=101)
    execution_id = store.save_run_execution(
        run_execution_uid="execution-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-001",
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={
            "resolved_train_paths": ["data/datasets/core_1h_spot/train/set_a/candles.csv"],
            "resolved_validation_paths": ["data/datasets/core_1h_spot/validation/set_b/candles.csv"],
            "train_count": 1,
            "validation_count": 1,
        },
        status="completed",
        experimental_space_snapshot_json={
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "experiment_preset_name": "standard",
        },
        resolved_dataset_root="data/datasets",
        log_artifact_path="artifacts/multiseed/multiseed_001/run_a_seed101.txt",
    )

    assert execution_id == 1

    fingerprint = build_execution_fingerprint(
        config_hash=hash_config_snapshot(config_snapshot),
        effective_seed=101,
        dataset_signature="sig-001",
        logic_version=CURRENT_LOGIC_VERSION,
    )
    loaded = store.find_run_execution_by_fingerprint(fingerprint)

    assert loaded is not None
    assert loaded["run_id"] == "run-001"
    assert loaded["config_json_snapshot"]["dataset_catalog_id"] == "core_1h_spot"
    assert loaded["dataset_context_json"]["train_count"] == 1
    assert loaded["experimental_space_snapshot_json"]["signal_pack_name"] == "policy_v21_default"
    assert loaded["resolved_dataset_root"] == "data/datasets"


def test_save_champion_persists_snapshots_and_hashes(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed-001",
        configs_dir_snapshot={"configs": ["a.json"]},
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
    config_snapshot = build_config_snapshot(seed=101)
    run_execution_id = store.save_run_execution(
        run_execution_uid="execution-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-001",
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
    )

    genome_snapshot = build_genome_snapshot()
    champion_id = store.save_champion(
        champion_uid="champion-001",
        run_execution_id=run_execution_id,
        run_id="run-001",
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        generation_number=17,
        mutation_seed=101,
        champion_type="robust",
        genome_json_snapshot=genome_snapshot,
        experimental_space_snapshot_json={
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "policy_v2_default",
            "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {},
            "experiment_preset_name": "standard",
        },
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        train_metrics_json={"selection": 12.3},
        validation_metrics_json={"selection": 9.8},
        champion_metrics_json={"selection_gap": 2.5},
        champion_card_artifact_path="artifacts/analysis/card.json",
    )

    assert champion_id == 1

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                config_hash,
                genome_hash,
                config_json_snapshot,
                genome_json_snapshot,
                experimental_space_snapshot_json,
                champion_metrics_json,
                champion_card_artifact_path
            FROM champions
            WHERE id = ?
            """,
            (champion_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == hash_config_snapshot(config_snapshot)
    assert row[1] == hash_genome_snapshot(genome_snapshot)
    assert '"dataset_catalog_id":"core_1h_spot"' in row[2]
    assert '"threshold_open":0.4' in row[3]
    assert '"signal_pack_name":"policy_v21_default"' in row[4]
    assert '"selection_gap":2.5' in row[5]
    assert row[6] == "artifacts/analysis/card.json"

    loaded_champion = store.load_champions(run_ids=["run-001"])[0]
    assert loaded_champion["experimental_space_snapshot_json"]["decision_policy_name"] == (
        "policy_v2_default"
    )


def test_save_analysis_and_evaluation_memberships(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid="multiseed-001",
        configs_dir_snapshot={"configs": ["a.json"]},
        requested_parallel_workers=1,
        effective_parallel_workers=1,
        dataset_root="data/datasets",
        runs_planned=1,
        runs_completed=1,
        runs_reused=0,
        runs_failed=0,
        champions_found=True,
        champion_analysis_status="completed",
        external_evaluation_status="completed",
        audit_evaluation_status="completed",
    )
    config_snapshot = build_config_snapshot(seed=101)
    run_execution_id = store.save_run_execution(
        run_execution_uid="execution-001",
        multiseed_run_id=multiseed_run_id,
        run_id="run-001",
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        effective_seed=101,
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        dataset_context_json={"train_count": 1, "validation_count": 1},
        status="completed",
    )
    champion_id = store.save_champion(
        champion_uid="champion-001",
        run_execution_id=run_execution_id,
        run_id="run-001",
        config_name="run_a.json",
        config_json_snapshot=config_snapshot,
        generation_number=17,
        mutation_seed=101,
        champion_type="robust",
        genome_json_snapshot=build_genome_snapshot(),
        dataset_catalog_id="core_1h_spot",
        dataset_signature="sig-001",
        train_metrics_json={"selection": 12.3},
        validation_metrics_json={"selection": 9.8},
    )

    analysis_id = store.save_champion_analysis(
        champion_analysis_uid="analysis-001",
        multiseed_run_id=multiseed_run_id,
        analysis_type="automatic_post_multiseed",
        champion_count=1,
        selection_scope_json={"run_ids": ["run-001"]},
        analysis_summary_json={"champion_count": 1},
        flat_csv_artifact_path="artifacts/multiseed/run/champions.csv",
    )
    store.add_champion_analysis_members(analysis_id, [champion_id])

    evaluation_id = store.save_champion_evaluation(
        champion_evaluation_uid="evaluation-001",
        multiseed_run_id=multiseed_run_id,
        evaluation_type="external",
        evaluation_origin="automatic_post_multiseed",
        champion_count=1,
        dataset_source_type="catalog",
        dataset_set_name="bnb_external",
        dataset_catalog_id="bnb_external",
        dataset_root="data/datasets",
        dataset_signature="external-sig-001",
        selection_scope_json={"run_ids": ["run-001"]},
        evaluation_summary_json={"positive_profit_count": 1},
        report_artifact_path="artifacts/multiseed/run/external/report.txt",
    )
    store.add_champion_evaluation_members(evaluation_id, [champion_id])

    with sqlite3.connect(database_path) as connection:
        analysis_member_count = connection.execute(
            "SELECT COUNT(*) FROM champion_analysis_members WHERE champion_analysis_id = ?",
            (analysis_id,),
        ).fetchone()[0]
        evaluation_member_count = connection.execute(
            "SELECT COUNT(*) FROM champion_evaluation_members WHERE champion_evaluation_id = ?",
            (evaluation_id,),
        ).fetchone()[0]
        analysis_row = connection.execute(
            """
            SELECT analysis_type, selection_scope_json, flat_csv_artifact_path
            FROM champion_analyses
            WHERE id = ?
            """,
            (analysis_id,),
        ).fetchone()
        evaluation_row = connection.execute(
            """
            SELECT evaluation_type, evaluation_summary_json, report_artifact_path
            FROM champion_evaluations
            WHERE id = ?
            """,
            (evaluation_id,),
        ).fetchone()

    assert analysis_member_count == 1
    assert evaluation_member_count == 1
    assert analysis_row == (
        "automatic_post_multiseed",
        '{"run_ids":["run-001"]}',
        "artifacts/multiseed/run/champions.csv",
    )
    assert evaluation_row == (
        "external",
        '{"positive_profit_count":1}',
        "artifacts/multiseed/run/external/report.txt",
    )


def test_hash_and_fingerprint_generation_is_stable() -> None:
    config_snapshot = build_config_snapshot(seed=101)
    genome_snapshot = build_genome_snapshot()

    first_config_hash = hash_config_snapshot(config_snapshot)
    second_config_hash = hash_config_snapshot(dict(config_snapshot))
    first_genome_hash = hash_genome_snapshot(genome_snapshot)
    second_genome_hash = hash_genome_snapshot(dict(genome_snapshot))
    first_fingerprint = build_execution_fingerprint(
        config_hash=first_config_hash,
        effective_seed=101,
        dataset_signature="sig-001",
        logic_version=CURRENT_LOGIC_VERSION,
    )
    second_fingerprint = build_execution_fingerprint(
        config_hash=second_config_hash,
        effective_seed=101,
        dataset_signature="sig-001",
        logic_version=CURRENT_LOGIC_VERSION,
    )

    assert first_config_hash == second_config_hash
    assert first_genome_hash == second_genome_hash
    assert first_fingerprint == second_fingerprint
    assert len(first_fingerprint) == 64


def test_execution_fingerprint_changes_when_logic_version_changes() -> None:
    config_snapshot = build_config_snapshot(seed=101)

    previous_fingerprint = build_execution_fingerprint(
        config_hash=hash_config_snapshot(config_snapshot),
        effective_seed=101,
        dataset_signature="sig-001",
        logic_version="v6",
    )
    current_fingerprint = build_execution_fingerprint(
        config_hash=hash_config_snapshot(config_snapshot),
        effective_seed=101,
        dataset_signature="sig-001",
        logic_version=CURRENT_LOGIC_VERSION,
    )

    assert CURRENT_LOGIC_VERSION == "v13"
    assert previous_fingerprint != current_fingerprint


def test_execution_fingerprint_is_not_affected_by_modular_identity_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "test_fingerprint_metadata_ignored.db"
    store = PersistenceStore(database_path)
    try:
        store.initialize()
        multiseed_run_id = store.save_multiseed_run(
            multiseed_run_uid="multiseed-001",
            configs_dir_snapshot={"configs": ["a.json"]},
            requested_parallel_workers=1,
            effective_parallel_workers=1,
            dataset_root="data/datasets",
            runs_planned=2,
            runs_completed=0,
            runs_reused=0,
            runs_failed=0,
            champions_found=False,
            champion_analysis_status="pending",
            external_evaluation_status="pending",
            audit_evaluation_status="pending",
        )
        config_snapshot = build_config_snapshot(seed=101)
        first_id = store.save_run_execution(
            run_execution_uid="execution-001",
            multiseed_run_id=multiseed_run_id,
            run_id="run-001",
            config_name="run_a.json",
            config_json_snapshot=config_snapshot,
            effective_seed=101,
            dataset_catalog_id="core_1h_spot",
            dataset_signature="sig-001",
            dataset_context_json={"train_count": 1, "validation_count": 1},
            status="completed",
            experimental_space_snapshot_json={
                "signal_pack_name": "policy_v21_default",
                "decision_policy_name": "policy_v2_default",
            },
        )
        second_id = store.save_run_execution(
            run_execution_uid="execution-002",
            multiseed_run_id=multiseed_run_id,
            run_id="run-002",
            config_name="run_a.json",
            config_json_snapshot=config_snapshot,
            effective_seed=101,
            dataset_catalog_id="core_1h_spot",
            dataset_signature="sig-001",
            dataset_context_json={"train_count": 1, "validation_count": 1},
            status="completed",
            experimental_space_snapshot_json={
                "signal_pack_name": "other_signal_pack",
                "decision_policy_name": "other_decision_policy",
            },
        )

        rows = store.load_run_executions(run_ids=["run-001", "run-002"])
        fingerprints = {row["execution_fingerprint"] for row in rows}

        assert first_id != second_id
        assert len(fingerprints) == 1
    finally:
        if database_path.exists():
            database_path.unlink()


def test_utc_now_iso_returns_utc_text_timestamp() -> None:
    value = utc_now_iso()
    assert value.endswith("Z")
    assert "T" in value
