import json
import os
import statistics
import tempfile
import time
import uuid
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, is_dataclass, replace
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path

from evo_system.champions.metrics import build_dataset_signature
from evo_system.champions.rules import (
    ROBUST_MAX_ABS_SELECTION_GAP,
    ROBUST_MAX_VALIDATION_DRAWDOWN,
    ROBUST_MIN_VALIDATION_PROFIT,
    ROBUST_MIN_VALIDATION_SELECTION,
    ROBUST_MIN_VALIDATION_TRADES,
    SPECIALIST_MAX_ABS_SELECTION_GAP,
    SPECIALIST_MAX_VALIDATION_DRAWDOWN,
    SPECIALIST_MIN_VALIDATION_PROFIT,
    SPECIALIST_MIN_VALIDATION_SELECTION,
    SPECIALIST_MIN_VALIDATION_TRADES,
)
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.environment.dataset_pool_loader import DatasetPoolLoader
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    format_effective_dataset_roots,
    resolve_dataset_root,
    resolve_effective_dataset_roots,
)
from evo_system.experimentation.parallel_progress import (
    PROGRESS_POLL_INTERVAL_SECONDS,
    format_active_job_progress,
    read_progress_snapshot,
)
from evo_system.experimentation.post_multiseed_analysis import (
    DEFAULT_AUDIT_DIR,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
    load_multiseed_champions,
    run_post_multiseed_analysis,
    write_multiseed_quick_summary,
)
from evo_system.experimentation.presets import (
    apply_preset_to_config_data,
    apply_preset_to_seeds,
    get_preset_by_name,
)
from evo_system.experimentation.historical_run import (
    DEFAULT_EXTERNAL_VALIDATION_DIR,
    TRAIN_SAMPLE_SIZE,
    execute_historical_run,
)
from evo_system.orchestration.config_loader import load_run_config
from evo_system.reporting import DEFAULT_DB_PATH
from evo_system.storage import (
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
    build_execution_fingerprint,
    hash_config_snapshot,
)

CONFIGS_DIR = Path("configs/runs")
MULTISEED_ROOT_DIR = Path("artifacts/multiseed")
DEFAULT_SEED_START = 101
DEFAULT_SEED_COUNT = 6
DEFAULT_CONTEXT_NAME: str | None = None
MULTISEED_RUN_SUMMARY_NAME = "multiseed_run_summary.txt"


@dataclass(frozen=True)
class MultiseedJob:
    config_path: Path
    seed: int
    output_dir: Path
    dataset_root: Path
    context_name: str | None
    preset_name: str | None
    progress_snapshot_path: Path
    run_execution_uid: str
    effective_config_snapshot: dict
    dataset_catalog_id: str
    dataset_signature: str
    dataset_context_json: dict
    requested_dataset_root: Path
    resolved_dataset_root: Path
    execution_fingerprint: str


@dataclass(frozen=True)
class MultiseedExecutionOutcome:
    run_summaries: list[HistoricalRunSummary]
    failures: list[str]


@dataclass(frozen=True)
class PreparedRunExecution:
    run_execution_uid: str
    config_name: str
    effective_seed: int
    config_json_snapshot: dict
    dataset_catalog_id: str
    dataset_signature: str
    dataset_context_json: dict
    requested_dataset_root: Path
    resolved_dataset_root: Path
    execution_fingerprint: str


def calculate_effective_parallel_workers(
    job_count: int,
    requested_parallel_workers: int,
) -> int:
    if requested_parallel_workers <= 1:
        return 1
    if job_count <= 1:
        return 1
    return min(requested_parallel_workers, job_count)


def format_parallel_progress(
    completed_jobs: int,
    total_jobs: int,
    success_count: int,
    failure_count: int,
    last_label: str,
) -> str:
    return (
        f"[{completed_jobs}/{total_jobs}] completed | "
        f"success={success_count} | "
        f"failed={failure_count} | "
        f"last={last_label}"
    )


def print_parallel_status(
    *,
    completed_jobs: int,
    total_jobs: int,
    success_count: int,
    failure_count: int,
    active_job_lines: list[str],
) -> None:
    print(
        f"Completed: {completed_jobs}/{total_jobs} | "
        f"success={success_count} | failed={failure_count}"
    )
    if active_job_lines:
        print("Active jobs:")
        for line in active_job_lines:
            print(line)


def collect_active_job_lines(
    jobs: list[MultiseedJob],
) -> list[str]:
    lines: list[str] = []
    for job in jobs:
        snapshot = read_progress_snapshot(job.progress_snapshot_path)
        lines.append(
            format_active_job_progress(
                snapshot,
                fallback_label=job.config_path.name,
            )
        )
    return lines


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def build_effective_config_snapshot(
    config_path: Path,
    preset_name: str | None,
    seed: int,
) -> dict:
    preset = get_preset_by_name(preset_name)
    base_config = load_config(config_path)
    effective_config = apply_preset_to_config_data(base_config, preset)
    config_copy = dict(effective_config)
    config_copy["mutation_seed"] = seed
    return config_copy


