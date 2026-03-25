from __future__ import annotations

from typing import Literal


ChampionType = Literal["robust", "specialist", "rejected"]


def classify_champion(row: dict) -> ChampionType:
    """
    Classifies a champion into:
    - robust
    - specialist
    - rejected
    """

    validation_profit = row.get("validation_profit")
    validation_drawdown = row.get("validation_drawdown")
    validation_trades = row.get("validation_trades")
    selection_gap = row.get("selection_gap")
    validation_scores = row.get("validation_dataset_scores", [])
    validation_profits = row.get("validation_dataset_profits", [])

    if validation_profit is None:
        return "rejected"

    # -------------------------
    # BASIC FILTER (must pass)
    # -------------------------
    if validation_profit <= 0:
        return "rejected"

    if validation_drawdown is not None and validation_drawdown > 0.05:
        return "rejected"

    # -------------------------
    # DISTRIBUTION ANALYSIS
    # -------------------------
    positive = sum(1 for p in validation_profits if isinstance(p, (int, float)) and p > 0)
    negative = sum(1 for p in validation_profits if isinstance(p, (int, float)) and p < 0)

    # -------------------------
    # ROBUST CHAMPION
    # -------------------------
    if (
        validation_profit >= 0.02
        and (validation_drawdown is None or validation_drawdown <= 0.03)
        and validation_trades is not None
        and validation_trades >= 10
        and selection_gap is not None
        and abs(selection_gap) <= 1.5
        and positive >= negative
    ):
        return "robust"

    # -------------------------
    # SPECIALIST CHAMPION
    # -------------------------
    if (
        validation_profit >= 0.02
        and validation_trades is not None
        and validation_trades >= 8
        and selection_gap is not None
        and abs(selection_gap) <= 2.5
    ):
        return "specialist"

    return "rejected"