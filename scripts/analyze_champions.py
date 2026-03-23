from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any


DEFAULT_DB_PATH = Path("data/evolution.db")
DEFAULT_OUTPUT_ROOT = Path("artifacts/analysis")


GENOME_NUMERIC_FIELDS = [
    "threshold_open",
    "threshold_close",
    "position_size",
    "stop_loss",
    "take_profit",
    "momentum_threshold",
    "trend_threshold",
    "trend_window",
    "exit_momentum_threshold",
    "ret_short_window",
    "ret_mid_window",
    "ma_window",
    "range_window",
    "vol_short_window",
    "vol_long_window",
    "weight_ret_short",
    "weight_ret_mid",
    "weight_dist_ma",
    "weight_range_pos",
    "weight_vol_ratio",
]

GENOME_BOOL_FIELDS = [
    "use_momentum",
    "use_trend",
    "use_exit_momentum",
]

KEY_METRIC_FIELDS = [
    "train_selection",
    "train_profit",
    "train_drawdown",
    "train_trades",
    "validation_selection",
    "validation_profit",
    "validation_drawdown",
    "validation_trades",
    "selection_gap",
    "validation_dispersion",
]

SIGNAL_PAIR_FIELDS = [
    ("use_momentum", "use_trend"),
    ("use_momentum", "use_exit_momentum"),
    ("use_trend", "use_exit_momentum"),
]


@dataclass
class ChampionRow:
    id: int
    run_id: str
    generation_number: int | None
    mutation_seed: int | None
    config_name: str | None
    genome: dict[str, Any]
    metrics: dict[str, Any]
    created_at: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze persisted champions from SQLite.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database. Default: data/evolution.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Default: artifacts/analysis/champions_<timestamp>",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run_id filter.",
    )
    parser.add_argument(
        "--config-name",
        type=str,
        default=None,
        help="Optional config_name filter.",
    )
    return parser.parse_args()


def ensure_output_dir(output_dir: Path | None) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    auto_dir = DEFAULT_OUTPUT_ROOT / f"champions_{timestamp}"
    auto_dir.mkdir(parents=True, exist_ok=True)
    return auto_dir


def load_champions(
    db_path: Path,
    run_id: str | None = None,
    config_name: str | None = None,
) -> list[ChampionRow]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    query = """
        SELECT
            id,
            run_id,
            generation_number,
            mutation_seed,
            config_name,
            genome_json,
            metrics_json,
            created_at
        FROM champions
    """

    conditions: list[str] = []
    params: list[Any] = []

    if run_id is not None:
        conditions.append("run_id = ?")
        params.append(run_id)

    if config_name is not None:
        conditions.append("config_name = ?")
        params.append(config_name)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id ASC"

    rows: list[ChampionRow] = []

    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(query, tuple(params))
        for db_row in cursor.fetchall():
            rows.append(
                ChampionRow(
                    id=int(db_row[0]),
                    run_id=str(db_row[1]),
                    generation_number=db_row[2],
                    mutation_seed=db_row[3],
                    config_name=db_row[4],
                    genome=json.loads(db_row[5]),
                    metrics=json.loads(db_row[6]),
                    created_at=db_row[7],
                )
            )

    return rows


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def safe_median(values: list[float]) -> float:
    return median(values) if values else 0.0


def safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return pstdev(values)


def safe_min(values: list[float]) -> float:
    return min(values) if values else 0.0


