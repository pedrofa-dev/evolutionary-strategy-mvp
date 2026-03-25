from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median, pstdev
from typing import Any


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


def summarize_numeric_fields(
    rows: list[dict[str, Any]],
    fields: list[str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}

    for field in fields:
        values = [
            float(row[field])
            for row in rows
            if isinstance(row.get(field), (int, float))
        ]
        if values:
            result[field] = numeric_summary(values)

    return result


def summarize_bool_fields(
    rows: list[dict[str, Any]],
    fields: list[str],
) -> dict[str, dict[str, float]]:
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


def build_signal_pair_summary(
    rows: list[dict[str, Any]],
    signal_pair_fields: list[tuple[str, str]],
) -> dict[str, dict[str, float]]:
    total = len(rows)
    result: dict[str, dict[str, float]] = {}

    if total == 0:
        return result

    for left, right in signal_pair_fields:
        both = sum(1 for row in rows if bool(row.get(left)) and bool(row.get(right)))
        left_only = sum(
            1 for row in rows if bool(row.get(left)) and not bool(row.get(right))
        )
        right_only = sum(
            1 for row in rows if not bool(row.get(left)) and bool(row.get(right))
        )
        neither = total - both - left_only - right_only

        result[f"{left}__{right}"] = {
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
        grouped[str(row.get("config_name") or "unknown")].append(row)

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


def build_context_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("experimental_context") or "unknown")].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for context_key, context_rows in sorted(grouped.items()):
        validation_selection_values = [
            float(row["validation_selection"])
            for row in context_rows
            if isinstance(row.get("validation_selection"), (int, float))
        ]
        validation_profit_values = [
            float(row["validation_profit"])
            for row in context_rows
            if isinstance(row.get("validation_profit"), (int, float))
        ]
        first_row = context_rows[0]
        summary[context_key] = {
            "champion_count": float(len(context_rows)),
            "context_label": first_row.get("context_label"),
            "context_name": first_row.get("context_name"),
            "config_name": first_row.get("config_name"),
            "dataset_root": first_row.get("dataset_root"),
            "train_dataset_count_available": first_row.get(
                "train_dataset_count_available"
            ),
            "validation_dataset_count_available": first_row.get(
                "validation_dataset_count_available"
            ),
            "train_sample_size": first_row.get("train_sample_size"),
            "dataset_signature": first_row.get("dataset_signature"),
            "mean_validation_selection": safe_mean(validation_selection_values),
            "mean_validation_profit": safe_mean(validation_profit_values),
        }

    return summary


def build_context_config_summary(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("experimental_context") or "unknown")].append(row)

    summary: dict[str, dict[str, dict[str, float]]] = {}
    for context_key, context_rows in sorted(grouped.items()):
        summary[context_key] = build_config_summary(context_rows)

    return summary


def build_context_mix_warnings(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    distinct_signatures = {
        str(row.get("dataset_signature"))
        for row in rows
        if row.get("dataset_signature") is not None
    }
    distinct_contexts = {
        str(row.get("experimental_context"))
        for row in rows
        if row.get("experimental_context") is not None
    }
    distinct_configs = {
        str(row.get("config_name"))
        for row in rows
        if row.get("config_name") is not None
    }

    if len(distinct_signatures) > 1:
        warnings.append(
            "WARNING: multiple dataset_signature values detected. This report mixes different dataset pools or sampling contexts."
        )
    elif len(distinct_contexts) == 1 and len(distinct_configs) > 1:
        warnings.append(
            "Notice: multiple config_name values detected within the same experimental context."
        )

    return warnings


def detect_recurrent_patterns(
    rows: list[dict[str, Any]],
    genome_bool_fields: list[str],
    signal_pair_fields: list[tuple[str, str]],
) -> dict[str, Any]:
    patterns: dict[str, Any] = {}
    total = len(rows)

    if total == 0:
        return patterns

    bool_summary = summarize_bool_fields(rows, genome_bool_fields)
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
        concentration_ratio = 0.0 if value_range == 0 else iqr / value_range

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

    pair_summary = build_signal_pair_summary(rows, signal_pair_fields)
    patterns["signal_pair_patterns"] = {}
    for pair_name, stats in pair_summary.items():
        if stats["both_rate"] >= 0.50:
            patterns["signal_pair_patterns"][pair_name] = {
                "type": "frequent_pair",
                "both_rate": stats["both_rate"],
            }

    patterns["meta"] = {"champion_count": total}
    return patterns


def build_top_examples(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    examples: dict[str, dict[str, Any]] = {}
    if not rows:
        return examples

    def best_by(field: str, reverse: bool = True) -> dict[str, Any]:
        valid_rows = [row for row in rows if isinstance(row.get(field), (int, float))]
        if not valid_rows:
            return {}
        return sorted(
            valid_rows,
            key=lambda row: float(row[field]),
            reverse=reverse,
        )[0]

    examples["best_validation_selection"] = best_by("validation_selection", True)
    examples["best_validation_profit"] = best_by("validation_profit", True)
    examples["lowest_validation_drawdown"] = best_by(
        "validation_drawdown",
        False,
    )
    examples["lowest_abs_selection_gap"] = (
        sorted(
            [row for row in rows if isinstance(row.get("selection_gap"), (int, float))],
            key=lambda row: abs(float(row["selection_gap"])),
        )[0]
        if rows
        else {}
    )
    return examples


def safe_list_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return safe_std(values)
