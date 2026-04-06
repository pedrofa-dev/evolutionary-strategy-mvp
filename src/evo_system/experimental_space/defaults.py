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
from evo_system.experimental_space.asset_loader import ASSETS_ROOT, load_all_declarative_assets
from evo_system.experimental_space.gene_catalog import (
    MODULAR_GENOME_V1_GENE_TYPE_CATALOG,
    GeneTypeCatalog,
    get_gene_catalog,
)
from evo_system.experimental_space.decision_policies import DefaultDecisionPolicy
from evo_system.experimental_space.market_modes import (
    FuturesMarketMode,
    SpotMarketMode,
)
from evo_system.experimental_space.policy_engines import (
    DefaultPolicyEngine,
    PolicyEngine,
)
from evo_system.experimental_space.registry import NamedRegistry
from evo_system.experimental_space.signal_packs import (
    DefaultSignalPack,
    POLICY_V21_FEATURE_NAMES,
)
from evo_system.mutation.mutator import MutationProfile


# Phase 1 of incremental modularization:
# - These default implementations expose the active runtime modules through
#   explicit registries and stable names.
# - Some components still wrap existing helpers, but SignalPack and
#   DecisionPolicy now own the active modular semantics directly.


@dataclass(frozen=True)
class PolicyV2CompatibilityGenomeSchema(GenomeSchema):
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


@dataclass(frozen=True)
class DeclarativeGenomeSchemaAdapter(GenomeSchema):
    """Bounded adapter for declarative genome schema assets.

    This adapter intentionally stays narrow:
    - module order comes from the declarative asset
    - runtime genome construction still delegates to the compatible built-in
      schema and gene catalog
    - it does not introduce new execution or mutation semantics
    """

    name: str
    module_names: tuple[str, ...]
    gene_type_catalog: GeneTypeCatalog
    base_schema: GenomeSchema

    def is_active_for_genome(self, genome: Genome) -> bool:
        return self.base_schema.is_active_for_genome(genome)

    def get_gene_type_catalog(self) -> GeneTypeCatalog:
        return self.gene_type_catalog

    def get_module_names(self) -> tuple[str, ...]:
        return self.module_names

    def build_default_module(self, module_name: str) -> Any:
        if module_name not in self.module_names:
            raise KeyError(f"Unknown genome schema module: {module_name}")
        return self.gene_type_catalog.build_default_module(module_name)

    def build_genome_from_modules(
        self,
        *,
        position_size: float,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
    ) -> Genome:
        return self.gene_type_catalog.build_genome(
            position_size=position_size,
            schema_fields=schema_fields,
            gene_blocks=gene_blocks,
        )

    def build_genome(self, **kwargs: Any) -> Genome:
        return self.base_schema.build_genome(**kwargs)

@dataclass(frozen=True)
class RuntimeMutationProfileAdapter(MutationProfileDefinition):
    """Adapter that resolves the current runtime mutation profile dataclass."""

    name: str = "default_runtime_profile"

    def resolve_runtime_profile(
        self,
        profile: MutationProfile | None = None,
    ) -> MutationProfile:
        return profile or MutationProfile()


@dataclass(frozen=True)
class DeclarativeMutationProfileAdapter(MutationProfileDefinition):
    """Resolve a declarative mutation profile asset through the existing mutator."""

    name: str
    default_profile: MutationProfile

    def resolve_runtime_profile(
        self,
        profile: MutationProfile | None = None,
    ) -> MutationProfile:
        return profile or self.default_profile


