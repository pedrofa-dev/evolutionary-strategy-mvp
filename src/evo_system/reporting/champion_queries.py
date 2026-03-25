from __future__ import annotations

from typing import Any

from evo_system.reporting.champion_loader import ChampionRow, resolve_config_name


def filter_champions(
    champions: list[ChampionRow],
    config_name: str | None = None,
) -> list[ChampionRow]:
    if config_name is None:
        return champions

    return [
        champion
        for champion in champions
        if resolve_config_name(champion) == config_name
        or champion.config_name == config_name
    ]


def classify_champion_fallback(card: dict[str, Any]) -> str:
    scores = card.get("scores", {})
    stability = card.get("stability", {})
    distribution = card.get("distribution", {})

    validation_profit = scores.get("validation_profit")
    validation_drawdown = scores.get("validation_drawdown")
    selection_gap = scores.get("selection_gap")
    validation_std = stability.get("validation_std")
    positive_datasets = distribution.get("positive_datasets")
    negative_datasets = distribution.get("negative_datasets")

    if not isinstance(validation_profit, (int, float)):
        return "unstable"

    if (
        isinstance(validation_std, (int, float))
        and isinstance(selection_gap, (int, float))
        and isinstance(positive_datasets, int)
        and isinstance(negative_datasets, int)
        and validation_profit > 0.0
        and (validation_drawdown is None or float(validation_drawdown) <= 0.0020)
        and validation_std <= 0.50
        and abs(float(selection_gap)) <= 0.75
        and positive_datasets >= negative_datasets
    ):
        return "robust"

    if (
        isinstance(positive_datasets, int)
        and isinstance(negative_datasets, int)
        and isinstance(selection_gap, (int, float))
        and validation_profit > 0.0
        and abs(float(selection_gap)) <= 1.00
        and positive_datasets > 0
        and negative_datasets > 0
        and positive_datasets < negative_datasets
    ):
        return "specialist"

    return "unstable"


def select_primary_champion_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked_rows = [
        row
        for row in rows
        if isinstance(row.get("validation_selection"), (int, float))
    ]
    if not ranked_rows:
        return rows[0] if rows else None

    return sorted(
        ranked_rows,
        key=lambda row: (
            float(row.get("validation_selection", 0.0)),
            float(row.get("validation_profit", 0.0)),
            -abs(float(row.get("selection_gap", 0.0))),
        ),
        reverse=True,
    )[0]
