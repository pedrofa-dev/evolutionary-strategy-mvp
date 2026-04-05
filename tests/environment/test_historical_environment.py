from evo_system.domain.agent import Agent
from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
)
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.environment.historical_environment import HistoricalEnvironment


def _agent(**changes: float | int | bool) -> Agent:
    genome_kwargs: dict[str, float | int | bool] = {
        "threshold_open": 0.1,
        "threshold_close": 0.0,
        "position_size": 1.0,
        "stop_loss": 0.5,
        "take_profit": 1.0,
        "ret_short_window": 1,
        "ret_mid_window": 2,
        "ma_window": 3,
        "range_window": 3,
        "vol_short_window": 2,
        "vol_long_window": 3,
    }
    genome_kwargs.update(changes)
    genome = Genome(**genome_kwargs)
    return Agent.create(genome)


def test_historical_environment_returns_drawdown_in_episode_result() -> None:
    candles = [
        HistoricalCandle("1", 100, 110, 100, 110),
        HistoricalCandle("2", 110, 110, 90, 95),
        HistoricalCandle("3", 95, 100, 90, 100),
        HistoricalCandle("4", 100, 120, 100, 120),
        HistoricalCandle("5", 120, 120, 80, 85),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(_agent(weight_ret_short=1.0))

    assert isinstance(result.drawdown, float)
    assert result.drawdown >= 0.0


def test_historical_environment_entry_depends_on_weighted_local_features_not_normalized_price() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    zero_weight_result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
        )
    )
    weighted_result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            weight_ret_short=1.0,
        )
    )

    assert zero_weight_result.trades == 0
    assert weighted_result.trades == 1


def test_historical_environment_regime_filter_acts_as_setup_gate() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment_without_filter = HistoricalEnvironment(candles)
    environment_with_filter = HistoricalEnvironment(
        candles,
        regime_filter_enabled=True,
        min_trend_long_for_entry=0.9,
        min_breakout_for_entry=0.9,
    )

    agent = _agent(
        threshold_open=0.1,
        threshold_close=-1.0,
        weight_ret_short=1.0,
    )

    result_without_filter = environment_without_filter.run_episode(agent)
    result_with_filter = environment_with_filter.run_episode(agent)

    assert result_without_filter.trades == 1
    assert result_with_filter.trades == 0


def test_historical_environment_opens_only_when_setup_is_valid_and_trigger_score_exceeds_threshold() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    valid_result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            weight_ret_short=1.0,
            use_momentum=True,
            momentum_threshold=0.05,
        )
    )
    blocked_by_setup_result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            weight_ret_short=1.0,
            use_momentum=True,
            momentum_threshold=0.2,
        )
    )
    blocked_by_threshold_result = environment.run_episode(
        _agent(
            threshold_open=1.1,
            threshold_close=-1.0,
            weight_ret_short=1.0,
        )
    )

    assert valid_result.trades == 1
    assert blocked_by_setup_result.trades == 0
    assert blocked_by_threshold_result.trades == 0


def test_historical_environment_closes_when_trigger_score_falls_below_close_threshold() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
        HistoricalCandle("4", 108, 107, 107, 107),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-0.1,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1
    assert result.profit == (108 - 110) / 110


def test_historical_environment_stop_loss_still_works() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 90, 90, 90),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            stop_loss=0.05,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1
    assert result.profit == (90 - 110) / 110


def test_historical_environment_take_profit_still_works() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 125, 110, 125),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            take_profit=0.1,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1
    assert result.profit == (125 - 110) / 110


def test_historical_environment_exit_momentum_still_works() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            weight_ret_short=1.0,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.01,
        )
    )

    assert result.trades == 1
    assert result.profit == (108 - 110) / 110


def test_historical_environment_uses_expanded_feature_weights_without_breaking_execution() -> None:
    candles = [
        HistoricalCandle("1", 100, 101, 99, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 110, 105, 106),
        HistoricalCandle("5", 106, 112, 105, 111),
        HistoricalCandle("6", 111, 115, 109, 114),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.02,
            threshold_close=-1.0,
            ma_window=4,
            vol_long_window=4,
            weight_trend_strength=1.0,
            weight_realized_volatility=1.0,
            weight_trend_long=1.0,
            weight_breakout=1.0,
        )
    )

    assert result.trades >= 0
    assert isinstance(result.profit, float)


