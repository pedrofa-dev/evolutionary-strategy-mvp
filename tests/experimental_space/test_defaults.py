import pytest

from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    TradeControlGene,
)
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.experimental_space.base import EntryDecision, ExitDecision, SignalPack
from evo_system.experimental_space import (
    decision_policy_registry,
    get_decision_policy,
    genome_schema_registry,
    get_default_decision_policy,
    get_default_genome_schema,
    get_default_market_mode,
    get_default_mutation_profile_definition,
    get_default_signal_pack,
    get_genome_schema,
    get_market_mode,
    get_mutation_profile_definition,
    get_signal_pack,
    market_mode_registry,
    mutation_profile_registry,
    signal_pack_registry,
)
from evo_system.mutation.mutator import MutationProfile
from evo_system.orchestration.runner import EvolutionRunner


def _sample_environment() -> HistoricalEnvironment:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 111, 106, 110),
        HistoricalCandle("5", 110, 115, 109, 114),
        HistoricalCandle("6", 114, 118, 113, 117),
    ]
    return HistoricalEnvironment(candles)


def test_default_registries_expose_phase_one_components() -> None:
    assert signal_pack_registry.default_name == "policy_v21_default"
    assert genome_schema_registry.default_name == "policy_v2_default"
    assert decision_policy_registry.default_name == "policy_v2_default"
    assert mutation_profile_registry.default_name == "default_runtime_profile"
    assert market_mode_registry.default_name == "spot"
    assert "modular_genome_v1" in genome_schema_registry.list_names()


def test_component_registries_resolve_named_defaults_explicitly() -> None:
    assert get_signal_pack("policy_v21_default").name == "policy_v21_default"
    assert get_genome_schema("modular_genome_v1").name == "modular_genome_v1"
    assert get_decision_policy("policy_v2_default").name == "policy_v2_default"
    assert get_market_mode("spot").name == "spot"
    assert (
        get_mutation_profile_definition("default_runtime_profile").name
        == "default_runtime_profile"
    )


def test_default_signal_pack_matches_current_environment_methods() -> None:
    environment = _sample_environment()
    genome = EvolutionRunner(mutation_seed=42)._build_random_genome()
    trend_series = environment._get_trend_series(genome.trend_window)

    signal_pack = get_default_signal_pack()

    features = signal_pack.build_signal_features(
        environment=environment,
        index=5,
        normalized_momentum=environment._normalized_momentum_series[5],
        normalized_trend=trend_series[5],
        ret_short_series=environment._get_return_series(genome.ret_short_window),
        ret_mid_series=environment._get_return_series(genome.ret_mid_window),
        ma_distance_series=environment._get_ma_distance_series(genome.ma_window),
        range_position_series=environment._get_range_position_series(genome.range_window),
        vol_ratio_series=environment._get_vol_ratio_series(
            genome.vol_short_window,
            genome.vol_long_window,
        ),
        trend_strength_series=environment._get_trend_strength_series(genome.ma_window),
        realized_volatility_series=environment._get_realized_volatility_series(
            genome.vol_long_window
        ),
        trend_long_series=environment._get_trend_long_series(genome.ma_window),
        breakout_series=environment._get_breakout_series(genome.range_window),
    )
    direct_features = environment._get_policy_v21_signal_features(
        index=5,
        normalized_momentum=environment._normalized_momentum_series[5],
        normalized_trend=trend_series[5],
        ret_short_series=environment._get_return_series(genome.ret_short_window),
        ret_mid_series=environment._get_return_series(genome.ret_mid_window),
        ma_distance_series=environment._get_ma_distance_series(genome.ma_window),
        range_position_series=environment._get_range_position_series(genome.range_window),
        vol_ratio_series=environment._get_vol_ratio_series(
            genome.vol_short_window,
            genome.vol_long_window,
        ),
        trend_strength_series=environment._get_trend_strength_series(genome.ma_window),
        realized_volatility_series=environment._get_realized_volatility_series(
            genome.vol_long_window
        ),
        trend_long_series=environment._get_trend_long_series(genome.ma_window),
        breakout_series=environment._get_breakout_series(genome.range_window),
    )

    assert features == direct_features
    assert signal_pack.build_signal_families(
        environment=environment,
        signal_features=features,
    ) == environment._get_signal_families(signal_features=features)