def build_dataset_context_snapshot(
    *,
    effective_config_snapshot: dict,
    requested_dataset_root: Path,
) -> tuple[str, Path, dict]:
    resolved_dataset_root = resolve_dataset_root(requested_dataset_root)
    dataset_catalog_id = effective_config_snapshot["dataset_catalog_id"]
    loader = DatasetPoolLoader()
    train_dataset_paths, validation_dataset_paths = loader.load_paths(
        resolved_dataset_root,
        dataset_catalog_id=dataset_catalog_id,
    )
    train_sample_size = min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths))
    dataset_signature = build_dataset_signature(
        all_train_dataset_paths=train_dataset_paths,
        validation_dataset_paths=validation_dataset_paths,
        dataset_root=resolved_dataset_root,
        train_sample_size=train_sample_size,
    )
    dataset_context_json = {
        "dataset_catalog_id": dataset_catalog_id,
        "resolved_train_paths": [str(path) for path in train_dataset_paths],
        "resolved_validation_paths": [str(path) for path in validation_dataset_paths],
        "train_count": len(train_dataset_paths),
        "validation_count": len(validation_dataset_paths),
        "train_sample_size": train_sample_size,
        "resolved_dataset_root": str(resolved_dataset_root),
    }
    return dataset_signature, resolved_dataset_root, dataset_context_json


def prepare_run_execution(
    config_path: Path,
    *,
    seed: int,
    preset_name: str | None,
    dataset_root: Path,
) -> PreparedRunExecution:
    effective_config_snapshot = build_effective_config_snapshot(
        config_path,
        preset_name,
        seed,
    )
    dataset_signature, resolved_dataset_root, dataset_context_json = (
        build_dataset_context_snapshot(
            effective_config_snapshot=effective_config_snapshot,
            requested_dataset_root=dataset_root,
        )
    )
    config_hash = hash_config_snapshot(effective_config_snapshot)
    return PreparedRunExecution(
        run_execution_uid=str(uuid.uuid4()),
        config_name=config_path.name,
        effective_seed=seed,
        config_json_snapshot=effective_config_snapshot,
        dataset_catalog_id=effective_config_snapshot["dataset_catalog_id"],
        dataset_signature=dataset_signature,
        dataset_context_json=dataset_context_json,
        requested_dataset_root=dataset_root,
        resolved_dataset_root=resolved_dataset_root,
        execution_fingerprint=build_execution_fingerprint(
            config_hash=config_hash,
            effective_seed=seed,
            dataset_signature=dataset_signature,
            logic_version=CURRENT_LOGIC_VERSION,
        ),
    )


def build_default_multiseed_seeds() -> list[int]:
    return list(range(DEFAULT_SEED_START, DEFAULT_SEED_START + DEFAULT_SEED_COUNT))


def resolve_config_seeds(config_path: Path) -> list[int]:
    config = load_run_config(str(config_path))

    if config.seeds is not None:
        return list(config.seeds)

    if config.seed_start is not None and config.seed_count is not None:
        return list(range(config.seed_start, config.seed_start + config.seed_count))

    return build_default_multiseed_seeds()


def resolve_seed_map(
    config_paths: list[Path],
    preset_name: str | None,
) -> dict[Path, list[int]]:
    preset = get_preset_by_name(preset_name)
    seed_map: dict[Path, list[int]] = {}

    for config_path in config_paths:
        seed_map[config_path] = apply_preset_to_seeds(
            resolve_config_seeds(config_path),
            preset,
        )

    return seed_map


def format_seed_plan(seed_map: dict[Path, list[int]]) -> str:
    unique_seed_lists = {
        tuple(seeds)
        for seeds in seed_map.values()
    }

    if len(unique_seed_lists) == 1:
        seeds = list(next(iter(unique_seed_lists)))
        return ", ".join(str(seed) for seed in seeds)

    parts: list[str] = []
    for config_path, seeds in sorted(seed_map.items()):
        parts.append(
            f"{config_path.name}: {', '.join(str(seed) for seed in seeds)}"
        )
    return " | ".join(parts)


def write_temp_config(config_data: dict) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )

    with temp_file:
        json.dump(config_data, temp_file, indent=2)

    return Path(temp_file.name)


def build_log_name(config_path: Path, seed: int) -> str:
    return f"run_{config_path.stem}_seed{seed}.txt"


def build_progress_snapshot_path(
    output_dir: Path,
    config_path: Path,
    seed: int,
) -> Path:
    return output_dir / f"progress_{config_path.stem}_seed{seed}.json"


def preserve_original_config_path(
    summary: HistoricalRunSummary,
    original_config_path: Path,
) -> HistoricalRunSummary:
    if is_dataclass(summary):
        return replace(summary, config_path=original_config_path)

    setattr(summary, "config_path", original_config_path)
    return summary