def safe_max(values: list[float]) -> float:
    return max(values) if values else 0.0


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    index = (len(sorted_values) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return sorted_values[lower]

    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def numeric_summary(values: list[float]) -> dict[str, float]:
    sorted_values = sorted(values)
    return {
        "count": float(len(values)),
        "mean": safe_mean(values),
        "median": safe_median(values),
        "std": safe_std(values),
        "min": safe_min(values),
        "p25": percentile(sorted_values, 0.25),
        "p75": percentile(sorted_values, 0.75),
        "max": safe_max(values),
    }


def normalize_bool(value: Any) -> bool:
    return bool(value)


def flatten_champion(champion: ChampionRow) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "id": champion.id,
        "run_id": champion.run_id,
        "generation_number": champion.generation_number,
        "mutation_seed": champion.mutation_seed,
        "config_name": champion.config_name,
        "created_at": champion.created_at,
    }

    for field in GENOME_BOOL_FIELDS:
        flat[field] = normalize_bool(champion.genome.get(field, False))

    for field in GENOME_NUMERIC_FIELDS:
        flat[field] = champion.genome.get(field)

    for field in KEY_METRIC_FIELDS:
        flat[field] = champion.metrics.get(field)

    flat["train_dataset_count"] = len(champion.metrics.get("train_dataset_names", []))
    flat["validation_dataset_count"] = len(champion.metrics.get("validation_dataset_names", []))
    flat["train_violation_count"] = len(champion.metrics.get("train_violations", []))
    flat["validation_violation_count"] = len(champion.metrics.get("validation_violations", []))
    flat["train_is_valid"] = champion.metrics.get("train_is_valid")
    flat["validation_is_valid"] = champion.metrics.get("validation_is_valid")

    train_scores = champion.metrics.get("train_dataset_scores", [])
    validation_scores = champion.metrics.get("validation_dataset_scores", [])
    train_profits = champion.metrics.get("train_dataset_profits", [])
    validation_profits = champion.metrics.get("validation_dataset_profits", [])
    train_drawdowns = champion.metrics.get("train_dataset_drawdowns", [])
    validation_drawdowns = champion.metrics.get("validation_dataset_drawdowns", [])

    flat["train_score_best"] = safe_max(train_scores)
    flat["train_score_worst"] = safe_min(train_scores)
    flat["validation_score_best"] = safe_max(validation_scores)
    flat["validation_score_worst"] = safe_min(validation_scores)

    flat["train_profit_best"] = safe_max(train_profits)
    flat["train_profit_worst"] = safe_min(train_profits)
    flat["validation_profit_best"] = safe_max(validation_profits)
    flat["validation_profit_worst"] = safe_min(validation_profits)

    flat["train_drawdown_best"] = safe_min(train_drawdowns)
    flat["train_drawdown_worst"] = safe_max(train_drawdowns)
    flat["validation_drawdown_best"] = safe_min(validation_drawdowns)
    flat["validation_drawdown_worst"] = safe_max(validation_drawdowns)

    return flat


def export_flat_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted(rows[0].keys())

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_numeric_fields(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}

    for field in fields:
        values: list[float] = []
        for row in rows:
            value = row.get(field)
            if isinstance(value, (int, float)) and value is not None:
                values.append(float(value))

        if values:
            result[field] = numeric_summary(values)

    return result


