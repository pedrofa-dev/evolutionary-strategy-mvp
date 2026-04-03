from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
    build_policy_v2_genome,
)
from evo_system.experimental_space.gene_catalog import (
    MODULAR_GENOME_V1_GENE_TYPE_CATALOG,
)
from evo_system.experimental_space.defaults import get_genome_schema
from evo_system.mutation.mutator import MutationProfile, Mutator


def test_mutator_uses_default_mutation_profile_when_not_provided() -> None:
    mutator = Mutator(seed=42)

    assert mutator.profile == MutationProfile()


def test_mutator_accepts_custom_mutation_profile() -> None:
    profile = MutationProfile(
        strong_mutation_probability=0.25,
        numeric_delta_scale=1.5,
        flag_flip_probability=0.10,
        weight_delta=0.35,
        window_step_mode="wide",
    )

    mutator = Mutator(seed=42, profile=profile)

    assert mutator.profile == profile


def test_mutate_returns_new_genome() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator = Mutator(seed=42)

    mutated = mutator.mutate(genome)

    assert mutated is not genome
    assert isinstance(mutated, Genome)


def test_mutate_is_reproducible_with_same_seed() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator1 = Mutator(seed=42)
    mutator2 = Mutator(seed=42)

    mutated1 = mutator1.mutate(genome)
    mutated2 = mutator2.mutate(genome)

    assert mutated1 == mutated2


def test_mutate_preserves_valid_ranges() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator = Mutator(seed=42)

    mutated = mutator.mutate(genome)

    mutated.validate()


def test_mutate_preserves_threshold_order() -> None:
    genome = Genome(
        threshold_open=0.6,
        threshold_close=0.2,
        position_size=0.1,
        stop_loss=0.03,
        take_profit=0.08,
    )

    mutator = Mutator(seed=1)

    mutated = mutator.mutate(genome)

    assert mutated.threshold_close <= mutated.threshold_open


def test_mutate_can_produce_valid_mutations_repeatedly() -> None:
    genome = Genome(
        threshold_open=0.7,
        threshold_close=0.3,
        position_size=0.15,
        stop_loss=0.03,
        take_profit=0.09,
        use_trend=True,
        trend_threshold=0.0006,
        trend_window=4,
        use_exit_momentum=True,
        exit_momentum_threshold=-0.0008,
    )

    mutator = Mutator(seed=123)

    for _ in range(50):
        mutated = mutator.mutate(genome)
        mutated.validate()


def test_mutate_updates_new_feature_weights_with_small_mutation() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
        weight_trend_strength=0.2,
        weight_realized_volatility=-0.3,
        weight_trend_long=0.4,
        weight_breakout=-0.2,
    )

    profile = MutationProfile(strong_mutation_probability=0.0)
    mutator = Mutator(seed=42, profile=profile)

    mutated = mutator.mutate(genome)

    assert mutated.weight_trend_strength != genome.weight_trend_strength
    assert mutated.weight_realized_volatility != genome.weight_realized_volatility
    assert mutated.weight_trend_long != genome.weight_trend_long
    assert mutated.weight_breakout != genome.weight_breakout


def test_strong_mutate_sets_new_feature_weights_in_valid_range() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    profile = MutationProfile(strong_mutation_probability=1.0)
    mutator = Mutator(seed=7, profile=profile)

    mutated = mutator.mutate(genome)

    assert -2.0 <= mutated.weight_trend_strength <= 2.0
    assert -2.0 <= mutated.weight_realized_volatility <= 2.0
    assert -2.0 <= mutated.weight_trend_long <= 2.0
    assert -2.0 <= mutated.weight_breakout <= 2.0


def test_mutate_policy_v2_preserves_v2_blocks_without_legacy_threshold_dependency() -> None:
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=0.8,
            momentum_weight=0.6,
            breakout_weight=0.4,
            range_weight=0.1,
            volatility_weight=-0.2,
            entry_score_threshold=0.45,
            min_positive_families=2,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=0.05,
            exit_on_signal_reversal=True,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
        ),
        trade_control=TradeControlGene(
            cooldown_bars=0,
            min_holding_bars=1,
            reentry_block_bars=0,
        ),
    )

    mutator = Mutator(seed=42, profile=MutationProfile(strong_mutation_probability=0.0))

    mutated = mutator.mutate(genome)

    assert mutated.policy_v2_enabled is True
    assert mutated.entry_trigger is not None
    assert mutated.exit_policy is not None
    assert mutated.trade_control is not None
    assert mutated.threshold_open == 0.0
    assert mutated.threshold_close == 0.0


def test_mutator_respects_entry_trigger_weight_constraints_for_policy_v2() -> None:
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        entry_trigger=EntryTriggerGene(
            trend_weight=-0.8,
            momentum_weight=0.2,
            breakout_weight=-0.6,
            range_weight=0.1,
            volatility_weight=0.0,
            entry_score_threshold=0.43,
            min_positive_families=1,
            require_trend_or_breakout=False,
        ),
    )

    mutator = Mutator(
        seed=42,
        profile=MutationProfile(strong_mutation_probability=1.0),
        entry_trigger_constraints={
            "min_trend_weight": 0.0,
            "min_breakout_weight": 0.0,
        },
    )

    mutated = mutator.mutate(genome)

    assert mutated.entry_trigger is not None
    assert mutated.entry_trigger.trend_weight >= 0.0
    assert mutated.entry_trigger.breakout_weight >= 0.0


