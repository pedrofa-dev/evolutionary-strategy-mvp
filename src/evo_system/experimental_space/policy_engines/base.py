from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from evo_system.experimental_space.base import DecisionPolicy


@runtime_checkable
class PolicyEngine(Protocol):
    """Future plugin contract for contributed decision-policy engines.

    Scope of this phase:
    - This does not replace the current ``DecisionPolicy`` runtime path.
    - It only defines the future plugin-facing seam so external modules can be
      registered cleanly without reopening core refactors later.
    """

    name: str

    def build_decision_policy(self) -> "DecisionPolicy":
        """Return the decision-policy implementation contributed by the plugin."""