@dataclass(frozen=True)
class DeclarativeSignalPackAdapter(SignalPack):
    """Resolve a declarative signal pack asset through the current signal vocabulary."""

    name: str
    feature_names: tuple[str, ...]
    family_names: tuple[str, ...]
    source_by_feature_name: dict[str, str]

    def build_signal_features(self, *, environment: Any, **kwargs: Any) -> dict[str, float]:
        base_pack = DefaultSignalPack()
        base_features = base_pack.build_signal_features(environment=environment, **kwargs)
        return {
            feature_name: float(base_features.get(source_name, 0.0))
            for feature_name, source_name in self.source_by_feature_name.items()
        }

    def build_signal_families(
        self,
        *,
        environment: Any,
        signal_features: dict[str, float],
    ) -> dict[str, float]:
        base_pack = DefaultSignalPack()
        canonical_features = {
            feature_name: 0.0 for feature_name in POLICY_V21_FEATURE_NAMES
        }
        for feature_name, source_name in self.source_by_feature_name.items():
            canonical_features[source_name] = float(signal_features.get(feature_name, 0.0))
        return base_pack.build_signal_families(
            environment=environment,
            signal_features=canonical_features,
        )


DECLARATIVE_ASSET_ROOT = ASSETS_ROOT


signal_pack_registry: NamedRegistry[SignalPack] = NamedRegistry()
genome_schema_registry: NamedRegistry[GenomeSchema] = NamedRegistry()
policy_engine_registry: NamedRegistry[PolicyEngine] = NamedRegistry()
decision_policy_registry: NamedRegistry[DecisionPolicy] = NamedRegistry()
mutation_profile_registry: NamedRegistry[MutationProfileDefinition] = NamedRegistry()
market_mode_registry: NamedRegistry[MarketMode] = NamedRegistry()


