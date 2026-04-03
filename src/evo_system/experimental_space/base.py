from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from evo_system.domain.genome import Genome

if TYPE_CHECKING:
    from evo_system.mutation.mutator import MutationProfile


# Phase 1 of incremental modularization:
# - These protocols define stable boundaries for future experimental-space
#   modules without changing the current runtime behavior.
# - Default implementations should wrap existing behavior rather than replace it.


@runtime_checkable
class SignalPack(Protocol):
    """Expose the raw features and family scores consumed by decision logic."""

    name: str

    def build_signal_features(self, *, environment: Any, **kwargs: Any) -> dict[str, float]:
        """Build normalized raw features for the active signal set."""

    def build_signal_families(
        self,
        *,
        environment: Any,
        signal_features: dict[str, float],
    ) -> dict[str, float]:
        """Collapse raw features into family scores consumed by genes."""


@runtime_checkable
class GenomeSchema(Protocol):
    """Describe how active genomes are composed for a given policy schema."""

    name: str

    def is_active_for_genome(self, genome: Genome) -> bool:
        """Return whether the schema owns the provided genome instance."""

    def build_genome(self, **kwargs: Any) -> Genome:
        """Build a structurally valid genome for the active schema."""


@runtime_checkable
class DecisionPolicy(Protocol):
    """Apply gene blocks plus signals to runtime entry decisions."""

    name: str

    def get_entry_trigger_score(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> float:
        """Return the weighted trigger score used by the active runtime."""

    def passes_entry_context(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> bool:
        """Return whether market context permits entries."""

    def passes_entry_trigger(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
    ) -> bool:
        """Return whether conviction rules permit entries."""


@runtime_checkable
class MutationProfileDefinition(Protocol):
    """Resolve the runtime mutation profile used by the current mutator."""

    name: str

    def resolve_runtime_profile(
        self,
        profile: MutationProfile | None = None,
    ) -> MutationProfile:
        """Return the concrete runtime mutation profile to execute with."""
