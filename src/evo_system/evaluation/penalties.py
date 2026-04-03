from evo_system.evaluation.vetoes import MIN_TRADES


MAX_DISPERSION = 80.0

DEFAULT_COST_PENALTY_WEIGHT = 0.25

TOO_FEW_TRADES_PENALTY = 0.5
DISPERSION_VIOLATION_PENALTY = 0.5
POSITION_SIZE_VIOLATION_PENALTY = 1.0
TAKE_PROFIT_VIOLATION_PENALTY = 1.0

INVALID_VALIDATION_PENALTY = 5.0
NEGATIVE_VALIDATION_PENALTY = 2.0


def collect_soft_penalty_violations(
    dispersion: float,
) -> list[str]:
    """Collect evaluation issues that should hurt score but not hard-fail it.

    Why it exists:
    - Some pathologies signal fragility without being strong enough to void the
      whole evaluation.
    """
    violations: list[str] = []

    if dispersion > MAX_DISPERSION:
        violations.append("dispersion_too_high")

    return violations


def calculate_evaluation_penalty(
    violations: list[str],
    median_trades: float,
) -> float:
    """Translate soft/hard violation labels into an additive score penalty.

    Invariants:
    - This function must not silently turn hard vetoes into valid outcomes.
    - Trade scarcity remains penalized even when it is already a veto signal.

    Context:
    - The evaluator combines this with scoring and veto validity checks.
    """
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
