from statistics import median

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.environment.historical_environment import HistoricalEnvironment


MIN_TRADES = 5
MIN_POSITION_SIZE = 0.05
MIN_TAKE_PROFIT = 0.02
MAX_DISPERSION = 80.0
INVALID_SCORE = -9999.0
DISPERSION_WEIGHT = 0.3
DRAWDOWN_WEIGHT = 2.0


class AgentEvaluator:
    def evaluate(
        self,
        agent: Agent,
        environments: list[HistoricalEnvironment],
    ) -> AgentEvaluation:
        if not environments:
            raise ValueError("environments cannot be empty")

        scores: list[float] = []
        trades: list[int] = []
        profits: list[float] = []
        drawdowns: list[float] = []

        for environment in environments:
            result = environment.run_episode(agent)

            score = result.profit - DRAWDOWN_WEIGHT * result.drawdown

            scores.append(score)
            trades.append(result.trades)
            profits.append(result.profit)
            drawdowns.append(result.drawdown)

        aggregated_score = median(scores)
        dispersion = max(scores) - min(scores) if len(scores) > 1 else 0.0
        median_trades = median(trades)
        median_profit = median(profits)
        median_drawdown = median(drawdowns)

        violations: list[str] = []

        if median_trades < MIN_TRADES:
            violations.append("too_few_trades")

        if agent.genome.position_size < MIN_POSITION_SIZE:
            violations.append("position_size_too_small")

        if agent.genome.take_profit < MIN_TAKE_PROFIT:
            violations.append("take_profit_too_small")

        if dispersion > MAX_DISPERSION:
            violations.append("dispersion_too_high")

        is_valid = len(violations) == 0

        if not is_valid:
            aggregated_score = INVALID_SCORE
            selection_score = INVALID_SCORE
        else:
            selection_score = aggregated_score - DISPERSION_WEIGHT * dispersion

        return AgentEvaluation(
            aggregated_score=aggregated_score,
            dispersion=dispersion,
            selection_score=selection_score,
            median_trades=median_trades,
            median_profit=median_profit,
            median_drawdown=median_drawdown,
            dataset_scores=scores,
            dataset_profits=profits,
            dataset_drawdowns=drawdowns,
            is_valid=is_valid,
            violations=violations,
        )