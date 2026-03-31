import argparse
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    format_effective_dataset_roots,
    resolve_effective_dataset_roots,
)
from evo_system.experimentation.parallel_progress import (
    PROGRESS_POLL_INTERVAL_SECONDS,
    format_active_job_progress,
    read_progress_snapshot,
)
from evo_system.experimentation.post_batch_analysis import (
    DEFAULT_AUDIT_DIR,
    run_post_batch_analysis,
    write_batch_quick_summary,
    write_batch_run_summary,
)
from evo_system.experimentation.single_run import (
    DEFAULT_EXTERNAL_VALIDATION_DIR,
    execute_historical_run,
)
from evo_system.reporting import DEFAULT_DB_PATH

CONFIGS_DIR = Path("configs/runs")
BATCHES_ROOT_DIR = Path("artifacts/batches")


@dataclass(frozen=True)
class BatchJob:
    config_path: Path
    output_dir: Path
    dataset_root: Path
    log_name: str
    progress_snapshot_path: Path


@dataclass(frozen=True)
class BatchExecutionOutcome:
    run_summaries: list[HistoricalRunSummary]
    failures: list[str]


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
    jobs: list[BatchJob],
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


def build_log_name(config_path: Path) -> str:
    return f"run_{config_path.stem}.txt"


def build_progress_snapshot_path(batch_dir: Path, config_path: Path) -> Path:
    return batch_dir / f"progress_{config_path.stem}.json"


def create_batch_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = BATCHES_ROOT_DIR / f"batch_{timestamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def execute_batch_job(job: BatchJob) -> HistoricalRunSummary:
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            return execute_historical_run(
                config_path=job.config_path,
                output_dir=job.output_dir,
                log_name=job.log_name,
                dataset_root=job.dataset_root,
                progress_snapshot_path=job.progress_snapshot_path,
            )