def test_default_signal_pack_exposes_stable_feature_and_family_names() -> None:
    signal_pack = get_default_signal_pack()

    assert signal_pack.feature_names == (
        "trend_strength_medium",
        "trend_strength_long",
        "momentum_short",
        "momentum_persistence",
        "breakout_strength_medium",
        "range_position_medium",
        "realized_volatility_medium",
        "volatility_ratio_short_long",
    )
    assert signal_pack.family_names == (
        "trend",
        "momentum",
        "breakout",
        "range",
        "volatility",
        "realized_volatility",
    )


def test_historical_environment_routes_signal_methods_through_selected_signal_pack() -> None:
    class FakeSignalPack:
        name = "test_signal_pack"
        feature_names = ("fake_feature",)
        family_names = ("fake_family",)

        def build_signal_features(self, *, environment, **kwargs):
            return {"fake_feature": 0.25}

        def build_signal_families(self, *, environment, signal_features):
            return {"fake_family": signal_features["fake_feature"]}

    signal_pack_registry.register("test_signal_pack", FakeSignalPack())
    environment = _sample_environment()
    environment = HistoricalEnvironment(
        environment.candles,
        signal_pack_name="test_signal_pack",
    )

    assert environment._get_policy_v21_signal_features(
        index=1,
        normalized_momentum=0.0,
        normalized_trend=0.0,
        ret_short_series=[0.0, 0.0],
        ret_mid_series=[0.0, 0.0],
        ma_distance_series=[0.0, 0.0],
        range_position_series=[0.0, 0.0],
        vol_ratio_series=[0.0, 0.0],
        trend_strength_series=[0.0, 0.0],
        realized_volatility_series=[0.0, 0.0],
        trend_long_series=[0.0, 0.0],
        breakout_series=[0.0, 0.0],
    ) == {"fake_feature": 0.25}
    assert environment._get_signal_families(
        signal_features={"fake_feature": 0.25}
    ) == {"fake_family": 0.25}


def test_historical_environment_routes_decision_methods_through_selected_decision_policy() -> None:
    class FakeDecisionPolicy:
        name = "test_decision_policy"

        def get_entry_trigger_score(self, *, environment, genome, signal_families):
            return 0.75

        def passes_entry_context(self, *, environment, genome, signal_families):
            return True

        def passes_entry_trigger(
            self,
            *,
            environment,
            genome,
            signal_families,
            trigger_score,
        ):
            return trigger_score >= 0.75

        def should_enter(
            self,
            *,
            environment,
            genome,
            signal_families,
            trigger_score,
            regime_filter_ok,
        ):
            return regime_filter_ok and trigger_score >= 0.75

        def should_exit(
            self,
            *,
            environment,
            genome,
            signal_families,
            trigger_score,
            normalized_momentum,
            trade_return,
            holding_bars,
        ):
            return holding_bars >= 2

        def evaluate_entry(
            self,
            *,
            environment,
            genome,
            signal_families,
            regime_filter_ok,
        ):
            return EntryDecision(
                trigger_score=0.75,
                context_ok=True,
                trigger_ok=True,
                regime_filter_ok=regime_filter_ok,
                should_enter=regime_filter_ok,
            )

        def evaluate_exit(
            self,
            *,
            environment,
            genome,
            signal_families,
            normalized_momentum,
            trade_return,
            holding_bars,
        ):
            return ExitDecision(
                hit_stop_loss=False,
                hit_take_profit=False,
                should_close_by_score=False,
                should_close_on_reversal=False,
                should_close_on_holding_limit=holding_bars >= 2,
                should_close=holding_bars >= 2,
            )

    decision_policy_registry.register("test_decision_policy", FakeDecisionPolicy())
    environment = _sample_environment()
    environment = HistoricalEnvironment(
        environment.candles,
        decision_policy_name="test_decision_policy",
    )
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )
    families = {
        "trend": 0.0,
        "momentum": 0.0,
        "breakout": 0.0,
        "range": 0.0,
        "volatility": 0.0,
        "realized_volatility": 0.0,
    }

    assert environment._get_entry_trigger_score(genome, families) == 0.75
    assert environment._passes_entry_context(genome, families) is True
    assert environment._passes_entry_trigger(genome, families, 0.75) is True
    assert (
        environment._evaluate_policy_v2_entry(
            genome=genome,
            signal_families=families,
            regime_filter_ok=True,
        )
        == EntryDecision(
            trigger_score=0.75,
            context_ok=True,
            trigger_ok=True,
            regime_filter_ok=True,
            should_enter=True,
        )
    )
    assert (
        environment._evaluate_policy_v2_exit(
            genome=genome,
            signal_families=families,
            normalized_momentum=0.0,
            trade_return=0.0,
            holding_bars=2,
        )
        == ExitDecision(
            hit_stop_loss=False,
            hit_take_profit=False,
            should_close_by_score=False,
            should_close_on_reversal=False,
            should_close_on_holding_limit=True,
            should_close=True,
        )
    )


