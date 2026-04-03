from __future__ import annotations

import random
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
from evo_system.experimental_space.gene_catalog import (
    GeneFieldSpec,
    GeneTypeCatalog,
    GeneTypeSpec,
    MODULAR_GENOME_V1_GENE_TYPE_CATALOG,
    normalize_gene_data,
)


@dataclass(frozen=True)
class MutationProfile:
    # Responsibility boundary:
    # - MutationProfile controls mutation intensity, not policy semantics.
    # - It is a natural future candidate for configuration-driven mutation
    #   selection, but should stay separate from genome meaning.
    strong_mutation_probability: float = 0.10
    numeric_delta_scale: float = 1.0
    flag_flip_probability: float = 0.05
    weight_delta: float = 0.20
    window_step_mode: str = "default"  # "small", "default", "wide"

    def main_delta(self) -> float:
        return 0.03 * self.numeric_delta_scale

    def stop_loss_delta(self) -> float:
        return 0.01 * self.numeric_delta_scale

    def signal_delta(self) -> float:
        return 0.001 * self.numeric_delta_scale

    def window_choices(self) -> tuple[int, ...]:
        if self.window_step_mode == "small":
            return (-1, 1)
        if self.window_step_mode == "wide":
            return (-3, -2, -1, 1, 2, 3)
        return (-2, -1, 1, 2)


