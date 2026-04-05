from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from evo_system.experimental_space.identity import (
    format_experimental_space_stack_label,
    resolve_persisted_experimental_space_snapshot,
)
from evo_system.storage.persistence_store import (
    CHAMPIONS_JSON_COLUMNS,
    DEFAULT_PERSISTENCE_DB_PATH,
    RUN_EXECUTIONS_JSON_COLUMNS,
)


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


@dataclass(frozen=True)
class PersistedEvaluationBreakdown:
    selection_score: float | None = None
    median_profit: float | None = None
    median_drawdown: float | None = None
    median_trades: float | None = None
    dispersion: float | None = None
    dataset_scores: list[float] = field(default_factory=list)
    dataset_profits: list[float] = field(default_factory=list)
    dataset_drawdowns: list[float] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    is_valid: bool | None = None


@dataclass(frozen=True)
class PersistedGenomeSnapshot:
    champion_id: int | None
    generation_number: int | None
    champion_type: str | None
    genome_snapshot: dict[str, Any] | None
    genome_repr: str | None


@dataclass(frozen=True)
class PersistedRunListItem:
    run_id: str
    config_name: str
    effective_seed: int
    status: str
    dataset_catalog_id: str | None
    dataset_signature: str | None
    started_at: str | None
    completed_at: str | None
    champion_persisted: bool
    external_validation_status: str | None
    market_mode_name: str | None
    leverage: float | None
    stack_label: str
    runtime_component_fingerprint: str | None


@dataclass(frozen=True)
class PersistedRunSummaryView:
    run_id: str
    config_name: str
    config_path: str | None
    effective_seed: int
    status: str
    config_hash: str
    execution_fingerprint: str
    logic_version: str
    runtime_component_fingerprint: str | None
    dataset_catalog_id: str | None
    dataset_signature: str | None
    dataset_context: dict[str, Any]
    config_json_snapshot: dict[str, Any]
    summary_payload: dict[str, Any]
    experimental_space_snapshot: dict[str, Any] | None
    market_mode_name: str | None
    leverage: float | None
    stack_label: str
    best_train_selection_score: float | None
    final_validation_selection_score: float | None
    final_validation_profit: float | None
    final_validation_drawdown: float | None
    final_validation_trades: float | None
    best_genome_generation: int | None
    champion_persisted: bool
    champion_type: str | None
    external_validation_status: str | None
    total_run_time_seconds: float | None
    average_generation_time_seconds: float | None
    train_breakdown: PersistedEvaluationBreakdown | None
    validation_breakdown: PersistedEvaluationBreakdown | None
    best_genome: PersistedGenomeSnapshot | None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _resolve_market_mode_name(
    *,
    config_snapshot: dict[str, Any] | None,
    experimental_space_snapshot: dict[str, Any] | None,
) -> str | None:
    if experimental_space_snapshot is not None:
        return str(experimental_space_snapshot.get("market_mode_name"))
    if config_snapshot is None:
        return None
    return str(config_snapshot.get("market_mode_name", "spot"))


def _resolve_leverage(
    *,
    config_snapshot: dict[str, Any] | None,
    experimental_space_snapshot: dict[str, Any] | None,
) -> float | None:
    if experimental_space_snapshot is not None:
        return _safe_float(experimental_space_snapshot.get("leverage"))
    if config_snapshot is None:
        return 1.0
    return _safe_float(config_snapshot.get("leverage", 1.0))


def _build_breakdown(metrics: dict[str, Any] | None) -> PersistedEvaluationBreakdown | None:
    if not metrics:
        return None
    return PersistedEvaluationBreakdown(
        selection_score=_safe_float(metrics.get("selection_score")),
        median_profit=_safe_float(metrics.get("median_profit")),
        median_drawdown=_safe_float(metrics.get("median_drawdown")),
        median_trades=_safe_float(metrics.get("median_trades")),
        dispersion=_safe_float(metrics.get("dispersion")),
        dataset_scores=[float(value) for value in metrics.get("dataset_scores") or []],
        dataset_profits=[float(value) for value in metrics.get("dataset_profits") or []],
        dataset_drawdowns=[float(value) for value in metrics.get("dataset_drawdowns") or []],
        violations=[str(value) for value in metrics.get("violations") or []],
        is_valid=(
            bool(metrics["is_valid"])
            if metrics.get("is_valid") is not None
            else None
        ),
    )