def test_mutator_uses_modular_gene_catalog_by_default_for_policy_v2() -> None:
    mutator = Mutator(seed=42)

    assert mutator.gene_type_catalog == MODULAR_GENOME_V1_GENE_TYPE_CATALOG
    assert mutator.gene_type_catalog.list_gene_type_names() == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]


def test_mutator_uses_schema_catalog_and_module_order_deterministically() -> None:
    schema = get_genome_schema("modular_genome_v1")
    mutator = Mutator(seed=42, genome_schema=schema)

    assert mutator.gene_type_catalog == schema.get_gene_type_catalog()
    assert mutator.modular_engine._get_module_names() == schema.get_module_names()


def test_mutate_policy_v2_is_reproducible_with_same_seed() -> None:
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=0.8,
            momentum_weight=0.6,
            breakout_weight=0.4,
            range_weight=0.1,
            volatility_weight=-0.2,
            entry_score_threshold=0.45,
            min_positive_families=2,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=0.05,
            exit_on_signal_reversal=True,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
        ),
        trade_control=TradeControlGene(
            cooldown_bars=1,
            min_holding_bars=2,
            reentry_block_bars=1,
        ),
    )

    mutator1 = Mutator(seed=42, profile=MutationProfile(strong_mutation_probability=0.0))
    mutator2 = Mutator(seed=42, profile=MutationProfile(strong_mutation_probability=0.0))

    assert mutator1.mutate(genome) == mutator2.mutate(genome)


def test_mutate_policy_v2_strong_is_reproducible_with_same_seed() -> None:
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=0.8,
            momentum_weight=0.6,
            breakout_weight=0.4,
            range_weight=0.1,
            volatility_weight=-0.2,
            entry_score_threshold=0.45,
            min_positive_families=2,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=0.05,
            exit_on_signal_reversal=True,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
        ),
        trade_control=TradeControlGene(
            cooldown_bars=1,
            min_holding_bars=2,
            reentry_block_bars=1,
        ),
    )

    profile = MutationProfile(strong_mutation_probability=1.0)
    mutator1 = Mutator(seed=42, profile=profile)
    mutator2 = Mutator(seed=42, profile=profile)

    assert mutator1.mutate(genome) == mutator2.mutate(genome)


def test_modular_engine_can_mutate_target_gene_module_with_constraints() -> None:
    mutator = Mutator(
        seed=42,
        profile=MutationProfile(strong_mutation_probability=0.0),
        entry_trigger_constraints={
            "min_trend_weight": 0.0,
            "min_breakout_weight": 0.0,
        },
    )

    mutated_module = mutator.modular_engine.mutate_module_small(
        "entry_trigger",
        EntryTriggerGene(
            trend_weight=-0.8,
            momentum_weight=0.2,
            breakout_weight=-0.6,
            range_weight=0.1,
            volatility_weight=0.0,
            entry_score_threshold=0.43,
            min_positive_families=1,
            require_trend_or_breakout=False,
        ),
    )

    assert isinstance(mutated_module, EntryTriggerGene)
    assert mutated_module.trend_weight >= 0.0
    assert mutated_module.breakout_weight >= 0.0


def test_modular_engine_can_rebuild_module_from_catalog_metadata() -> None:
    mutator = Mutator(seed=42)

    rebuilt_module = mutator.modular_engine.rebuild_module(
        "exit_policy",
        {
            "exit_score_threshold": 0.05,
            "exit_on_signal_reversal": True,
            "max_holding_bars": 24,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
        },
    )

    assert rebuilt_module == ExitPolicyGene(
        exit_score_threshold=0.05,
        exit_on_signal_reversal=True,
        max_holding_bars=24,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )


def test_modular_engine_can_build_default_module_from_catalog_metadata() -> None:
    mutator = Mutator(seed=42)

    rebuilt_module = mutator.modular_engine.rebuild_module("entry_trigger", {})

    assert rebuilt_module == EntryTriggerGene()


def test_modular_engine_normalizes_schema_field_order_constraints() -> None:
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        ret_short_window=9,
        ret_mid_window=10,
        vol_short_window=19,
        vol_long_window=20,
    )
    mutator = Mutator(seed=42, profile=MutationProfile(strong_mutation_probability=0.0))

    mutated = mutator.mutate(genome)

    assert mutated.ret_short_window < mutated.ret_mid_window
    assert mutated.vol_short_window < mutated.vol_long_window


def test_strong_policy_v2_mutation_is_deterministic_with_schema_selected() -> None:
    schema = get_genome_schema("modular_genome_v1")
    genome = build_policy_v2_genome(
        position_size=0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(),
        exit_policy=ExitPolicyGene(),
        trade_control=TradeControlGene(),
    )
    profile = MutationProfile(strong_mutation_probability=1.0)

    mutator_a = Mutator(seed=99, profile=profile, genome_schema=schema)
    mutator_b = Mutator(seed=99, profile=profile, genome_schema=schema)

    assert mutator_a.mutate(genome) == mutator_b.mutate(genome)
