from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from evo_system.experimentation.presets import get_preset_by_name
from evo_system.storage import PersistenceStore
from evo_system.storage.persistence_store import (
    DEFAULT_PERSISTENCE_DB_PATH,
    MULTISEED_RUNS_JSON_COLUMNS,
)

if TYPE_CHECKING:
    from application.run_lab.service import SavedRunConfigResult


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_LAB_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "ui_run_lab"
MULTISEED_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "multiseed"
RUNNING_QUEUE_JOB_STATUSES = {"launching", "running"}
FINAL_QUEUE_JOB_STATUSES = {"finished", "failed", "cancelled"}
QUEUE_STARTUP_GRACE_SECONDS = 120
PROGRESS_LIVENESS_GRACE_SECONDS = 120


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


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_process_exists(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_repo_artifact_path(repo_root: Path, relative_path_value: str | None) -> Path | None:
    if not relative_path_value:
        return None
    candidate = repo_root / relative_path_value
    try:
        resolved = candidate.resolve()
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return resolved


def _campaign_to_queue_status(campaign_status: str) -> str:
    normalized = campaign_status.strip().lower()
    if normalized == "running":
        return "running"
    if normalized == "cancelled":
        return "cancelled"
    if normalized == "completed":
        return "finished"
    return "failed"


def _seed_total_from_config_payload(config_payload: dict[str, Any]) -> int:
    explicit_seeds = config_payload.get("seeds")
    if isinstance(explicit_seeds, list):
        return len(explicit_seeds)
    seed_count = config_payload.get("seed_count")
    if seed_count is None:
        return 0
    try:
        return max(int(seed_count), 0)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class SubmittedRunQueueJobResult:
    saved_config: SavedRunConfigResult
    job_id: str
    campaign_id: str
    status: str
    preset_name: str | None
    parallel_workers: int
    queue_concurrency_limit: int
    launch_log_path: str
    execution_configs_dir: str
    pid: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "saved_config": self.saved_config.to_dict(),
            "job_id": self.job_id,
            "campaign_id": self.campaign_id,
            "status": self.status,
            "preset_name": self.preset_name,
            "parallel_workers": self.parallel_workers,
            "queue_concurrency_limit": self.queue_concurrency_limit,
            "launch_log_path": self.launch_log_path,
            "execution_configs_dir": self.execution_configs_dir,
            "pid": self.pid,
        }


@dataclass(frozen=True)
class CancelledQueuedJobResult:
    job_id: str
    campaign_id: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "campaign_id": self.campaign_id,
            "status": self.status,
        }


class ExecutionQueueDispatcher:
    def __init__(
        self,
        service: "ExecutionQueueService",
        *,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self.service = service
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="execution-queue-dispatcher",
            daemon=True,
        )

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(self.poll_interval_seconds, 0.1) + 1.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.service.reconcile_and_dispatch()
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval_seconds)


