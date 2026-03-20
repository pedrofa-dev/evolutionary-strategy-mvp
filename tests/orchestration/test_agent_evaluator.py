from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.orchestration.agent_evaluator import AgentEvaluator


def build_environment() -> HistoricalEnvironment:
    candles = [
        HistoricalCandle("1", 100, 110, 95, 105),
        HistoricalCandle("2", 105, 115, 100, 110),
        HistoricalCandle("3", 110, 120, 105, 115),
        HistoricalCandle("4", 115, 125, 110, 120),
        HistoricalCandle("5", 120, 130, 115, 125),
        HistoricalCandle("6", 125, 135, 120, 130),
    ]
    return HistoricalEnvironment(candles)


def test_agent_evaluator_rejects_small_position_size() -> None:
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
    assert evaluation.aggregated_score == -9999.0
    assert evaluation.selection_score == -9999.0


def test_agent_evaluator_rejects_small_take_profit() -> None:
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
    assert evaluation.aggregated_score == -9999.0
    assert evaluation.selection_score == -9999.0


def test_agent_evaluator_rejects_too_few_trades() -> None:
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
    assert evaluation.aggregated_score == -9999.0
    assert evaluation.selection_score == -9999.0


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