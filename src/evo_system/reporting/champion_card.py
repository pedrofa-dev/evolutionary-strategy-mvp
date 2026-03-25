from __future__ import annotations

from typing import Any

from evo_system.reporting.champion_queries import classify_champion_fallback
from evo_system.reporting.champion_stats import safe_list_std


def build_best_and_worst_dataset(
    dataset_names: list[Any],
    dataset_scores: list[Any],
) -> tuple[str | None, str | None]:
    pairs = [
        (str(name), float(score))
        for name, score in zip(dataset_names, dataset_scores)
        if isinstance(score, (int, float))
    ]

    if not pairs:
        return None, None

    best_dataset = max(pairs, key=lambda item: item[1])[0]
    worst_dataset = min(pairs, key=lambda item: item[1])[0]
    return best_dataset, worst_dataset


def count_distribution(values: list[Any]) -> tuple[int | None, int | None]:
    numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric_values:
        return None, None

    positive_count = sum(1 for value in numeric_values if value > 0.0)
    negative_count = sum(1 for value in numeric_values if value < 0.0)
    return positive_count, negative_count


def build_genome_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "threshold_open": row.get("threshold_open"),
        "threshold_close": row.get("threshold_close"),
        "stop_loss": row.get("stop_loss"),
        "take_profit": row.get("take_profit"),
        "use_momentum": row.get("use_momentum"),
        "use_trend": row.get("use_trend"),
        "use_exit_momentum": row.get("use_exit_momentum"),
        "ret_short_window": row.get("ret_short_window"),
        "ret_mid_window": row.get("ret_mid_window"),
        "ma_window": row.get("ma_window"),
        "range_window": row.get("range_window"),
        "vol_short_window": row.get("vol_short_window"),
        "vol_long_window": row.get("vol_long_window"),
    }


def build_champion_card(row: dict[str, Any]) -> dict[str, Any]:
    validation_dataset_names = row.get("all_validation_dataset_names") or row.get(
        "validation_dataset_names",
        [],
    )
    validation_dataset_scores = row.get("validation_dataset_scores", [])
    validation_dataset_profits = row.get("validation_dataset_profits", [])

    best_dataset, worst_dataset = build_best_and_worst_dataset(
        validation_dataset_names,
        validation_dataset_scores,
    )
    positive_datasets, negative_datasets = count_distribution(
        validation_dataset_profits
    )

    card = {
        "champion_id": row.get("id"),
        "config_name": row.get("config_name"),
        "seed": row.get("mutation_seed"),
        "type": row.get("champion_type"),
        "scores": {
            "train_selection": row.get("train_selection"),
            "validation_selection": row.get("validation_selection"),
            "selection_gap": row.get("selection_gap"),
            "validation_profit": row.get("validation_profit"),
            "validation_drawdown": row.get("validation_drawdown"),
            "validation_trades": row.get("validation_trades"),
        },
        "stability": {
            "validation_std": safe_list_std(validation_dataset_scores),
            "best_dataset": best_dataset,
            "worst_dataset": worst_dataset,
        },
        "distribution": {
            "positive_datasets": positive_datasets,
            "negative_datasets": negative_datasets,
        },
        "genome_summary": build_genome_summary(row),
    }

    # Source of truth:
    # if the run already persisted champion_type, respect it.
    # Only use legacy classification as fallback for older champions.
    if not isinstance(card["type"], str) or not card["type"].strip():
        card["type"] = classify_champion_fallback(card)

    return card