def create_multiseed_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    multiseed_dir = MULTISEED_ROOT_DIR / f"multiseed_{timestamp}"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    return multiseed_dir


def build_multiseed_jobs(
    seed_map: dict[Path, list[int]],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None,
) -> list[MultiseedJob]:
    jobs: list[MultiseedJob] = []
    for config_path in sorted(seed_map):
        for seed in seed_map[config_path]:
            prepared_execution = prepare_run_execution(
                config_path,
                seed=seed,
                preset_name=preset_name,
                dataset_root=dataset_root,
            )
            jobs.append(
                MultiseedJob(
                    config_path=config_path,
                    seed=seed,
                    output_dir=output_dir,
                    dataset_root=dataset_root,
                    context_name=context_name,
                    preset_name=preset_name,
                    progress_snapshot_path=build_progress_snapshot_path(
                        output_dir,
                        config_path,
                        seed,
                    ),
                    run_execution_uid=prepared_execution.run_execution_uid,
                    effective_config_snapshot=prepared_execution.config_json_snapshot,
                    dataset_catalog_id=prepared_execution.dataset_catalog_id,
                    dataset_signature=prepared_execution.dataset_signature,
                    dataset_context_json=prepared_execution.dataset_context_json,
                    requested_dataset_root=prepared_execution.requested_dataset_root,
                    resolved_dataset_root=prepared_execution.resolved_dataset_root,
                    execution_fingerprint=prepared_execution.execution_fingerprint,
                )
            )
    return jobs


def execute_multiseed_job(job: MultiseedJob) -> HistoricalRunSummary:
    temp_config_path = write_temp_config(job.effective_config_snapshot)

    try:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            with redirect_stdout(devnull), redirect_stderr(devnull):
                summary = execute_historical_run(
                    config_path=temp_config_path,
                    output_dir=job.output_dir,
                    log_name=build_log_name(job.config_path, job.seed),
                    config_name_override=job.config_path.name,
                    dataset_root=job.dataset_root,
                    context_name=job.context_name,
                    progress_snapshot_path=job.progress_snapshot_path,
                )
                return preserve_original_config_path(summary, job.config_path)
    finally:
        temp_config_path.unlink(missing_ok=True)


def execute_multiseed_job_sequential(job: MultiseedJob) -> HistoricalRunSummary:
    temp_config_path = write_temp_config(job.effective_config_snapshot)

    try:
        summary = execute_historical_run(
            config_path=temp_config_path,
            output_dir=job.output_dir,
            log_name=build_log_name(job.config_path, job.seed),
            config_name_override=job.config_path.name,
            dataset_root=job.dataset_root,
            context_name=job.context_name,
            progress_snapshot_path=job.progress_snapshot_path,
        )
        return preserve_original_config_path(summary, job.config_path)
    finally:
        temp_config_path.unlink(missing_ok=True)


def safe_mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def safe_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def classify_summary_champion(summary: HistoricalRunSummary) -> str:
    if summary.final_validation_profit <= 0.0:
        return "rejected"

    if (
        summary.final_validation_selection_score >= ROBUST_MIN_VALIDATION_SELECTION
        and summary.final_validation_profit >= ROBUST_MIN_VALIDATION_PROFIT
        and summary.final_validation_drawdown <= ROBUST_MAX_VALIDATION_DRAWDOWN
        and summary.final_validation_trades >= ROBUST_MIN_VALIDATION_TRADES
        and abs(summary.train_validation_selection_gap) <= ROBUST_MAX_ABS_SELECTION_GAP
    ):
        return "robust"

    if (
        summary.final_validation_selection_score >= SPECIALIST_MIN_VALIDATION_SELECTION
        and summary.final_validation_profit >= SPECIALIST_MIN_VALIDATION_PROFIT
        and summary.final_validation_drawdown <= SPECIALIST_MAX_VALIDATION_DRAWDOWN
        and summary.final_validation_trades >= SPECIALIST_MIN_VALIDATION_TRADES
        and abs(summary.train_validation_selection_gap) <= SPECIALIST_MAX_ABS_SELECTION_GAP
    ):
        return "specialist"

    return "rejected"


def is_champion(summary: HistoricalRunSummary) -> bool:
    return classify_summary_champion(summary) != "rejected"


def build_configs_dir_snapshot(config_paths: list[Path]) -> dict:
    return {
        "config_count": len(config_paths),
        "configs": [
            {
                "config_name": path.name,
                "config_path": str(path),
            }
            for path in sorted(config_paths)
        ],
    }


