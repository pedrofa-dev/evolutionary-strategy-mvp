from dataclasses import dataclass


@dataclass(frozen=True)
class AgentEvaluation:
    aggregated_score: float
    dispersion: float
    selection_score: float
    median_trades: float
    median_profit: float
    median_drawdown: float
    dataset_scores: list[float]
    dataset_profits: list[float]
    dataset_drawdowns: list[float]
    is_valid: bool
    violations: list[str]
    worst_dataset_score: float
    bottom_quartile_score: float
    score_mad: float