def test_default_decision_policy_matches_current_environment_methods() -> None:
    environment = _sample_environment()
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=1.0,
            momentum_weight=0.5,
            breakout_weight=0.25,
            range_weight=0.0,
            volatility_weight=-0.5,
            entry_score_threshold=0.2,
            min_positive_families=1,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=-0.1,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
        ),
        trade_control=TradeControlGene(),
    )
    families = {
        "trend": 0.6,
        "momentum": 0.4,
        "breakout": 0.5,
        "range": 0.1,
        "volatility": -0.2,
        "realized_volatility": 0.0,
    }
    decision_policy = get_default_decision_policy()

    score = decision_policy.get_entry_trigger_score(
        environment=environment,
        genome=genome,
        signal_families=families,
    )

    assert score == environment._get_entry_trigger_score(genome, families)
    assert decision_policy.passes_entry_context(
        environment=environment,
        genome=genome,
        signal_families=families,
    ) == environment._passes_entry_context(genome, families)
    assert decision_policy.passes_entry_trigger(
        environment=environment,
        genome=genome,
        signal_families=families,
        trigger_score=score,
    ) == environment._passes_entry_trigger(genome, families, score)


def test_default_mutation_profile_definition_preserves_current_runtime_profile() -> None:
    definition = get_default_mutation_profile_definition()
    custom_profile = MutationProfile(numeric_delta_scale=1.5)

    assert definition.resolve_runtime_profile(custom_profile) == custom_profile
    assert definition.resolve_runtime_profile(None) == MutationProfile()


def test_runner_and_environment_expose_default_modular_components() -> None:
    environment = _sample_environment()
    runner = EvolutionRunner(mutation_seed=42)

    assert environment.signal_pack.name == "policy_v21_default"
    assert environment.decision_policy.name == "policy_v2_default"
    assert environment.market_mode.name == "spot"
    assert runner.genome_schema.name == "policy_v2_default"
    assert runner.mutation_profile_definition.name == "default_runtime_profile"


def test_default_market_mode_preserves_current_runtime_mode() -> None:
    market_mode = get_default_market_mode()

    assert market_mode.name == "spot"
    assert market_mode.flat_position == "flat"
    assert market_mode.get_default_entry_position() == "long"
    assert market_mode.can_transition("flat", "long") is True
    assert market_mode.can_transition("long", "flat") is True
    assert market_mode.can_transition("flat", "short") is False


