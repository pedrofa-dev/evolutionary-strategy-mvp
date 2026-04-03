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
    MutationProfileDefinition,
    SignalPack,
)
from evo_system.experimental_space.registry import NamedRegistry
from evo_system.mutation.mutator import MutationProfile


# Phase 1 of incremental modularization:
# - These default implementations are adapters over the current runtime.
# - They exist to make boundaries explicit before any deeper refactor happens.


@dataclass(frozen=True)
class CurrentPolicyV21SignalPack(SignalPack):
    """Adapter over the current policy_v2.1 signal feature/family builders."""

    name: str = "policy_v21_default"

    def build_signal_features(self, *, environment: Any, **kwargs: Any) -> dict[str, float]:
        return environment._get_policy_v21_signal_features(**kwargs)

    def build_signal_families(
        self,
        *,
        environment: Any,
        signal_features: dict[str, float],
    ) -> dict[str, float]:
        return environment._get_signal_families(signal_features=signal_features)


@dataclass(frozen=True)
class CurrentPolicyV2GenomeSchema(GenomeSchema):
    """Adapter over the current block-based genome construction helper."""

    name: str = "policy_v2_default"

    def is_active_for_genome(self, genome: Genome) -> bool:
        return genome.policy_v2_enabled

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


@dataclass(frozen=True)
class CurrentPolicyV2DecisionPolicy(DecisionPolicy):
    """Adapter over the current entry-context and trigger runtime logic."""

    name: str = "policy_v2_default"

    def get_entry_trigger_score(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> float:
        return environment._get_entry_trigger_score(genome, signal_families)

    def passes_entry_context(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> bool:
        return environment._passes_entry_context(genome, signal_families)

    def passes_entry_trigger(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
    ) -> bool:
        return environment._passes_entry_trigger(
            genome,
            signal_families,
            trigger_score,
        )


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


def get_default_signal_pack() -> SignalPack:
    return signal_pack_registry.get_default()


def get_default_genome_schema() -> GenomeSchema:
    return genome_schema_registry.get_default()


def get_genome_schema(name: str) -> GenomeSchema:
    return genome_schema_registry.get(name)


def get_default_decision_policy() -> DecisionPolicy:
    return decision_policy_registry.get_default()


def get_default_mutation_profile_definition() -> MutationProfileDefinition:
    return mutation_profile_registry.get_default()
