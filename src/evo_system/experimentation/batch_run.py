import argparse
from datetime import datetime
from pathlib import Path

from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.experimentation.single_run import (
    DEFAULT_DATASET_ROOT,
    execute_historical_run,
)

CONFIGS_DIR = Path("configs/runs")
BATCHES_ROOT_DIR = Path("artifacts/batches")


def build_ranking_lines_by_selection(
    run_summaries: list[HistoricalRunSummary],
) -> list[str]:
    lines: list[str] = []

    sorted_runs = sorted(
        run_summaries,
        key=lambda summary: summary.final_validation_selection_score,
        reverse=True,
    )

    lines.append("Ranking by final validation selection score")

    for index, summary in enumerate(sorted_runs, start=1):
        lines.append(
            f"{index}. "
            f"{summary.config_name} | "
            f"run_id={summary.run_id} | "
            f"mutation_seed={summary.mutation_seed} | "
            f"best_train={summary.best_train_selection_score:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_drawdown={summary.final_validation_drawdown:.4f} | "
            f"validation_trades={summary.final_validation_trades:.1f} | "
            f"selection_gap={summary.train_validation_selection_gap:.4f} | "
            f"profit_gap={summary.train_validation_profit_gap:.4f}"
        )
        lines.append(f"  best_genome={summary.best_genome_repr}")
        lines.append(f"  log={summary.log_file_path}")
        lines.append("")

    return lines


def build_ranking_lines_by_profit(
    run_summaries: list[HistoricalRunSummary],
) -> list[str]:
    lines: list[str] = []

    sorted_runs = sorted(
        run_summaries,
        key=lambda summary: summary.final_validation_profit,
        reverse=True,
    )

    lines.append("Ranking by final validation profit")

    for index, summary in enumerate(sorted_runs, start=1):
        lines.append(
            f"{index}. "
            f"{summary.config_name} | "
            f"run_id={summary.run_id} | "
            f"mutation_seed={summary.mutation_seed} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_drawdown={summary.final_validation_drawdown:.4f} | "
            f"validation_trades={summary.final_validation_trades:.1f} | "
            f"selection_gap={summary.train_validation_selection_gap:.4f} | "
            f"profit_gap={summary.train_validation_profit_gap:.4f}"
        )
        lines.append(f"  best_genome={summary.best_genome_repr}")
        lines.append(f"  log={summary.log_file_path}")
        lines.append("")

    return lines


def build_batch_summary_lines(
    run_summaries: list[HistoricalRunSummary],
    dataset_root: Path,
) -> list[str]:
    lines: list[str] = []

    lines.append(f"Batch executed at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Dataset root: {dataset_root}")
    lines.append(f"Runs executed: {len(run_summaries)}")
    lines.append("")

    lines.extend(build_ranking_lines_by_selection(run_summaries))
    lines.append("")
    lines.extend(build_ranking_lines_by_profit(run_summaries))

    return lines


def build_log_name(config_path: Path) -> str:
    return f"run_{config_path.stem}.txt"


def create_batch_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = BATCHES_ROOT_DIR / f"batch_{timestamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def write_batch_summary(
    run_summaries: list[HistoricalRunSummary],
    batch_dir: Path,
    dataset_root: Path,
) -> Path:
    batch_summary_path = batch_dir / "batch_summary.txt"
    lines = build_batch_summary_lines(
        run_summaries=run_summaries,
        dataset_root=dataset_root,
    )
    batch_summary_path.write_text("\n".join(lines), encoding="utf-8")
    return batch_summary_path


def run_batch_experiment(
    configs_dir: Path = CONFIGS_DIR,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
) -> Path | None:
    config_files = sorted(configs_dir.glob("*.json"))

    if not config_files:
        print("No config files found.")
        return None

    print(f"Found {len(config_files)} config files.")
    print(f"Dataset root: {dataset_root}")

    batch_dir = create_batch_dir()
    print(f"Writing batch artifacts to {batch_dir}")

    run_summaries: list[HistoricalRunSummary] = []

    for config_path in config_files:
        print()
        print(f"=== Running {config_path.name} ===")

        summary = execute_historical_run(
            config_path=config_path,
            output_dir=batch_dir,
            log_name=build_log_name(config_path),
            dataset_root=dataset_root,
        )
        run_summaries.append(summary)

    batch_summary_path = write_batch_summary(
        run_summaries=run_summaries,
        batch_dir=batch_dir,
        dataset_root=dataset_root,
    )

    print()
    print(f"Batch summary saved to {batch_summary_path}")
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
    args = parser.parse_args(argv)

    run_batch_experiment(
        configs_dir=args.configs_dir,
        dataset_root=args.dataset_root,
    )


if __name__ == "__main__":
    main()