def test_futures_market_mode_supports_long_and_short_with_v1_leverage_only() -> None:
    market_mode = get_market_mode("futures")

    market_mode.validate_runtime_config(leverage=1.0)

    assert market_mode.can_transition("flat", "long") is True
    assert market_mode.can_transition("flat", "short") is True
    assert market_mode.can_transition("short", "flat") is True
    assert market_mode.calculate_trade_return(
        entry_price=100.0,
        current_price=90.0,
        position="short",
    ) == 0.1
    assert market_mode.calculate_trade_return(
        entry_price=100.0,
        current_price=110.0,
        position="short",
    ) == -0.1
    net_profit, trade_cost = market_mode.close_trade(
        trade_return=0.1,
        position_size=1.0,
        trade_cost_rate=0.01,
        position="short",
        leverage=1.0,
    )
    assert net_profit == pytest.approx(0.09)
    assert trade_cost == pytest.approx(0.01)

    with pytest.raises(ValueError, match="supports leverage=1.0 only"):
        market_mode.validate_runtime_config(leverage=2.0)


def test_spot_market_mode_rejects_short_and_non_unit_leverage() -> None:
    market_mode = get_market_mode("spot")

    assert market_mode.can_transition("flat", "short") is False
    assert market_mode.calculate_trade_return(
        entry_price=100.0,
        current_price=110.0,
        position="long",
    ) == 0.1
    net_profit, trade_cost = market_mode.close_trade(
        trade_return=0.1,
        position_size=1.0,
        trade_cost_rate=0.01,
        position="long",
        leverage=1.0,
    )
    assert net_profit == pytest.approx(0.09)
    assert trade_cost == pytest.approx(0.01)

    with pytest.raises(ValueError, match="supports leverage=1.0 only"):
        market_mode.validate_runtime_config(leverage=2.0)

    with pytest.raises(ValueError, match="spot does not support short positions"):
        market_mode.calculate_trade_return(
            entry_price=100.0,
            current_price=90.0,
            position="short",
        )


def test_default_genome_schema_builds_active_policy_v2_genomes() -> None:
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )

    assert genome.policy_v2_enabled is True


def test_genome_schema_exposes_gene_type_catalog() -> None:
    schema = get_genome_schema("modular_genome_v1")
    catalog = schema.get_gene_type_catalog()

    assert catalog.name == "modular_genome_v1_gene_catalog"
    assert catalog.list_gene_type_names() == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]
    assert schema.get_module_names() == (
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    )
    assert schema.get_module_names() == schema.get_module_names()


def test_modular_genome_schema_v1_builds_explicit_gene_blocks() -> None:
    schema = get_genome_schema("modular_genome_v1")

    genome = schema.build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )

    assert genome.policy_v2_enabled is True
    assert isinstance(genome.entry_context, EntryContextGene)
    assert isinstance(genome.entry_trigger, EntryTriggerGene)
    assert isinstance(genome.exit_policy, ExitPolicyGene)
    assert isinstance(genome.trade_control, TradeControlGene)


def test_modular_genome_schema_v1_builds_default_modules_explicitly() -> None:
    schema = get_genome_schema("modular_genome_v1")

    assert isinstance(schema.build_default_module("entry_context"), EntryContextGene)
    assert isinstance(schema.build_default_module("entry_trigger"), EntryTriggerGene)
    assert isinstance(schema.build_default_module("exit_policy"), ExitPolicyGene)
    assert isinstance(schema.build_default_module("trade_control"), TradeControlGene)


def test_runner_can_select_modular_genome_schema_v1_explicitly() -> None:
    runner = EvolutionRunner(
        mutation_seed=42,
        genome_schema_name="modular_genome_v1",
    )

    genome = runner._build_random_genome()

    assert runner.genome_schema.name == "modular_genome_v1"
    assert genome.policy_v2_enabled is True
    assert isinstance(genome.entry_context, EntryContextGene)
    assert isinstance(genome.entry_trigger, EntryTriggerGene)
    assert isinstance(genome.exit_policy, ExitPolicyGene)
    assert isinstance(genome.trade_control, TradeControlGene)


