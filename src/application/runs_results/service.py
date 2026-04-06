from __future__ import annotations

import json
import sqlite3
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from application.execution_queue import ExecutionQueueService
from application.execution_queue.service import (
    FINAL_QUEUE_JOB_STATUSES,
    RUNNING_QUEUE_JOB_STATUSES,
)
from evo_system.experimentation.parallel_progress import (
    format_active_job_progress,
    read_progress_snapshot,
)
from evo_system.reporting.champion_card import build_champion_card
from evo_system.storage import PersistenceStore
from evo_system.storage.persistence_store import (
    CHAMPION_ANALYSES_JSON_COLUMNS,
    CHAMPION_EVALUATIONS_JSON_COLUMNS,
    CHAMPIONS_JSON_COLUMNS,
    DEFAULT_PERSISTENCE_DB_PATH,
    EXECUTION_QUEUE_JOBS_JSON_COLUMNS,
    MULTISEED_RUNS_JSON_COLUMNS,
    RUN_EXECUTIONS_JSON_COLUMNS,
)


def _load_json(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _row_to_dict(row: sqlite3.Row, json_columns: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        payload[key] = _load_json(value) if key in json_columns and value is not None else value
    return payload


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _population_std(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    mean_value = _mean(values)
    assert mean_value is not None
    return (sum((value - mean_value) ** 2 for value in values) / len(values)) ** 0.5


def _resolve_repo_path(repo_root: Path, path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _is_path_inside(parent: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_artifact_path(repo_root: Path, path_value: str | None) -> Path | None:
    resolved = _resolve_repo_path(repo_root, path_value)
    if resolved is None:
        return None
    artifacts_root = repo_root / "artifacts"
    if not _is_path_inside(artifacts_root, resolved):
        return None
    return resolved


def _load_json_file(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_quick_summary(path: Path | None) -> dict[str, str | None]:
    result = {
        "verdict": None,
        "likely_limit": None,
        "next_action": None,
    }
    if path is None or not path.exists():
        return result

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return result

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if line.startswith("Final verdict: "):
            result["verdict"] = line.removeprefix("Final verdict: ").strip()
        elif line.startswith("Likely limit: "):
            result["likely_limit"] = line.removeprefix("Likely limit: ").strip()
        elif line.startswith("Next action: "):
            result["next_action"] = line.removeprefix("Next action: ").strip()
    return result


def _extract_config_names(configs_dir_snapshot: dict[str, Any]) -> list[str]:
    configs = configs_dir_snapshot.get("configs") or []
    names: list[str] = []
    for item in configs:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            config_name = item.get("config_name")
            if isinstance(config_name, str):
                names.append(config_name)
    return names


def _summarize_dataset_ids(run_rows: list[dict[str, Any]]) -> tuple[list[str], str]:
    dataset_ids = sorted(
        {
            str(row["dataset_catalog_id"])
            for row in run_rows
            if row.get("dataset_catalog_id") is not None
        }
    )
    if not dataset_ids:
        return [], "unknown"
    if len(dataset_ids) == 1:
        return dataset_ids, dataset_ids[0]
    return dataset_ids, "multiple datasets"


def _select_primary_config_name(config_names: list[str], fallback_name: str | None) -> str:
    if fallback_name:
        return fallback_name
    if len(config_names) == 1:
        return config_names[0]
    if config_names:
        return f"{len(config_names)} configs"
    return "unknown"


def _reuse_overview_message(
    *,
    reused_count: int,
    fresh_success_count: int,
    failed_count: int,
) -> str:
    if reused_count > 0:
        return f"Matched prior completed executions were reused for {reused_count} seed(s)."
    if fresh_success_count > 0 and failed_count == 0:
        return "No prior completed execution was reused for this campaign."
    if fresh_success_count > 0 or failed_count > 0:
        return "No prior completed execution was reused before the fresh execution attempts in this campaign."
    return "Reuse outcome is not available."


def _load_external_rows(
    evaluation_row: dict[str, Any] | None,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], bool]:
    if evaluation_row is None:
        return [], False
    json_artifact_path = _resolve_repo_path(repo_root, evaluation_row.get("json_artifact_path"))
    rows = _load_json_file(json_artifact_path)
    if not isinstance(rows, list):
        return [], False
    return [row for row in rows if isinstance(row, dict)], True


@dataclass(frozen=True)
class CampaignSummaryView:
    campaign_id: str
    multiseed_run_id: int
    config_name: str
    config_names: tuple[str, ...]
    dataset_label: str
    dataset_catalog_ids: tuple[str, ...]
    preset_name: str | None
    created_at: str
    status: str
    seeds_planned: int
    seeds_completed: int
    seeds_reused: int
    runs_failed: int
    mean_score: float | None
    score_std_dev: float | None
    champion_count: int
    train_to_validation_survival_rate: float | None
    validation_to_external_survival_rate: float | None
    verdict: str | None
    likely_limit: str | None
    next_action: str | None
    has_quick_summary: bool
    quick_summary_source: str | None
    has_external_evaluation: bool
    external_artifact_available: bool
    has_champion: bool
    champion_classification: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "multiseed_run_id": self.multiseed_run_id,
            "config_name": self.config_name,
            "config_names": list(self.config_names),
            "dataset_label": self.dataset_label,
            "dataset_catalog_ids": list(self.dataset_catalog_ids),
            "preset_name": self.preset_name,
            "created_at": self.created_at,
            "status": self.status,
            "seeds_planned": self.seeds_planned,
            "seeds_completed": self.seeds_completed,
            "seeds_reused": self.seeds_reused,
            "runs_failed": self.runs_failed,
            "mean_score": self.mean_score,
            "score_std_dev": self.score_std_dev,
            "champion_count": self.champion_count,
            "train_to_validation_survival_rate": self.train_to_validation_survival_rate,
            "validation_to_external_survival_rate": self.validation_to_external_survival_rate,
            "verdict": self.verdict,
            "likely_limit": self.likely_limit,
            "next_action": self.next_action,
            "has_quick_summary": self.has_quick_summary,
            "quick_summary_source": self.quick_summary_source,
            "has_external_evaluation": self.has_external_evaluation,
            "external_artifact_available": self.external_artifact_available,
            "has_champion": self.has_champion,
            "champion_classification": self.champion_classification,
        }


@dataclass(frozen=True)
class CampaignExecutionView:
    run_id: str
    seed: int
    status: str
    train_score: float | None
    validation_score: float | None
    external_score: float | None
    champion_classification: str | None
    external_status: str | None
    reuse_status: str | None
    reuse_reason: str | None
    reuse_reason_source: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "status": self.status,
            "train_score": self.train_score,
            "validation_score": self.validation_score,
            "external_score": self.external_score,
            "champion_classification": self.champion_classification,
            "external_status": self.external_status,
            "reuse_status": self.reuse_status,
            "reuse_reason": self.reuse_reason,
            "reuse_reason_source": self.reuse_reason_source,
        }


@dataclass(frozen=True)
class EvaluationPanelView:
    train_mean_score: float | None
    validation_mean_score: float | None
    external_mean_score: float | None
    selection_gap_mean: float | None
    validation_score_std_dev: float | None
    external_valid_count: int
    external_positive_profit_count: int
    external_rows_generated: int
    external_status: str | None
    has_external_evaluation: bool
    external_artifact_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "train_mean_score": self.train_mean_score,
            "validation_mean_score": self.validation_mean_score,
            "external_mean_score": self.external_mean_score,
            "selection_gap_mean": self.selection_gap_mean,
            "validation_score_std_dev": self.validation_score_std_dev,
            "external_valid_count": self.external_valid_count,
            "external_positive_profit_count": self.external_positive_profit_count,
            "external_rows_generated": self.external_rows_generated,
            "external_status": self.external_status,
            "has_external_evaluation": self.has_external_evaluation,
            "external_artifact_available": self.external_artifact_available,
        }


@dataclass(frozen=True)
class CampaignChampionView:
    champion_id: int | None
    classification: str | None
    score: float | None
    return_pct: float | None
    drawdown: float | None
    profit_factor: float | None
    trades: float | None
    stack_label: str | None
    config_name: str | None
    source: str | None
    traceability: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "champion_id": self.champion_id,
            "classification": self.classification,
            "score": self.score,
            "return_pct": self.return_pct,
            "drawdown": self.drawdown,
            "profit_factor": self.profit_factor,
            "trades": self.trades,
            "stack_label": self.stack_label,
            "config_name": self.config_name,
            "source": self.source,
            "traceability": dict(self.traceability) if self.traceability is not None else None,
        }


@dataclass(frozen=True)
class CampaignDetailView:
    summary: CampaignSummaryView
    champion: CampaignChampionView | None
    executions: tuple[CampaignExecutionView, ...]
    evaluation: EvaluationPanelView
    reuse_overview: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "champion": self.champion.to_dict() if self.champion is not None else None,
            "executions": [item.to_dict() for item in self.executions],
            "evaluation": self.evaluation.to_dict(),
            "reuse_overview": dict(self.reuse_overview),
        }


