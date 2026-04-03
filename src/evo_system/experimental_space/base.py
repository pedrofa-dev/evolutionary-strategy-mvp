from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from evo_system.domain.genome import Genome

if TYPE_CHECKING:
    from evo_system.experimental_space.gene_catalog import GeneTypeCatalog
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

    def get_gene_type_catalog(self) -> "GeneTypeCatalog":
        """Return the catalog that defines module structure for this schema."""

    def get_module_names(self) -> tuple[str, ...]:
        """Return the stable module order for this schema."""

    def build_default_module(self, module_name: str) -> Any:
        """Build the default module instance for one schema-owned block."""

    def build_genome_from_modules(
        self,
        *,
        position_size: float,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
    ) -> Genome:
        """Build a genome from schema fields plus reconstructed modules."""

    def build_genome(self, **kwargs: Any) -> Genome:
        """Build a structurally valid genome for the active schema."""


@dataclass(frozen=True)
class EntryDecision:
    """Stable result of one entry-policy evaluation step."""

    trigger_score: float
    context_ok: bool
    trigger_ok: bool
    regime_filter_ok: bool
    should_enter: bool


@dataclass(frozen=True)
class ExitDecision:
    """Stable result of one exit-policy evaluation step."""

    hit_stop_loss: bool
    hit_take_profit: bool
    should_close_by_score: bool
    should_close_on_reversal: bool
    should_close_on_holding_limit: bool
    should_close: bool


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

    def should_enter(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
        regime_filter_ok: bool,
    ) -> bool:
        """Return whether the active decision policy wants to open a trade."""

    def should_exit(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> bool:
        """Return whether the active decision policy wants to close a trade."""

    def evaluate_entry(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        regime_filter_ok: bool,
    ) -> EntryDecision:
        """Return the full entry evaluation result for the active policy."""

    def evaluate_exit(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> ExitDecision:
        """Return the full exit evaluation result for the active policy."""


@runtime_checkable
class MutationProfileDefinition(Protocol):
    """Resolve the runtime mutation profile used by the current mutator."""

    name: str

    def resolve_runtime_profile(
        self,
        profile: MutationProfile | None = None,
    ) -> MutationProfile:
        """Return the concrete runtime mutation profile to execute with."""
