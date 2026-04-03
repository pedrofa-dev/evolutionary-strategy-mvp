from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


@dataclass(frozen=True)
class GeneTypeSpec:
    """Group mutable fields that belong to one modular genome block.

    The catalog groups fields by structural ownership, not by trading
    interpretation. Trading semantics still live in genome definitions and
    runtime decision code.
    """

    name: str
    factory_name: str
    field_specs: tuple[GeneFieldSpec, ...]


@dataclass(frozen=True)
class SchemaFieldSpec:
    """Describe mutable schema-level fields that are not gene blocks."""

    field_name: str
    mutation_kind: str
    minimum: int
    maximum: int


@dataclass(frozen=True)
class GeneTypeCatalog:
    """Centralize the mutable surface of the active modular genome schema.

    Why it exists:
    - Mutation needs one authoritative description of what is mutable and where
      each field belongs.

    Constraints:
    - The catalog describes mutation space and structural normalization only.
    - It must not become a second home for policy logic.
    """

    name: str
    gene_types: tuple[GeneTypeSpec, ...]
    schema_fields: tuple[SchemaFieldSpec, ...]

    def get_gene_type(self, name: str) -> GeneTypeSpec:
        for gene_type in self.gene_types:
            if gene_type.name == name:
                return gene_type
        raise KeyError(f"Unknown gene type: {name}")

    def list_gene_type_names(self) -> list[str]:
        return [gene_type.name for gene_type in self.gene_types]

    def list_schema_field_names(self) -> list[str]:
        return [field.field_name for field in self.schema_fields]


MODULAR_GENOME_V1_GENE_TYPE_CATALOG = GeneTypeCatalog(
    name="modular_genome_v1_gene_catalog",
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
            factory_name="build_entry_context",
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
            factory_name="build_entry_trigger",
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
            factory_name="build_exit_policy",
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
            factory_name="build_trade_control",
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
