from __future__ import annotations

from dataclasses import dataclass

from evo_system.experimental_space.base import DecisionPolicy
from evo_system.experimental_space.decision_policies import DefaultDecisionPolicy
from evo_system.experimental_space.policy_engines.base import PolicyEngine


@dataclass(frozen=True)
class DefaultPolicyEngine(PolicyEngine):
    """Built-in code engine for the canonical runtime decision policy.

    Responsibility boundary:
    - The engine owns how the built-in decision-policy implementation is
      provided from code.
    - The returned ``DecisionPolicy`` remains the official runtime contract
      consumed by the environment.

    Current phase:
    - This is a compatibility seam only.
    - It does not introduce declarative policies or replace the current
      decision-policy runtime path.
    """

    name: str = "policy_v2_default_engine"

    def build_decision_policy(self) -> DecisionPolicy:
        return DefaultDecisionPolicy()
