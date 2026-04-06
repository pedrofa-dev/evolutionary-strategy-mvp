import sqlite3
from pathlib import Path

from evo_system.experimental_space.identity import build_runtime_component_fingerprint
from evo_system.storage.persistence_store import (
    CANONICAL_INDEX_NAMES,
    CANONICAL_TABLE_NAMES,
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
    build_execution_fingerprint,
    hash_config_snapshot,
    hash_genome_snapshot,
    utc_now_iso,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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

    assert set(CANONICAL_TABLE_NAMES).issubset(table_names)
    assert set(CANONICAL_INDEX_NAMES).issubset(index_names)


def test_default_persistence_path_and_no_parallel_legacy_store() -> None:
    assert DEFAULT_PERSISTENCE_DB_PATH == Path("data/evolution_v2.db")
    assert not Path("src/evo_system/storage/sqlite_store.py").exists()


def test_no_parallel_sqlite_writer_exists_in_src_tree() -> None:
    python_files = list((REPO_ROOT / "src").rglob("*.py"))

    sqlite_write_connect_users = []
    direct_sql_writers = []

    for file_path in python_files:
        relative_path = file_path.relative_to(REPO_ROOT).as_posix()
        text = file_path.read_text(encoding="utf-8")

        if "sqlite3.connect(" in text and relative_path not in {
            "src/evo_system/storage/persistence_store.py",
            "src/evo_system/storage/run_read_repository.py",
            "src/application/runs_results/service.py",
            "src/application/execution_queue/service.py",
        }:
            sqlite_write_connect_users.append(relative_path)

        if relative_path != "src/evo_system/storage/persistence_store.py" and any(
            token in text
            for token in (
                "INSERT INTO ",
                "UPDATE run_executions",
                "UPDATE champions",
                "CREATE TABLE IF NOT EXISTS ",
            )
        ):
            direct_sql_writers.append(relative_path)

    assert sqlite_write_connect_users == []
    assert direct_sql_writers == []


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
            "market_mode_name": "spot",
            "leverage": 1.0,
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
    assert loaded["experimental_space_snapshot_json"]["leverage"] == 1.0
    assert loaded["resolved_dataset_root"] == "data/datasets"

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                config_hash,
                effective_seed,
                dataset_catalog_id,
                dataset_signature,
                logic_version,
                execution_fingerprint,
                runtime_component_fingerprint
            FROM run_executions
            WHERE id = ?
            """,
            (execution_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == hash_config_snapshot(config_snapshot)
    assert row[1] == 101
    assert row[2] == "core_1h_spot"
    assert row[3] == "sig-001"
    assert row[4] == CURRENT_LOGIC_VERSION
    assert row[5] == fingerprint
    assert row[6] == build_runtime_component_fingerprint(
        loaded["experimental_space_snapshot_json"]
    )


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
            "market_mode_name": "spot",
            "leverage": 1.0,
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


def test_execution_queue_settings_and_jobs_are_persisted(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence.db"
    store = PersistenceStore(database_path)
    store.initialize()

    assert store.get_execution_queue_concurrency_limit() == 1
    assert store.set_execution_queue_concurrency_limit(3) == 3
    assert store.get_execution_queue_concurrency_limit() == 3

    store.save_execution_queue_job(
        queue_job_uid="queue-001",
        campaign_id="multiseed_001",
        config_name="queued_probe.json",
        config_path="configs/runs/queued_probe.json",
        config_payload_json={"seed_count": 4},
        parallel_workers=2,
        execution_configs_dir="artifacts/ui_run_lab/config_sets/queued_probe",
        launch_log_path="artifacts/ui_run_lab/config_sets/queued_probe/launch.log",
        multiseed_output_dir="artifacts/multiseed/multiseed_001",
        experiment_preset_name="standard",
    )

    row = store.load_execution_queue_job("queue-001")
    assert row is not None
    assert row["status"] == "queued"
    assert row["config_payload_json"]["seed_count"] == 4

    store.update_execution_queue_job(
        "queue-001",
        status="running",
        started_at=utc_now_iso(),
        command_json=["python", "scripts/run_experiment.py"],
        pid=1234,
    )
    updated = store.load_execution_queue_job("queue-001")
    assert updated is not None
    assert updated["status"] == "running"
    assert updated["pid"] == 1234
    assert updated["command_json"][0] == "python"


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

    assert CURRENT_LOGIC_VERSION == "v15"
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
                "market_mode_name": "spot",
                "leverage": 1.0,
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
                "market_mode_name": "futures",
                "leverage": 1.0,
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
