import argparse
import json
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime
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
from evo_system.experimentation.presets import (
    apply_preset_to_config_data,
    apply_preset_to_seeds,
    get_available_preset_names,
    get_preset_by_name,
)
from evo_system.experimentation.single_run import (
    DEFAULT_DATASET_ROOT,
    execute_historical_run,
)

CONFIGS_DIR = Path("configs/runs")
BATCHES_ROOT_DIR = Path("artifacts/batches")
DEFAULT_SEEDS = [101, 102, 103]
DEFAULT_CONTEXT_NAME: str | None = None


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


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


def create_multiseed_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    multiseed_dir = BATCHES_ROOT_DIR / f"multiseed_{timestamp}"
    multiseed_dir.mkdir(parents=True, exist_ok=True)
    return multiseed_dir


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
    seeds: list[int],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None = None,
) -> list[HistoricalRunSummary]:
    summaries: list[HistoricalRunSummary] = []
    preset = get_preset_by_name(preset_name)

    for config_path in config_paths:
        base_config = load_config(config_path)
        effective_config = apply_preset_to_config_data(base_config, preset)

        for seed in seeds:
            print()
            print(f"=== Running {config_path.name} with seed {seed} ===")
            if context_name:
                print(f"Context: {context_name}")
            if preset is not None:
                print(
                    f"Preset: {preset.name} | "
                    f"generations={effective_config['generations_planned']}"
                )

            config_copy = dict(effective_config)
            config_copy["mutation_seed"] = seed
            temp_config_path = write_temp_config(config_copy)

            try:
                summary = execute_historical_run(
                    config_path=temp_config_path,
                    output_dir=output_dir,
                    log_name=build_log_name(config_path, seed),
                    config_name_override=config_path.name,
                    dataset_root=dataset_root,
                    context_name=context_name,
                )

                summaries.append(summary)
            finally:
                temp_config_path.unlink(missing_ok=True)

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
    seeds: list[int],
    output_dir: Path,
    dataset_root: Path,
    context_name: str | None,
    preset_name: str | None,
    effective_generations: int | None,
) -> Path:
    summary_path = output_dir / "multiseed_summary.txt"

    lines = [
        f"Multiseed batch executed at: {datetime.now().isoformat(timespec='seconds')}",
        f"Preset: {preset_name or 'none'}",
        f"Effective generations: {effective_generations if effective_generations is not None else 'config-defined'}",
        f"Context name: {context_name or 'none'}",
        f"Dataset root: {dataset_root}",
        f"Configs executed: {len(set(summary.config_name for summary in summaries))}",
        f"Seeds per config: {len(seeds)}",
        f"Seeds used: {', '.join(str(seed) for seed in seeds)}",
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
) -> Path | None:
    config_paths = sorted(configs_dir.glob("*.json"))

    if not config_paths:
        print("No config files found.")
        return None

    preset = get_preset_by_name(preset_name)
    seeds = apply_preset_to_seeds(DEFAULT_SEEDS, preset)
    effective_generations = preset.generations if preset is not None else None

    print(f"Found {len(config_paths)} config files.")
    print(f"Using seeds: {seeds}")
    print(f"Preset: {preset_name or 'none'}")
    print(
        "Effective generations: "
        f"{effective_generations if effective_generations is not None else 'config-defined'}"
    )
    print(f"Context name: {context_name or 'none'}")
    print(f"Dataset root: {dataset_root}")

    output_dir = create_multiseed_dir()
    print(f"Writing multiseed artifacts to {output_dir}")

    summaries = execute_multiseed_runs(
        config_paths=config_paths,
        seeds=seeds,
        output_dir=output_dir,
        dataset_root=dataset_root,
        context_name=context_name,
        preset_name=preset_name,
    )

    summary_path = write_multiseed_summary(
        summaries=summaries,
        seeds=seeds,
        output_dir=output_dir,
        dataset_root=dataset_root,
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
    args = parser.parse_args(argv)

    run_multiseed_experiment(
        configs_dir=args.configs_dir,
        dataset_root=args.dataset_root,
        preset_name=args.preset,
    )


if __name__ == "__main__":
    main()
