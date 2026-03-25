from statistics import median

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.evaluation.penalties import (
    DEFAULT_COST_PENALTY_WEIGHT,
    calculate_evaluation_penalty,
    collect_soft_penalty_violations,
)
from evo_system.evaluation.scoring import (
    calculate_bottom_quartile_score,
    calculate_dataset_score,
    calculate_dispersion,
    calculate_mad,
    calculate_selection_score,
)
from evo_system.evaluation.vetoes import (
    collect_veto_violations,
    is_valid_evaluation,
)


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
            score = calculate_dataset_score(
                profit=result.profit,
                drawdown=result.drawdown,
                cost=result.cost,
                trades=result.trades,
                cost_penalty_weight=self.cost_penalty_weight,
            )

            scores.append(score)
            trades.append(result.trades)
            profits.append(result.profit)
            drawdowns.append(result.drawdown)

        aggregated_score = median(scores)
        dispersion = calculate_dispersion(scores)
        median_trades = median(trades)
        median_profit = median(profits)
        median_drawdown = median(drawdowns)

        worst_dataset_score = min(scores)
        bottom_quartile_score = calculate_bottom_quartile_score(scores)
        score_mad = calculate_mad(scores, aggregated_score)

        violations = collect_veto_violations(
            agent=agent,
            median_trades=median_trades,
        )
        violations.extend(collect_soft_penalty_violations(dispersion))

        aggregated_score -= calculate_evaluation_penalty(
            violations=violations,
            median_trades=median_trades,
        )

        selection_score = calculate_selection_score(
            aggregated_score=aggregated_score,
            score_mad=score_mad,
            bottom_quartile_score=bottom_quartile_score,
        )
        is_valid = is_valid_evaluation(violations)

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