@dataclass(frozen=True)
class CampaignComparisonEntry:
    campaign_id: str
    config_name: str
    dataset_label: str
    mean_score: float | None
    score_std_dev: float | None
    train_to_validation_survival_rate: float | None
    validation_to_external_survival_rate: float | None
    champion_classification: str | None
    champion_score: float | None
    champion_return_pct: float | None
    champion_drawdown: float | None
    champion_trades: float | None
    verdict: str | None
    has_champion: bool
    has_external_evaluation: bool
    external_artifact_available: bool
    has_quick_summary: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "config_name": self.config_name,
            "dataset_label": self.dataset_label,
            "mean_score": self.mean_score,
            "score_std_dev": self.score_std_dev,
            "train_to_validation_survival_rate": self.train_to_validation_survival_rate,
            "validation_to_external_survival_rate": self.validation_to_external_survival_rate,
            "champion_classification": self.champion_classification,
            "champion_score": self.champion_score,
            "champion_return_pct": self.champion_return_pct,
            "champion_drawdown": self.champion_drawdown,
            "champion_trades": self.champion_trades,
            "verdict": self.verdict,
            "has_champion": self.has_champion,
            "has_external_evaluation": self.has_external_evaluation,
            "external_artifact_available": self.external_artifact_available,
            "has_quick_summary": self.has_quick_summary,
        }


