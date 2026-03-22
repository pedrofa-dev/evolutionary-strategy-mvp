from __future__ import annotations

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

SCORE_SCALE = 1000.0
TRADE_BONUS = 0.01

TOO_FEW_TRADES_PENALTY = 0.5
DISPERSION_VIOLATION_PENALTY = 0.5
POSITION_SIZE_VIOLATION_PENALTY = 1.0
TAKE_PROFIT_VIOLATION_PENALTY = 1.0


class AgentEvaluator:
    def evaluate(
        self,
        agent: Agent,
        environments: list[HistoricalEnvironment],
    ) -> AgentEvaluation:
        if not environments:
            raise ValueError("environments cannot be empty")

        dataset_scores: list[float] = []
        dataset_trades: list[int] = []
        dataset_profits: list[float] = []
        dataset_drawdowns: list[float] = []

        for environment in environments:
            result = environment.run_episode(agent)

            raw_score = result.profit - DRAWDOWN_WEIGHT * result.drawdown
            score = SCORE_SCALE * raw_score + TRADE_BONUS * result.trades

            dataset_scores.append(score)
            dataset_trades.append(result.trades)
            dataset_profits.append(result.profit)
            dataset_drawdowns.append(result.drawdown)

        aggregated_score = median(dataset_scores)
        dispersion = (
            max(dataset_scores) - min(dataset_scores)
            if len(dataset_scores) > 1
            else 0.0
        )

        median_trades = median(dataset_trades)
        median_profit = median(dataset_profits)
        median_drawdown = median(dataset_drawdowns)

        violations = self._collect_violations(
            agent=agent,
            median_trades=median_trades,
            dispersion=dispersion,
        )

        penalty = self._calculate_penalty(
            violations=violations,
            median_trades=median_trades,
        )

        aggregated_score -= penalty
        selection_score = aggregated_score - DISPERSION_WEIGHT * dispersion

        return AgentEvaluation(
            aggregated_score=aggregated_score,
            dispersion=dispersion,
            selection_score=selection_score,
            median_trades=median_trades,
            median_profit=median_profit,
            median_drawdown=median_drawdown,
            dataset_scores=dataset_scores,
            dataset_profits=dataset_profits,
            dataset_drawdowns=dataset_drawdowns,
            is_valid=len(violations) == 0,
            violations=violations,
        )

    def _collect_violations(
        self,
        agent: Agent,
        median_trades: float,
        dispersion: float,
    ) -> list[str]:
        violations: list[str] = []

        if median_trades < MIN_TRADES:
            violations.append("too_few_trades")

        if agent.genome.position_size < MIN_POSITION_SIZE:
            violations.append("position_size_too_small")

        if agent.genome.take_profit < MIN_TAKE_PROFIT:
            violations.append("take_profit_too_small")

        if dispersion > MAX_DISPERSION:
            violations.append("dispersion_too_high")

        return violations

    def _calculate_penalty(
        self,
        violations: list[str],
        median_trades: float,
    ) -> float:
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

        return penalty