def _resolve_snapshot(
    config_snapshot: dict[str, Any] | None,
    *candidate_snapshots: dict[str, Any] | None,
) -> dict[str, Any] | None:
    for snapshot in candidate_snapshots:
        normalized_snapshot = resolve_persisted_experimental_space_snapshot(
            experimental_space_snapshot=snapshot,
            config_json_snapshot=config_snapshot,
        )
        if normalized_snapshot is not None:
            return normalized_snapshot
    return None


class RunReadRepository:
    """Read-only access layer for persisted runs.

    Why it exists:
    - Reporting, audit, and future UI/API work need a stable way to reconstruct
      run results from the canonical database without re-executing the runtime.

    Constraints:
    - This repository must not recalculate scores or mutate persistence state.
    - It must degrade safely when optional persisted fields are missing.
    """

    def __init__(self, database_path: str | Path = DEFAULT_PERSISTENCE_DB_PATH) -> None:
        self.database_path = Path(database_path)

    @contextmanager
    def _connect_readonly(self) -> Iterator[sqlite3.Connection]:
        if not self.database_path.exists():
            raise FileNotFoundError(f"Database not found: {self.database_path}")

        connection = sqlite3.connect(
            f"file:{self.database_path.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _fetch_run_execution(self, run_id: str) -> dict[str, Any] | None:
        with self._connect_readonly() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM run_executions
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return _row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS)

    def _fetch_champion(
        self,
        *,
        run_execution_id: int | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        if run_execution_id is None and run_id is None:
            return None

        if run_execution_id is not None:
            query = """
                SELECT *
                FROM champions
                WHERE run_execution_id = ?
                ORDER BY id DESC
                LIMIT 1
            """
            parameters = (run_execution_id,)
        else:
            query = """
                SELECT *
                FROM champions
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1
            """
            parameters = (run_id,)

        with self._connect_readonly() as connection:
            cursor = connection.execute(query, parameters)
            row = cursor.fetchone()

        if row is None:
            return None
        return _row_to_dict(row, CHAMPIONS_JSON_COLUMNS)

    def list_runs(self, *, limit: int = 50) -> list[PersistedRunListItem]:
        with self._connect_readonly() as connection:
            cursor = connection.execute(
                """
                SELECT
                    re.run_id,
                    re.config_name,
                    re.effective_seed,
                    re.status,
                    re.dataset_catalog_id,
                    re.dataset_signature,
                    re.started_at,
                    re.completed_at,
                    re.config_json_snapshot,
                    re.summary_json,
                    re.experimental_space_snapshot_json,
                    re.runtime_component_fingerprint,
                    EXISTS(
                        SELECT 1
                        FROM champions c
                        WHERE c.run_execution_id = re.id
                    ) AS champion_persisted
                FROM run_executions re
                ORDER BY re.id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        items: list[PersistedRunListItem] = []
        for row in rows:
            payload = _row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS)
            summary_payload = payload.get("summary_json") or {}
            snapshot = _resolve_snapshot(
                payload.get("config_json_snapshot"),
                payload.get("experimental_space_snapshot_json"),
                summary_payload.get("experimental_space_snapshot"),
            )
            items.append(
                PersistedRunListItem(
                    run_id=str(payload["run_id"]),
                    config_name=str(payload["config_name"]),
                    effective_seed=int(payload["effective_seed"]),
                    status=str(payload["status"]),
                    dataset_catalog_id=payload.get("dataset_catalog_id"),
                    dataset_signature=payload.get("dataset_signature"),
                    started_at=payload.get("started_at"),
                    completed_at=payload.get("completed_at"),
                    champion_persisted=bool(payload["champion_persisted"]),
                    external_validation_status=summary_payload.get(
                        "external_validation_status"
                    ),
                    market_mode_name=_resolve_market_mode_name(
                        config_snapshot=payload.get("config_json_snapshot"),
                        experimental_space_snapshot=snapshot,
                    ),
                    leverage=_resolve_leverage(
                        config_snapshot=payload.get("config_json_snapshot"),
                        experimental_space_snapshot=snapshot,
                    ),
                    stack_label=format_experimental_space_stack_label(snapshot),
                    runtime_component_fingerprint=payload.get(
                        "runtime_component_fingerprint"
                    ),
                )
            )
        return items

    def get_run(self, run_id: str) -> PersistedRunSummaryView | None:
        return self.get_run_summary(run_id)

    def get_run_summary(self, run_id: str) -> PersistedRunSummaryView | None:
        run_row = self._fetch_run_execution(run_id)
        if run_row is None:
            return None

        champion_row = self._fetch_champion(
            run_execution_id=int(run_row["id"]),
            run_id=run_id,
        )
        summary_payload = dict(run_row.get("summary_json") or {})
        normalized_snapshot = _resolve_snapshot(
            run_row.get("config_json_snapshot"),
            run_row.get("experimental_space_snapshot_json"),
            summary_payload.get("experimental_space_snapshot"),
            (champion_row or {}).get("experimental_space_snapshot_json"),
        )

        best_genome = self.get_best_genome(run_id)

        return PersistedRunSummaryView(
            run_id=str(run_row["run_id"]),
            config_name=str(run_row["config_name"]),
            config_path=summary_payload.get("config_path"),
            effective_seed=int(run_row["effective_seed"]),
            status=str(run_row["status"]),
            config_hash=str(run_row["config_hash"]),
            execution_fingerprint=str(run_row["execution_fingerprint"]),
            logic_version=str(run_row["logic_version"]),
            runtime_component_fingerprint=run_row.get("runtime_component_fingerprint"),
            dataset_catalog_id=run_row.get("dataset_catalog_id"),
            dataset_signature=run_row.get("dataset_signature"),
            dataset_context=dict(run_row.get("dataset_context_json") or {}),
            config_json_snapshot=dict(run_row.get("config_json_snapshot") or {}),
            summary_payload=summary_payload,
            experimental_space_snapshot=normalized_snapshot,
            market_mode_name=_resolve_market_mode_name(
                config_snapshot=run_row.get("config_json_snapshot"),
                experimental_space_snapshot=normalized_snapshot,
            ),
            leverage=_resolve_leverage(
                config_snapshot=run_row.get("config_json_snapshot"),
                experimental_space_snapshot=normalized_snapshot,
            ),
            stack_label=format_experimental_space_stack_label(normalized_snapshot),
            best_train_selection_score=_safe_float(
                summary_payload.get("best_train_selection_score")
            ),
            final_validation_selection_score=_safe_float(
                summary_payload.get("final_validation_selection_score")
            ),
            final_validation_profit=_safe_float(
                summary_payload.get("final_validation_profit")
            ),
            final_validation_drawdown=_safe_float(
                summary_payload.get("final_validation_drawdown")
            ),
            final_validation_trades=_safe_float(
                summary_payload.get("final_validation_trades")
            ),
            best_genome_generation=_safe_int(
                summary_payload.get("generation_of_best")
                or (champion_row or {}).get("generation_number")
            ),
            champion_persisted=champion_row is not None,
            champion_type=(champion_row or {}).get("champion_type"),
            external_validation_status=summary_payload.get("external_validation_status"),
            total_run_time_seconds=_safe_float(summary_payload.get("total_run_time_seconds")),
            average_generation_time_seconds=_safe_float(
                summary_payload.get("average_generation_time_seconds")
            ),
            train_breakdown=_build_breakdown(
                (champion_row or {}).get("train_metrics_json")
            ),
            validation_breakdown=_build_breakdown(
                (champion_row or {}).get("validation_metrics_json")
            ),
            best_genome=best_genome,
        )

    def get_train_validation_breakdowns(
        self,
        run_id: str,
    ) -> tuple[PersistedEvaluationBreakdown | None, PersistedEvaluationBreakdown | None]:
        run_row = self._fetch_run_execution(run_id)
        champion_row = self._fetch_champion(
            run_execution_id=int(run_row["id"]) if run_row is not None else None,
            run_id=run_id,
        )
        if champion_row is None:
            return None, None
        return (
            _build_breakdown(champion_row.get("train_metrics_json")),
            _build_breakdown(champion_row.get("validation_metrics_json")),
        )

    def get_best_genome(self, run_id: str) -> PersistedGenomeSnapshot | None:
        run_row = self._fetch_run_execution(run_id)
        if run_row is None:
            return None

        champion_row = self._fetch_champion(
            run_execution_id=int(run_row["id"]),
            run_id=run_id,
        )
        if champion_row is not None:
            return PersistedGenomeSnapshot(
                champion_id=int(champion_row["id"]),
                generation_number=_safe_int(champion_row.get("generation_number")),
                champion_type=champion_row.get("champion_type"),
                genome_snapshot=dict(champion_row.get("genome_json_snapshot") or {}),
                genome_repr=(run_row.get("summary_json") or {}).get("best_genome_repr"),
            )

        summary_payload = run_row.get("summary_json") or {}
        genome_repr = summary_payload.get("best_genome_repr")
        if genome_repr is None:
            return None

        return PersistedGenomeSnapshot(
            champion_id=None,
            generation_number=_safe_int(summary_payload.get("generation_of_best")),
            champion_type=None,
            genome_snapshot=None,
            genome_repr=str(genome_repr),
        )