@dataclass(frozen=True)
class ExecutionMonitorItem:
    job_id: str
    campaign_id: str
    config_name: str
    preset_name: str | None
    launched_at: str
    status: str
    seeds_finished: int
    seeds_total: int
    seeds_remaining: int
    seeds_running: int
    requested_parallel_workers: int
    effective_parallel_workers: int
    generation_progress: str | None
    results_path: str | None
    is_recent: bool
    is_active: bool
    can_cancel: bool
    queue_position: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "campaign_id": self.campaign_id,
            "config_name": self.config_name,
            "preset_name": self.preset_name,
            "launched_at": self.launched_at,
            "status": self.status,
            "seeds_finished": self.seeds_finished,
            "seeds_total": self.seeds_total,
            "seeds_remaining": self.seeds_remaining,
            "seeds_running": self.seeds_running,
            "requested_parallel_workers": self.requested_parallel_workers,
            "effective_parallel_workers": self.effective_parallel_workers,
            "generation_progress": self.generation_progress,
            "results_path": self.results_path,
            "is_recent": self.is_recent,
            "is_active": self.is_active,
            "can_cancel": self.can_cancel,
            "queue_position": self.queue_position,
        }


@dataclass(frozen=True)
class DeletedCampaignResult:
    campaign_id: str
    deleted_row_counts: dict[str, int]
    deleted_artifact_paths: tuple[str, ...]
    missing_artifact_paths: tuple[str, ...]
    artifact_delete_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "deleted_row_counts": dict(self.deleted_row_counts),
            "deleted_artifact_paths": list(self.deleted_artifact_paths),
            "missing_artifact_paths": list(self.missing_artifact_paths),
            "artifact_delete_failures": list(self.artifact_delete_failures),
        }


@dataclass(frozen=True)
class CancelledQueueJobView:
    job_id: str
    campaign_id: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "campaign_id": self.campaign_id,
            "status": self.status,
        }