def build_run_summary_payload(summary: HistoricalRunSummary) -> dict:
    return {
        "run_id": summary.run_id,
        "config_name": summary.config_name,
        "mutation_seed": summary.mutation_seed,
        "best_train_selection_score": summary.best_train_selection_score,
        "final_validation_selection_score": summary.final_validation_selection_score,
        "final_validation_profit": summary.final_validation_profit,
        "final_validation_drawdown": summary.final_validation_drawdown,
        "final_validation_trades": summary.final_validation_trades,
        "best_genome_repr": summary.best_genome_repr,
        "generation_of_best": summary.generation_of_best,
        "train_validation_selection_gap": summary.train_validation_selection_gap,
        "train_validation_profit_gap": summary.train_validation_profit_gap,
        "log_file_path": str(summary.log_file_path),
        "config_path": str(summary.config_path) if summary.config_path is not None else None,
    }


def create_multiseed_run_record(
    *,
    store: PersistenceStore,
    output_dir: Path,
    configs_dir: Path,
    config_paths: list[Path],
    dataset_root: Path,
    preset_name: str | None,
    context_name: str | None,
    requested_parallel_workers: int,
    effective_parallel_workers: int,
    runs_planned: int,
) -> tuple[int, str]:
    multiseed_run_uid = output_dir.name
    multiseed_run_id = store.save_multiseed_run(
        multiseed_run_uid=multiseed_run_uid,
        configs_dir_snapshot={
            "configs_dir": str(configs_dir),
            **build_configs_dir_snapshot(config_paths),
        },
        requested_parallel_workers=requested_parallel_workers,
        effective_parallel_workers=effective_parallel_workers,
        dataset_root=dataset_root,
        runs_planned=runs_planned,
        runs_completed=0,
        runs_failed=0,
        champions_found=False,
        champion_analysis_status="pending",
        external_evaluation_status="pending",
        audit_evaluation_status="pending",
        status="running",
        logic_version=CURRENT_LOGIC_VERSION,
        preset_name=preset_name,
        context_name=context_name,
        artifacts_root_path=output_dir,
    )
    return multiseed_run_id, multiseed_run_uid


def persist_run_execution_start(
    *,
    store: PersistenceStore,
    multiseed_run_id: int,
    job: MultiseedJob,
    context_name: str | None,
) -> int:
    store.find_run_execution_by_fingerprint(job.execution_fingerprint)
    return store.save_run_execution(
        run_execution_uid=job.run_execution_uid,
        multiseed_run_id=multiseed_run_id,
        run_id=job.run_execution_uid,
        config_name=job.config_path.name,
        config_json_snapshot=job.effective_config_snapshot,
        effective_seed=job.seed,
        dataset_catalog_id=job.dataset_catalog_id,
        dataset_signature=job.dataset_signature,
        dataset_context_json=job.dataset_context_json,
        status="running",
        logic_version=CURRENT_LOGIC_VERSION,
        context_name=context_name,
        preset_name=job.preset_name,
        requested_dataset_root=job.requested_dataset_root,
        resolved_dataset_root=job.resolved_dataset_root,
        progress_snapshot_artifact_path=job.progress_snapshot_path,
    )


def persist_run_execution_success(
    *,
    store: PersistenceStore,
    run_execution_id: int,
    summary: HistoricalRunSummary,
    job: MultiseedJob,
) -> None:
    store.update_run_execution_status(
        run_execution_id,
        status="completed",
        run_id=summary.run_id,
        log_artifact_path=summary.log_file_path,
        progress_snapshot_artifact_path=job.progress_snapshot_path,
        summary_json=build_run_summary_payload(summary),
    )


def persist_run_execution_failure(
    *,
    store: PersistenceStore,
    run_execution_id: int,
    job: MultiseedJob,
    error: Exception,
) -> None:
    store.update_run_execution_status(
        run_execution_id,
        status="failed",
        failure_reason=str(error),
        progress_snapshot_artifact_path=job.progress_snapshot_path,
    )


