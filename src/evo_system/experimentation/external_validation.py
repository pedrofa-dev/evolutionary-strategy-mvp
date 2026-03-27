from __future__ import annotations

from pathlib import Path

from evo_system.champions.classifier import count_positive_and_negative_datasets
from evo_system.champions.metrics import format_dataset_path
from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.environment.csv_loader import load_historical_candles
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.evaluation import AgentEvaluator


def build_environment(
    dataset_path: Path,
    trade_cost_rate: float,
    regime_filter_enabled: bool = False,
    min_trend_long_for_entry: float = 0.0,
    min_breakout_for_entry: float = 0.0,
    max_realized_volatility_for_entry: float | None = None,
) -> HistoricalEnvironment:
    candles = load_historical_candles(dataset_path)
    return HistoricalEnvironment(
        candles,
        trade_cost_rate=trade_cost_rate,
        regime_filter_enabled=regime_filter_enabled,
        min_trend_long_for_entry=min_trend_long_for_entry,
        min_breakout_for_entry=min_breakout_for_entry,
        max_realized_volatility_for_entry=max_realized_volatility_for_entry,
    )


def run_external_validation(
    agent: Agent,
    external_dataset_paths: list[Path],
    cost_penalty_weight: float,
    trade_cost_rate: float,
    trade_count_penalty_weight: float = 0.0,
    regime_filter_enabled: bool = False,
    min_trend_long_for_entry: float = 0.0,
    min_breakout_for_entry: float = 0.0,
    max_realized_volatility_for_entry: float | None = None,
) -> AgentEvaluation:
    if not external_dataset_paths:
        raise ValueError("external_dataset_paths cannot be empty")

    evaluator = AgentEvaluator(
        cost_penalty_weight=cost_penalty_weight,
        trade_count_penalty_weight=trade_count_penalty_weight,
    )
    environments = [
        build_environment(
            path,
            trade_cost_rate=trade_cost_rate,
            regime_filter_enabled=regime_filter_enabled,
            min_trend_long_for_entry=min_trend_long_for_entry,
            min_breakout_for_entry=min_breakout_for_entry,
            max_realized_volatility_for_entry=max_realized_volatility_for_entry,
        )
        for path in external_dataset_paths
    ]
    return evaluator.evaluate(agent=agent, environments=environments)


def build_external_validation_metrics(
    evaluation: AgentEvaluation,
    dataset_paths: list[Path],
    dataset_root: Path,
) -> dict:
    positive_datasets, negative_datasets = count_positive_and_negative_datasets(
        evaluation.dataset_profits
    )

    return {
        "external_validation_dataset_names": [
            format_dataset_path(path, dataset_root) for path in dataset_paths
        ],
        "external_validation_dataset_count": len(dataset_paths),
        "external_validation_selection": evaluation.selection_score,
        "external_validation_profit": evaluation.median_profit,
        "external_validation_drawdown": evaluation.median_drawdown,
        "external_validation_trades": evaluation.median_trades,
        "external_validation_dispersion": evaluation.dispersion,
        "external_validation_positive_datasets": positive_datasets,
        "external_validation_negative_datasets": negative_datasets,
        "external_validation_scores": evaluation.dataset_scores,
        "external_validation_profits": evaluation.dataset_profits,
        "external_validation_drawdowns": evaluation.dataset_drawdowns,
        "external_validation_violations": evaluation.violations,
        "external_validation_is_valid": evaluation.is_valid,
    }