def test_default_decision_policy_should_enter_matches_current_policy_v2_logic() -> None:
    environment = _sample_environment()
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=1.0,
            momentum_weight=0.5,
            breakout_weight=0.25,
            range_weight=0.0,
            volatility_weight=-0.5,
            entry_score_threshold=0.2,
            min_positive_families=1,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=-0.1,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
        ),
        trade_control=TradeControlGene(),
    )
    families = {
        "trend": 0.6,
        "momentum": 0.4,
        "breakout": 0.5,
        "range": 0.1,
        "volatility": -0.2,
        "realized_volatility": 0.0,
    }
    decision_policy = get_default_decision_policy()
    score = decision_policy.get_entry_trigger_score(
        environment=environment,
        genome=genome,
        signal_families=families,
    )

    assert decision_policy.should_enter(
        environment=environment,
        genome=genome,
        signal_families=families,
        trigger_score=score,
        regime_filter_ok=True,
    ) == environment._should_enter_policy_v2(
        genome=genome,
        signal_families=families,
        trigger_score=score,
        regime_filter_ok=True,
    )


def test_default_decision_policy_evaluate_entry_matches_current_policy_v2_logic() -> None:
    environment = _sample_environment()
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=1.0,
            momentum_weight=0.5,
            breakout_weight=0.25,
            range_weight=0.0,
            volatility_weight=-0.5,
            entry_score_threshold=0.2,
            min_positive_families=1,
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=-0.1,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
        ),
        trade_control=TradeControlGene(),
    )
    families = {
        "trend": 0.6,
        "momentum": 0.4,
        "breakout": 0.5,
        "range": 0.1,
        "volatility": -0.2,
        "realized_volatility": 0.0,
    }
    decision_policy = get_default_decision_policy()

    assert decision_policy.evaluate_entry(
        environment=environment,
        genome=genome,
        signal_families=families,
        regime_filter_ok=True,
    ) == environment._evaluate_policy_v2_entry(
        genome=genome,
        signal_families=families,
        regime_filter_ok=True,
    )


def test_default_decision_policy_should_exit_matches_current_policy_v2_logic() -> None:
    environment = _sample_environment()
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        exit_policy=ExitPolicyGene(
            exit_score_threshold=0.1,
            exit_on_signal_reversal=True,
            max_holding_bars=24,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
        ),
        trade_control=TradeControlGene(min_holding_bars=1),
    )
    families = {
        "trend": -0.2,
        "momentum": -0.1,
        "breakout": 0.0,
        "range": 0.0,
        "volatility": 0.0,
        "realized_volatility": 0.0,
    }
    decision_policy = get_default_decision_policy()

    assert decision_policy.should_exit(
        environment=environment,
        genome=genome,
        signal_families=families,
        trigger_score=-0.1,
        normalized_momentum=-0.2,
        trade_return=0.0,
        holding_bars=2,
    ) == environment._should_exit_policy_v2(
        genome=genome,
        signal_families=families,
        trigger_score=-0.1,
        normalized_momentum=-0.2,
        trade_return=0.0,
        holding_bars=2,
    )


def test_default_decision_policy_evaluate_exit_matches_current_policy_v2_logic() -> None:
    environment = _sample_environment()
    genome = get_default_genome_schema().build_genome(
        position_size=0.5,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        exit_policy=ExitPolicyGene(
            exit_score_threshold=0.1,
            exit_on_signal_reversal=True,
            max_holding_bars=24,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
        ),
        trade_control=TradeControlGene(min_holding_bars=1),
    )
    families = {
        "trend": -0.2,
        "momentum": -0.1,
        "breakout": 0.0,
        "range": 0.0,
        "volatility": 0.0,
        "realized_volatility": 0.0,
    }
    decision_policy = get_default_decision_policy()

    assert decision_policy.evaluate_exit(
        environment=environment,
        genome=genome,
        signal_families=families,
        normalized_momentum=-0.2,
        trade_return=0.0,
        holding_bars=2,
    ) == environment._evaluate_policy_v2_exit(
        genome=genome,
        signal_families=families,
        normalized_momentum=-0.2,
        trade_return=0.0,
        holding_bars=2,
    )