class ExecutionQueueService:
    """Local persisted queue for canonical multiseed launch orchestration."""

    def __init__(
        self,
        *,
        database_path: str | Path = DEFAULT_PERSISTENCE_DB_PATH,
        repo_root: Path = REPO_ROOT,
        run_lab_artifacts_dir: Path = RUN_LAB_ARTIFACTS_DIR,
        multiseed_artifacts_dir: Path = MULTISEED_ARTIFACTS_DIR,
        launcher: Any = None,
        process_exists_checker: Callable[[int | None], bool] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.repo_root = repo_root
        self.run_lab_artifacts_dir = run_lab_artifacts_dir
        self.multiseed_artifacts_dir = multiseed_artifacts_dir
        self.store = PersistenceStore(self.database_path)
        self.store.initialize()
        self.launcher = launcher or subprocess.Popen
        self.process_exists_checker = process_exists_checker or _safe_process_exists
        self._dispatcher: ExecutionQueueDispatcher | None = None

    def get_concurrency_limit(self) -> int:
        return self.store.get_execution_queue_concurrency_limit()

    def start_background_dispatcher(
        self,
        *,
        poll_interval_seconds: float = 5.0,
    ) -> ExecutionQueueDispatcher:
        if self._dispatcher is None:
            self._dispatcher = ExecutionQueueDispatcher(
                self,
                poll_interval_seconds=poll_interval_seconds,
            )
            self._dispatcher.start()
        return self._dispatcher

    def stop_background_dispatcher(self) -> None:
        if self._dispatcher is None:
            return
        self._dispatcher.stop()
        self._dispatcher = None

    def submit_run(
        self,
        *,
        saved_config: SavedRunConfigResult,
        payload: dict[str, Any],
        queue_concurrency_limit: int | None = None,
    ) -> SubmittedRunQueueJobResult:
        preset_name = payload.get("experiment_preset_name")
        preset = (
            get_preset_by_name(str(preset_name))
            if preset_name not in {None, ""}
            else None
        )
        if preset_name not in {None, ""} and preset is None:
            raise ValueError(f"Unknown experiment preset: {preset_name}")

        parallel_workers = int(payload.get("parallel_workers") or 1)
        if parallel_workers <= 0:
            raise ValueError("Parallel workers must be greater than 0.")
        if queue_concurrency_limit is not None and int(queue_concurrency_limit) <= 0:
            raise ValueError("Queue concurrency limit must be greater than 0.")

        effective_queue_limit = (
            self.store.set_execution_queue_concurrency_limit(queue_concurrency_limit)
            if queue_concurrency_limit is not None
            else self.store.get_execution_queue_concurrency_limit()
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        config_stem = Path(saved_config.config_name).stem
        execution_dir = self.run_lab_artifacts_dir / "config_sets" / f"{timestamp}_{config_stem}"
        execution_dir.mkdir(parents=True, exist_ok=True)

        saved_config_path = self.repo_root / saved_config.config_path
        execution_config_path = execution_dir / saved_config.config_name
        shutil.copy2(saved_config_path, execution_config_path)

        multiseed_output_dir = self._reserve_multiseed_output_dir()
        campaign_id = multiseed_output_dir.name
        launch_log_path = execution_dir / "launch.log"
        queue_job_uid = self._build_queue_job_uid()

        self.store.save_execution_queue_job(
            queue_job_uid=queue_job_uid,
            campaign_id=campaign_id,
            config_name=saved_config.config_name,
            config_path=saved_config.config_path,
            config_payload_json=saved_config.config_payload,
            experiment_preset_name=preset.name if preset is not None else None,
            parallel_workers=parallel_workers,
            execution_configs_dir=execution_dir,
            launch_log_path=launch_log_path,
            multiseed_output_dir=multiseed_output_dir,
        )

        self.reconcile_and_dispatch()
        job = self.store.load_execution_queue_job(queue_job_uid)
        assert job is not None
        return SubmittedRunQueueJobResult(
            saved_config=saved_config,
            job_id=queue_job_uid,
            campaign_id=campaign_id,
            status=str(job["status"]),
            preset_name=job.get("experiment_preset_name"),
            parallel_workers=int(job["parallel_workers"]),
            queue_concurrency_limit=effective_queue_limit,
            launch_log_path=str(job["launch_log_path"]),
            execution_configs_dir=str(job["execution_configs_dir"]),
            pid=int(job["pid"]) if job.get("pid") is not None else None,
        )

    def cancel_queued_job(self, job_id: str) -> CancelledQueuedJobResult | None:
        job = self.store.load_execution_queue_job(job_id)
        if job is None:
            return None
        if str(job["status"]) != "queued":
            raise ValueError("Only queued executions can be cancelled safely.")

        self._delete_if_safe(self.run_lab_artifacts_dir, job.get("execution_configs_dir"))
        self._delete_if_safe(self.multiseed_artifacts_dir, job.get("multiseed_output_dir"))
        timestamp = _utc_now_iso()
        self.store.update_execution_queue_job(
            job_id,
            status="cancelled",
            cancelled_at=timestamp,
            completed_at=timestamp,
        )
        return CancelledQueuedJobResult(
            job_id=job_id,
            campaign_id=str(job["campaign_id"]),
            status="cancelled",
        )

    def reconcile_and_dispatch(self) -> None:
        jobs = self.store.load_execution_queue_jobs()
        for job in jobs:
            if str(job["status"]) in RUNNING_QUEUE_JOB_STATUSES:
                self._reconcile_active_job(job)

        jobs = self.store.load_execution_queue_jobs()
        active_count = sum(
            1 for job in jobs if str(job["status"]) in RUNNING_QUEUE_JOB_STATUSES
        )
        concurrency_limit = self.store.get_execution_queue_concurrency_limit()
        for job in jobs:
            if str(job["status"]) != "queued":
                continue
            if active_count >= concurrency_limit:
                break
            launched = self._launch_job(job)
            if launched:
                active_count += 1

    def _launch_job(self, job: dict[str, Any]) -> bool:
        self.store.update_execution_queue_job(
            str(job["queue_job_uid"]),
            status="launching",
            started_at=_utc_now_iso(),
        )

        command = self._build_command(job)
        launch_log_path = self.repo_root / str(job["launch_log_path"])
        launch_log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = launch_log_path.open("w", encoding="utf-8")
        try:
            process = self.launcher(
                command,
                cwd=str(self.repo_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
        except Exception as exc:
            self.store.update_execution_queue_job(
                str(job["queue_job_uid"]),
                status="failed",
                completed_at=_utc_now_iso(),
                command_json=command,
                failure_message=str(exc),
            )
            return False
        finally:
            log_handle.close()

        self.store.update_execution_queue_job(
            str(job["queue_job_uid"]),
            status="running",
            command_json=command,
            pid=int(process.pid),
        )
        return True

    def _reconcile_active_job(self, job: dict[str, Any]) -> None:
        campaign_row = self._load_campaign_row(str(job["campaign_id"]))
        run_rows = (
            self._load_run_rows(int(campaign_row["id"]))
            if campaign_row is not None
            else []
        )
        process_is_alive = self.process_exists_checker(
            int(job["pid"]) if job.get("pid") is not None else None
        )
        if campaign_row is not None:
            queue_status = _campaign_to_queue_status(str(campaign_row["status"]))
            campaign_has_running_seed = any(
                str(row.get("status") or "") == "running" for row in run_rows
            )
            if queue_status != "running" and not campaign_has_running_seed:
                self.store.update_execution_queue_job(
                    str(job["queue_job_uid"]),
                    status=queue_status,
                    completed_at=str(campaign_row.get("completed_at") or _utc_now_iso()),
                )
                return

            if process_is_alive or self._campaign_has_recent_progress(run_rows):
                if str(job["status"]) != "running":
                    self.store.update_execution_queue_job(
                        str(job["queue_job_uid"]),
                        status="running",
                    )
                return

            self._mark_campaign_interrupted(
                campaign_row,
                run_rows=run_rows,
                reason=(
                    "Persisted campaign was marked running but no live process "
                    "or recent progress was detected during queue reconciliation."
                ),
            )
            self.store.update_execution_queue_job(
                str(job["queue_job_uid"]),
                status="failed",
                completed_at=_utc_now_iso(),
                failure_message=(
                    "Queued launch no longer has a live process behind it and the "
                    "persisted campaign was reconciled as interrupted."
                ),
            )
            return

        started_at = _parse_iso_timestamp(job.get("started_at"))
        if started_at is not None:
            age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
            if age_seconds <= QUEUE_STARTUP_GRACE_SECONDS:
                return

        if process_is_alive:
            if str(job["status"]) != "running":
                self.store.update_execution_queue_job(
                    str(job["queue_job_uid"]),
                    status="running",
                )
            return

        self.store.update_execution_queue_job(
            str(job["queue_job_uid"]),
            status="failed",
            completed_at=_utc_now_iso(),
            failure_message=(
                "Queued launch did not produce a persisted campaign row and the process is no longer running."
            ),
        )

    def _build_queue_job_uid(self) -> str:
        return f"queue_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    def _reserve_multiseed_output_dir(self) -> Path:
        self.multiseed_artifacts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"multiseed_{timestamp}"
        candidate = self.multiseed_artifacts_dir / base_name
        suffix = 2
        while candidate.exists():
            candidate = self.multiseed_artifacts_dir / f"{base_name}_{suffix}"
            suffix += 1
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    def _build_command(self, job: dict[str, Any]) -> list[str]:
        command = [
            sys.executable,
            "scripts/run_experiment.py",
            "--configs-dir",
            str(self.repo_root / str(job["execution_configs_dir"])),
            "--multiseed-output-dir",
            str(self.repo_root / str(job["multiseed_output_dir"])),
            "--parallel-workers",
            str(job["parallel_workers"]),
        ]
        preset_name = job.get("experiment_preset_name")
        if preset_name not in {None, ""}:
            command.extend(["--preset", str(preset_name)])
        return command

    def _delete_if_safe(self, root: Path, relative_path_value: str | None) -> None:
        if not relative_path_value:
            return
        candidate = self.repo_root / relative_path_value
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root.resolve())
        except ValueError:
            return
        if not resolved.exists():
            return
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()

    def _connect_readonly(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.database_path.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _load_campaign_row(self, campaign_id: str) -> dict[str, Any] | None:
        if not self.database_path.exists():
            return None
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

    def _load_run_rows(self, multiseed_run_id: int) -> list[dict[str, Any]]:
        if not self.database_path.exists():
            return []
        with self._connect_readonly() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM run_executions
                WHERE multiseed_run_id = ?
                ORDER BY id ASC
                """,
                (multiseed_run_id,),
            ).fetchall()
        return [_row_to_dict(row, set()) for row in rows]

    def _campaign_has_recent_progress(self, run_rows: list[dict[str, Any]]) -> bool:
        now = datetime.now(timezone.utc)
        for row in run_rows:
            if str(row.get("status") or "") != "running":
                continue
            progress_path = _safe_repo_artifact_path(
                self.repo_root,
                row.get("progress_snapshot_artifact_path"),
            )
            if progress_path is None or not progress_path.exists():
                continue
            modified_at = datetime.fromtimestamp(progress_path.stat().st_mtime, tz=timezone.utc)
            if (now - modified_at).total_seconds() <= PROGRESS_LIVENESS_GRACE_SECONDS:
                return True
        return False

    def _mark_campaign_interrupted(
        self,
        campaign_row: dict[str, Any],
        *,
        run_rows: list[dict[str, Any]],
        reason: str,
    ) -> None:
        running_rows = [
            row for row in run_rows if str(row.get("status") or "") == "running"
        ]
        for row in running_rows:
            self.store.update_run_execution_status(
                int(row["id"]),
                status="failed",
                completed_at=_utc_now_iso(),
                failure_reason=reason,
            )

        runs_failed = int(campaign_row.get("runs_failed") or 0) + len(running_rows)
        self.store.update_multiseed_run_status(
            int(campaign_row["id"]),
            status="failed",
            completed_at=_utc_now_iso(),
            runs_failed=runs_failed,
            failure_summary_json={
                "reason": "execution_interrupted",
                "message": reason,
            },
        )

    def build_job_seed_total(self, job: dict[str, Any]) -> int:
        payload = job.get("config_payload_json")
        if not isinstance(payload, dict):
            return 0
        return _seed_total_from_config_payload(payload)