def execute_multiseed_runs_with_failures(
    config_paths: list[Path],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None = None,
    requested_parallel_workers: int = 1,
    persistence_store: PersistenceStore | None = None,
    multiseed_run_id: int | None = None,
) -> MultiseedExecutionOutcome:
    seed_map = resolve_seed_map(config_paths, preset_name)
    jobs = build_multiseed_jobs(
        seed_map=seed_map,
        output_dir=output_dir,
        dataset_root=dataset_root,
        context_name=context_name,
        preset_name=preset_name,
    )
    preset = get_preset_by_name(preset_name)
    total_jobs = len(jobs)
    effective_parallel_workers = calculate_effective_parallel_workers(
        job_count=total_jobs,
        requested_parallel_workers=requested_parallel_workers,
    )

    if requested_parallel_workers > 1 and effective_parallel_workers == 1:
        print(
            "Parallel execution requested with "
            f"{requested_parallel_workers} workers, but only {total_jobs} job "
            "is scheduled. Falling back to sequential execution."
        )

    if effective_parallel_workers <= 1:
        summaries: list[HistoricalRunSummary] = []
        failures: list[str] = []
        for index, job in enumerate(jobs, start=1):
            run_execution_id: int | None = None
            if persistence_store is not None and multiseed_run_id is not None:
                run_execution_id = persist_run_execution_start(
                    store=persistence_store,
                    multiseed_run_id=multiseed_run_id,
                    job=job,
                    context_name=context_name,
                )
            print()
            print(
                f"[{index}/{total_jobs}] starting | "
                f"mode=sequential | job={job.config_path.name} seed={job.seed}"
            )
            print(f"=== Running {job.config_path.name} with seed {job.seed} ===")
            if context_name:
                print(f"Context: {context_name}")
            if preset is not None:
                effective_config = apply_preset_to_config_data(load_config(job.config_path), preset)
                print(
                    f"Preset: {preset.name} | "
                    f"generations={effective_config['generations_planned']}"
                )
            try:
                summary = execute_multiseed_job_sequential(job)
                summaries.append(summary)
                if persistence_store is not None and run_execution_id is not None:
                    persist_run_execution_success(
                        store=persistence_store,
                        run_execution_id=run_execution_id,
                        summary=summary,
                        job=job,
                    )
            except Exception as exc:
                failures.append(f"{job.config_path.name} seed {job.seed}: {exc}")
                if persistence_store is not None and run_execution_id is not None:
                    persist_run_execution_failure(
                        store=persistence_store,
                        run_execution_id=run_execution_id,
                        job=job,
                        error=exc,
                    )
                print(f"FAILED {job.config_path.name} seed {job.seed}: {exc}")
                job.progress_snapshot_path.unlink(missing_ok=True)
        return MultiseedExecutionOutcome(run_summaries=summaries, failures=failures)

    print(
        f"Running multiseed jobs in parallel with {effective_parallel_workers} workers."
    )
    summaries: list[HistoricalRunSummary] = []
    failures: list[str] = []
    completed_jobs = 0
    success_count = 0
    failure_count = 0

    with ProcessPoolExecutor(
        max_workers=effective_parallel_workers,
        mp_context=get_context("spawn"),
    ) as executor:
        run_execution_ids_by_job_key: dict[tuple[str, int], int] = {}
        if persistence_store is not None and multiseed_run_id is not None:
            for job in jobs:
                run_execution_ids_by_job_key[(str(job.config_path), job.seed)] = (
                    persist_run_execution_start(
                        store=persistence_store,
                        multiseed_run_id=multiseed_run_id,
                        job=job,
                        context_name=context_name,
                    )
                )
        future_to_job = {
            executor.submit(execute_multiseed_job, job): job
            for job in jobs
        }
        pending_futures = set(future_to_job)
        last_progress_report_time = 0.0

        while pending_futures:
            done_futures, pending_futures = wait(
                pending_futures,
                timeout=PROGRESS_POLL_INTERVAL_SECONDS,
                return_when=FIRST_COMPLETED,
            )
            current_time = time.perf_counter()

            if not done_futures:
                active_jobs = [
                    future_to_job[future]
                    for future in pending_futures
                ]
                print_parallel_status(
                    completed_jobs=completed_jobs,
                    total_jobs=total_jobs,
                    success_count=success_count,
                    failure_count=failure_count,
                    active_job_lines=collect_active_job_lines(active_jobs),
                )
                last_progress_report_time = current_time
                continue

            for future in done_futures:
                job = future_to_job[future]
                completed_jobs += 1
                try:
                    summary = future.result()
                except Exception as exc:
                    failures.append(f"{job.config_path.name} seed {job.seed}: {exc}")
                    failure_count += 1
                    run_execution_id = run_execution_ids_by_job_key.get(
                        (str(job.config_path), job.seed)
                    )
                    if persistence_store is not None and run_execution_id is not None:
                        persist_run_execution_failure(
                            store=persistence_store,
                            run_execution_id=run_execution_id,
                            job=job,
                            error=exc,
                        )
                    print(
                        format_parallel_progress(
                            completed_jobs=completed_jobs,
                            total_jobs=total_jobs,
                            success_count=success_count,
                            failure_count=failure_count,
                            last_label=f"{job.config_path.name} seed={job.seed} failed",
                        )
                    )
                    print(f"FAILED {job.config_path.name} seed {job.seed}: {exc}")
                    job.progress_snapshot_path.unlink(missing_ok=True)
                    continue

                summaries.append(summary)
                success_count += 1
                run_execution_id = run_execution_ids_by_job_key.get(
                    (str(job.config_path), job.seed)
                )
                if persistence_store is not None and run_execution_id is not None:
                    persist_run_execution_success(
                        store=persistence_store,
                        run_execution_id=run_execution_id,
                        summary=summary,
                        job=job,
                    )
                print(
                    format_parallel_progress(
                        completed_jobs=completed_jobs,
                        total_jobs=total_jobs,
                        success_count=success_count,
                        failure_count=failure_count,
                        last_label=f"{job.config_path.name} seed={job.seed}",
                    )
                )
                print(
                    f"Completed {job.config_path.name} seed {job.seed} -> run_id={summary.run_id}"
                )
                job.progress_snapshot_path.unlink(missing_ok=True)

            if pending_futures and (
                last_progress_report_time == 0.0
                or current_time - last_progress_report_time >= PROGRESS_POLL_INTERVAL_SECONDS
            ):
                active_jobs = [
                    future_to_job[future]
                    for future in pending_futures
                ]
                print_parallel_status(
                    completed_jobs=completed_jobs,
                    total_jobs=total_jobs,
                    success_count=success_count,
                    failure_count=failure_count,
                    active_job_lines=collect_active_job_lines(active_jobs),
                )
                last_progress_report_time = current_time

    return MultiseedExecutionOutcome(run_summaries=summaries, failures=failures)


