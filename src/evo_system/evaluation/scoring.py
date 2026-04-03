from statistics import median

from evo_system.domain.agent_evaluation import AgentEvaluation


DRAWDOWN_WEIGHT = 0.5
DISPERSION_WEIGHT = 0.3
DOWNSIDE_WEIGHT = 0.4
TRAIN_WEIGHT = 0.30
VALIDATION_WEIGHT = 0.70
OVERFIT_GAP_WEIGHT = 0.75
UNDERFIT_GAP_WEIGHT = 0.50
VALIDATION_DISPERSION_WEIGHT = 0.50

SCORE_SCALE = 1000.0
TRADE_BONUS = 0.01


def calculate_dataset_score(
    profit: float,
    drawdown: float,
    cost: float,
    trades: int,
    cost_penalty_weight: float,
) -> float:
    """Score one dataset episode on net outcome rather than raw activity.

    Invariants:
    - Profit, drawdown, and trading cost must remain the dominant drivers.
    - Trade count is only a weak tie-breaker and must not become the main edge.

    Constraints:
    - Experimental layers may tune policy behavior, but must not reinterpret
      this function as a champion-selection shortcut.
    """
    raw_score = (
        profit
        - DRAWDOWN_WEIGHT * drawdown
        - cost_penalty_weight * cost
    )
    return SCORE_SCALE * raw_score + TRADE_BONUS * trades


def calculate_dispersion(scores: list[float]) -> float:
    return max(scores) - min(scores) if len(scores) > 1 else 0.0


def calculate_bottom_quartile_score(scores: list[float]) -> float:
    sorted_scores = sorted(scores)
    sample_size = max(1, len(sorted_scores) // 4)
    bottom_scores = sorted_scores[:sample_size]
    return sum(bottom_scores) / len(bottom_scores)


def calculate_mad(values: list[float], center: float) -> float:
    absolute_deviations = [abs(value - center) for value in values]
    return median(absolute_deviations)


def calculate_selection_score(
    aggregated_score: float,
    score_mad: float,
    bottom_quartile_score: float,
    median_trades: float,
    trade_count_penalty_weight: float,
) -> float:
    """Convert aggregated performance into a selection score for evolution.

    Why it exists:
    - Evolution should prefer stable, downside-aware agents, not just agents
      with high mean score on favorable subsets.

    Invariants:
    - Dispersion and downside penalties must remain visible in selection.
    - Trade-count penalty is a cost-control term, not a reward for inactivity.
    """
    downside_penalty = max(0.0, -bottom_quartile_score)
    return (
        aggregated_score
        - DISPERSION_WEIGHT * score_mad
        - DOWNSIDE_WEIGHT * downside_penalty
        - trade_count_penalty_weight * median_trades
    )


def build_evolution_selection_score(
    train_evaluation: AgentEvaluation,
    validation_evaluation: AgentEvaluation,
    invalid_validation_penalty: float,
    negative_validation_penalty: float,
) -> float:
    """Rank genomes for reproduction using train and validation together.

    Context:
    - This is the bridge between per-dataset evaluation and the evolutionary
      loop in experiment execution.

    Invariants:
    - Validation remains the authority over train.
    - Overfit and underfit gaps both matter.
    - Invalid validation must stay strongly penalized.

    Constraints:
    - Do not let configuration experiments bypass this by weakening validation
      penalties here. That belongs in explicit evaluation-policy changes.
    """
    selection_gap = (
        train_evaluation.selection_score
        - validation_evaluation.selection_score
    )

    overfit_penalty = max(0.0, selection_gap)
    underfit_penalty = max(0.0, -selection_gap)
    validation_dispersion_penalty = validation_evaluation.dispersion

    score = (
        TRAIN_WEIGHT * train_evaluation.selection_score
        + VALIDATION_WEIGHT * validation_evaluation.selection_score
        - OVERFIT_GAP_WEIGHT * overfit_penalty
        - UNDERFIT_GAP_WEIGHT * underfit_penalty
        - VALIDATION_DISPERSION_WEIGHT * validation_dispersion_penalty
    )

    if not validation_evaluation.is_valid:
        score -= invalid_validation_penalty

    if validation_evaluation.selection_score < 0.0:
        score -= negative_validation_penalty

    return score
