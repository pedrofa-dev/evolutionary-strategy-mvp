from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
    build_policy_v2_genome,
)


# Phase 2 of incremental modularization:
# - The catalog below centralizes mutation metadata for the active modular
#   genome layout.
# - It does not change runtime semantics by itself; it only makes the mutable
#   surface explicit for mutation and future schema-driven tooling.


@dataclass(frozen=True)
class GeneFieldSpec:
    """Describe mutation-space metadata for one field.

    Constraints:
    - This spec defines ranges, step behavior, and normalization inputs only.
    - It must not encode decision-policy semantics or evaluation rules.
    """

    field_name: str
    mutation_kind: str
    minimum: float | int | None = None
    maximum: float | int | None = None
    delta_kind: str = "main"
    strong_min: float | int | None = None
    strong_max: float | int | None = None
    strong_choices: tuple[int, ...] | None = None
    small_choices: tuple[int, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "mutation_kind": self.mutation_kind,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "delta_kind": self.delta_kind,
            "strong_min": self.strong_min,
            "strong_max": self.strong_max,
            "strong_choices": list(self.strong_choices)
            if self.strong_choices is not None
            else None,
            "small_choices": list(self.small_choices)
            if self.small_choices is not None
            else None,
        }


@dataclass(frozen=True)
class GeneTypeSpec:
    """Group mutable fields that belong to one modular genome block.

    The catalog groups fields by structural ownership, not by trading
    interpretation. Trading semantics still live in genome definitions and
    runtime decision code.
    """

    name: str
    builder: Callable[[dict[str, Any]], Any]
    field_specs: tuple[GeneFieldSpec, ...]
    normalizer: Callable[[dict[str, Any]], dict[str, Any]]
    constraint_applier: Callable[[dict[str, Any], dict[str, float]], dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "builder": _callable_label(self.builder),
            "field_specs": [field_spec.to_dict() for field_spec in self.field_specs],
            "normalizer": _callable_label(self.normalizer),
            "constraint_applier": (
                _callable_label(self.constraint_applier)
                if self.constraint_applier is not None
                else None
            ),
        }


@dataclass(frozen=True)
class SchemaFieldSpec:
    """Describe mutable schema-level fields that are not gene blocks."""

    field_name: str
    mutation_kind: str
    minimum: int
    maximum: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "mutation_kind": self.mutation_kind,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


@dataclass(frozen=True)
class GeneTypeDefinition:
    """Serializable structural metadata for one gene block.

    This DTO is intentionally descriptive only. It is derived from the active
    ``GeneTypeCatalog`` and exists to expose stable structural metadata for
    inspection, reporting, and future declarative/UI work.

    It does not own runtime behavior, mutation execution, or decision
    semantics, and it is not yet the canonical runtime source of truth.
    """

    name: str
    builder_name: str
    field_specs: tuple[GeneFieldSpec, ...]
    supports_constraints: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "builder_name": self.builder_name,
            "field_specs": [field_spec.to_dict() for field_spec in self.field_specs],
            "supports_constraints": self.supports_constraints,
        }


@dataclass(frozen=True)
class GenomeSchemaSlot:
    """Serializable structural description of one schema-owned slot/module.

    This is a derived structural view of schema composition. In the current
    runtime, all active slots are required single-instance gene blocks; those
    defaults are made explicit here so future declarative schemas can evolve
    without changing the current behavior.
    """

    name: str
    slot_kind: str
    field_names: tuple[str, ...]
    required: bool = True
    cardinality_min: int = 1
    cardinality_max: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slot_kind": self.slot_kind,
            "field_names": list(self.field_names),
            "required": self.required,
            "cardinality_min": self.cardinality_min,
            "cardinality_max": self.cardinality_max,
        }