def execute_multiseed_runs(
    config_paths: list[Path],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None = None,
    requested_parallel_workers: int = 1,
    persistence_store: PersistenceStore | None = None,
    multiseed_run_id: int | None = None,
) -> list[HistoricalRunSummary]:
    outcome = execute_multiseed_runs_with_failures(
        config_paths=config_paths,
        output_dir=output_dir,
        dataset_root=dataset_root,
        context_name=context_name,
        preset_name=preset_name,
        requested_parallel_workers=requested_parallel_workers,
        persistence_store=persistence_store,
        multiseed_run_id=multiseed_run_id,
    )
    if outcome.failures:
        failure_summary = "\n".join(outcome.failures)
        raise RuntimeError(
            f"Multiseed execution completed with failures:\n{failure_summary}"
        )
    return outcome.run_summaries


def build_grouped_summary_lines(
    summaries: list[HistoricalRunSummary],
) -> list[str]:
    grouped: dict[str, list[HistoricalRunSummary]] = defaultdict(list)

    for summary in summaries:
        grouped[summary.config_name].append(summary)

    wins_by_config: dict[str, int] = defaultdict(int)
    sorted_grouped_items = sorted(grouped.items())

    for seed_runs in zip(
        *[
            sorted(runs, key=lambda run: run.mutation_seed)
            for _, runs in sorted_grouped_items
        ]
    ):
        best_score = max(run.final_validation_selection_score for run in seed_runs)
        winners = [
            run for run in seed_runs
            if run.final_validation_selection_score == best_score
        ]

        if len(winners) == 1:
            wins_by_config[winners[0].config_name] += 1

    aggregated_rows = []

    for config_name, runs in grouped.items():
        runs_sorted = sorted(runs, key=lambda run: run.mutation_seed)

        selection_scores = [r.final_validation_selection_score for r in runs_sorted]
        profits = [r.final_validation_profit for r in runs_sorted]
        drawdowns = [r.final_validation_drawdown for r in runs_sorted]
        trades = [r.final_validation_trades for r in runs_sorted]
        abs_gaps = [abs(r.train_validation_selection_gap) for r in runs_sorted]

        champion_count = sum(1 for run in runs_sorted if is_champion(run))
        champion_rate = champion_count / len(runs_sorted) if runs_sorted else 0.0

        aggregated_rows.append(
            {
                "config_name": config_name,
                "runs": runs_sorted,
                "mean_validation_selection": safe_mean(selection_scores),
                "std_validation_selection": safe_stdev(selection_scores),
                "best_validation_selection": max(selection_scores),
                "worst_validation_selection": min(selection_scores),
                "mean_validation_profit": safe_mean(profits),
                "std_validation_profit": safe_stdev(profits),
                "mean_validation_drawdown": safe_mean(drawdowns),
                "mean_validation_trades": safe_mean(trades),
                "mean_abs_selection_gap": safe_mean(abs_gaps),
                "wins_count": wins_by_config[config_name],
                "champion_count": champion_count,
                "champion_rate": champion_rate,
            }
        )

    aggregated_rows.sort(
        key=lambda row: (
            row["champion_rate"],
            row["mean_validation_selection"],
            row["mean_validation_profit"],
            -row["std_validation_selection"],
        ),
        reverse=True,
    )

    lines: list[str] = []
    lines.append("Ranking by champion rate and mean validation selection score")
    lines.append("")

    for index, row in enumerate(aggregated_rows, start=1):
        lines.append(
            f"{index}. "
            f"{row['config_name']} | "
            f"champion_count={row['champion_count']} | "
            f"champion_rate={row['champion_rate']:.2f} | "
            f"wins={row['wins_count']} | "
            f"mean_validation_selection={row['mean_validation_selection']:.4f} | "
            f"std_validation_selection={row['std_validation_selection']:.4f} | "
            f"best_validation_selection={row['best_validation_selection']:.4f} | "
            f"worst_validation_selection={row['worst_validation_selection']:.4f} | "
            f"mean_validation_profit={row['mean_validation_profit']:.4f} | "
            f"std_validation_profit={row['std_validation_profit']:.4f} | "
            f"mean_validation_drawdown={row['mean_validation_drawdown']:.4f} | "
            f"mean_validation_trades={row['mean_validation_trades']:.1f} | "
            f"mean_abs_selection_gap={row['mean_abs_selection_gap']:.4f}"
        )

        for run in row["runs"]:
            champion_type = classify_summary_champion(run)
            lines.append(
                f" seed={run.mutation_seed} | "
                f"champion={is_champion(run)} | "
                f"type={champion_type} | "
                f"validation_selection={run.final_validation_selection_score:.4f} | "
                f"validation_profit={run.final_validation_profit:.4f} | "
                f"drawdown={run.final_validation_drawdown:.4f} | "
                f"trades={run.final_validation_trades:.1f} | "
                f"selection_gap={run.train_validation_selection_gap:.4f} | "
                f"log={run.log_file_path.name}"
            )

        lines.append("")

    return lines


