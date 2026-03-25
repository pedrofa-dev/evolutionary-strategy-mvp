from evo_system.champions.rules import (
    ROBUST_MAX_ABS_SELECTION_GAP,
    ROBUST_MAX_VALIDATION_DRAWDOWN,
    ROBUST_MIN_VALIDATION_PROFIT,
    ROBUST_MIN_VALIDATION_SELECTION,
    ROBUST_MIN_VALIDATION_TRADES,
    SPECIALIST_MAX_ABS_SELECTION_GAP,
    SPECIALIST_MAX_VALIDATION_DRAWDOWN,
    SPECIALIST_MIN_DATASET_PROFIT,
    SPECIALIST_MIN_VALIDATION_PROFIT,
    SPECIALIST_MIN_VALIDATION_SELECTION,
    SPECIALIST_MIN_VALIDATION_TRADES,
)
from evo_system.champions.types import ChampionType
from evo_system.domain.agent_evaluation import AgentEvaluation


def count_positive_and_negative_datasets(
    profits: list[float],
) -> tuple[int, int]:
    positive_count = sum(1 for profit in profits if profit > 0.0)
    negative_count = sum(1 for profit in profits if profit < 0.0)
    return positive_count, negative_count


def has_severe_validation_loss(
    profits: list[float],
    min_allowed_profit: float,
) -> bool:
    return any(profit < min_allowed_profit for profit in profits)


def classify_champion(
    train_evaluation: AgentEvaluation,
    validation_evaluation: AgentEvaluation,
) -> ChampionType:
    if not validation_evaluation.is_valid:
        return "rejected"

    if validation_evaluation.median_profit <= 0.0:
        return "rejected"

    selection_gap = (
        train_evaluation.selection_score
        - validation_evaluation.selection_score
    )

    positive_datasets, negative_datasets = count_positive_and_negative_datasets(
        validation_evaluation.dataset_profits
    )

    if (
        validation_evaluation.selection_score >= ROBUST_MIN_VALIDATION_SELECTION
        and validation_evaluation.median_profit >= ROBUST_MIN_VALIDATION_PROFIT
        and validation_evaluation.median_drawdown <= ROBUST_MAX_VALIDATION_DRAWDOWN
        and validation_evaluation.median_trades >= ROBUST_MIN_VALIDATION_TRADES
        and abs(selection_gap) <= ROBUST_MAX_ABS_SELECTION_GAP
        and positive_datasets >= negative_datasets
    ):
        return "robust"

    if (
        validation_evaluation.selection_score >= SPECIALIST_MIN_VALIDATION_SELECTION
        and validation_evaluation.median_profit >= SPECIALIST_MIN_VALIDATION_PROFIT
        and validation_evaluation.median_drawdown <= SPECIALIST_MAX_VALIDATION_DRAWDOWN
        and validation_evaluation.median_trades >= SPECIALIST_MIN_VALIDATION_TRADES
        and abs(selection_gap) <= SPECIALIST_MAX_ABS_SELECTION_GAP
        and positive_datasets >= negative_datasets
        and not has_severe_validation_loss(
            validation_evaluation.dataset_profits,
            SPECIALIST_MIN_DATASET_PROFIT,
        )
    ):
        return "specialist"

    return "rejected"


def should_persist_champion(champion_type: ChampionType) -> bool:
    return champion_type != "rejected"
