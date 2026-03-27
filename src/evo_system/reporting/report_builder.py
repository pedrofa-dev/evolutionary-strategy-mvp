from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from evo_system.reporting.champion_card import build_champion_card
from evo_system.reporting.champion_loader import flatten_champion, load_champions
from evo_system.reporting.champion_queries import (
    filter_champions,
    select_primary_champion_row,
)
from evo_system.reporting.champion_stats import (
    build_config_summary,
    build_context_config_summary,
    build_context_mix_warnings,
    build_context_summary,
    build_signal_pair_summary,
    build_top_examples,
    detect_recurrent_patterns,
    summarize_bool_fields,
    summarize_numeric_fields,
)


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
    "weight_trend_strength",
    "weight_realized_volatility",
    "weight_trend_long",
    "weight_breakout",
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


def ensure_output_dir(output_dir: Path | None) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    auto_dir = DEFAULT_OUTPUT_ROOT / f"champions_{timestamp}"
    auto_dir.mkdir(parents=True, exist_ok=True)
    return auto_dir


def export_flat_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted(
        {
            key
            for row in rows
            for key in row.keys()
        }
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def format_context_summary_block(summary: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["Experimental context summary"]

    if not summary:
        lines.append("  No data.")
        lines.append("")
        return lines

    for _, stats in summary.items():
        lines.append(
            f"  context={stats.get('context_label') or 'unknown'} | "
            f"context_name={stats.get('context_name') or 'none'} | "
            f"dataset_root={stats.get('dataset_root') or 'unknown'} | "
            f"train_dataset_count_available={stats.get('train_dataset_count_available', 'unknown')} | "
            f"validation_dataset_count_available={stats.get('validation_dataset_count_available', 'unknown')} | "
            f"train_sample_size={stats.get('train_sample_size', 'unknown')} | "
            f"dataset_signature={stats.get('dataset_signature') or 'unknown'} | "
            f"champions={int(stats['champion_count'])} | "
            f"mean_validation_selection={stats['mean_validation_selection']:.6f} | "
            f"mean_validation_profit={stats['mean_validation_profit']:.6f}"
        )

    lines.append("")
    return lines


def format_context_config_summary_block(
    summary: dict[str, dict[str, dict[str, float]]],
) -> list[str]:
    lines = ["Config summary by context"]

    if not summary:
        lines.append("  No data.")
        lines.append("")
        return lines

    for context_key, config_summary in summary.items():
        lines.append(f"  Context: {context_key}")
        if not config_summary:
            lines.append("  No config data.")
            continue

        for config_name, stats in config_summary.items():
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


def format_context_warning_block(warnings: list[str]) -> list[str]:
    lines = ["Context consistency"]

    if not warnings:
        lines.append("  No mixed contexts detected.")
        lines.append("")
        return lines

    lines.append("  Review context mixing before comparing champions.")
    for warning in warnings:
        lines.append(f"  {warning}")

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
            lines.append(f"    {field}: type={data['type']} | rate={rate:.2%}")

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
    pair_summary = build_signal_pair_summary(rows, SIGNAL_PAIR_FIELDS)
    context_summary = build_context_summary(rows)
    context_config_summary = build_context_config_summary(rows)
    config_summary = build_config_summary(rows)
    context_warnings = build_context_mix_warnings(rows)
    patterns = detect_recurrent_patterns(
        rows,
        genome_bool_fields=GENOME_BOOL_FIELDS,
        signal_pair_fields=SIGNAL_PAIR_FIELDS,
    )
    top_examples = build_top_examples(rows)

    lines: list[str] = [
        "Champion analysis report",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Champion count: {len(rows)}",
        f"Run filter: {run_id or 'none'}",
        f"Config filter: {config_name or 'none'}",
        "",
    ]
    lines.extend(format_context_warning_block(context_warnings))
    lines.extend(format_context_summary_block(context_summary))
    lines.extend(format_context_config_summary_block(context_config_summary))
    lines.extend(
        format_numeric_summary_block("Genome numeric summary", genome_numeric_summary)
    )
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
        "context_summary": context_summary,
        "context_config_summary": context_config_summary,
        "context_warnings": context_warnings,
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


def analyze_champions(
    db_path: Path,
    output_dir: Path | None = None,
    run_id: str | None = None,
    config_name: str | None = None,
) -> dict[str, Any] | None:
    final_output_dir = ensure_output_dir(output_dir)
    champions = filter_champions(
        load_champions(db_path=db_path, run_id=run_id),
        config_name,
    )

    if not champions:
        return None

    flat_rows = [flatten_champion(champion) for champion in champions]
    csv_path = final_output_dir / "champions_flat.csv"
    report_path = final_output_dir / "champion_report.txt"
    patterns_path = final_output_dir / "patterns.json"
    champion_card_path = final_output_dir / "champion_card.json"

    export_flat_csv(flat_rows, csv_path)
    report_data = write_report(
        report_path=report_path,
        rows=flat_rows,
        run_id=run_id,
        config_name=config_name,
    )
    primary_row = select_primary_champion_row(flat_rows)
    champion_card = build_champion_card(primary_row) if primary_row is not None else {}

    patterns_path.write_text(
        json.dumps(make_json_safe(report_data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    champion_card_path.write_text(
        json.dumps(make_json_safe(champion_card), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "champion_count": len(champions),
        "output_dir": final_output_dir,
        "csv_path": csv_path,
        "report_path": report_path,
        "patterns_path": patterns_path,
        "champion_card_path": champion_card_path,
        "report_data": report_data,
        "champion_card": champion_card,
    }
