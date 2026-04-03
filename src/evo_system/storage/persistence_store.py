from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# CORE COMPONENT - DO NOT MODIFY FROM UI OR EXPERIMENTAL LAYER.
# This token is part of reusable execution identity. Changing it casually
# breaks comparability across campaigns; failing to change it when runtime
# semantics change can incorrectly reuse incompatible executions.
CURRENT_LOGIC_VERSION = "v13"
DEFAULT_PERSISTENCE_DB_PATH = Path("data/evolution_v2.db")
REPO_ROOT = Path(__file__).resolve().parents[3]

MULTISEED_RUNS_JSON_COLUMNS = {
    "configs_dir_snapshot_json",
    "failure_summary_json",
    "environment_snapshot_json",
}
RUN_EXECUTIONS_JSON_COLUMNS = {
    "config_json_snapshot",
    "dataset_context_json",
    "experimental_space_snapshot_json",
    "summary_json",
}
CHAMPIONS_JSON_COLUMNS = {
    "genome_json_snapshot",
    "config_json_snapshot",
    "experimental_space_snapshot_json",
    "train_metrics_json",
    "validation_metrics_json",
    "champion_metrics_json",
}
CHAMPION_ANALYSES_JSON_COLUMNS = {
    "selection_scope_json",
    "analysis_summary_json",
}
CHAMPION_EVALUATIONS_JSON_COLUMNS = {
    "selection_scope_json",
    "evaluation_summary_json",
}


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def serialize_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_config_snapshot(config_json_snapshot: dict[str, Any]) -> str:
    return sha256_hex(serialize_json(config_json_snapshot))


def hash_genome_snapshot(genome_json_snapshot: dict[str, Any]) -> str:
    return sha256_hex(serialize_json(genome_json_snapshot))


def build_execution_fingerprint(
    *,
    config_hash: str,
    effective_seed: int,
    dataset_signature: str,
    logic_version: str,
) -> str:
    """CORE COMPONENT - DO NOT MODIFY FROM UI OR EXPERIMENTAL LAYER.

    Why:
    - This is the canonical reuse identity for multiseed executions.

    Invariants:
    - It must remain strict: config snapshot + seed + dataset identity +
      logic_version.
    - Modular traceability metadata such as experimental-space snapshots must
      not silently enter this fingerprint in metadata-only phases.

    Risk:
    - Weakening this causes invalid reuse and contaminated research history.
    """
    return sha256_hex(
        serialize_json(
            {
                "config_hash": config_hash,
                "effective_seed": effective_seed,
                "dataset_signature": dataset_signature,
                "logic_version": logic_version,
            }
        )
    )


def to_repo_relative_path(path: str | Path | None) -> str | None:
    if path is None:
        return None

    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()

    try:
        return candidate.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def _load_json_payload(payload: str | None) -> Any:
    if payload is None:
        return None
    return json.loads(payload)