class RunsResultsApplicationService:
    """Application-facing service for persisted multiseed campaigns.

    This layer stays intentionally conservative:
    - it reads canonical persistence rows and persisted reporting artifacts
    - it does not re-evaluate, rescore, or invent new runtime behavior
    - the only write operation exposed here is explicit campaign deletion
      for operator cleanup
    """

    def __init__(
        self,
        database_path: str | Path = DEFAULT_PERSISTENCE_DB_PATH,
        *,
        repo_root: Path | None = None,
        queue_service: ExecutionQueueService | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.queue_service = queue_service or ExecutionQueueService(
            database_path=self.database_path,
            repo_root=self.repo_root,
        )

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

    def list_campaigns(self, *, limit: int = 50) -> list[CampaignSummaryView]:
        campaign_rows = self._fetch_campaign_rows(limit=limit)
        return [self._build_campaign_summary(row) for row in campaign_rows]

    def get_campaign(self, campaign_id: str) -> CampaignDetailView | None:
        campaign_row = self._fetch_campaign_row(campaign_id)
        if campaign_row is None:
            return None

        summary = self._build_campaign_summary(campaign_row)
        run_rows = self._fetch_run_rows(campaign_row["id"])
        champion_analysis_row = self._fetch_latest_champion_analysis(campaign_row["id"])
        external_evaluation_row = self._fetch_latest_evaluation(campaign_row["id"], "external")
        external_rows, external_artifact_available = _load_external_rows(
            external_evaluation_row,
            self.repo_root,
        )
        external_rows_by_run_id = {
            str(row["run_id"]): row
            for row in external_rows
            if isinstance(row, dict) and row.get("run_id") is not None
        }
        champion_rows = self._fetch_champion_rows(campaign_row["id"])
        champion_by_run_id = {
            str(row["run_id"]): row
            for row in champion_rows
        }

        executions = tuple(
            CampaignExecutionView(
                run_id=str(run_row["run_id"]),
                seed=int(run_row["effective_seed"]),
                status=str(run_row["status"]),
                train_score=_safe_float((run_row.get("summary_json") or {}).get("best_train_selection_score")),
                validation_score=_safe_float(
                    (run_row.get("summary_json") or {}).get("final_validation_selection_score")
                ),
                external_score=_safe_float(
                    external_rows_by_run_id.get(str(run_row["run_id"]), {}).get(
                        "external_validation_selection"
                    )
                ),
                champion_classification=champion_by_run_id.get(str(run_row["run_id"]), {}).get(
                    "champion_type"
                ),
                external_status=(
                    "evaluated"
                    if str(run_row["run_id"]) in external_rows_by_run_id
                    else None
                ),
                reuse_status=self._build_execution_reuse_status(run_row),
                reuse_reason=self._build_execution_reuse_reason(run_row),
                reuse_reason_source=self._build_execution_reuse_reason_source(run_row),
            )
            for run_row in run_rows
        )

        champion = self._build_campaign_champion(champion_analysis_row, champion_rows)
        evaluation = self._build_evaluation_panel(
            run_rows,
            external_evaluation_row,
            external_artifact_available=external_artifact_available,
        )

        return CampaignDetailView(
            summary=summary,
            champion=champion,
            executions=executions,
            evaluation=evaluation,
            reuse_overview=self._build_campaign_reuse_overview(summary),
        )

    def compare_campaigns(self, campaign_ids: list[str]) -> list[CampaignComparisonEntry]:
        entries: list[CampaignComparisonEntry] = []
        for campaign_id in campaign_ids:
            detail = self.get_campaign(campaign_id)
            if detail is None:
                continue
            entries.append(
                CampaignComparisonEntry(
                    campaign_id=detail.summary.campaign_id,
                    config_name=detail.summary.config_name,
                    dataset_label=detail.summary.dataset_label,
                    mean_score=detail.summary.mean_score,
                    score_std_dev=detail.summary.score_std_dev,
                    train_to_validation_survival_rate=detail.summary.train_to_validation_survival_rate,
                    validation_to_external_survival_rate=detail.summary.validation_to_external_survival_rate,
                    champion_classification=(
                        detail.champion.classification if detail.champion is not None else None
                    ),
                    champion_score=detail.champion.score if detail.champion is not None else None,
                    champion_return_pct=(
                        detail.champion.return_pct if detail.champion is not None else None
                    ),
                    champion_drawdown=(
                        detail.champion.drawdown if detail.champion is not None else None
                    ),
                    champion_trades=detail.champion.trades if detail.champion is not None else None,
                    verdict=detail.summary.verdict,
                    has_champion=detail.summary.has_champion,
                    has_external_evaluation=detail.summary.has_external_evaluation,
                    external_artifact_available=detail.summary.external_artifact_available,
                    has_quick_summary=detail.summary.has_quick_summary,
                )
            )
        return entries

    def list_execution_monitor_items(self, *, limit: int = 6) -> list[ExecutionMonitorItem]:
        self.queue_service.reconcile_and_dispatch()
        queue_jobs = self._fetch_execution_queue_jobs(limit=max(limit * 4, limit * 2))
        items: list[ExecutionMonitorItem] = []
        queued_positions = {
            str(job["queue_job_uid"]): index + 1
            for index, job in enumerate(
                self.queue_service.store.load_execution_queue_jobs(statuses=["queued"])
            )
        }

        for job in queue_jobs:
            item = self._build_monitor_item_from_queue_job(
                job,
                queue_position=queued_positions.get(str(job["queue_job_uid"])),
            )
            if item is None:
                continue
            items.append(item)
            if len(items) >= limit:
                break

        represented_campaign_ids = {item.campaign_id for item in items}
        if len(items) < limit:
            campaign_rows = self._fetch_campaign_rows(limit=max(limit * 3, limit))
            for campaign_row in campaign_rows:
                if str(campaign_row["multiseed_run_uid"]) in represented_campaign_ids:
                    continue
                item = self._build_execution_monitor_item(campaign_row)
                if item is None:
                    continue
                items.append(item)
                if len(items) >= limit:
                    break
        return items

    def delete_campaign(self, campaign_id: str) -> DeletedCampaignResult | None:
        queued_jobs = [
            job
            for job in self._fetch_execution_queue_jobs(limit=200)
            if str(job["campaign_id"]) == campaign_id
        ]
        if any(str(job.get("status") or "") in RUNNING_QUEUE_JOB_STATUSES for job in queued_jobs):
            raise ValueError(
                "Campaign still has an active queued execution job and cannot be deleted yet."
            )
        campaign_row = self._fetch_campaign_row(campaign_id)
        if campaign_row is None:
            return None

        run_rows = self._fetch_run_rows(int(campaign_row["id"]))
        if str(campaign_row.get("status") or "") == "running" or any(
            str(row.get("status") or "") == "running" for row in run_rows
        ):
            raise ValueError(
                "Campaign is still running in canonical persistence and cannot be deleted yet."
            )

        artifact_paths = self._collect_campaign_artifact_paths(campaign_row, run_rows=run_rows)
        deleted_row_counts = PersistenceStore(self.database_path).delete_multiseed_run(
            int(campaign_row["id"])
        )
        deleted_row_counts["execution_queue_jobs"] = PersistenceStore(
            self.database_path
        ).delete_execution_queue_jobs_for_campaign(campaign_id)

        deleted_artifact_paths: list[str] = []
        missing_artifact_paths: list[str] = []
        artifact_delete_failures: list[str] = []

        for path in artifact_paths:
            relative_path = path.relative_to(self.repo_root).as_posix()
            if not path.exists():
                missing_artifact_paths.append(relative_path)
                continue
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted_artifact_paths.append(relative_path)
            except OSError:
                artifact_delete_failures.append(relative_path)

        return DeletedCampaignResult(
            campaign_id=campaign_id,
            deleted_row_counts=deleted_row_counts,
            deleted_artifact_paths=tuple(deleted_artifact_paths),
            missing_artifact_paths=tuple(missing_artifact_paths),
            artifact_delete_failures=tuple(artifact_delete_failures),
        )

    def cancel_queued_job(self, job_id: str) -> CancelledQueueJobView | None:
        result = self.queue_service.cancel_queued_job(job_id)
        if result is None:
            return None
        return CancelledQueueJobView(
            job_id=result.job_id,
            campaign_id=result.campaign_id,
            status=result.status,
        )

    def _build_campaign_reuse_overview(
        self,
        summary: CampaignSummaryView,
    ) -> dict[str, Any]:
        reused_count = int(summary.seeds_reused)
        fresh_success_count = max(int(summary.seeds_completed) - reused_count, 0)
        failed_count = int(summary.runs_failed)
        return {
            "reused_count": reused_count,
            "fresh_success_count": fresh_success_count,
            "failed_count": failed_count,
            "message": _reuse_overview_message(
                reused_count=reused_count,
                fresh_success_count=fresh_success_count,
                failed_count=failed_count,
            ),
            "reason_scope_note": (
                "Per-seed reuse reasons are only available for executions that persisted a new run row."
            ),
        }

    def _build_execution_reuse_status(self, run_row: dict[str, Any]) -> str:
        execution_status = str(
            (run_row.get("summary_json") or {}).get("execution_status") or "executed"
        ).strip().lower()
        if execution_status == "reused":
            return "matched prior completed execution"
        return "fresh execution"

    def _build_execution_reuse_reason(self, run_row: dict[str, Any]) -> str:
        reason, _ = self._derive_execution_reuse_reason(run_row)
        return reason

    def _build_execution_reuse_reason_source(self, run_row: dict[str, Any]) -> str:
        _, source = self._derive_execution_reuse_reason(run_row)
        return source

    def _derive_execution_reuse_reason(self, run_row: dict[str, Any]) -> tuple[str, str]:
        if self._build_execution_reuse_status(run_row) == "matched prior completed execution":
            return (
                "Matched prior completed execution.",
                "exact_persisted_summary",
            )

        row_id = int(run_row["id"])
        exact_prior_rows = self._find_prior_run_rows(
            """
            execution_fingerprint = ?
            """,
            (str(run_row["execution_fingerprint"]),),
            current_row_id=row_id,
        )
        if any(str(row.get("status") or "") == "completed" for row in exact_prior_rows):
            return (
                "A prior completed match already existed before this execution, so reuse was expected but not applied.",
                "exact_prior_row",
            )
        if exact_prior_rows:
            return (
                "Previous matching execution existed but was not completed.",
                "exact_prior_row",
            )

        config_hash = str(run_row["config_hash"])
        effective_seed = int(run_row["effective_seed"])
        dataset_signature = str(run_row["dataset_signature"])
        logic_version = str(run_row["logic_version"])

        previous_logic_rows = self._find_prior_run_rows(
            """
            config_hash = ? AND effective_seed = ? AND dataset_signature = ? AND logic_version != ?
            """,
            (config_hash, effective_seed, dataset_signature, logic_version),
            current_row_id=row_id,
        )
        if any(str(row.get("status") or "") == "completed" for row in previous_logic_rows):
            return (
                "Matching execution existed under a different logic version.",
                "derived_prior_match",
            )

        previous_dataset_rows = self._find_prior_run_rows(
            """
            config_hash = ? AND effective_seed = ? AND logic_version = ? AND dataset_signature != ?
            """,
            (config_hash, effective_seed, logic_version, dataset_signature),
            current_row_id=row_id,
        )
        if any(str(row.get("status") or "") == "completed" for row in previous_dataset_rows):
            return (
                "Matching config and seed existed under a different dataset signature.",
                "derived_prior_match",
            )

        previous_seed_rows = self._find_prior_run_rows(
            """
            config_hash = ? AND dataset_signature = ? AND logic_version = ? AND effective_seed != ?
            """,
            (config_hash, dataset_signature, logic_version, effective_seed),
            current_row_id=row_id,
        )
        if any(str(row.get("status") or "") == "completed" for row in previous_seed_rows):
            return (
                "Matching config and dataset existed under a different seed.",
                "derived_prior_match",
            )

        return (
            "No matching completed execution was found.",
            "exact_no_completed_match",
        )

    def _find_prior_run_rows(
        self,
        where_clause: str,
        parameters: tuple[Any, ...],
        *,
        current_row_id: int,
    ) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM run_executions
                WHERE id < ? AND {where_clause}
                ORDER BY id DESC
                LIMIT 25
                """,
                (current_row_id, *parameters),
            ).fetchall()
        return [_row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS) for row in rows]

    def _fetch_campaign_rows(self, *, limit: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM multiseed_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_dict(row, MULTISEED_RUNS_JSON_COLUMNS) for row in rows]

    def _fetch_execution_queue_jobs(self, *, limit: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_queue_jobs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_dict(row, EXECUTION_QUEUE_JOBS_JSON_COLUMNS) for row in rows]

    def _fetch_campaign_row(self, campaign_id: str) -> dict[str, Any] | None:
        with self._connect_readonly() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM multiseed_runs
                WHERE multiseed_run_uid = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row, MULTISEED_RUNS_JSON_COLUMNS)

    def _fetch_run_rows(self, multiseed_run_id: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM run_executions
                WHERE multiseed_run_id = ?
                ORDER BY effective_seed ASC, id ASC
                """,
                (multiseed_run_id,),
            ).fetchall()
        return [_row_to_dict(row, RUN_EXECUTIONS_JSON_COLUMNS) for row in rows]

    def _build_monitor_item_from_queue_job(
        self,
        job: dict[str, Any],
        *,
        queue_position: int | None,
    ) -> ExecutionMonitorItem | None:
        status = str(job.get("status") or "unknown")
        campaign_row = self._fetch_campaign_row(str(job["campaign_id"]))
        run_rows: list[dict[str, Any]] = []
        launched_at = str(job.get("started_at") or job.get("created_at") or "")
        if campaign_row is not None:
            run_rows = self._fetch_run_rows(int(campaign_row["id"]))
            launched_at = str(campaign_row.get("started_at") or launched_at)
            seeds_finished = (
                int(campaign_row.get("runs_completed") or 0)
                + int(campaign_row.get("runs_reused") or 0)
                + int(campaign_row.get("runs_failed") or 0)
            )
            seeds_total = int(campaign_row.get("runs_planned") or 0)
            requested_parallel_workers = int(campaign_row.get("requested_parallel_workers") or 1)
            effective_parallel_workers = int(campaign_row.get("effective_parallel_workers") or 1)
            generation_progress = self._build_generation_progress_label(run_rows)
            results_path = f"/results/{job['campaign_id']}"
            is_active = status in RUNNING_QUEUE_JOB_STATUSES
        else:
            seeds_total = self.queue_service.build_job_seed_total(job)
            seeds_finished = 0
            requested_parallel_workers = int(job.get("parallel_workers") or 1)
            effective_parallel_workers = requested_parallel_workers
            generation_progress = None
            results_path = None
            is_active = status in {"queued", *RUNNING_QUEUE_JOB_STATUSES}

        try:
            parsed = datetime.fromisoformat(launched_at.replace("Z", "+00:00"))
            is_recent = (datetime.now(timezone.utc) - parsed).total_seconds() <= 3600
        except ValueError:
            is_recent = status not in FINAL_QUEUE_JOB_STATUSES

        if not is_active and not is_recent:
            return None

        return ExecutionMonitorItem(
            job_id=str(job["queue_job_uid"]),
            campaign_id=str(job["campaign_id"]),
            config_name=str(job.get("config_name") or "unknown"),
            preset_name=job.get("experiment_preset_name"),
            launched_at=launched_at,
            status=status,
            seeds_finished=seeds_finished,
            seeds_total=seeds_total,
            seeds_remaining=max(seeds_total - seeds_finished, 0),
            seeds_running=sum(1 for row in run_rows if str(row.get("status") or "") == "running"),
            requested_parallel_workers=requested_parallel_workers,
            effective_parallel_workers=effective_parallel_workers,
            generation_progress=generation_progress,
            results_path=results_path,
            is_recent=is_recent,
            is_active=is_active,
            can_cancel=status == "queued",
            queue_position=queue_position if status == "queued" else None,
        )

    def _fetch_champion_rows(self, multiseed_run_id: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT c.*
                FROM champions c
                INNER JOIN run_executions re ON re.id = c.run_execution_id
                WHERE re.multiseed_run_id = ?
                ORDER BY c.id ASC
                """,
                (multiseed_run_id,),
            ).fetchall()
        return [_row_to_dict(row, CHAMPIONS_JSON_COLUMNS) for row in rows]

    def _fetch_latest_champion_analysis(self, multiseed_run_id: int) -> dict[str, Any] | None:
        with self._connect_readonly() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM champion_analyses
                WHERE multiseed_run_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (multiseed_run_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row, CHAMPION_ANALYSES_JSON_COLUMNS)

    def _fetch_latest_evaluation(
        self,
        multiseed_run_id: int,
        evaluation_type: str,
    ) -> dict[str, Any] | None:
        with self._connect_readonly() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM champion_evaluations
                WHERE multiseed_run_id = ? AND evaluation_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (multiseed_run_id, evaluation_type),
            ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row, CHAMPION_EVALUATIONS_JSON_COLUMNS)

    def _fetch_champion_analysis_rows(self, multiseed_run_id: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM champion_analyses
                WHERE multiseed_run_id = ?
                ORDER BY id DESC
                """,
                (multiseed_run_id,),
            ).fetchall()
        return [_row_to_dict(row, CHAMPION_ANALYSES_JSON_COLUMNS) for row in rows]

    def _fetch_champion_evaluation_rows(self, multiseed_run_id: int) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM champion_evaluations
                WHERE multiseed_run_id = ?
                ORDER BY id DESC
                """,
                (multiseed_run_id,),
            ).fetchall()
        return [_row_to_dict(row, CHAMPION_EVALUATIONS_JSON_COLUMNS) for row in rows]

    def _build_campaign_summary(self, campaign_row: dict[str, Any]) -> CampaignSummaryView:
        run_rows = self._fetch_run_rows(int(campaign_row["id"]))
        champion_rows = self._fetch_champion_rows(int(campaign_row["id"]))
        champion_analysis_row = self._fetch_latest_champion_analysis(int(campaign_row["id"]))
        external_evaluation_row = self._fetch_latest_evaluation(int(campaign_row["id"]), "external")

        scores = [
            score
            for score in (
                _safe_float((row.get("summary_json") or {}).get("final_validation_selection_score"))
                for row in run_rows
            )
            if score is not None
        ]
        config_names = _extract_config_names(campaign_row.get("configs_dir_snapshot_json") or {})
        dataset_catalog_ids, dataset_label = _summarize_dataset_ids(run_rows)
        quick_summary = _parse_quick_summary(
            _resolve_repo_path(self.repo_root, campaign_row.get("quick_summary_artifact_path"))
        )
        champion_card = (
            ((champion_analysis_row or {}).get("analysis_summary_json") or {}).get("champion_card")
        )
        champion_type = champion_card.get("type") if isinstance(champion_card, dict) else None
        _, external_artifact_available = _load_external_rows(
            external_evaluation_row,
            self.repo_root,
        )
        external_mean_summary = (
            ((external_evaluation_row or {}).get("evaluation_summary_json") or {}).get("mean_summary")
            or {}
        )
        champion_count = len(champion_rows)
        runs_completed = int(campaign_row["runs_completed"])
        external_valid_count = int(external_mean_summary.get("valid_count") or 0)

        return CampaignSummaryView(
            campaign_id=str(campaign_row["multiseed_run_uid"]),
            multiseed_run_id=int(campaign_row["id"]),
            config_name=_select_primary_config_name(config_names, None),
            config_names=tuple(config_names),
            dataset_label=dataset_label,
            dataset_catalog_ids=tuple(dataset_catalog_ids),
            preset_name=campaign_row.get("preset_name"),
            created_at=str(campaign_row["started_at"]),
            status=str(campaign_row["status"]),
            seeds_planned=int(campaign_row["runs_planned"]),
            seeds_completed=runs_completed,
            seeds_reused=int(campaign_row["runs_reused"]),
            runs_failed=int(campaign_row["runs_failed"]),
            mean_score=_mean(scores),
            score_std_dev=_population_std(scores),
            champion_count=champion_count,
            train_to_validation_survival_rate=(
                champion_count / runs_completed if runs_completed > 0 else None
            ),
            validation_to_external_survival_rate=(
                external_valid_count / champion_count if champion_count > 0 else None
            ),
            verdict=quick_summary["verdict"],
            likely_limit=quick_summary["likely_limit"],
            next_action=quick_summary["next_action"],
            has_quick_summary=any(value is not None for value in quick_summary.values()),
            quick_summary_source=(
                "persisted_quick_summary"
                if any(value is not None for value in quick_summary.values())
                else None
            ),
            has_external_evaluation=external_evaluation_row is not None,
            external_artifact_available=external_artifact_available,
            has_champion=champion_count > 0,
            champion_classification=champion_type if isinstance(champion_type, str) else None,
        )

    def _build_execution_monitor_item(
        self,
        campaign_row: dict[str, Any],
    ) -> ExecutionMonitorItem | None:
        run_rows = self._fetch_run_rows(int(campaign_row["id"]))
        status = str(campaign_row.get("status") or "unknown")
        is_active = status == "running" or any(str(row.get("status") or "") == "running" for row in run_rows)

        try:
            parsed = datetime.fromisoformat(str(campaign_row["started_at"]).replace("Z", "+00:00"))
            is_recent = (datetime.now(timezone.utc) - parsed).total_seconds() <= 3600
        except ValueError:
            is_recent = False

        if not is_active and not is_recent:
            return None

        config_names = _extract_config_names(campaign_row.get("configs_dir_snapshot_json") or {})
        seeds_finished = (
            int(campaign_row.get("runs_completed") or 0)
            + int(campaign_row.get("runs_reused") or 0)
            + int(campaign_row.get("runs_failed") or 0)
        )
        seeds_total = int(campaign_row.get("runs_planned") or 0)

        return ExecutionMonitorItem(
            job_id=f"campaign:{campaign_row['multiseed_run_uid']}",
            campaign_id=str(campaign_row["multiseed_run_uid"]),
            config_name=_select_primary_config_name(config_names, None),
            preset_name=campaign_row.get("preset_name"),
            launched_at=str(campaign_row["started_at"]),
            status=status,
            seeds_finished=seeds_finished,
            seeds_total=seeds_total,
            seeds_remaining=max(seeds_total - seeds_finished, 0),
            seeds_running=sum(1 for row in run_rows if str(row.get("status") or "") == "running"),
            requested_parallel_workers=int(campaign_row.get("requested_parallel_workers") or 1),
            effective_parallel_workers=int(campaign_row.get("effective_parallel_workers") or 1),
            generation_progress=self._build_generation_progress_label(run_rows),
            results_path=f"/results/{campaign_row['multiseed_run_uid']}",
            is_recent=is_recent,
            is_active=is_active,
            can_cancel=False,
            queue_position=None,
        )

    def _build_generation_progress_label(self, run_rows: list[dict[str, Any]]) -> str | None:
        progress_lines: list[str] = []
        for row in run_rows:
            if str(row.get("status") or "") != "running":
                continue
            progress_path = _safe_artifact_path(
                self.repo_root,
                row.get("progress_snapshot_artifact_path"),
            )
            if progress_path is None:
                continue
            snapshot = read_progress_snapshot(progress_path)
            if snapshot is None:
                continue
            progress_lines.append(
                format_active_job_progress(
                    snapshot,
                    fallback_label=str(row.get("config_name") or row.get("run_id") or "run"),
                )
            )
        if not progress_lines:
            return None
        if len(progress_lines) == 1:
            return progress_lines[0].removeprefix("- ").strip()
        return f"{progress_lines[0].removeprefix('- ').strip()} + {len(progress_lines) - 1} more active seed"

    def _collect_campaign_artifact_paths(
        self,
        campaign_row: dict[str, Any],
        *,
        run_rows: list[dict[str, Any]] | None = None,
    ) -> list[Path]:
        multiseed_run_id = int(campaign_row["id"])
        resolved_paths: list[Path] = []

        for key in (
            "artifacts_root_path",
            "summary_artifact_path",
            "quick_summary_artifact_path",
            "champions_summary_artifact_path",
        ):
            path = _safe_artifact_path(self.repo_root, campaign_row.get(key))
            if path is not None:
                resolved_paths.append(path)

        effective_run_rows = run_rows if run_rows is not None else self._fetch_run_rows(multiseed_run_id)
        for row in effective_run_rows:
            for key in (
                "log_artifact_path",
                "progress_snapshot_artifact_path",
                "per_run_summary_artifact_path",
            ):
                path = _safe_artifact_path(self.repo_root, row.get(key))
                if path is not None:
                    resolved_paths.append(path)

        for row in self._fetch_champion_rows(multiseed_run_id):
            for key in ("champion_card_artifact_path", "serialized_snapshot_artifact_path"):
                path = _safe_artifact_path(self.repo_root, row.get(key))
                if path is not None:
                    resolved_paths.append(path)

        for row in self._fetch_champion_analysis_rows(multiseed_run_id):
            for key in (
                "output_dir_artifact_path",
                "flat_csv_artifact_path",
                "report_artifact_path",
                "patterns_artifact_path",
                "champion_card_artifact_path",
            ):
                path = _safe_artifact_path(self.repo_root, row.get(key))
                if path is not None:
                    resolved_paths.append(path)

        for row in self._fetch_champion_evaluation_rows(multiseed_run_id):
            for key in (
                "output_dir_artifact_path",
                "flat_csv_artifact_path",
                "json_artifact_path",
                "report_artifact_path",
                "per_champion_dir_artifact_path",
            ):
                path = _safe_artifact_path(self.repo_root, row.get(key))
                if path is not None:
                    resolved_paths.append(path)

        unique_paths = sorted(
            {path.resolve() for path in resolved_paths},
            key=lambda item: (0 if item.is_dir() else 1, -len(item.parts)),
        )
        filtered_paths: list[Path] = []
        for path in unique_paths:
            if any(existing.is_dir() and _is_path_inside(existing, path) for existing in filtered_paths):
                continue
            filtered_paths.append(path)
        return filtered_paths

    def _build_campaign_champion(
        self,
        champion_analysis_row: dict[str, Any] | None,
        champion_rows: list[dict[str, Any]],
    ) -> CampaignChampionView | None:
        analysis_summary = (champion_analysis_row or {}).get("analysis_summary_json") or {}
        champion_card = analysis_summary.get("champion_card")
        if isinstance(champion_card, dict) and champion_card:
            scores = champion_card.get("scores") or {}
            modular_identity = champion_card.get("modular_identity") or {}
            return CampaignChampionView(
                champion_id=_safe_int(champion_card.get("champion_id")),
                classification=champion_card.get("type"),
                score=_safe_float(scores.get("validation_selection")),
                return_pct=_safe_float(scores.get("validation_profit")),
                drawdown=_safe_float(scores.get("validation_drawdown")),
                profit_factor=None,
                trades=_safe_float(scores.get("validation_trades")),
                stack_label=modular_identity.get("stack_label"),
                config_name=champion_card.get("config_name"),
                source="champion_analysis",
                traceability=champion_card.get("traceability"),
            )

        if not champion_rows:
            return None

        best_row = max(
            champion_rows,
            key=lambda row: _safe_float((row.get("validation_metrics_json") or {}).get("selection_score")) or float("-inf"),
        )
        fallback_card = build_champion_card(
            {
                "id": best_row.get("id"),
                "config_name": best_row.get("config_name"),
                "mutation_seed": best_row.get("mutation_seed"),
                "champion_type": best_row.get("champion_type"),
                "validation_selection": (best_row.get("validation_metrics_json") or {}).get("selection_score"),
                "validation_profit": (best_row.get("validation_metrics_json") or {}).get("median_profit"),
                "validation_drawdown": (best_row.get("validation_metrics_json") or {}).get("median_drawdown"),
                "validation_trades": (best_row.get("validation_metrics_json") or {}).get("median_trades"),
                "selection_gap": (best_row.get("champion_metrics_json") or {}).get("selection_gap"),
                "signal_pack_name": "unknown",
                "genome_schema_name": "unknown",
                "gene_type_catalog_name": "unknown",
                "decision_policy_name": "unknown",
                "mutation_profile_name": "unknown",
                "market_mode_name": "unknown",
                "leverage": None,
                "modular_stack_label": "unknown",
                "logic_version": best_row.get("logic_version"),
                "config_hash": best_row.get("config_hash"),
                "config_json_snapshot": best_row.get("config_json_snapshot"),
                "experimental_space_snapshot": best_row.get("experimental_space_snapshot_json"),
            }
        )
        scores = fallback_card.get("scores") or {}
        modular_identity = fallback_card.get("modular_identity") or {}
        return CampaignChampionView(
            champion_id=_safe_int(fallback_card.get("champion_id")),
            classification=fallback_card.get("type"),
            score=_safe_float(scores.get("validation_selection")),
            return_pct=_safe_float(scores.get("validation_profit")),
            drawdown=_safe_float(scores.get("validation_drawdown")),
            profit_factor=None,
            trades=_safe_float(scores.get("validation_trades")),
            stack_label=modular_identity.get("stack_label"),
            config_name=fallback_card.get("config_name"),
            source="champion_row_fallback",
            traceability=fallback_card.get("traceability"),
        )

    def _build_evaluation_panel(
        self,
        run_rows: list[dict[str, Any]],
        external_evaluation_row: dict[str, Any] | None,
        *,
        external_artifact_available: bool,
    ) -> EvaluationPanelView:
        train_scores = [
            score
            for score in (
                _safe_float((row.get("summary_json") or {}).get("best_train_selection_score"))
                for row in run_rows
            )
            if score is not None
        ]
        validation_scores = [
            score
            for score in (
                _safe_float((row.get("summary_json") or {}).get("final_validation_selection_score"))
                for row in run_rows
            )
            if score is not None
        ]
        gaps = [
            gap
            for gap in (
                _safe_float((row.get("summary_json") or {}).get("train_validation_selection_gap"))
                for row in run_rows
            )
            if gap is not None
        ]
        external_summary = (
            ((external_evaluation_row or {}).get("evaluation_summary_json") or {}).get("mean_summary")
            or {}
        )
        return EvaluationPanelView(
            train_mean_score=_mean(train_scores),
            validation_mean_score=_mean(validation_scores),
            external_mean_score=_safe_float(external_summary.get("mean_post_selection")),
            selection_gap_mean=_mean(gaps),
            validation_score_std_dev=_population_std(validation_scores),
            external_valid_count=int(external_summary.get("valid_count") or 0),
            external_positive_profit_count=int(external_summary.get("positive_profit_count") or 0),
            external_rows_generated=int(
                ((external_evaluation_row or {}).get("evaluation_summary_json") or {}).get("rows_generated")
                or 0
            ),
            external_status=external_evaluation_row.get("evaluation_origin") if external_evaluation_row else None,
            has_external_evaluation=external_evaluation_row is not None,
            external_artifact_available=external_artifact_available,
        )