signal_pack_registry.register(
    "policy_v21_default",
    DefaultSignalPack(),
    default=True,
)
genome_schema_registry.register(
    "policy_v2_default",
    PolicyV2CompatibilityGenomeSchema(),
    default=True,
)
genome_schema_registry.register(
    "modular_genome_v1",
    ModularGenomeSchemaV1(),
)
policy_engine_registry.register(
    "policy_v2_default_engine",
    DefaultPolicyEngine(),
    default=True,
)
decision_policy_registry.register(
    "policy_v2_default",
    policy_engine_registry.get_default().build_decision_policy(),
    default=True,
)
mutation_profile_registry.register(
    "default_runtime_profile",
    RuntimeMutationProfileAdapter(),
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
    if signal_pack_registry.has(name):
        return signal_pack_registry.get(name)

    declarative_signal_pack = _load_declarative_signal_pack(name)
    if declarative_signal_pack is not None:
        return declarative_signal_pack

    return signal_pack_registry.get(name)


def get_default_genome_schema() -> GenomeSchema:
    return genome_schema_registry.get_default()


def get_genome_schema(name: str) -> GenomeSchema:
    if genome_schema_registry.has(name):
        return genome_schema_registry.get(name)

    declarative_schema = _load_declarative_genome_schema(name)
    if declarative_schema is not None:
        return declarative_schema

    return genome_schema_registry.get(name)


def get_default_decision_policy() -> DecisionPolicy:
    return decision_policy_registry.get_default()


def get_decision_policy(name: str) -> DecisionPolicy:
    return decision_policy_registry.get(name)


def get_default_policy_engine() -> PolicyEngine:
    return policy_engine_registry.get_default()


def get_policy_engine(name: str) -> PolicyEngine:
    return policy_engine_registry.get(name)


def get_default_mutation_profile_definition() -> MutationProfileDefinition:
    return mutation_profile_registry.get_default()


def get_mutation_profile_definition(name: str) -> MutationProfileDefinition:
    if mutation_profile_registry.has(name):
        return mutation_profile_registry.get(name)

    declarative_definition = _load_declarative_mutation_profile_definition(name)
    if declarative_definition is not None:
        return declarative_definition

    return mutation_profile_registry.get(name)


def get_default_market_mode() -> MarketMode:
    return market_mode_registry.get_default()


def get_market_mode(name: str) -> MarketMode:
    return market_mode_registry.get(name)


def _load_declarative_mutation_profile_definition(
    name: str,
) -> MutationProfileDefinition | None:
    assets = load_all_declarative_assets(DECLARATIVE_ASSET_ROOT).get(
        "mutation_profiles",
        [],
    )
    for asset in assets:
        if asset.name != name:
            continue
        profile_payload = asset.payload.get("profile")
        if not isinstance(profile_payload, dict):
            return None
        return DeclarativeMutationProfileAdapter(
            name=asset.name,
            default_profile=MutationProfile.from_dict(profile_payload),
        )
    return None


def _load_declarative_signal_pack(name: str) -> SignalPack | None:
    assets = load_all_declarative_assets(DECLARATIVE_ASSET_ROOT).get(
        "signal_packs",
        [],
    )
    for asset in assets:
        if asset.name != name:
            continue
        signal_entries = asset.payload.get("signals")
        if not isinstance(signal_entries, list):
            return None

        source_by_feature_name: dict[str, str] = {}
        for entry in signal_entries:
            if not isinstance(entry, dict):
                return None
            signal_id = entry.get("signal_id")
            if not isinstance(signal_id, str) or not signal_id.strip():
                return None
            alias = entry.get("alias")
            feature_name = alias if isinstance(alias, str) and alias.strip() else signal_id
            params = entry.get("params")
            source_name = signal_id
            if isinstance(params, dict):
                source_value = params.get("source")
                if isinstance(source_value, str) and source_value.strip():
                    source_name = source_value
            source_by_feature_name[feature_name] = source_name

        return DeclarativeSignalPackAdapter(
            name=asset.name,
            feature_names=tuple(source_by_feature_name.keys()),
            family_names=DefaultSignalPack().family_names,
            source_by_feature_name=source_by_feature_name,
        )
    return None


def _load_declarative_genome_schema(name: str) -> GenomeSchema | None:
    assets = load_all_declarative_assets(DECLARATIVE_ASSET_ROOT).get(
        "genome_schemas",
        [],
    )
    for asset in assets:
        if asset.name != name:
            continue

        gene_catalog_name = asset.payload.get("gene_catalog")
        if not isinstance(gene_catalog_name, str) or not gene_catalog_name.strip():
            raise ValueError(
                f"Genome schema asset {asset.path} is missing a valid 'gene_catalog'."
            )

        try:
            gene_catalog = get_gene_catalog(gene_catalog_name)
        except KeyError as exc:
            raise ValueError(
                f"Unknown gene_catalog {gene_catalog_name!r} in genome schema asset: "
                f"{asset.path}"
            ) from exc

        base_schema_name = _runtime_schema_name_for_gene_catalog(gene_catalog_name)
        base_schema = genome_schema_registry.get(base_schema_name)

        modules = asset.payload.get("modules")
        if not isinstance(modules, list):
            raise ValueError(
                f"Genome schema asset {asset.path} must define a modules list."
            )

        module_names: list[str] = []
        for module in modules:
            if not isinstance(module, dict):
                raise ValueError(
                    f"Genome schema asset {asset.path} contains a non-object module."
                )
            module_name = module.get("name")
            if not isinstance(module_name, str) or not module_name.strip():
                raise ValueError(
                    f"Genome schema asset {asset.path} contains a module without a "
                    f"valid name."
                )
            module_names.append(module_name)

        return DeclarativeGenomeSchemaAdapter(
            name=asset.name,
            module_names=tuple(module_names),
            gene_type_catalog=gene_catalog,
            base_schema=base_schema,
        )
    return None


def _runtime_schema_name_for_gene_catalog(gene_catalog_name: str) -> str:
    runtime_schema_names_by_gene_catalog = {
        MODULAR_GENOME_V1_GENE_TYPE_CATALOG.name: "modular_genome_v1",
    }
    try:
        return runtime_schema_names_by_gene_catalog[gene_catalog_name]
    except KeyError as exc:
        raise ValueError(
            f"No runtime genome schema is registered for gene_catalog "
            f"{gene_catalog_name!r}."
        ) from exc
