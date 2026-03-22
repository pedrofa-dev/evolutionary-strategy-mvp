from statistics import median

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.environment.historical_environment import HistoricalEnvironment


MIN_TRADES = 5
MIN_POSITION_SIZE = 0.05
MIN_TAKE_PROFIT = 0.02
MAX_DISPERSION = 80.0

DRAWDOWN_WEIGHT = 0.5
DISPERSION_WEIGHT = 0.3
DOWNSIDE_WEIGHT = 0.4

SCORE_SCALE = 1000.0
TRADE_BONUS = 0.01

DEFAULT_COST_PENALTY_WEIGHT = 0.25

TOO_FEW_TRADES_PENALTY = 0.5
DISPERSION_VIOLATION_PENALTY = 0.5
POSITION_SIZE_VIOLATION_PENALTY = 1.0
TAKE_PROFIT_VIOLATION_PENALTY = 1.0


class AgentEvaluator:
    def __init__(self, cost_penalty_weight: float = DEFAULT_COST_PENALTY_WEIGHT) -> None:
        if cost_penalty_weight < 0.0:
            raise ValueError("cost_penalty_weight must be greater than or equal to 0.0")

        self.cost_penalty_weight = cost_penalty_weight

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

            raw_score = (
                result.profit
                - DRAWDOWN_WEIGHT * result.drawdown
                - self.cost_penalty_weight * result.cost
            )
            score = SCORE_SCALE * raw_score + TRADE_BONUS * result.trades

            scores.append(score)
            trades.append(result.trades)
            profits.append(result.profit)
            drawdowns.append(result.drawdown)

        aggregated_score = median(scores)
        dispersion = max(scores) - min(scores) if len(scores) > 1 else 0.0
        median_trades = median(trades)
        median_profit = median(profits)
        median_drawdown = median(drawdowns)

        worst_dataset_score = min(scores)
        bottom_quartile_score = self._calculate_bottom_quartile_score(scores)
        score_mad = self._calculate_mad(scores, aggregated_score)

        violations: list[str] = []

        if median_trades < MIN_TRADES:
            violations.append("too_few_trades")

        if agent.genome.position_size < MIN_POSITION_SIZE:
            violations.append("position_size_too_small")

        if agent.genome.take_profit < MIN_TAKE_PROFIT:
            violations.append("take_profit_too_small")

        if dispersion > MAX_DISPERSION:
            violations.append("dispersion_too_high")

        penalty = 0.0

        if "too_few_trades" in violations:
            missing_trades = max(0.0, MIN_TRADES - median_trades)
            penalty += TOO_FEW_TRADES_PENALTY * missing_trades

        if "dispersion_too_high" in violations:
            penalty += DISPERSION_VIOLATION_PENALTY

        if "position_size_too_small" in violations:
            penalty += POSITION_SIZE_VIOLATION_PENALTY

        if "take_profit_too_small" in violations:
            penalty += TAKE_PROFIT_VIOLATION_PENALTY

        aggregated_score -= penalty

        downside_penalty = max(0.0, -bottom_quartile_score)
        selection_score = (
            aggregated_score
            - DISPERSION_WEIGHT * score_mad
            - DOWNSIDE_WEIGHT * downside_penalty
        )

        is_valid = len(violations) == 0

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
            worst_dataset_score=worst_dataset_score,
            bottom_quartile_score=bottom_quartile_score,
            score_mad=score_mad,
        )

    def _calculate_bottom_quartile_score(self, scores: list[float]) -> float:
        sorted_scores = sorted(scores)
        sample_size = max(1, len(sorted_scores) // 4)
        bottom_scores = sorted_scores[:sample_size]
        return sum(bottom_scores) / len(bottom_scores)

    def _calculate_mad(self, values: list[float], center: float) -> float:
        absolute_deviations = [abs(value - center) for value in values]
        return median(absolute_deviations)