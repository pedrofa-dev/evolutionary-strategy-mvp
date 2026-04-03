from evo_system.domain.agent import Agent


MIN_TRADES = 5
MIN_POSITION_SIZE = 0.05
MIN_TAKE_PROFIT = 0.02

HARD_VIOLATIONS = {
    "too_few_trades",
    "position_size_too_small",
    "take_profit_too_small",
}


def collect_veto_violations(
    agent: Agent,
    median_trades: float,
) -> list[str]:
    """Collect non-negotiable evaluation failures.

    Why it exists:
    - These are guardrails against degenerate policies that can look attractive
      in score space while being operationally meaningless after costs.

    Constraints:
    - Experimental config layers must not loosen these implicitly.
    - Any change here is an evaluation-policy change, not a config tweak.
    """
    violations: list[str] = []

    if median_trades < MIN_TRADES:
        violations.append("too_few_trades")

    if agent.genome.position_size < MIN_POSITION_SIZE:
        violations.append("position_size_too_small")

    if agent.genome.take_profit < MIN_TAKE_PROFIT:
        violations.append("take_profit_too_small")

    return violations


def is_valid_evaluation(violations: list[str]) -> bool:
    """Return whether an evaluation survives the hard veto layer.

    Invariant:
    - A hard-vetoed evaluation must never be treated as a valid champion input.
    """
    return not any(violation in HARD_VIOLATIONS for violation in violations)