def write_multiseed_summary(
    summaries: list[HistoricalRunSummary],
    seed_map: dict[Path, list[int]],
    output_dir: Path,
    dataset_root_label: str,
    context_name: str | None,
    preset_name: str | None,
    effective_generations: int | None,
) -> Path:
    summary_path = output_dir / MULTISEED_RUN_SUMMARY_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    unique_seed_lists = {tuple(seeds) for seeds in seed_map.values()}
    seed_count_label = (
        str(len(next(iter(unique_seed_lists))))
        if len(unique_seed_lists) == 1
        else "variable"
    )

    lines = [
        f"Multiseed executed at: {datetime.now().isoformat(timespec='seconds')}",
        f"Preset: {preset_name or 'none'}",
        f"Effective generations: {effective_generations if effective_generations is not None else 'config-defined'}",
        f"Context name: {context_name or 'none'}",
        f"Dataset root: {dataset_root_label}",
        f"Configs executed: {len(set(summary.config_name for summary in summaries))}",
        f"Seeds per config: {seed_count_label}",
        f"Seeds used: {format_seed_plan(seed_map)}",
        f"Total runs: {len(summaries)}",
        "",
        "Champion criteria:",
        " robust -> validation_selection >= 1.5 | validation_profit >= 0.02 | validation_drawdown <= 0.03 | validation_trades >= 10.0 | abs(selection_gap) <= 1.5",
        " specialist -> validation_selection >= 8.0 | validation_profit >= 0.03 | validation_drawdown <= 0.12 | validation_trades >= 10.0 | abs(selection_gap) <= 20.0",
        " rejected -> everything else",
        "",
    ]

    lines.extend(build_grouped_summary_lines(summaries))
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def resolve_multiseed_persistence_statuses(
    *,
    run_summaries: list[HistoricalRunSummary],
    skip_post_multiseed_analysis: bool,
) -> tuple[bool, str, str, str]:
    champions = load_multiseed_champions(
        DEFAULT_DB_PATH,
        [summary.run_id for summary in run_summaries],
    )
    champions_found = bool(champions)

    if not champions_found:
        return (
            False,
            "skipped_no_champions",
            "skipped_no_champions",
            "skipped_no_champions",
        )

    if skip_post_multiseed_analysis:
        return (
            True,
            "skipped_by_flag",
            "skipped_by_flag",
            "skipped_by_flag",
        )

    return (
        True,
        "legacy_completed",
        "legacy_managed",
        "legacy_managed",
    )