def execute_batch_jobs_with_failures(
    config_files: list[Path],
    batch_dir: Path,
    dataset_root: Path,
    requested_parallel_workers: int,
) -> BatchExecutionOutcome:
    jobs = [
        BatchJob(
            config_path=config_path,
            output_dir=batch_dir,
            dataset_root=dataset_root,
            log_name=build_log_name(config_path),
            progress_snapshot_path=build_progress_snapshot_path(batch_dir, config_path),
        )
        for config_path in config_files
    ]

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
        run_summaries: list[HistoricalRunSummary] = []
        for index, job in enumerate(jobs, start=1):
            print()
            print(f"[{index}/{total_jobs}] starting | mode=sequential | job={job.config_path.name}")
            print(f"=== Running {job.config_path.name} ===")
            run_summaries.append(
                execute_historical_run(
                    config_path=job.config_path,
                    output_dir=job.output_dir,
                    log_name=job.log_name,
                    dataset_root=job.dataset_root,
                )
            )
        return BatchExecutionOutcome(run_summaries=run_summaries, failures=[])

    print(f"Running batch jobs in parallel with {effective_parallel_workers} workers.")
    run_summaries: list[HistoricalRunSummary] = []
    failures: list[str] = []
    completed_jobs = 0
    success_count = 0
    failure_count = 0

    with ProcessPoolExecutor(
        max_workers=effective_parallel_workers,
        mp_context=get_context("spawn"),
    ) as executor:
        future_to_job = {
            executor.submit(execute_batch_job, job): job
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
                active_jobs = [future_to_job[future] for future in pending_futures]
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
                    failures.append(f"{job.config_path.name}: {exc}")
                    failure_count += 1
                    print(
                        format_parallel_progress(
                            completed_jobs=completed_jobs,
                            total_jobs=total_jobs,
                            success_count=success_count,
                            failure_count=failure_count,
                            last_label=f"{job.config_path.name} failed",
                        )
                    )
                    print(f"FAILED {job.config_path.name}: {exc}")
                    job.progress_snapshot_path.unlink(missing_ok=True)
                    continue

                run_summaries.append(summary)
                success_count += 1
                print(
                    format_parallel_progress(
                        completed_jobs=completed_jobs,
                        total_jobs=total_jobs,
                        success_count=success_count,
                        failure_count=failure_count,
                        last_label=job.config_path.name,
                    )
                )
                print(f"Completed {job.config_path.name} -> run_id={summary.run_id}")
                job.progress_snapshot_path.unlink(missing_ok=True)

            if pending_futures and (
                last_progress_report_time == 0.0
                or current_time - last_progress_report_time >= PROGRESS_POLL_INTERVAL_SECONDS
            ):
                active_jobs = [future_to_job[future] for future in pending_futures]
                print_parallel_status(
                    completed_jobs=completed_jobs,
                    total_jobs=total_jobs,
                    success_count=success_count,
                    failure_count=failure_count,
                    active_job_lines=collect_active_job_lines(active_jobs),
                )
                last_progress_report_time = current_time

    return BatchExecutionOutcome(run_summaries=run_summaries, failures=failures)


def execute_batch_jobs(
    config_files: list[Path],
    batch_dir: Path,
    dataset_root: Path,
    requested_parallel_workers: int,
) -> list[HistoricalRunSummary]:
    outcome = execute_batch_jobs_with_failures(
        config_files=config_files,
        batch_dir=batch_dir,
        dataset_root=dataset_root,
        requested_parallel_workers=requested_parallel_workers,
    )
    if outcome.failures:
        failure_summary = "\n".join(outcome.failures)
        raise RuntimeError(f"Batch execution completed with failures:\n{failure_summary}")
    return outcome.run_summaries


def run_batch_experiment(
    configs_dir: Path = CONFIGS_DIR,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    parallel_workers: int = 1,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    audit_dir: Path = DEFAULT_AUDIT_DIR,
    skip_post_batch_analysis: bool = False,
) -> Path | None:
    if parallel_workers <= 0:
        raise ValueError("parallel_workers must be greater than 0")

    config_files = sorted(configs_dir.glob("*.json"))

    if not config_files:
        print("No config files found.")
        return None

    job_count = len(config_files)
    effective_dataset_roots = resolve_effective_dataset_roots(
        config_paths=config_files,
        requested_dataset_root=dataset_root,
    )
    dataset_root_label = format_effective_dataset_roots(effective_dataset_roots)
    effective_parallel_workers = calculate_effective_parallel_workers(
        job_count=job_count,
        requested_parallel_workers=parallel_workers,
    )

    print(f"Found {len(config_files)} config files.")
    print(f"Dataset root: {dataset_root_label}")
    print("Execution mode: batch")
    print(f"Jobs scheduled: {job_count}")
    print(f"Requested parallel workers: {parallel_workers}")
    print(f"Effective parallel workers: {effective_parallel_workers}")
    print(
        "Execution strategy: "
        f"{'parallel' if effective_parallel_workers > 1 else 'sequential'}"
    )

    batch_dir = create_batch_dir()
    print(f"Writing batch artifacts to {batch_dir}")

    outcome = execute_batch_jobs_with_failures(
        config_files=config_files,
        batch_dir=batch_dir,
        dataset_root=dataset_root,
        requested_parallel_workers=parallel_workers,
    )

    if skip_post_batch_analysis:
        batch_summary_path = write_batch_run_summary(
            batch_dir=batch_dir,
            run_summaries=outcome.run_summaries,
            dataset_root_label=dataset_root_label,
        )
        write_batch_quick_summary(
            batch_dir=batch_dir,
            run_summaries=outcome.run_summaries,
            dataset_root_label=dataset_root_label,
            failures=outcome.failures,
            runs_planned=len(config_files),
        )
        print("Post-batch analysis skipped -> champions/external/audit summaries not generated")
    else:
        post_batch_result = run_post_batch_analysis(
            batch_dir=batch_dir,
            run_summaries=outcome.run_summaries,
            config_paths=config_files,
            dataset_root_label=dataset_root_label,
            db_path=DEFAULT_DB_PATH,
            external_validation_dir=external_validation_dir,
            audit_dir=audit_dir,
            failures=outcome.failures,
        )
        batch_summary_path = post_batch_result.batch_summary_path

    print()
    print(f"Batch summary saved to {batch_summary_path}")

    if outcome.failures:
        failure_summary = "\n".join(outcome.failures)
        raise RuntimeError(f"Batch execution completed with failures:\n{failure_summary}")

    return batch_summary_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Execute historical batch runs.")
    parser.add_argument(
        "--configs-dir",
        type=Path,
        default=CONFIGS_DIR,
        help="Directory containing run config JSON files.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=1,
        help="Number of worker processes for independent runs. Default: 1.",
    )
    parser.add_argument(
        "--external-validation-dir",
        type=Path,
        default=DEFAULT_EXTERNAL_VALIDATION_DIR,
        help="Direct directory containing post-batch external validation CSV datasets.",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=DEFAULT_AUDIT_DIR,
        help="Direct directory containing post-batch audit CSV datasets.",
    )
    parser.add_argument(
        "--skip-post-batch-analysis",
        action="store_true",
        help="Skip automatic post-batch champion analysis and reevaluation.",
    )
    args = parser.parse_args(argv)

    run_batch_experiment(
        configs_dir=args.configs_dir,
        dataset_root=args.dataset_root,
        parallel_workers=args.parallel_workers,
        external_validation_dir=args.external_validation_dir,
        audit_dir=args.audit_dir,
        skip_post_batch_analysis=args.skip_post_batch_analysis,
    )


if __name__ == "__main__":
    main()
