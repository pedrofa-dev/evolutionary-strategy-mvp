import argparse
import json
import os
import statistics
import tempfile
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path

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
from evo_system.experimentation.presets import (
    apply_preset_to_config_data,
    apply_preset_to_seeds,
    get_available_preset_names,
    get_preset_by_name,
)
from evo_system.experimentation.single_run import execute_historical_run
from evo_system.orchestration.config_loader import load_run_config

CONFIGS_DIR = Path("configs/runs")
BATCHES_ROOT_DIR = Path("artifacts/batches")
DEFAULT_SEED_START = 101
DEFAULT_SEED_COUNT = 6
DEFAULT_CONTEXT_NAME: str | None = None


@dataclass(frozen=True)
class MultiseedJob:
    config_path: Path
    seed: int
    output_dir: Path
    dataset_root: Path
    context_name: str | None
    preset_name: str | None
    progress_snapshot_path: Path


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


def create_multiseed_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    multiseed_dir = BATCHES_ROOT_DIR / f"multiseed_{timestamp}"
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
                )
            )
    return jobs


def execute_multiseed_job(job: MultiseedJob) -> HistoricalRunSummary:
    preset = get_preset_by_name(job.preset_name)
    base_config = load_config(job.config_path)
    effective_config = apply_preset_to_config_data(base_config, preset)
    config_copy = dict(effective_config)
    config_copy["mutation_seed"] = job.seed
    temp_config_path = write_temp_config(config_copy)

    try:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            with redirect_stdout(devnull), redirect_stderr(devnull):
                return execute_historical_run(
                    config_path=temp_config_path,
                    output_dir=job.output_dir,
                    log_name=build_log_name(job.config_path, job.seed),
                    config_name_override=job.config_path.name,
                    dataset_root=job.dataset_root,
                    context_name=job.context_name,
                    progress_snapshot_path=job.progress_snapshot_path,
                )
    finally:
        temp_config_path.unlink(missing_ok=True)


def execute_multiseed_job_sequential(job: MultiseedJob) -> HistoricalRunSummary:
    preset = get_preset_by_name(job.preset_name)
    base_config = load_config(job.config_path)
    effective_config = apply_preset_to_config_data(base_config, preset)
    config_copy = dict(effective_config)
    config_copy["mutation_seed"] = job.seed
    temp_config_path = write_temp_config(config_copy)

    try:
        return execute_historical_run(
            config_path=temp_config_path,
            output_dir=job.output_dir,
            log_name=build_log_name(job.config_path, job.seed),
            config_name_override=job.config_path.name,
            dataset_root=job.dataset_root,
            context_name=job.context_name,
            progress_snapshot_path=job.progress_snapshot_path,
        )
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


def execute_multiseed_runs(
    config_paths: list[Path],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None = None,
    requested_parallel_workers: int = 1,
) -> list[HistoricalRunSummary]:
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
        for index, job in enumerate(jobs, start=1):
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
            summaries.append(execute_multiseed_job_sequential(job))
        return summaries

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

    if failures:
        failure_summary = "\n".join(failures)
        raise RuntimeError(
            f"Multiseed execution completed with failures:\n{failure_summary}"
        )

    return summaries


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
    summary_path = output_dir / "multiseed_summary.txt"
    unique_seed_lists = {tuple(seeds) for seeds in seed_map.values()}
    seed_count_label = (
        str(len(next(iter(unique_seed_lists))))
        if len(unique_seed_lists) == 1
        else "variable"
    )

    lines = [
        f"Multiseed batch executed at: {datetime.now().isoformat(timespec='seconds')}",
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


def run_multiseed_experiment(
    configs_dir: Path = CONFIGS_DIR,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    preset_name: str | None = None,
    context_name: str | None = DEFAULT_CONTEXT_NAME,
    parallel_workers: int = 1,
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

    summaries = execute_multiseed_runs(
        config_paths=config_paths,
        output_dir=output_dir,
        dataset_root=dataset_root,
        context_name=context_name,
        preset_name=preset_name,
        requested_parallel_workers=parallel_workers,
    )

    summary_path = write_multiseed_summary(
        summaries=summaries,
        seed_map=seed_map,
        output_dir=output_dir,
        dataset_root_label=dataset_root_label,
        context_name=context_name,
        preset_name=preset_name,
        effective_generations=effective_generations,
    )

    print()
    print(f"Multiseed summary saved to {summary_path}")
    return summary_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Execute historical multiseed runs.")
    parser.add_argument(
        "--preset",
        type=str,
        choices=get_available_preset_names(),
        default=None,
        help="Optional execution preset overriding generations and seeds/max_seeds.",
    )
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
    args = parser.parse_args(argv)

    run_multiseed_experiment(
        configs_dir=args.configs_dir,
        dataset_root=args.dataset_root,
        preset_name=args.preset,
        parallel_workers=args.parallel_workers,
    )


if __name__ == "__main__":
    main()
