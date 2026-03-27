import pytest

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.evaluation import AgentEvaluator
from evo_system.environment.historical_environment import HistoricalEnvironment


def build_environment(trade_cost_rate: float = 0.0) -> HistoricalEnvironment:
    candles = [
        HistoricalCandle("1", 100, 110, 95, 105),
        HistoricalCandle("2", 105, 115, 100, 110),
        HistoricalCandle("3", 110, 120, 105, 115),
        HistoricalCandle("4", 115, 125, 110, 120),
        HistoricalCandle("5", 120, 130, 115, 125),
        HistoricalCandle("6", 125, 135, 120, 130),
    ]
    return HistoricalEnvironment(candles, trade_cost_rate=trade_cost_rate)


def test_agent_evaluator_penalizes_small_position_size() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.01,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert evaluation.is_valid is False
    assert "position_size_too_small" in evaluation.violations
    assert evaluation.aggregated_score < 0.0
    assert evaluation.selection_score <= evaluation.aggregated_score


def test_agent_evaluator_penalizes_small_take_profit() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.01,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert evaluation.is_valid is False
    assert "take_profit_too_small" in evaluation.violations
    assert evaluation.aggregated_score < 0.0
    assert evaluation.selection_score <= evaluation.aggregated_score


def test_agent_evaluator_penalizes_too_few_trades() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.95,
            threshold_close=0.9,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert evaluation.is_valid is False
    assert "too_few_trades" in evaluation.violations
    assert evaluation.aggregated_score < 0.0
    assert evaluation.selection_score <= evaluation.aggregated_score


def test_agent_evaluator_returns_valid_evaluation_for_viable_agent() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment(), build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert isinstance(evaluation.aggregated_score, float)
    assert isinstance(evaluation.dispersion, float)
    assert isinstance(evaluation.selection_score, float)
    assert isinstance(evaluation.median_trades, float)
    assert isinstance(evaluation.median_profit, float)
    assert isinstance(evaluation.median_drawdown, float)
    assert isinstance(evaluation.is_valid, bool)
    assert isinstance(evaluation.violations, list)
    assert isinstance(evaluation.worst_dataset_score, float)
    assert isinstance(evaluation.bottom_quartile_score, float)
    assert isinstance(evaluation.score_mad, float)


def test_agent_evaluator_supports_feature_based_agents() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment(), build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.4,
            threshold_close=0.1,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
            ret_short_window=1,
            ret_mid_window=2,
            ma_window=3,
            range_window=3,
            vol_short_window=2,
            vol_long_window=4,
            weight_ret_short=1.0,
            weight_ret_mid=0.8,
            weight_dist_ma=0.4,
            weight_range_pos=0.2,
            weight_vol_ratio=0.1,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert isinstance(evaluation.aggregated_score, float)
    assert isinstance(evaluation.selection_score, float)
    assert isinstance(evaluation.dataset_scores, list)
    assert len(evaluation.dataset_scores) == 2
    assert isinstance(evaluation.violations, list)
    assert isinstance(evaluation.worst_dataset_score, float)
    assert isinstance(evaluation.bottom_quartile_score, float)
    assert isinstance(evaluation.score_mad, float)


def test_agent_evaluator_penalizes_costly_environments() -> None:
    evaluator = AgentEvaluator(cost_penalty_weight=0.25)

    environments_without_cost = [
        HistoricalEnvironment(
            [
                HistoricalCandle("1", 100, 100, 100, 100),
                HistoricalCandle("2", 100, 100, 100, 120),
                HistoricalCandle("3", 120, 140, 120, 140),
                HistoricalCandle("4", 140, 140, 140, 140),
                HistoricalCandle("5", 140, 140, 140, 140),
                HistoricalCandle("6", 140, 140, 140, 140),
            ],
            trade_cost_rate=0.0,
        )
    ]
    environments_with_cost = [
        HistoricalEnvironment(
            [
                HistoricalCandle("1", 100, 100, 100, 100),
                HistoricalCandle("2", 100, 100, 100, 120),
                HistoricalCandle("3", 120, 140, 120, 140),
                HistoricalCandle("4", 140, 140, 140, 140),
                HistoricalCandle("5", 140, 140, 140, 140),
                HistoricalCandle("6", 140, 140, 140, 140),
            ],
            trade_cost_rate=0.01,
        )
    ]

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=1.0,
            stop_loss=0.5,
            take_profit=0.1,
        )
    )

    evaluation_without_cost = evaluator.evaluate(agent, environments_without_cost)
    evaluation_with_cost = evaluator.evaluate(agent, environments_with_cost)

    assert evaluation_with_cost.aggregated_score < evaluation_without_cost.aggregated_score
    assert evaluation_with_cost.selection_score < evaluation_without_cost.selection_score