def test_historical_environment_uses_explicit_zero_weight_fallback() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 105, 100, 105),
    ]

    environment = HistoricalEnvironment(candles)

    no_open_result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=0.0,
        )
    )
    neutral_threshold_result = environment.run_episode(
        _agent(
            threshold_open=0.0,
            threshold_close=0.0,
        )
    )

    assert no_open_result.trades == 0
    assert neutral_threshold_result.trades == 1


def test_historical_environment_applies_trade_cost_to_closed_trade() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 125, 110, 125),
    ]

    environment_without_cost = HistoricalEnvironment(candles, trade_cost_rate=0.0)
    environment_with_cost = HistoricalEnvironment(candles, trade_cost_rate=0.01)

    agent = _agent(
        threshold_open=0.1,
        threshold_close=-1.0,
        position_size=1.0,
        take_profit=0.1,
        weight_ret_short=1.0,
    )

    result_without_cost = environment_without_cost.run_episode(agent)
    result_with_cost = environment_with_cost.run_episode(agent)

    assert result_without_cost.trades == 1
    assert result_with_cost.trades == 1
    assert result_without_cost.profit == (125 - 110) / 110
    assert result_with_cost.profit == ((125 - 110) / 110) - 0.01
    assert result_without_cost.cost == 0.0
    assert result_with_cost.cost == 0.01


def test_historical_environment_applies_trade_cost_on_forced_final_close() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles, trade_cost_rate=0.01)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            position_size=1.0,
            take_profit=1.0,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1
    assert result.profit == ((120 - 110) / 110) - 0.01
    assert result.cost == 0.01


def test_historical_environment_cooldown_zero_keeps_existing_reentry_behavior() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
        HistoricalCandle("4", 108, 120, 108, 120),
        HistoricalCandle("5", 120, 118, 118, 118),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-0.1,
            min_bars_between_entries=0,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 2


def test_historical_environment_entry_confirmation_one_matches_current_behavior() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            entry_confirmation_bars=1,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1


def test_historical_environment_entry_score_margin_zero_matches_current_behavior() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            entry_score_margin=0.0,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1


def test_historical_environment_entry_score_margin_blocks_when_margin_is_not_met() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 105, 100, 105),
        HistoricalCandle("3", 105, 104, 104, 104),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.04,
            threshold_close=-1.0,
            entry_score_margin=0.5,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 0


def test_historical_environment_entry_score_margin_allows_entry_when_margin_is_met() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 107, 100, 107),
        HistoricalCandle("3", 107, 110, 107, 110),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.04,
            threshold_close=-1.0,
            entry_score_margin=0.02,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1


def test_historical_environment_requires_two_consecutive_bars_before_entry() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
        HistoricalCandle("4", 108, 107, 107, 107),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            entry_confirmation_bars=2,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 0


def test_historical_environment_requires_three_consecutive_bars_before_entry() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
        HistoricalCandle("4", 120, 130, 120, 130),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-1.0,
            entry_confirmation_bars=3,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1


def test_historical_environment_blocks_immediate_reentry_when_cooldown_is_active() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
        HistoricalCandle("4", 108, 120, 108, 120),
        HistoricalCandle("5", 120, 118, 118, 118),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-0.1,
            min_bars_between_entries=1,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 1


def test_historical_environment_allows_reentry_after_required_bars() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 108, 108, 108),
        HistoricalCandle("4", 108, 107, 107, 107),
        HistoricalCandle("5", 107, 120, 107, 120),
        HistoricalCandle("6", 120, 118, 118, 118),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=0.1,
            threshold_close=-0.1,
            min_bars_between_entries=1,
            weight_ret_short=1.0,
        )
    )

    assert result.trades == 2


def test_historical_environment_policy_v2_opens_when_context_and_trigger_pass() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            policy_v2_enabled=True,
            entry_context=EntryContextGene(min_trend_strength=-1.0),
            entry_trigger=EntryTriggerGene(
                momentum_weight=1.0,
                entry_score_threshold=0.2,
                min_positive_families=1,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=-1.0,
                stop_loss_pct=0.5,
                take_profit_pct=1.0,
            ),
            trade_control=TradeControlGene(),
        )
    )

    assert result.trades == 1


def test_historical_environment_policy_v2_closes_on_max_holding_bars() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            policy_v2_enabled=True,
            entry_context=EntryContextGene(),
            entry_trigger=EntryTriggerGene(
                momentum_weight=1.0,
                entry_score_threshold=0.2,
                min_positive_families=1,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=-1.0,
                max_holding_bars=1,
                stop_loss_pct=0.5,
                take_profit_pct=1.0,
            ),
            trade_control=TradeControlGene(),
        )
    )

    assert result.trades == 1
    assert result.profit == (120 - 110) / 110