def run_multiseed_experiment(
    configs_dir: Path = CONFIGS_DIR,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    preset_name: str | None = None,
    context_name: str | None = DEFAULT_CONTEXT_NAME,
    parallel_workers: int = 1,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    skip_post_multiseed_analysis: bool = False,
) -> Path | None:
    if parallel_workers <= 0:
        raise ValueError("parallel_workers must be greater than 0")

    config_paths = sorted(configs_dir.glob("*.json"))

    if not config_paths:
        print("No config files found.")
        return None

    preset = get_preset_by_name(preset_name)
    seed_map = resolve_seed_map(config_paths, preset_name)
    effective_generations = preset.generations if preset is not None else None
    job_count = sum(len(seeds) for seeds in seed_map.values())
    effective_dataset_roots = resolve_effective_dataset_roots(
        config_paths=config_paths,
        requested_dataset_root=dataset_root,
    )
    dataset_root_label = format_effective_dataset_roots(effective_dataset_roots)
    effective_parallel_workers = calculate_effective_parallel_workers(
        job_count=job_count,
        requested_parallel_workers=parallel_workers,
    )

    print("Execution mode: multiseed")
    print(f"Found {len(config_paths)} config files.")
    print(f"Using seeds: {format_seed_plan(seed_map)}")
    print(f"Jobs scheduled: {job_count}")
    print(f"Preset: {preset_name or 'none'}")
    print(
        "Effective generations: "
        f"{effective_generations if effective_generations is not None else 'config-defined'}"
    )
    print(f"Context name: {context_name or 'none'}")
    print(f"Dataset root: {dataset_root_label}")
    print(f"Requested parallel workers: {parallel_workers}")
    print(f"Effective parallel workers: {effective_parallel_workers}")
    print(
        "Execution strategy: "
        f"{'parallel' if effective_parallel_workers > 1 else 'sequential'}"
    )

    output_dir = create_multiseed_dir()
    print(f"Writing multiseed artifacts to {output_dir}")

    persistence_store = PersistenceStore(DEFAULT_PERSISTENCE_DB_PATH)
    persistence_store.initialize()
    multiseed_run_id, _ = create_multiseed_run_record(
        store=persistence_store,
        output_dir=output_dir,
        configs_dir=configs_dir,
        config_paths=config_paths,
        dataset_root=dataset_root,
        preset_name=preset_name,
        context_name=context_name,
        requested_parallel_workers=parallel_workers,
        effective_parallel_workers=effective_parallel_workers,
        runs_planned=job_count,
    )
    outcome: MultiseedExecutionOutcome | None = None
    summary_path: Path | None = None

    try:
        outcome = execute_multiseed_runs_with_failures(
            config_paths=config_paths,
            output_dir=output_dir,
            dataset_root=dataset_root,
            context_name=context_name,
            preset_name=preset_name,
            requested_parallel_workers=parallel_workers,
            persistence_store=persistence_store,
            multiseed_run_id=multiseed_run_id,
        )

        summary_path = write_multiseed_summary(
            summaries=outcome.run_summaries,
            seed_map=seed_map,
            output_dir=output_dir,
            dataset_root_label=dataset_root_label,
            context_name=context_name,
            preset_name=preset_name,
            effective_generations=effective_generations,
        )

        if skip_post_multiseed_analysis:
            write_multiseed_quick_summary(
                multiseed_dir=output_dir,
                run_summaries=outcome.run_summaries,
                dataset_root_label=dataset_root_label,
                failures=outcome.failures,
                seeds_planned=job_count,
            )
            print(
                "Post-multiseed analysis skipped -> champions/external/audit summaries not generated"
            )
        else:
            post_analysis_result = run_post_multiseed_analysis(
                multiseed_dir=output_dir,
                summary_path=summary_path,
                run_summaries=outcome.run_summaries,
                dataset_root_label=dataset_root_label,
                db_path=DEFAULT_DB_PATH,
                external_validation_dir=external_validation_dir,
                audit_dir=audit_dir,
                failures=outcome.failures,
                seeds_planned=job_count,
            )
            print(
                f"Multiseed champions summary saved to {post_analysis_result.champions_summary_path}"
            )
            print(
                "Multiseed post-validation directory saved to "
                f"{output_dir / POST_MULTISEED_VALIDATION_DIRNAME}"
            )

        champions_found, champion_analysis_status, external_evaluation_status, audit_evaluation_status = (
            resolve_multiseed_persistence_statuses(
                run_summaries=outcome.run_summaries,
                skip_post_multiseed_analysis=skip_post_multiseed_analysis,
            )
        )
        persistence_store.update_multiseed_run_status(
            multiseed_run_id,
            status="completed_with_failures" if outcome.failures else "completed",
            runs_completed=len(outcome.run_summaries),
            runs_failed=len(outcome.failures),
            champions_found=champions_found,
            champion_analysis_status=champion_analysis_status,
            external_evaluation_status=external_evaluation_status,
            audit_evaluation_status=audit_evaluation_status,
            failure_summary_json=(
                {"failures": outcome.failures}
                if outcome.failures
                else None
            ),
            summary_artifact_path=summary_path,
            quick_summary_artifact_path=output_dir / MULTISEED_QUICK_SUMMARY_NAME,
            champions_summary_artifact_path=(
                output_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
                if (output_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME).exists()
                else None
            ),
            artifacts_root_path=output_dir,
        )
    except Exception as exc:
        persistence_store.update_multiseed_run_status(
            multiseed_run_id,
            status="failed",
            runs_completed=len(outcome.run_summaries) if outcome is not None else 0,
            runs_failed=len(outcome.failures) if outcome is not None else job_count,
            champions_found=False,
            champion_analysis_status="failed",
            external_evaluation_status="failed",
            audit_evaluation_status="failed",
            failure_summary_json={"failures": [str(exc)]},
            summary_artifact_path=summary_path,
            quick_summary_artifact_path=(
                output_dir / MULTISEED_QUICK_SUMMARY_NAME
                if (output_dir / MULTISEED_QUICK_SUMMARY_NAME).exists()
                else None
            ),
            champions_summary_artifact_path=(
                output_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME
                if (output_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME).exists()
                else None
            ),
            artifacts_root_path=output_dir,
        )
        raise

    print()
    print(f"Multiseed summary saved to {summary_path}")
    print(f"Multiseed quick summary saved to {output_dir / MULTISEED_QUICK_SUMMARY_NAME}")

    if outcome.failures:
        failure_summary = "\n".join(outcome.failures)
        raise RuntimeError(
            f"Multiseed execution completed with failures:\n{failure_summary}"
        )
    return summary_path