class ModularGenomeMutationEngine:
    """Mutate modular genomes through centralized schema/catalog metadata.

    Why it exists:
    - This engine removes most of the ad hoc field-by-field mutation logic for
      active modular genomes.
    - It keeps mutation metadata separate from mutation execution so future
      schemas can swap catalogs without rewriting the whole mutator.

    Constraints:
    - It must preserve current policy_v2 behavior as closely as possible.
    - It must not redefine signal meaning, evaluation rules, or decision
      semantics.
    """

    def __init__(
        self,
        *,
        random_source: random.Random,
        profile: MutationProfile,
        gene_type_catalog: GeneTypeCatalog,
        entry_trigger_constraints: dict[str, float],
    ) -> None:
        self.random = random_source
        self.profile = profile
        self.gene_type_catalog = gene_type_catalog
        self.entry_trigger_constraints = entry_trigger_constraints

    def mutate_small(self, genome: Genome) -> Genome:
        schema_fields = self._mutate_schema_fields_small(genome)
        gene_blocks = self._mutate_gene_blocks_small(genome)

        return self._build_modular_genome(
            genome=genome,
            schema_fields=schema_fields,
            gene_blocks=gene_blocks,
            position_size=self._clamp(
                genome.position_size + self._scaled_delta(0.03),
                0.05,
                1.0,
            ),
        )

    def mutate_strong(self, genome: Genome) -> Genome:
        schema_fields = self._mutate_schema_fields_strong()
        gene_blocks = self._mutate_gene_blocks_strong()

        return self._build_modular_genome(
            genome=genome,
            schema_fields=schema_fields,
            gene_blocks=gene_blocks,
            position_size=self.random.uniform(0.05, 1.0),
        )

    def mutate_module_small(self, module_name: str, module_value: Any) -> Any:
        spec = self.gene_type_catalog.get_gene_type(module_name)
        mutated_data = {
            field_spec.field_name: self._mutate_field_small(
                spec,
                field_spec,
                getattr(module_value, field_spec.field_name),
            )
            for field_spec in spec.field_specs
        }
        return self._build_module(spec, mutated_data)

    def mutate_module_strong(self, module_name: str) -> Any:
        spec = self.gene_type_catalog.get_gene_type(module_name)
        mutated_data = {
            field_spec.field_name: self._mutate_field_strong(field_spec)
            for field_spec in spec.field_specs
        }
        return self._build_module(spec, mutated_data)

    def rebuild_module(self, module_name: str, module_data: dict[str, Any]) -> Any:
        """Rebuild one module from catalog metadata plus normalized payload.

        Why it exists:
        - Tests and future schema-driven tooling need one explicit path to
          reconstruct modular gene blocks from metadata.
        """
        spec = self.gene_type_catalog.get_gene_type(module_name)
        return self._build_module(spec, module_data)

    def _mutate_gene_blocks_small(self, genome: Genome) -> dict[str, Any]:
        return {
            "entry_context": self.mutate_module_small(
                "entry_context",
                genome.entry_context or EntryContextGene(),
            ),
            "entry_trigger": self.mutate_module_small(
                "entry_trigger",
                genome.entry_trigger or EntryTriggerGene(),
            ),
            "exit_policy": self.mutate_module_small(
                "exit_policy",
                genome.exit_policy or ExitPolicyGene(),
            ),
            "trade_control": self.mutate_module_small(
                "trade_control",
                genome.trade_control or TradeControlGene(),
            ),
        }

    def _mutate_gene_blocks_strong(self) -> dict[str, Any]:
        return {
            "entry_context": self.mutate_module_strong("entry_context"),
            "entry_trigger": self.mutate_module_strong("entry_trigger"),
            "exit_policy": self.mutate_module_strong("exit_policy"),
            "trade_control": self.mutate_module_strong("trade_control"),
        }

    def _build_modular_genome(
        self,
        *,
        genome: Genome,
        schema_fields: dict[str, int],
        gene_blocks: dict[str, Any],
        position_size: float,
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

    def _build_module(self, spec: GeneTypeSpec, data: dict[str, Any]) -> Any:
        normalized = normalize_gene_data(spec.name, data)

        if spec.name == "entry_trigger":
            normalized = self._apply_entry_trigger_constraints(normalized)

        if spec.factory_name == "build_entry_context":
            return EntryContextGene.from_dict(normalized)
        if spec.factory_name == "build_entry_trigger":
            return EntryTriggerGene.from_dict(normalized)
        if spec.factory_name == "build_exit_policy":
            return ExitPolicyGene.from_dict(normalized)
        if spec.factory_name == "build_trade_control":
            return TradeControlGene.from_dict(normalized)

        raise KeyError(f"Unknown factory for gene type: {spec.factory_name}")

    def _mutate_schema_fields_small(self, genome: Genome) -> dict[str, int]:
        # Schema-level mutation owns only non-gene structural fields such as
        # windows. It must stay separate from gene-block mutation.
        mutated = {
            field_spec.field_name: self._mutate_schema_field_small(
                field_spec,
                getattr(genome, field_spec.field_name),
            )
            for field_spec in self.gene_type_catalog.schema_fields
        }

        return self._normalize_schema_fields(mutated)

    def _mutate_schema_fields_strong(self) -> dict[str, int]:
        mutated = {
            field_spec.field_name: self._mutate_schema_field_strong(field_spec)
            for field_spec in self.gene_type_catalog.schema_fields
        }

        return self._normalize_schema_fields(mutated)

    def _mutate_schema_field_small(
        self,
        field_spec,
        current_value: int,
    ) -> int:
        return self._mutate_window(
            current_value,
            field_spec.minimum,
            field_spec.maximum,
        )

    def _mutate_schema_field_strong(self, field_spec) -> int:
        return self.random.randint(field_spec.minimum, field_spec.maximum)

    def _normalize_schema_fields(self, mutated: dict[str, int]) -> dict[str, int]:
        normalized = dict(mutated)

        if normalized["ret_short_window"] >= normalized["ret_mid_window"]:
            normalized["ret_short_window"] = max(2, normalized["ret_mid_window"] - 1)

        if normalized["vol_short_window"] >= normalized["vol_long_window"]:
            normalized["vol_short_window"] = max(2, normalized["vol_long_window"] - 1)

        return normalized

    def _mutate_field_small(
        self,
        gene_spec: GeneTypeSpec,
        field_spec: GeneFieldSpec,
        value: Any,
    ) -> Any:
        if field_spec.mutation_kind == "weight":
            return self._mutate_weight(float(value))

        if field_spec.mutation_kind == "threshold":
            return self._clamp(
                float(value) + self.random.uniform(-self.profile.main_delta(), self.profile.main_delta()),
                float(field_spec.minimum),
                float(field_spec.maximum),
            )

        if field_spec.mutation_kind == "bounded_float":
            delta = self.profile.stop_loss_delta() if field_spec.delta_kind == "stop_loss" else self.profile.main_delta()
            return self._clamp(
                float(value) + self.random.uniform(-delta, delta),
                float(field_spec.minimum),
                float(field_spec.maximum),
            )

        if field_spec.mutation_kind == "flag":
            if self.random.random() < self.profile.flag_flip_probability:
                return not bool(value)
            return bool(value)

        if field_spec.mutation_kind == "count":
            choices = field_spec.small_choices or (-1, 0, 1)
            return max(
                int(field_spec.minimum),
                min(
                    int(field_spec.maximum),
                    int(value) + self.random.choice(choices),
                ),
            )

        raise KeyError(
            f"Unsupported mutation kind {field_spec.mutation_kind} for {gene_spec.name}.{field_spec.field_name}"
        )

    def _mutate_field_strong(self, field_spec: GeneFieldSpec) -> Any:
        if field_spec.mutation_kind == "weight":
            return self.random.uniform(float(field_spec.strong_min), float(field_spec.strong_max))

        if field_spec.mutation_kind == "threshold":
            return self.random.uniform(float(field_spec.strong_min), float(field_spec.strong_max))

        if field_spec.mutation_kind == "bounded_float":
            return self.random.uniform(float(field_spec.strong_min), float(field_spec.strong_max))

        if field_spec.mutation_kind == "flag":
            return self.random.choice([True, False])

        if field_spec.mutation_kind == "count":
            if field_spec.strong_choices is not None:
                return self.random.choice(field_spec.strong_choices)
            return self.random.randint(int(field_spec.strong_min), int(field_spec.strong_max))

        raise KeyError(f"Unsupported strong mutation kind {field_spec.mutation_kind}")

    def _apply_entry_trigger_constraints(
        self,
        trigger_data: dict[str, float | int | bool],
    ) -> dict[str, float | int | bool]:
        constrained = dict(trigger_data)

        for field_name in (
            "trend_weight",
            "momentum_weight",
            "breakout_weight",
            "range_weight",
            "volatility_weight",
        ):
            min_key = f"min_{field_name}"
            max_key = f"max_{field_name}"

            if min_key in self.entry_trigger_constraints:
                constrained[field_name] = max(
                    float(constrained[field_name]),
                    float(self.entry_trigger_constraints[min_key]),
                )

            if max_key in self.entry_trigger_constraints:
                constrained[field_name] = min(
                    float(constrained[field_name]),
                    float(self.entry_trigger_constraints[max_key]),
                )

        return constrained

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _scaled_delta(self, base_delta: float) -> float:
        delta = base_delta * self.profile.numeric_delta_scale
        return self.random.uniform(-delta, delta)

    def _mutate_weight(self, value: float) -> float:
        delta = self.profile.weight_delta
        return self._clamp(value + self.random.uniform(-delta, delta), -3.0, 3.0)

    def _mutate_window(self, value: int, min_value: int, max_value: int) -> int:
        step = self.random.choice(self.profile.window_choices())
        return int(self._clamp(value + step, min_value, max_value))


class Mutator:
    """Mutate genomes while preserving structural validity.

    Responsibility boundary:
    - Mutation logic explores the search space; it must not redefine what
      signals, genes, or decisions mean.

    Context:
    - Active modular genomes delegate to `ModularGenomeMutationEngine`.
    - Legacy genomes stay on a bounded compatibility path until historical
      support can be retired safely.
    """
    def __init__(
        self,
        seed: int | None = None,
        profile: MutationProfile | None = None,
        entry_trigger_constraints: dict[str, float] | None = None,
        gene_type_catalog: GeneTypeCatalog | None = None,
    ) -> None:
        self.random = random.Random(seed)
        self.profile = profile or MutationProfile()
        self.entry_trigger_constraints = entry_trigger_constraints or {}
        self.gene_type_catalog = gene_type_catalog or MODULAR_GENOME_V1_GENE_TYPE_CATALOG
        self.modular_engine = ModularGenomeMutationEngine(
            random_source=self.random,
            profile=self.profile,
            gene_type_catalog=self.gene_type_catalog,
            entry_trigger_constraints=self.entry_trigger_constraints,
        )

    def mutate(self, genome: Genome) -> Genome:
        # Dependency note:
        # - Genome schema selection currently dispatches mutation behavior.
        # - A future modular design could swap schema-specific mutators via a
        #   factory, but not by changing genome validity rules here.
        if genome.policy_v2_enabled:
            if self.random.random() < self.profile.strong_mutation_probability:
                return self.modular_engine.mutate_strong(genome)
            return self.modular_engine.mutate_small(genome)

        if self.random.random() < self.profile.strong_mutation_probability:
            return self._strong_mutate_legacy(genome)
        return self._small_mutate_legacy(genome)

    # =========================
    # SMALL MUTATION
    # =========================

    def _small_mutate_legacy(self, genome: Genome) -> Genome:
        main_delta = self.profile.main_delta()
        stop_loss_delta = self.profile.stop_loss_delta()
        signal_delta = self.profile.signal_delta()

        threshold_open = self._clamp(
            genome.threshold_open + self.random.uniform(-main_delta, main_delta),
            0.0,
            1.0,
        )

        threshold_close = self._clamp(
            genome.threshold_close + self.random.uniform(-main_delta, main_delta),
            0.0,
            1.0,
        )

        position_size = self._clamp(
            genome.position_size + self._scaled_delta(0.03),
            0.05,
            1.0,
        )

        stop_loss = self._clamp(
            genome.stop_loss + self.random.uniform(-stop_loss_delta, stop_loss_delta),
            0.01,
            1.0,
        )

        take_profit = self._clamp(
            genome.take_profit + self.random.uniform(-main_delta, main_delta),
            0.01,
            2.0,
        )

        use_momentum = genome.use_momentum
        if self.random.random() < self.profile.flag_flip_probability:
            use_momentum = not use_momentum

        use_trend = genome.use_trend
        if self.random.random() < self.profile.flag_flip_probability:
            use_trend = not use_trend

        use_exit_momentum = genome.use_exit_momentum
        if self.random.random() < self.profile.flag_flip_probability:
            use_exit_momentum = not use_exit_momentum

        momentum_threshold = genome.momentum_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )
        trend_threshold = genome.trend_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )
        exit_momentum_threshold = genome.exit_momentum_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )

        trend_window = self._mutate_window(genome.trend_window, 2, 50)

        ret_short_window = self._mutate_window(genome.ret_short_window, 2, 10)
        ret_mid_window = self._mutate_window(genome.ret_mid_window, 5, 50)
        ma_window = self._mutate_window(genome.ma_window, 5, 100)
        range_window = self._mutate_window(genome.range_window, 5, 50)
        vol_short_window = self._mutate_window(genome.vol_short_window, 2, 20)
        vol_long_window = self._mutate_window(genome.vol_long_window, 10, 100)

        if ret_short_window >= ret_mid_window:
            ret_short_window = max(2, ret_mid_window - 1)

        if vol_short_window >= vol_long_window:
            vol_short_window = max(2, vol_long_window - 1)

        weight_ret_short = self._mutate_weight(genome.weight_ret_short)
        weight_ret_mid = self._mutate_weight(genome.weight_ret_mid)
        weight_dist_ma = self._mutate_weight(genome.weight_dist_ma)
        weight_range_pos = self._mutate_weight(genome.weight_range_pos)
        weight_vol_ratio = self._mutate_weight(genome.weight_vol_ratio)
        weight_trend_strength = self._mutate_weight(genome.weight_trend_strength)
        weight_realized_volatility = self._mutate_weight(
            genome.weight_realized_volatility
        )
        weight_trend_long = self._mutate_weight(genome.weight_trend_long)
        weight_breakout = self._mutate_weight(genome.weight_breakout)

        return Genome(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_score_margin=genome.entry_score_margin,
            min_bars_between_entries=genome.min_bars_between_entries,
            entry_confirmation_bars=genome.entry_confirmation_bars,
            policy_v2_enabled=genome.policy_v2_enabled,
            use_momentum=use_momentum,
            momentum_threshold=momentum_threshold,
            use_trend=use_trend,
            trend_threshold=trend_threshold,
            trend_window=trend_window,
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=exit_momentum_threshold,
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=ma_window,
            range_window=range_window,
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=weight_ret_short,
            weight_ret_mid=weight_ret_mid,
            weight_dist_ma=weight_dist_ma,
            weight_range_pos=weight_range_pos,
            weight_vol_ratio=weight_vol_ratio,
            weight_trend_strength=weight_trend_strength,
            weight_realized_volatility=weight_realized_volatility,
            weight_trend_long=weight_trend_long,
            weight_breakout=weight_breakout,
        )

    # =========================
    # STRONG MUTATION
    # =========================

    def _strong_mutate_legacy(self, genome: Genome) -> Genome:
        ret_short_window = self.random.randint(2, 10)
        ret_mid_window = self.random.randint(max(10, ret_short_window + 1), 50)
        vol_short_window = self.random.randint(2, 20)
        vol_long_window = self.random.randint(max(10, vol_short_window + 1), 100)

        return Genome(
            threshold_open=self.random.uniform(0.4, 1.0),
            threshold_close=self.random.uniform(0.0, 0.5),
            position_size=self.random.uniform(0.05, 1.0),
            stop_loss=self.random.uniform(0.01, 1.0),
            take_profit=self.random.uniform(0.01, 2.0),
            entry_score_margin=genome.entry_score_margin,
            min_bars_between_entries=genome.min_bars_between_entries,
            entry_confirmation_bars=genome.entry_confirmation_bars,
            policy_v2_enabled=genome.policy_v2_enabled,
            use_momentum=self.random.choice([True, False]),
            momentum_threshold=self.random.uniform(-0.01, 0.01),
            use_trend=self.random.choice([True, False]),
            trend_threshold=self.random.uniform(-0.01, 0.01),
            trend_window=self.random.randint(2, 50),
            use_exit_momentum=self.random.choice([True, False]),
            exit_momentum_threshold=self.random.uniform(-0.01, 0.01),
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self.random.randint(5, 100),
            range_window=self.random.randint(5, 50),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=self.random.uniform(-2, 2),
            weight_ret_mid=self.random.uniform(-2, 2),
            weight_dist_ma=self.random.uniform(-2, 2),
            weight_range_pos=self.random.uniform(-2, 2),
            weight_vol_ratio=self.random.uniform(-2, 2),
            weight_trend_strength=self.random.uniform(-2, 2),
            weight_realized_volatility=self.random.uniform(-2, 2),
            weight_trend_long=self.random.uniform(-2, 2),
            weight_breakout=self.random.uniform(-2, 2),
        )

    # =========================
    # HELPERS
    # =========================

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _scaled_delta(self, base_delta: float) -> float:
        delta = base_delta * self.profile.numeric_delta_scale
        return self.random.uniform(-delta, delta)

    def _mutate_weight(self, value: float) -> float:
        delta = self.profile.weight_delta
        return self._clamp(value + self.random.uniform(-delta, delta), -3.0, 3.0)

    def _mutate_window(self, value: int, min_value: int, max_value: int) -> int:
        step = self.random.choice(self.profile.window_choices())
        return int(self._clamp(value + step, min_value, max_value))