@dataclass(frozen=True)
class StructuralCompatibility:
    """Describe minimal structural compatibility between schema and catalog."""

    schema_name: str
    gene_catalog_name: str
    module_names: tuple[str, ...]
    schema_field_names: tuple[str, ...]
    policy_v2_enabled_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "gene_catalog_name": self.gene_catalog_name,
            "module_names": list(self.module_names),
            "schema_field_names": list(self.schema_field_names),
            "policy_v2_enabled_required": self.policy_v2_enabled_required,
        }


@dataclass(frozen=True)
class GeneTypeCatalog:
    """Centralize the mutable surface of the active modular genome schema.

    Why it exists:
    - Mutation needs one authoritative description of what is mutable and where
      each field belongs.

    Constraints:
    - The catalog describes mutation space and structural normalization only.
    - It must not become a second home for policy logic.

    Source of truth:
    - In the current architecture, the runtime source of truth still lives in
      this catalog plus the active ``GenomeSchema`` implementation.
    - Serializable DTOs such as ``GeneTypeDefinition`` and
      ``GenomeSchemaSlot`` are derived compatibility views, not independent
      runtime authorities yet.
    """

    name: str
    gene_types: tuple[GeneTypeSpec, ...]
    schema_fields: tuple[SchemaFieldSpec, ...]
    schema_normalizer: Callable[[dict[str, int]], dict[str, int]]
    genome_builder: Callable[[float, dict[str, int], dict[str, Any]], Genome]

    def get_gene_type(self, name: str) -> GeneTypeSpec:
        for gene_type in self.gene_types:
            if gene_type.name == name:
                return gene_type
        raise KeyError(f"Unknown gene type: {name}")

    def list_gene_type_names(self) -> list[str]:
        return [gene_type.name for gene_type in self.gene_types]

    def list_schema_field_names(self) -> list[str]:
        return [field.field_name for field in self.schema_fields]

    def describe_gene_types(self) -> tuple[GeneTypeDefinition, ...]:
        """Return descriptive DTOs derived from the active runtime catalog."""
        return tuple(
            GeneTypeDefinition(
                name=gene_type.name,
                builder_name=_callable_label(gene_type.builder),
                field_specs=gene_type.field_specs,
                supports_constraints=gene_type.constraint_applier is not None,
            )
            for gene_type in self.gene_types
        )

    def describe_schema_slots(self) -> tuple[GenomeSchemaSlot, ...]:
        """Return a structural view of schema-owned slots for external use."""
        return tuple(
            GenomeSchemaSlot(
                name=gene_type.name,
                slot_kind="gene_block",
                field_names=tuple(
                    field_spec.field_name for field_spec in gene_type.field_specs
                ),
            )
            for gene_type in self.gene_types
        )

    def describe_structural_compatibility(
        self,
        *,
        schema_name: str,
    ) -> StructuralCompatibility:
        return StructuralCompatibility(
            schema_name=schema_name,
            gene_catalog_name=self.name,
            module_names=tuple(self.list_gene_type_names()),
            schema_field_names=tuple(self.list_schema_field_names()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize catalog metadata using stable, descriptive field names."""
        return {
            "name": self.name,
            "gene_types": [gene_type.to_dict() for gene_type in self.gene_types],
            "schema_fields": [
                schema_field.to_dict() for schema_field in self.schema_fields
            ],
            "gene_type_definitions": [
                definition.to_dict()
                for definition in self.describe_gene_types()
            ],
            "schema_slots": [
                slot.to_dict() for slot in self.describe_schema_slots()
            ],
        }

    def build_module(
        self,
        name: str,
        data: dict[str, Any],
        constraints: dict[str, float] | None = None,
    ) -> Any:
        spec = self.get_gene_type(name)
        normalized = spec.normalizer(data)
        if spec.constraint_applier is not None:
            normalized = spec.constraint_applier(normalized, constraints or {})
        return spec.builder(normalized)

    def build_default_module(
        self,
        name: str,
        constraints: dict[str, float] | None = None,
    ) -> Any:
        spec = self.get_gene_type(name)
        default_instance = spec.builder({})
        default_data = asdict(default_instance)
        if spec.constraint_applier is not None:
            default_data = spec.constraint_applier(default_data, constraints or {})
        return spec.builder(default_data)

    def normalize_schema_fields(self, data: dict[str, int]) -> dict[str, int]:
        return self.schema_normalizer(data)

    def build_genome(
        self,
        *,
        position_size: float,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
    ) -> Genome:
        return self.genome_builder(position_size, schema_fields, gene_blocks)


def _identity_normalizer(data: dict[str, Any]) -> dict[str, Any]:
    return dict(data)


def _callable_label(callable_obj: Callable[..., Any]) -> str:
    return getattr(callable_obj, "__name__", callable_obj.__class__.__name__)


def _apply_entry_trigger_constraints(
    data: dict[str, Any],
    constraints: dict[str, float],
) -> dict[str, Any]:
    constrained = dict(data)

    for field_name in (
        "trend_weight",
        "momentum_weight",
        "breakout_weight",
        "range_weight",
        "volatility_weight",
    ):
        min_key = f"min_{field_name}"
        max_key = f"max_{field_name}"

        if min_key in constraints:
            constrained[field_name] = max(
                float(constrained[field_name]),
                float(constraints[min_key]),
            )

        if max_key in constraints:
            constrained[field_name] = min(
                float(constrained[field_name]),
                float(constraints[max_key]),
            )

    return constrained


def _normalize_modular_schema_fields(data: dict[str, int]) -> dict[str, int]:
    normalized = dict(data)

    if normalized["ret_short_window"] >= normalized["ret_mid_window"]:
        normalized["ret_short_window"] = max(2, normalized["ret_mid_window"] - 1)

    if normalized["vol_short_window"] >= normalized["vol_long_window"]:
        normalized["vol_short_window"] = max(2, normalized["vol_long_window"] - 1)

    return normalized


def _build_modular_policy_v2_genome(
    position_size: float,
    schema_fields: dict[str, int],
    gene_blocks: dict[str, Any],
) -> Genome:
    exit_policy = gene_blocks["exit_policy"]
    return build_policy_v2_genome(
        position_size=position_size,
        stop_loss_pct=exit_policy.stop_loss_pct,
        take_profit_pct=exit_policy.take_profit_pct,
        entry_context=gene_blocks["entry_context"],
        entry_trigger=gene_blocks["entry_trigger"],
        exit_policy=exit_policy,
        trade_control=gene_blocks["trade_control"],
        **schema_fields,
    )


MODULAR_GENOME_V1_GENE_TYPE_CATALOG = GeneTypeCatalog(
    name="modular_genome_v1_gene_catalog",
    schema_normalizer=_normalize_modular_schema_fields,
    genome_builder=_build_modular_policy_v2_genome,
    schema_fields=(
        SchemaFieldSpec("trend_window", "window", 2, 50),
        SchemaFieldSpec("ret_short_window", "window", 2, 10),
        SchemaFieldSpec("ret_mid_window", "window", 5, 50),
        SchemaFieldSpec("ma_window", "window", 5, 100),
        SchemaFieldSpec("range_window", "window", 5, 50),
        SchemaFieldSpec("vol_short_window", "window", 2, 20),
        SchemaFieldSpec("vol_long_window", "window", 10, 100),
    ),
    gene_types=(
        GeneTypeSpec(
            name="entry_context",
            builder=EntryContextGene.from_dict,
            normalizer=lambda data: normalize_gene_data("entry_context", data),
            field_specs=(
                GeneFieldSpec(
                    "min_trend_strength",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "min_breakout_strength",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "min_realized_volatility",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "max_realized_volatility",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "allowed_range_position_min",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "allowed_range_position_max",
                    "bounded_float",
                    minimum=-1.0,
                    maximum=1.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
            ),
        ),
        GeneTypeSpec(
            name="entry_trigger",
            builder=EntryTriggerGene.from_dict,
            normalizer=_identity_normalizer,
            constraint_applier=_apply_entry_trigger_constraints,
            field_specs=(
                GeneFieldSpec(
                    "trend_weight",
                    "weight",
                    minimum=-3.0,
                    maximum=3.0,
                    strong_min=-2.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "momentum_weight",
                    "weight",
                    minimum=-3.0,
                    maximum=3.0,
                    strong_min=-2.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "breakout_weight",
                    "weight",
                    minimum=-3.0,
                    maximum=3.0,
                    strong_min=-2.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "range_weight",
                    "weight",
                    minimum=-3.0,
                    maximum=3.0,
                    strong_min=-2.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "volatility_weight",
                    "weight",
                    minimum=-3.0,
                    maximum=3.0,
                    strong_min=-2.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "entry_score_threshold",
                    "threshold",
                    minimum=-5.0,
                    maximum=5.0,
                    strong_min=-1.0,
                    strong_max=2.0,
                ),
                GeneFieldSpec(
                    "min_positive_families",
                    "count",
                    minimum=0,
                    maximum=5,
                    strong_min=0,
                    strong_max=5,
                    small_choices=(-1, 0, 1),
                ),
                GeneFieldSpec(
                    "require_trend_or_breakout",
                    "flag",
                ),
            ),
        ),
        GeneTypeSpec(
            name="exit_policy",
            builder=ExitPolicyGene.from_dict,
            normalizer=_identity_normalizer,
            field_specs=(
                GeneFieldSpec(
                    "exit_score_threshold",
                    "threshold",
                    minimum=-5.0,
                    maximum=5.0,
                    strong_min=-1.0,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "exit_on_signal_reversal",
                    "flag",
                ),
                GeneFieldSpec(
                    "max_holding_bars",
                    "count",
                    minimum=0,
                    maximum=200,
                    strong_choices=(0, 6, 12, 24, 36, 48),
                    small_choices=(-2, -1, 0, 1, 2),
                ),
                GeneFieldSpec(
                    "stop_loss_pct",
                    "bounded_float",
                    minimum=0.01,
                    maximum=1.0,
                    delta_kind="stop_loss",
                    strong_min=0.01,
                    strong_max=1.0,
                ),
                GeneFieldSpec(
                    "take_profit_pct",
                    "bounded_float",
                    minimum=0.01,
                    maximum=2.0,
                    strong_min=0.01,
                    strong_max=2.0,
                ),
            ),
        ),
        GeneTypeSpec(
            name="trade_control",
            builder=TradeControlGene.from_dict,
            normalizer=_identity_normalizer,
            field_specs=(
                GeneFieldSpec(
                    "cooldown_bars",
                    "count",
                    minimum=0,
                    maximum=100,
                    strong_min=0,
                    strong_max=8,
                    small_choices=(-1, 0, 1),
                ),
                GeneFieldSpec(
                    "min_holding_bars",
                    "count",
                    minimum=0,
                    maximum=100,
                    strong_min=0,
                    strong_max=8,
                    small_choices=(-1, 0, 1),
                ),
                GeneFieldSpec(
                    "reentry_block_bars",
                    "count",
                    minimum=0,
                    maximum=100,
                    strong_min=0,
                    strong_max=8,
                    small_choices=(-1, 0, 1),
                ),
            ),
        ),
    ),
)


def normalize_gene_data(gene_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Apply structural normalization rules after field-level mutation."""

    normalized = dict(data)

    if gene_name == "entry_context":
        if normalized["min_realized_volatility"] > normalized["max_realized_volatility"]:
            normalized["min_realized_volatility"], normalized["max_realized_volatility"] = (
                normalized["max_realized_volatility"],
                normalized["min_realized_volatility"],
            )

        if normalized["allowed_range_position_min"] > normalized["allowed_range_position_max"]:
            normalized["allowed_range_position_min"], normalized["allowed_range_position_max"] = (
                normalized["allowed_range_position_max"],
                normalized["allowed_range_position_min"],
            )

    return normalized
