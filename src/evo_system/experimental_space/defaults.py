from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
    build_policy_v2_genome,
)
from evo_system.experimental_space.base import (
    DecisionPolicy,
    GenomeSchema,
    MarketMode,
    MutationProfileDefinition,
    SignalPack,
)
from evo_system.experimental_space.gene_catalog import (
    MODULAR_GENOME_V1_GENE_TYPE_CATALOG,
)
from evo_system.experimental_space.decision_policies import DefaultDecisionPolicy
from evo_system.experimental_space.market_modes import (
    FuturesMarketMode,
    SpotMarketMode,
)
from evo_system.experimental_space.registry import NamedRegistry
from evo_system.experimental_space.signal_packs import DefaultSignalPack
from evo_system.mutation.mutator import MutationProfile


# Phase 1 of incremental modularization:
# - These default implementations expose the active runtime modules through
#   explicit registries and stable names.
# - Some components still wrap existing helpers, but SignalPack and
#   DecisionPolicy now own the active modular semantics directly.


CurrentPolicyV21SignalPack = DefaultSignalPack


@dataclass(frozen=True)
class CurrentPolicyV2GenomeSchema(GenomeSchema):
    """Adapter over the current block-based genome construction helper."""

    name: str = "policy_v2_default"

    def is_active_for_genome(self, genome: Genome) -> bool:
        return genome.policy_v2_enabled

    def get_gene_type_catalog(self):
        return MODULAR_GENOME_V1_GENE_TYPE_CATALOG

    def get_module_names(self) -> tuple[str, ...]:
        return tuple(self.get_gene_type_catalog().list_gene_type_names())

    def build_default_module(self, module_name: str) -> Any:
        return self.get_gene_type_catalog().build_default_module(module_name)

    def build_genome_from_modules(
        self,
        *,
        position_size: float,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
    ) -> Genome:
        return self.get_gene_type_catalog().build_genome(
            position_size=position_size,
            schema_fields=schema_fields,
            gene_blocks=gene_blocks,
        )

    def build_genome(self, **kwargs: Any) -> Genome:
        return build_policy_v2_genome(**kwargs)


@dataclass(frozen=True)
class ModularGenomeSchemaV1(GenomeSchema):
    """Phase-1 explicit genome schema for the active modular policy layout.

    Why it exists:
    - This is the first real schema component under the modular abstraction
      layer.
    - It makes the active block structure explicit without replacing the
      current runtime semantics.

    Constraints:
    - It must remain compatible with the current policy_v2 execution lane.
    - It must not redefine evaluator, scoring, validation, or persistence.
    """

    name: str = "modular_genome_v1"

    def is_active_for_genome(self, genome: Genome) -> bool:
        return genome.policy_v2_enabled

    def get_gene_type_catalog(self):
        return MODULAR_GENOME_V1_GENE_TYPE_CATALOG

    def get_module_names(self) -> tuple[str, ...]:
        return tuple(self.get_gene_type_catalog().list_gene_type_names())

    def build_default_module(self, module_name: str) -> Any:
        return self.get_gene_type_catalog().build_default_module(module_name)

    def build_genome_from_modules(
        self,
        *,
        position_size: float,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
    ) -> Genome:
        return self.get_gene_type_catalog().build_genome(
            position_size=position_size,
            schema_fields=schema_fields,
            gene_blocks=gene_blocks,
        )

    def build_entry_context(self, **kwargs: Any) -> EntryContextGene:
        """Build the entry-context block for modular schema v1."""
        return EntryContextGene.from_dict(kwargs) if kwargs else EntryContextGene()

    def build_entry_trigger(self, **kwargs: Any) -> EntryTriggerGene:
        """Build the entry-trigger block for modular schema v1."""
        return EntryTriggerGene.from_dict(kwargs) if kwargs else EntryTriggerGene()

    def build_exit_policy(self, **kwargs: Any) -> ExitPolicyGene:
        """Build the exit-policy block for modular schema v1."""
        return ExitPolicyGene.from_dict(kwargs) if kwargs else ExitPolicyGene()

    def build_trade_control(self, **kwargs: Any) -> TradeControlGene:
        """Build the trade-control block for modular schema v1."""
        return TradeControlGene.from_dict(kwargs) if kwargs else TradeControlGene()

    def build_genome(self, **kwargs: Any) -> Genome:
        """Build a full active genome using explicit modular gene blocks."""
        entry_context = kwargs.pop("entry_context", None)
        entry_trigger = kwargs.pop("entry_trigger", None)
        exit_policy = kwargs.pop("exit_policy", None)
        trade_control = kwargs.pop("trade_control", None)

        return build_policy_v2_genome(
            **kwargs,
            entry_context=entry_context or self.build_entry_context(),
            entry_trigger=entry_trigger or self.build_entry_trigger(),
            exit_policy=exit_policy or self.build_exit_policy(),
            trade_control=trade_control or self.build_trade_control(),
        )


CurrentPolicyV2DecisionPolicy = DefaultDecisionPolicy


@dataclass(frozen=True)
class CurrentMutationProfileDefinition(MutationProfileDefinition):
    """Adapter that resolves the current runtime mutation profile dataclass."""

    name: str = "default_runtime_profile"

    def resolve_runtime_profile(
        self,
        profile: MutationProfile | None = None,
    ) -> MutationProfile:
        return profile or MutationProfile()


signal_pack_registry: NamedRegistry[SignalPack] = NamedRegistry()
genome_schema_registry: NamedRegistry[GenomeSchema] = NamedRegistry()
decision_policy_registry: NamedRegistry[DecisionPolicy] = NamedRegistry()
mutation_profile_registry: NamedRegistry[MutationProfileDefinition] = NamedRegistry()
market_mode_registry: NamedRegistry[MarketMode] = NamedRegistry()


signal_pack_registry.register(
    "policy_v21_default",
    CurrentPolicyV21SignalPack(),
    default=True,
)
genome_schema_registry.register(
    "policy_v2_default",
    CurrentPolicyV2GenomeSchema(),
    default=True,
)
genome_schema_registry.register(
    "modular_genome_v1",
    ModularGenomeSchemaV1(),
)
decision_policy_registry.register(
    "policy_v2_default",
    CurrentPolicyV2DecisionPolicy(),
    default=True,
)
mutation_profile_registry.register(
    "default_runtime_profile",
    CurrentMutationProfileDefinition(),
    default=True,
)
market_mode_registry.register(
    "spot",
    SpotMarketMode(),
    default=True,
)
market_mode_registry.register(
    "futures",
    FuturesMarketMode(),
)


def get_default_signal_pack() -> SignalPack:
    return signal_pack_registry.get_default()


def get_signal_pack(name: str) -> SignalPack:
    return signal_pack_registry.get(name)


def get_default_genome_schema() -> GenomeSchema:
    return genome_schema_registry.get_default()


def get_genome_schema(name: str) -> GenomeSchema:
    return genome_schema_registry.get(name)


def get_default_decision_policy() -> DecisionPolicy:
    return decision_policy_registry.get_default()


def get_decision_policy(name: str) -> DecisionPolicy:
    return decision_policy_registry.get(name)


def get_default_mutation_profile_definition() -> MutationProfileDefinition:
    return mutation_profile_registry.get_default()


def get_mutation_profile_definition(name: str) -> MutationProfileDefinition:
    return mutation_profile_registry.get(name)


def get_default_market_mode() -> MarketMode:
    return market_mode_registry.get_default()


def get_market_mode(name: str) -> MarketMode:
    return market_mode_registry.get(name)