def _row_to_dict(row: sqlite3.Row, json_columns: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if key in json_columns and value is not None:
            result[key] = _load_json_payload(value)
        else:
            result[key] = value
    return result


class PersistenceStore:
    """CORE COMPONENT - DO NOT MODIFY FROM UI OR EXPERIMENTAL LAYER.

    Why:
    - This store is the canonical source of truth for run, champion, analysis,
      and reevaluation persistence.

    Invariants:
    - Stored snapshots must stay self-contained and queryable.
    - Persistence semantics must remain aligned with runtime and reuse logic.

    Risk:
    - UI- or experiment-specific edits here can make historical results
      incomparable or corrupt the reuse guarantees of the system.
    """
    def __init__(self, database_path: str | Path = DEFAULT_PERSISTENCE_DB_PATH) -> None:
        self.database_path = Path(database_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        """CORE COMPONENT - DO NOT MODIFY FROM UI OR EXPERIMENTAL LAYER.

        Why:
        - This defines the canonical schema expected by runtime, reporting, and
          reevaluation.

        Risk:
        - Uncoordinated schema edits here can invalidate persistence and break
          cross-run analysis in subtle ways.
        """
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS multiseed_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    multiseed_run_uid TEXT NOT NULL UNIQUE,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    configs_dir_snapshot_json TEXT NOT NULL,
                    preset_name TEXT,
                    requested_parallel_workers INTEGER NOT NULL,
                    effective_parallel_workers INTEGER NOT NULL,
                    dataset_root TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    runs_planned INTEGER NOT NULL,
                    runs_completed INTEGER NOT NULL,
                    runs_reused INTEGER NOT NULL,
                    runs_failed INTEGER NOT NULL,
                    champions_found INTEGER NOT NULL,
                    champion_analysis_status TEXT NOT NULL,
                    external_evaluation_status TEXT NOT NULL,
                    audit_evaluation_status TEXT NOT NULL,
                    context_name TEXT,
                    notes TEXT,
                    failure_summary_json TEXT,
                    environment_snapshot_json TEXT,
                    summary_artifact_path TEXT,
                    quick_summary_artifact_path TEXT,
                    champions_summary_artifact_path TEXT,
                    artifacts_root_path TEXT
                );

                CREATE TABLE IF NOT EXISTS run_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_execution_uid TEXT NOT NULL UNIQUE,
                    multiseed_run_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    config_name TEXT NOT NULL,
                    config_json_snapshot TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    effective_seed INTEGER NOT NULL,
                    dataset_catalog_id TEXT NOT NULL,
                    dataset_signature TEXT NOT NULL,
                    dataset_context_json TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    execution_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    context_name TEXT,
                    preset_name TEXT,
                    experimental_space_snapshot_json TEXT,
                    requested_dataset_root TEXT,
                    resolved_dataset_root TEXT,
                    failure_reason TEXT,
                    log_artifact_path TEXT,
                    progress_snapshot_artifact_path TEXT,
                    per_run_summary_artifact_path TEXT,
                    summary_json TEXT,
                    FOREIGN KEY (multiseed_run_id) REFERENCES multiseed_runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS champions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    champion_uid TEXT NOT NULL UNIQUE,
                    run_execution_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    config_name TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    generation_number INTEGER NOT NULL,
                    mutation_seed INTEGER NOT NULL,
                    champion_type TEXT NOT NULL,
                    genome_json_snapshot TEXT NOT NULL,
                    genome_hash TEXT NOT NULL,
                    config_json_snapshot TEXT NOT NULL,
                    experimental_space_snapshot_json TEXT,
                    dataset_catalog_id TEXT NOT NULL,
                    dataset_signature TEXT NOT NULL,
                    train_metrics_json TEXT NOT NULL,
                    validation_metrics_json TEXT NOT NULL,
                    persisted_at TEXT NOT NULL,
                    context_name TEXT,
                    champion_metrics_json TEXT,
                    notes TEXT,
                    champion_card_artifact_path TEXT,
                    serialized_snapshot_artifact_path TEXT,
                    FOREIGN KEY (run_execution_id) REFERENCES run_executions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS champion_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    champion_analysis_uid TEXT NOT NULL UNIQUE,
                    multiseed_run_id INTEGER,
                    analysis_type TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    champion_count INTEGER NOT NULL,
                    selection_scope_json TEXT NOT NULL,
                    analysis_summary_json TEXT NOT NULL,
                    requested_by TEXT,
                    notes TEXT,
                    output_dir_artifact_path TEXT,
                    flat_csv_artifact_path TEXT,
                    report_artifact_path TEXT,
                    patterns_artifact_path TEXT,
                    champion_card_artifact_path TEXT,
                    FOREIGN KEY (multiseed_run_id) REFERENCES multiseed_runs(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS champion_analysis_members (
                    champion_analysis_id INTEGER NOT NULL,
                    champion_id INTEGER NOT NULL,
                    PRIMARY KEY (champion_analysis_id, champion_id),
                    FOREIGN KEY (champion_analysis_id) REFERENCES champion_analyses(id) ON DELETE CASCADE,
                    FOREIGN KEY (champion_id) REFERENCES champions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS champion_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    champion_evaluation_uid TEXT NOT NULL UNIQUE,
                    multiseed_run_id INTEGER,
                    evaluation_type TEXT NOT NULL,
                    evaluation_origin TEXT NOT NULL,
                    logic_version TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    champion_count INTEGER NOT NULL,
                    dataset_source_type TEXT NOT NULL,
                    dataset_set_name TEXT NOT NULL,
                    dataset_catalog_id TEXT,
                    dataset_root TEXT,
                    dataset_signature TEXT NOT NULL,
                    selection_scope_json TEXT NOT NULL,
                    evaluation_summary_json TEXT NOT NULL,
                    requested_by TEXT,
                    notes TEXT,
                    output_dir_artifact_path TEXT,
                    flat_csv_artifact_path TEXT,
                    json_artifact_path TEXT,
                    report_artifact_path TEXT,
                    per_champion_dir_artifact_path TEXT,
                    FOREIGN KEY (multiseed_run_id) REFERENCES multiseed_runs(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS champion_evaluation_members (
                    champion_evaluation_id INTEGER NOT NULL,
                    champion_id INTEGER NOT NULL,
                    PRIMARY KEY (champion_evaluation_id, champion_id),
                    FOREIGN KEY (champion_evaluation_id) REFERENCES champion_evaluations(id) ON DELETE CASCADE,
                    FOREIGN KEY (champion_id) REFERENCES champions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_run_executions_execution_fingerprint
                ON run_executions(execution_fingerprint);
                CREATE INDEX IF NOT EXISTS idx_run_executions_run_id
                ON run_executions(run_id);
                CREATE INDEX IF NOT EXISTS idx_run_executions_config_hash
                ON run_executions(config_hash);
                CREATE INDEX IF NOT EXISTS idx_run_executions_logic_version
                ON run_executions(logic_version);
                CREATE INDEX IF NOT EXISTS idx_run_executions_multiseed_run_id
                ON run_executions(multiseed_run_id);

                CREATE INDEX IF NOT EXISTS idx_champions_run_execution_id
                ON champions(run_execution_id);
                CREATE INDEX IF NOT EXISTS idx_champions_run_id
                ON champions(run_id);
                CREATE INDEX IF NOT EXISTS idx_champions_champion_type
                ON champions(champion_type);
                CREATE INDEX IF NOT EXISTS idx_champions_config_hash
                ON champions(config_hash);
                CREATE INDEX IF NOT EXISTS idx_champions_logic_version
                ON champions(logic_version);

                CREATE INDEX IF NOT EXISTS idx_champion_analyses_multiseed_run_id
                ON champion_analyses(multiseed_run_id);
                CREATE INDEX IF NOT EXISTS idx_champion_evaluations_multiseed_run_id
                ON champion_evaluations(multiseed_run_id);
                CREATE INDEX IF NOT EXISTS idx_champion_analysis_members_champion_id
                ON champion_analysis_members(champion_id);
                CREATE INDEX IF NOT EXISTS idx_champion_evaluation_members_champion_id
                ON champion_evaluation_members(champion_id);
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(multiseed_runs)")
            }
            if "runs_reused" not in existing_columns:
                connection.execute(
                    "ALTER TABLE multiseed_runs ADD COLUMN runs_reused INTEGER NOT NULL DEFAULT 0"
                )
            run_execution_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(run_executions)")
            }
            if "experimental_space_snapshot_json" not in run_execution_columns:
                connection.execute(
                    "ALTER TABLE run_executions ADD COLUMN experimental_space_snapshot_json TEXT"
                )
            champion_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(champions)")
            }
            if "experimental_space_snapshot_json" not in champion_columns:
                connection.execute(
                    "ALTER TABLE champions ADD COLUMN experimental_space_snapshot_json TEXT"
                )

    def save_multiseed_run(
        self,
        *,
        multiseed_run_uid: str,
        configs_dir_snapshot: dict[str, Any] | list[Any],
        requested_parallel_workers: int,
        effective_parallel_workers: int,
        dataset_root: str | Path,
        runs_planned: int,
        runs_completed: int,
        runs_reused: int,
        runs_failed: int,
        champions_found: bool,
        champion_analysis_status: str,
        external_evaluation_status: str,
        audit_evaluation_status: str,
        status: str = "running",
        logic_version: str = CURRENT_LOGIC_VERSION,
        started_at: str | None = None,
        completed_at: str | None = None,
        preset_name: str | None = None,
        context_name: str | None = None,
        notes: str | None = None,
        failure_summary_json: dict[str, Any] | list[Any] | None = None,
        environment_snapshot_json: dict[str, Any] | None = None,
        summary_artifact_path: str | Path | None = None,
        quick_summary_artifact_path: str | Path | None = None,
        champions_summary_artifact_path: str | Path | None = None,
        artifacts_root_path: str | Path | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO multiseed_runs (
                    multiseed_run_uid,
                    started_at,
                    completed_at,
                    status,
                    configs_dir_snapshot_json,
                    preset_name,
                    requested_parallel_workers,
                    effective_parallel_workers,
                    dataset_root,
                    logic_version,
                    runs_planned,
                    runs_completed,
                    runs_reused,
                    runs_failed,
                    champions_found,
                    champion_analysis_status,
                    external_evaluation_status,
                    audit_evaluation_status,
                    context_name,
                    notes,
                    failure_summary_json,
                    environment_snapshot_json,
                    summary_artifact_path,
                    quick_summary_artifact_path,
                    champions_summary_artifact_path,
                    artifacts_root_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    multiseed_run_uid,
                    started_at or utc_now_iso(),
                    completed_at,
                    status,
                    serialize_json(configs_dir_snapshot),
                    preset_name,
                    requested_parallel_workers,
                    effective_parallel_workers,
                    to_repo_relative_path(dataset_root),
                    logic_version,
                    runs_planned,
                    runs_completed,
                    runs_reused,
                    runs_failed,
                    int(champions_found),
                    champion_analysis_status,
                    external_evaluation_status,
                    audit_evaluation_status,
                    context_name,
                    notes,
                    serialize_json(failure_summary_json) if failure_summary_json is not None else None,
                    serialize_json(environment_snapshot_json) if environment_snapshot_json is not None else None,
                    to_repo_relative_path(summary_artifact_path),
                    to_repo_relative_path(quick_summary_artifact_path),
                    to_repo_relative_path(champions_summary_artifact_path),
                    to_repo_relative_path(artifacts_root_path),
                ),
            )
            return int(cursor.lastrowid)

    def update_multiseed_run_status(
        self,
        multiseed_run_id: int,
        *,
        status: str,
        completed_at: str | None = None,
        runs_completed: int | None = None,
        runs_reused: int | None = None,
        runs_failed: int | None = None,
        champions_found: bool | None = None,
        champion_analysis_status: str | None = None,
        external_evaluation_status: str | None = None,
        audit_evaluation_status: str | None = None,
        failure_summary_json: dict[str, Any] | list[Any] | None = None,
        environment_snapshot_json: dict[str, Any] | None = None,
        summary_artifact_path: str | Path | None = None,
        quick_summary_artifact_path: str | Path | None = None,
        champions_summary_artifact_path: str | Path | None = None,
        artifacts_root_path: str | Path | None = None,
    ) -> None:
        assignments = ["status = ?", "completed_at = ?"]
        parameters: list[Any] = [status, completed_at or utc_now_iso()]

        optional_updates = {
            "runs_completed": runs_completed,
            "runs_reused": runs_reused,
            "runs_failed": runs_failed,
            "champions_found": int(champions_found) if champions_found is not None else None,
            "champion_analysis_status": champion_analysis_status,
            "external_evaluation_status": external_evaluation_status,
            "audit_evaluation_status": audit_evaluation_status,
            "failure_summary_json": (
                serialize_json(failure_summary_json)
                if failure_summary_json is not None
                else None
            ),
            "environment_snapshot_json": (
                serialize_json(environment_snapshot_json)
                if environment_snapshot_json is not None
                else None
            ),
            "summary_artifact_path": to_repo_relative_path(summary_artifact_path),
            "quick_summary_artifact_path": to_repo_relative_path(quick_summary_artifact_path),
            "champions_summary_artifact_path": to_repo_relative_path(champions_summary_artifact_path),
            "artifacts_root_path": to_repo_relative_path(artifacts_root_path),
        }

        for column_name, value in optional_updates.items():
            if value is not None:
                assignments.append(f"{column_name} = ?")
                parameters.append(value)

        parameters.append(multiseed_run_id)

        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE multiseed_runs
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(parameters),
            )

    def save_run_execution(
        self,
        *,
        run_execution_uid: str,
        multiseed_run_id: int,
        run_id: str,
        config_name: str,
        config_json_snapshot: dict[str, Any],
        effective_seed: int,
        dataset_catalog_id: str,
        dataset_signature: str,
        dataset_context_json: dict[str, Any],
        status: str,
        logic_version: str = CURRENT_LOGIC_VERSION,
        started_at: str | None = None,
        completed_at: str | None = None,
        context_name: str | None = None,
        preset_name: str | None = None,
        experimental_space_snapshot_json: dict[str, Any] | None = None,
        requested_dataset_root: str | Path | None = None,
        resolved_dataset_root: str | Path | None = None,
        failure_reason: str | None = None,
        log_artifact_path: str | Path | None = None,
        progress_snapshot_artifact_path: str | Path | None = None,
        per_run_summary_artifact_path: str | Path | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> int:
        config_hash = hash_config_snapshot(config_json_snapshot)
        execution_fingerprint = build_execution_fingerprint(
            config_hash=config_hash,
            effective_seed=effective_seed,
            dataset_signature=dataset_signature,
            logic_version=logic_version,
        )

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO run_executions (
                    run_execution_uid,
                    multiseed_run_id,
                    run_id,
                    config_name,
                    config_json_snapshot,
                    config_hash,
                    effective_seed,
                    dataset_catalog_id,
                    dataset_signature,
                    dataset_context_json,
                    logic_version,
                    execution_fingerprint,
                    status,
                    started_at,
                    completed_at,
                    context_name,
                    preset_name,
                    experimental_space_snapshot_json,
                    requested_dataset_root,
                    resolved_dataset_root,
                    failure_reason,
                    log_artifact_path,
                    progress_snapshot_artifact_path,
                    per_run_summary_artifact_path,
                    summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_execution_uid,
                    multiseed_run_id,
                    run_id,
                    config_name,
                    serialize_json(config_json_snapshot),
                    config_hash,
                    effective_seed,
                    dataset_catalog_id,
                    dataset_signature,
                    serialize_json(dataset_context_json),
                    logic_version,
                    execution_fingerprint,
                    status,
                    started_at or utc_now_iso(),
                    completed_at,
                    context_name,
                    preset_name,
                    serialize_json(experimental_space_snapshot_json)
                    if experimental_space_snapshot_json is not None
                    else None,
                    to_repo_relative_path(requested_dataset_root),
                    to_repo_relative_path(resolved_dataset_root),
                    failure_reason,
                    to_repo_relative_path(log_artifact_path),
                    to_repo_relative_path(progress_snapshot_artifact_path),
                    to_repo_relative_path(per_run_summary_artifact_path),
                    serialize_json(summary_json) if summary_json is not None else None,
                ),
            )
            return int(cursor.lastrowid)

    def update_run_execution_status(
        self,
        run_execution_id: int,
        *,
        status: str,
        run_id: str | None = None,
        completed_at: str | None = None,
        failure_reason: str | None = None,
        log_artifact_path: str | Path | None = None,
        progress_snapshot_artifact_path: str | Path | None = None,
        per_run_summary_artifact_path: str | Path | None = None,
        experimental_space_snapshot_json: dict[str, Any] | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> None:
        assignments = ["status = ?", "completed_at = ?"]
        parameters: list[Any] = [status, completed_at or utc_now_iso()]

        optional_updates = {
            "run_id": run_id,
            "failure_reason": failure_reason,
            "log_artifact_path": to_repo_relative_path(log_artifact_path),
            "progress_snapshot_artifact_path": to_repo_relative_path(progress_snapshot_artifact_path),
            "per_run_summary_artifact_path": to_repo_relative_path(per_run_summary_artifact_path),
            "experimental_space_snapshot_json": (
                serialize_json(experimental_space_snapshot_json)
                if experimental_space_snapshot_json is not None
                else None
            ),
            "summary_json": serialize_json(summary_json) if summary_json is not None else None,
        }

        for column_name, value in optional_updates.items():
            if value is not None:
                assignments.append(f"{column_name} = ?")
                parameters.append(value)

        parameters.append(run_execution_id)

        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE run_executions
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(parameters),
            )

    def update_run_execution_artifacts(
        self,
        run_id: str,
        *,
        log_artifact_path: str | Path | None = None,
        progress_snapshot_artifact_path: str | Path | None = None,
        per_run_summary_artifact_path: str | Path | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> None:
        assignments: list[str] = []
        parameters: list[Any] = []

        optional_updates = {
            "log_artifact_path": to_repo_relative_path(log_artifact_path),
            "progress_snapshot_artifact_path": to_repo_relative_path(progress_snapshot_artifact_path),
            "per_run_summary_artifact_path": to_repo_relative_path(per_run_summary_artifact_path),
            "summary_json": serialize_json(summary_json) if summary_json is not None else None,
        }

        for column_name, value in optional_updates.items():
            if value is not None:
                assignments.append(f"{column_name} = ?")
                parameters.append(value)

        if not assignments:
            return

        parameters.append(run_id)

        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE run_executions
                SET {", ".join(assignments)}
                WHERE run_id = ?
                """,
                tuple(parameters),
            )

    def find_run_execution_by_fingerprint(self, execution_fingerprint: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM run_executions
                WHERE execution_fingerprint = ?
                ORDER BY
                    CASE WHEN status = 'completed' THEN 0 ELSE 1 END,
                    id DESC
                LIMIT 1
                """,
                (execution_fingerprint,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return _row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS)

    def load_champions(
        self,
        *,
        run_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM champions
        """
        parameters: list[Any] = []

        if run_ids:
            placeholders = ", ".join("?" for _ in run_ids)
            query += f" WHERE run_id IN ({placeholders})"
            parameters.extend(run_ids)

        query += " ORDER BY id ASC"

        with self.connect() as connection:
            cursor = connection.execute(query, tuple(parameters))
            rows = cursor.fetchall()

        return [_row_to_dict(row, CHAMPIONS_JSON_COLUMNS) for row in rows]

    def load_run_executions(
        self,
        *,
        run_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM run_executions
        """
        parameters: list[Any] = []

        if run_ids:
            placeholders = ", ".join("?" for _ in run_ids)
            query += f" WHERE run_id IN ({placeholders})"
            parameters.extend(run_ids)

        query += " ORDER BY id ASC"

        with self.connect() as connection:
            cursor = connection.execute(query, tuple(parameters))
            rows = cursor.fetchall()

        return [_row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS) for row in rows]

    def save_champion(
        self,
        *,
        champion_uid: str,
        run_execution_id: int,
        run_id: str,
        config_name: str,
        config_json_snapshot: dict[str, Any],
        generation_number: int,
        mutation_seed: int,
        champion_type: str,
        genome_json_snapshot: dict[str, Any],
        experimental_space_snapshot_json: dict[str, Any] | None = None,
        dataset_catalog_id: str,
        dataset_signature: str,
        train_metrics_json: dict[str, Any],
        validation_metrics_json: dict[str, Any],
        logic_version: str = CURRENT_LOGIC_VERSION,
        persisted_at: str | None = None,
        context_name: str | None = None,
        champion_metrics_json: dict[str, Any] | None = None,
        notes: str | None = None,
        champion_card_artifact_path: str | Path | None = None,
        serialized_snapshot_artifact_path: str | Path | None = None,
    ) -> int:
        config_hash = hash_config_snapshot(config_json_snapshot)
        genome_hash = hash_genome_snapshot(genome_json_snapshot)

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO champions (
                    champion_uid,
                    run_execution_id,
                    run_id,
                    config_name,
                    config_hash,
                    logic_version,
                    generation_number,
                    mutation_seed,
                    champion_type,
                    genome_json_snapshot,
                    genome_hash,
                    config_json_snapshot,
                    experimental_space_snapshot_json,
                    dataset_catalog_id,
                    dataset_signature,
                    train_metrics_json,
                    validation_metrics_json,
                    persisted_at,
                    context_name,
                    champion_metrics_json,
                    notes,
                    champion_card_artifact_path,
                    serialized_snapshot_artifact_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    champion_uid,
                    run_execution_id,
                    run_id,
                    config_name,
                    config_hash,
                    logic_version,
                    generation_number,
                    mutation_seed,
                    champion_type,
                    serialize_json(genome_json_snapshot),
                    genome_hash,
                    serialize_json(config_json_snapshot),
                    serialize_json(experimental_space_snapshot_json)
                    if experimental_space_snapshot_json is not None
                    else None,
                    dataset_catalog_id,
                    dataset_signature,
                    serialize_json(train_metrics_json),
                    serialize_json(validation_metrics_json),
                    persisted_at or utc_now_iso(),
                    context_name,
                    serialize_json(champion_metrics_json) if champion_metrics_json is not None else None,
                    notes,
                    to_repo_relative_path(champion_card_artifact_path),
                    to_repo_relative_path(serialized_snapshot_artifact_path),
                ),
            )
            return int(cursor.lastrowid)

    def save_champion_analysis(
        self,
        *,
        champion_analysis_uid: str,
        analysis_type: str,
        champion_count: int,
        selection_scope_json: dict[str, Any],
        analysis_summary_json: dict[str, Any],
        logic_version: str = CURRENT_LOGIC_VERSION,
        multiseed_run_id: int | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        requested_by: str | None = None,
        notes: str | None = None,
        output_dir_artifact_path: str | Path | None = None,
        flat_csv_artifact_path: str | Path | None = None,
        report_artifact_path: str | Path | None = None,
        patterns_artifact_path: str | Path | None = None,
        champion_card_artifact_path: str | Path | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO champion_analyses (
                    champion_analysis_uid,
                    multiseed_run_id,
                    analysis_type,
                    logic_version,
                    started_at,
                    completed_at,
                    champion_count,
                    selection_scope_json,
                    analysis_summary_json,
                    requested_by,
                    notes,
                    output_dir_artifact_path,
                    flat_csv_artifact_path,
                    report_artifact_path,
                    patterns_artifact_path,
                    champion_card_artifact_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    champion_analysis_uid,
                    multiseed_run_id,
                    analysis_type,
                    logic_version,
                    started_at or utc_now_iso(),
                    completed_at,
                    champion_count,
                    serialize_json(selection_scope_json),
                    serialize_json(analysis_summary_json),
                    requested_by,
                    notes,
                    to_repo_relative_path(output_dir_artifact_path),
                    to_repo_relative_path(flat_csv_artifact_path),
                    to_repo_relative_path(report_artifact_path),
                    to_repo_relative_path(patterns_artifact_path),
                    to_repo_relative_path(champion_card_artifact_path),
                ),
            )
            return int(cursor.lastrowid)

    def add_champion_analysis_members(
        self,
        champion_analysis_id: int,
        champion_ids: list[int],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO champion_analysis_members (
                    champion_analysis_id,
                    champion_id
                ) VALUES (?, ?)
                """,
                [(champion_analysis_id, champion_id) for champion_id in champion_ids],
            )

    def save_champion_evaluation(
        self,
        *,
        champion_evaluation_uid: str,
        evaluation_type: str,
        evaluation_origin: str,
        champion_count: int,
        dataset_source_type: str,
        dataset_set_name: str,
        dataset_signature: str,
        selection_scope_json: dict[str, Any],
        evaluation_summary_json: dict[str, Any],
        logic_version: str = CURRENT_LOGIC_VERSION,
        multiseed_run_id: int | None = None,
        dataset_catalog_id: str | None = None,
        dataset_root: str | Path | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        requested_by: str | None = None,
        notes: str | None = None,
        output_dir_artifact_path: str | Path | None = None,
        flat_csv_artifact_path: str | Path | None = None,
        json_artifact_path: str | Path | None = None,
        report_artifact_path: str | Path | None = None,
        per_champion_dir_artifact_path: str | Path | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO champion_evaluations (
                    champion_evaluation_uid,
                    multiseed_run_id,
                    evaluation_type,
                    evaluation_origin,
                    logic_version,
                    started_at,
                    completed_at,
                    champion_count,
                    dataset_source_type,
                    dataset_set_name,
                    dataset_catalog_id,
                    dataset_root,
                    dataset_signature,
                    selection_scope_json,
                    evaluation_summary_json,
                    requested_by,
                    notes,
                    output_dir_artifact_path,
                    flat_csv_artifact_path,
                    json_artifact_path,
                    report_artifact_path,
                    per_champion_dir_artifact_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    champion_evaluation_uid,
                    multiseed_run_id,
                    evaluation_type,
                    evaluation_origin,
                    logic_version,
                    started_at or utc_now_iso(),
                    completed_at,
                    champion_count,
                    dataset_source_type,
                    dataset_set_name,
                    dataset_catalog_id,
                    to_repo_relative_path(dataset_root),
                    dataset_signature,
                    serialize_json(selection_scope_json),
                    serialize_json(evaluation_summary_json),
                    requested_by,
                    notes,
                    to_repo_relative_path(output_dir_artifact_path),
                    to_repo_relative_path(flat_csv_artifact_path),
                    to_repo_relative_path(json_artifact_path),
                    to_repo_relative_path(report_artifact_path),
                    to_repo_relative_path(per_champion_dir_artifact_path),
                ),
            )
            return int(cursor.lastrowid)

    def add_champion_evaluation_members(
        self,
        champion_evaluation_id: int,
        champion_ids: list[int],
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO champion_evaluation_members (
                    champion_evaluation_id,
                    champion_id
                ) VALUES (?, ?)
                """,
                [(champion_evaluation_id, champion_id) for champion_id in champion_ids],
            )