def test_historical_environment_exposes_policy_v21_signal_features_consistently() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 111, 106, 110),
        HistoricalCandle("5", 110, 115, 109, 114),
        HistoricalCandle("6", 114, 118, 113, 117),
    ]

    environment = HistoricalEnvironment(candles)
    genome = _agent(
        policy_v2_enabled=True,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=1.0,
            momentum_weight=1.0,
            breakout_weight=1.0,
            range_weight=1.0,
            volatility_weight=-1.0,
            entry_score_threshold=0.2,
            min_positive_families=1,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=-1.0,
            stop_loss_pct=0.5,
            take_profit_pct=1.0,
        ),
        trade_control=TradeControlGene(),
    ).genome

    trend_series = environment._get_trend_series(genome.trend_window)
    features = environment._get_policy_v21_signal_features(
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

    assert set(features) == {
        "trend_strength_medium",
        "trend_strength_long",
        "momentum_short",
        "momentum_persistence",
        "breakout_strength_medium",
        "range_position_medium",
        "realized_volatility_medium",
        "volatility_ratio_short_long",
    }
    assert features["trend_strength_medium"] > 0.0
    assert features["trend_strength_long"] > 0.0
    assert features["momentum_short"] > 0.0
    assert features["momentum_persistence"] > 0.0


def test_historical_environment_policy_v21_runtime_is_not_blocked_by_legacy_thresholds() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 110, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    result = environment.run_episode(
        _agent(
            threshold_open=5.0,
            threshold_close=5.0,
            policy_v2_enabled=True,
            entry_context=EntryContextGene(),
            entry_trigger=EntryTriggerGene(
                momentum_weight=1.0,
                entry_score_threshold=0.2,
                min_positive_families=1,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=-1.0,
                stop_loss_pct=0.5,
                take_profit_pct=1.0,
            ),
            trade_control=TradeControlGene(),
        )
    )

    assert result.trades == 1


def test_historical_environment_explicit_default_signal_pack_preserves_results() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 111, 106, 110),
        HistoricalCandle("5", 110, 115, 109, 114),
        HistoricalCandle("6", 114, 118, 113, 117),
    ]
    agent = _agent(
        policy_v2_enabled=True,
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

    default_environment = HistoricalEnvironment(candles)
    explicit_environment = HistoricalEnvironment(
        candles,
        signal_pack_name="policy_v21_default",
    )

    assert default_environment.get_episode_diagnostics(agent) == explicit_environment.get_episode_diagnostics(agent)


def test_historical_environment_explicit_default_decision_policy_preserves_results() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 111, 106, 110),
        HistoricalCandle("5", 110, 115, 109, 114),
        HistoricalCandle("6", 114, 118, 113, 117),
    ]
    agent = _agent(
        policy_v2_enabled=True,
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

    default_environment = HistoricalEnvironment(candles)
    explicit_environment = HistoricalEnvironment(
        candles,
        decision_policy_name="policy_v2_default",
    )

    assert default_environment.get_episode_diagnostics(agent) == explicit_environment.get_episode_diagnostics(agent)


def test_historical_environment_explicit_spot_market_mode_preserves_results() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 111, 106, 110),
        HistoricalCandle("5", 110, 115, 109, 114),
        HistoricalCandle("6", 114, 118, 113, 117),
    ]
    agent = _agent(
        policy_v2_enabled=True,
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

    default_environment = HistoricalEnvironment(candles)
    explicit_environment = HistoricalEnvironment(
        candles,
        market_mode_name="spot",
        leverage=1.0,
    )

    assert default_environment.get_episode_diagnostics(agent) == explicit_environment.get_episode_diagnostics(agent)


def test_historical_environment_accepts_futures_mode_with_unit_leverage() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
    ]

    environment = HistoricalEnvironment(
        candles,
        market_mode_name="futures",
        leverage=1.0,
    )

    assert environment.market_mode.name == "futures"
    assert environment.leverage == 1.0


def test_historical_environment_rejects_non_unit_futures_leverage_in_v1() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
    ]

    try:
        HistoricalEnvironment(
            candles,
            market_mode_name="futures",
            leverage=2.0,
        )
    except ValueError as exc:
        assert "supports leverage=1.0 only" in str(exc)
    else:
        raise AssertionError("Expected futures leverage validation to fail.")