def test_agent_evaluator_penalty_weight_can_be_disabled() -> None:
    environments = [
        HistoricalEnvironment(
            [
                HistoricalCandle("1", 100, 100, 100, 100),
                HistoricalCandle("2", 100, 100, 100, 120),
                HistoricalCandle("3", 120, 140, 120, 140),
                HistoricalCandle("4", 140, 140, 140, 140),
                HistoricalCandle("5", 140, 140, 140, 140),
                HistoricalCandle("6", 140, 140, 140, 140),
            ],
            trade_cost_rate=0.01,
        )
    ]

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=1.0,
            stop_loss=0.5,
            take_profit=0.1,
        )
    )

    evaluator_without_cost_penalty = AgentEvaluator(cost_penalty_weight=0.0)
    evaluator_with_cost_penalty = AgentEvaluator(cost_penalty_weight=0.25)

    evaluation_without_cost_penalty = evaluator_without_cost_penalty.evaluate(agent, environments)
    evaluation_with_cost_penalty = evaluator_with_cost_penalty.evaluate(agent, environments)

    assert evaluation_with_cost_penalty.aggregated_score < evaluation_without_cost_penalty.aggregated_score
    assert evaluation_with_cost_penalty.selection_score < evaluation_without_cost_penalty.selection_score


def test_agent_evaluator_trade_count_penalty_weight_can_be_disabled() -> None:
    environments = [build_environment(), build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation_without_trade_penalty = AgentEvaluator(
        trade_count_penalty_weight=0.0
    ).evaluate(agent, environments)
    evaluation_with_zero_trade_penalty = AgentEvaluator(
        trade_count_penalty_weight=0.0
    ).evaluate(agent, environments)

    assert (
        evaluation_without_trade_penalty.selection_score
        == evaluation_with_zero_trade_penalty.selection_score
    )


def test_agent_evaluator_applies_trade_count_penalty_to_selection_score() -> None:
    environments = [
        HistoricalEnvironment(
            [
                HistoricalCandle("1", 100, 100, 100, 100),
                HistoricalCandle("2", 100, 100, 100, 120),
                HistoricalCandle("3", 120, 140, 120, 140),
                HistoricalCandle("4", 140, 140, 140, 140),
                HistoricalCandle("5", 140, 140, 140, 140),
                HistoricalCandle("6", 140, 140, 140, 140),
            ],
            trade_cost_rate=0.0,
        )
    ]

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=1.0,
            stop_loss=0.5,
            take_profit=0.1,
        )
    )

    evaluation_without_trade_penalty = AgentEvaluator(
        trade_count_penalty_weight=0.0
    ).evaluate(agent, environments)
    evaluation_with_trade_penalty = AgentEvaluator(
        trade_count_penalty_weight=0.001
    ).evaluate(agent, environments)

    assert (
        evaluation_with_trade_penalty.aggregated_score
        == evaluation_without_trade_penalty.aggregated_score
    )
    assert (
        evaluation_with_trade_penalty.selection_score
        < evaluation_without_trade_penalty.selection_score
    )
    assert (
        evaluation_without_trade_penalty.selection_score
        - evaluation_with_trade_penalty.selection_score
        == pytest.approx(0.001 * evaluation_without_trade_penalty.median_trades)
    )


def test_agent_evaluator_reports_zero_mad_for_identical_dataset_scores() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment(), build_environment(), build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert evaluation.score_mad == 0.0
    assert evaluation.worst_dataset_score == 0.0
    assert evaluation.bottom_quartile_score == 0.0
    assert evaluation.dataset_scores == [0.0, 0.0, 0.0]
    assert evaluation.aggregated_score < evaluation.worst_dataset_score


def test_agent_evaluator_bottom_quartile_matches_worst_score_with_three_datasets() -> None:
    evaluator = AgentEvaluator()
    environments = [build_environment(), build_environment(), build_environment()]

    agent = Agent.create(
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.05,
        )
    )

    evaluation = evaluator.evaluate(agent, environments)

    assert evaluation.bottom_quartile_score == min(evaluation.dataset_scores)
    assert evaluation.worst_dataset_score == min(evaluation.dataset_scores)