def summarize_bool_fields(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    total = len(rows)

    if total == 0:
        return result

    for field in fields:
        enabled = sum(1 for row in rows if bool(row.get(field)))
        disabled = total - enabled
        result[field] = {
            "enabled_count": float(enabled),
            "disabled_count": float(disabled),
            "enabled_rate": enabled / total,
        }

    return result


def build_signal_pair_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    total = len(rows)
    result: dict[str, dict[str, float]] = {}

    if total == 0:
        return result

    for left, right in SIGNAL_PAIR_FIELDS:
        both = sum(1 for row in rows if bool(row.get(left)) and bool(row.get(right)))
        left_only = sum(1 for row in rows if bool(row.get(left)) and not bool(row.get(right)))
        right_only = sum(1 for row in rows if not bool(row.get(left)) and bool(row.get(right)))
        neither = total - both - left_only - right_only

        key = f"{left}__{right}"
        result[key] = {
            "both_count": float(both),
            "left_only_count": float(left_only),
            "right_only_count": float(right_only),
            "neither_count": float(neither),
            "both_rate": both / total,
        }

    return result


def build_config_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        config_name = str(row.get("config_name") or "unknown")
        grouped[config_name].append(row)

    summary: dict[str, dict[str, float]] = {}

    for config_name, config_rows in sorted(grouped.items()):
        validation_selection_values = [
            float(row["validation_selection"])
            for row in config_rows
            if isinstance(row.get("validation_selection"), (int, float))
        ]
        validation_profit_values = [
            float(row["validation_profit"])
            for row in config_rows
            if isinstance(row.get("validation_profit"), (int, float))
        ]
        validation_drawdown_values = [
            float(row["validation_drawdown"])
            for row in config_rows
            if isinstance(row.get("validation_drawdown"), (int, float))
        ]
        validation_trades_values = [
            float(row["validation_trades"])
            for row in config_rows
            if isinstance(row.get("validation_trades"), (int, float))
        ]
        gap_values = [
            abs(float(row["selection_gap"]))
            for row in config_rows
            if isinstance(row.get("selection_gap"), (int, float))
        ]

        summary[config_name] = {
            "champion_count": float(len(config_rows)),
            "mean_validation_selection": safe_mean(validation_selection_values),
            "mean_validation_profit": safe_mean(validation_profit_values),
            "mean_validation_drawdown": safe_mean(validation_drawdown_values),
            "mean_validation_trades": safe_mean(validation_trades_values),
            "mean_abs_selection_gap": safe_mean(gap_values),
        }

    return summary


def detect_recurrent_patterns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    patterns: dict[str, Any] = {}
    total = len(rows)

    if total == 0:
        return patterns

    bool_summary = summarize_bool_fields(rows, GENOME_BOOL_FIELDS)
    patterns["signal_patterns"] = {}

    for field, stats in bool_summary.items():
        enabled_rate = stats["enabled_rate"]
        if enabled_rate >= 0.70:
            patterns["signal_patterns"][field] = {
                "type": "recurrent_enabled",
                "enabled_rate": enabled_rate,
            }
        elif enabled_rate <= 0.30:
            patterns["signal_patterns"][field] = {
                "type": "recurrent_disabled",
                "enabled_rate": enabled_rate,
            }

    numeric_fields_to_check = [
        "threshold_open",
        "threshold_close",
        "stop_loss",
        "take_profit",
        "weight_ret_short",
        "weight_ret_mid",
        "weight_dist_ma",
        "weight_range_pos",
        "weight_vol_ratio",
        "validation_selection",
        "validation_profit",
        "validation_drawdown",
        "validation_trades",
    ]

    patterns["concentrated_numeric_fields"] = {}

    for field in numeric_fields_to_check:
        values = [
            float(row[field])
            for row in rows
            if isinstance(row.get(field), (int, float))
        ]
        if not values:
            continue

        stats = numeric_summary(values)
        iqr = stats["p75"] - stats["p25"]
        value_range = stats["max"] - stats["min"]

        if value_range == 0:
            concentration_ratio = 0.0
        else:
            concentration_ratio = iqr / value_range

        if concentration_ratio <= 0.35:
            patterns["concentrated_numeric_fields"][field] = {
                "median": stats["median"],
                "p25": stats["p25"],
                "p75": stats["p75"],
                "iqr_to_range_ratio": concentration_ratio,
            }

    patterns["weight_sign_bias"] = {}
    weight_fields = [
        "weight_ret_short",
        "weight_ret_mid",
        "weight_dist_ma",
        "weight_range_pos",
        "weight_vol_ratio",
    ]

    for field in weight_fields:
        values = [
            float(row[field])
            for row in rows
            if isinstance(row.get(field), (int, float))
        ]
        if not values:
            continue

        positive_rate = sum(1 for value in values if value > 0.0) / len(values)
        negative_rate = sum(1 for value in values if value < 0.0) / len(values)

        if positive_rate >= 0.70:
            patterns["weight_sign_bias"][field] = {
                "type": "mostly_positive",
                "positive_rate": positive_rate,
            }
        elif negative_rate >= 0.70:
            patterns["weight_sign_bias"][field] = {
                "type": "mostly_negative",
                "negative_rate": negative_rate,
            }

    pair_summary = build_signal_pair_summary(rows)
    patterns["signal_pair_patterns"] = {}

    for pair_name, stats in pair_summary.items():
        if stats["both_rate"] >= 0.50:
            patterns["signal_pair_patterns"][pair_name] = {
                "type": "frequent_pair",
                "both_rate": stats["both_rate"],
            }

    patterns["meta"] = {
        "champion_count": total,
    }

    return patterns


def build_top_examples(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}

    if not rows:
        return examples

    def best_by(field: str, reverse: bool = True) -> dict[str, Any]:
        valid_rows = [row for row in rows if isinstance(row.get(field), (int, float))]
        if not valid_rows:
            return {}
        return sorted(valid_rows, key=lambda row: float(row[field]), reverse=reverse)[0]

    examples["best_validation_selection"] = best_by("validation_selection", reverse=True)
    examples["best_validation_profit"] = best_by("validation_profit", reverse=True)
    examples["lowest_validation_drawdown"] = best_by("validation_drawdown", reverse=False)
    examples["lowest_abs_selection_gap"] = sorted(
        [row for row in rows if isinstance(row.get("selection_gap"), (int, float))],
        key=lambda row: abs(float(row["selection_gap"])),
    )[0] if rows else {}

    return examples


def format_numeric_summary_block(
    title: str,
    stats_by_field: dict[str, dict[str, float]],
) -> list[str]:
    lines = [title]

    if not stats_by_field:
        lines.append("  No data.")
        lines.append("")
        return lines

    for field, stats in stats_by_field.items():
        lines.append(
            f"  {field}: "
            f"count={int(stats['count'])} | "
            f"mean={stats['mean']:.6f} | "
            f"median={stats['median']:.6f} | "
            f"std={stats['std']:.6f} | "
            f"min={stats['min']:.6f} | "
            f"p25={stats['p25']:.6f} | "
            f"p75={stats['p75']:.6f} | "
            f"max={stats['max']:.6f}"
        )

    lines.append("")
    return lines


def format_bool_summary_block(
    title: str,
    stats_by_field: dict[str, dict[str, float]],
) -> list[str]:
    lines = [title]

    if not stats_by_field:
        lines.append("  No data.")
        lines.append("")
        return lines

    for field, stats in stats_by_field.items():
        lines.append(
            f"  {field}: "
            f"enabled={int(stats['enabled_count'])} | "
            f"disabled={int(stats['disabled_count'])} | "
            f"enabled_rate={stats['enabled_rate']:.2%}"
        )

    lines.append("")
    return lines


def format_signal_pair_block(stats_by_pair: dict[str, dict[str, float]]) -> list[str]:
    lines = ["Signal pair co-occurrence"]

    if not stats_by_pair:
        lines.append("  No data.")
        lines.append("")
        return lines

    for pair_name, stats in stats_by_pair.items():
        lines.append(
            f"  {pair_name}: "
            f"both={int(stats['both_count'])} | "
            f"left_only={int(stats['left_only_count'])} | "
            f"right_only={int(stats['right_only_count'])} | "
            f"neither={int(stats['neither_count'])} | "
            f"both_rate={stats['both_rate']:.2%}"
        )

    lines.append("")
    return lines


def format_config_summary_block(summary: dict[str, dict[str, float]]) -> list[str]:
    lines = ["Config summary"]

    if not summary:
        lines.append("  No data.")
        lines.append("")
        return lines

    for config_name, stats in summary.items():
        lines.append(
            f"  {config_name}: "
            f"champions={int(stats['champion_count'])} | "
            f"mean_validation_selection={stats['mean_validation_selection']:.6f} | "
            f"mean_validation_profit={stats['mean_validation_profit']:.6f} | "
            f"mean_validation_drawdown={stats['mean_validation_drawdown']:.6f} | "
            f"mean_validation_trades={stats['mean_validation_trades']:.2f} | "
            f"mean_abs_selection_gap={stats['mean_abs_selection_gap']:.6f}"
        )

    lines.append("")
    return lines


def format_patterns_block(patterns: dict[str, Any]) -> list[str]:
    lines = ["Recurrent patterns"]

    if not patterns:
        lines.append("  No patterns detected.")
        lines.append("")
        return lines

    signal_patterns = patterns.get("signal_patterns", {})
    concentrated_fields = patterns.get("concentrated_numeric_fields", {})
    weight_sign_bias = patterns.get("weight_sign_bias", {})
    signal_pair_patterns = patterns.get("signal_pair_patterns", {})

    if signal_patterns:
        lines.append("  Signal patterns:")
        for field, data in signal_patterns.items():
            lines.append(
                f"    {field}: type={data['type']} | enabled_rate={data['enabled_rate']:.2%}"
            )

    if concentrated_fields:
        lines.append("  Concentrated numeric fields:")
        for field, data in concentrated_fields.items():
            lines.append(
                f"    {field}: median={data['median']:.6f} | "
                f"p25={data['p25']:.6f} | "
                f"p75={data['p75']:.6f} | "
                f"iqr_to_range_ratio={data['iqr_to_range_ratio']:.6f}"
            )

    if weight_sign_bias:
        lines.append("  Weight sign bias:")
        for field, data in weight_sign_bias.items():
            rate = data.get("positive_rate", data.get("negative_rate", 0.0))
            lines.append(
                f"    {field}: type={data['type']} | rate={rate:.2%}"
            )

    if signal_pair_patterns:
        lines.append("  Signal pair patterns:")
        for pair_name, data in signal_pair_patterns.items():
            lines.append(
                f"    {pair_name}: type={data['type']} | both_rate={data['both_rate']:.2%}"
            )

    if len(lines) == 1:
        lines.append("  No patterns detected.")

    lines.append("")
    return lines


def format_top_examples_block(examples: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["Top examples"]

    if not examples:
        lines.append("  No examples.")
        lines.append("")
        return lines

    for label, row in examples.items():
        if not row:
            continue

        lines.append(
            f"  {label}: "
            f"id={row.get('id')} | "
            f"config={row.get('config_name')} | "
            f"run_id={row.get('run_id')} | "
            f"generation={row.get('generation_number')} | "
            f"validation_selection={float(row.get('validation_selection', 0.0)):.6f} | "
            f"validation_profit={float(row.get('validation_profit', 0.0)):.6f} | "
            f"validation_drawdown={float(row.get('validation_drawdown', 0.0)):.6f} | "
            f"validation_trades={float(row.get('validation_trades', 0.0)):.2f} | "
            f"selection_gap={float(row.get('selection_gap', 0.0)):.6f}"
        )

    lines.append("")
    return lines


def write_report(
    report_path: Path,
    rows: list[dict[str, Any]],
    run_id: str | None,
    config_name: str | None,
) -> dict[str, Any]:
    genome_numeric_summary = summarize_numeric_fields(rows, GENOME_NUMERIC_FIELDS)
    genome_bool_summary = summarize_bool_fields(rows, GENOME_BOOL_FIELDS)
    metric_summary = summarize_numeric_fields(rows, KEY_METRIC_FIELDS)
    pair_summary = build_signal_pair_summary(rows)
    config_summary = build_config_summary(rows)
    patterns = detect_recurrent_patterns(rows)
    top_examples = build_top_examples(rows)

    lines: list[str] = [
        "Champion analysis report",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Champion count: {len(rows)}",
        f"Run filter: {run_id or 'none'}",
        f"Config filter: {config_name or 'none'}",
        "",
    ]

    lines.extend(format_numeric_summary_block("Genome numeric summary", genome_numeric_summary))
    lines.extend(format_bool_summary_block("Signal usage summary", genome_bool_summary))
    lines.extend(format_numeric_summary_block("Metric summary", metric_summary))
    lines.extend(format_signal_pair_block(pair_summary))
    lines.extend(format_config_summary_block(config_summary))
    lines.extend(format_patterns_block(patterns))
    lines.extend(format_top_examples_block(top_examples))

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "genome_numeric_summary": genome_numeric_summary,
        "genome_bool_summary": genome_bool_summary,
        "metric_summary": metric_summary,
        "signal_pair_summary": pair_summary,
        "config_summary": config_summary,
        "patterns": patterns,
        "top_examples": top_examples,
    }


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(sub_value) for key, sub_value in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def main() -> None:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)

    champions = load_champions(
        db_path=args.db_path,
        run_id=args.run_id,
        config_name=args.config_name,
    )

    if not champions:
        print("No champions found with the provided filters.")
        return

    flat_rows = [flatten_champion(champion) for champion in champions]

    csv_path = output_dir / "champions_flat.csv"
    report_path = output_dir / "champion_report.txt"
    patterns_path = output_dir / "patterns.json"

    export_flat_csv(flat_rows, csv_path)
    report_data = write_report(
        report_path=report_path,
        rows=flat_rows,
        run_id=args.run_id,
        config_name=args.config_name,
    )

    patterns_path.write_text(
        json.dumps(make_json_safe(report_data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Champions loaded: {len(champions)}")
    print(f"CSV exported to: {csv_path}")
    print(f"Report exported to: {report_path}")
    print(f"Patterns exported to: {patterns_path}")


if __name__ == "__main__":
    main()