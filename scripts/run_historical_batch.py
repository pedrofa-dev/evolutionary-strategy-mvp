from datetime import datetime
from pathlib import Path

from run_historical import RUN_LOG_DIR, HistoricalRunSummary, execute_historical_run
from evo_system.domain.run_summary import HistoricalRunSummary


CONFIGS_DIR = Path("configs/runs")


def build_batch_summary_lines(
    run_summaries: list[HistoricalRunSummary],
) -> list[str]:
    lines: list[str] = []

    lines.append(f"Batch executed at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Runs executed: {len(run_summaries)}")
    lines.append("")

    sorted_runs = sorted(
        run_summaries,
        key=lambda summary: summary.final_validation_selection_score,
        reverse=True,
    )

    lines.append("Ranking by final validation selection score")
    for index, summary in enumerate(sorted_runs, start=1):
        lines.append(
            f"{index}. {summary.config_name} | "
            f"run_id={summary.run_id} | "
            f"best_train={summary.best_train_selection_score:.4f} | "
            f"validation_selection={summary.final_validation_selection_score:.4f} | "
            f"validation_profit={summary.final_validation_profit:.4f} | "
            f"validation_drawdown={summary.final_validation_drawdown:.4f} | "
            f"validation_trades={summary.final_validation_trades:.1f}"
        )
        lines.append(f"   best_genome={summary.best_genome_repr}")
        lines.append(f"   log={summary.log_file_path}")
        lines.append("")

    return lines


def write_batch_summary(run_summaries: list[HistoricalRunSummary]) -> Path:
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_summary_path = RUN_LOG_DIR / f"batch_{timestamp}.txt"

    lines = build_batch_summary_lines(run_summaries)
    batch_summary_path.write_text("\n".join(lines), encoding="utf-8")

    return batch_summary_path


def main() -> None:
    config_files = sorted(CONFIGS_DIR.glob("*.json"))

    if not config_files:
        print("No config files found.")
        return

    print(f"Found {len(config_files)} config files.")

    run_summaries: list[HistoricalRunSummary] = []

    for config_path in config_files:
        print()
        print(f"=== Running {config_path.name} ===")
        summary = execute_historical_run(config_path)
        run_summaries.append(summary)

    batch_summary_path = write_batch_summary(run_summaries)

    print()
    print(f"Batch summary saved to {batch_summary_path}")


if __name__ == "__main__":
    main()