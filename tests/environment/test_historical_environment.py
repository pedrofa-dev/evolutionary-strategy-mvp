from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.environment.historical_environment import HistoricalEnvironment


def test_historical_environment_returns_drawdown_in_episode_result() -> None:
    candles = [
        HistoricalCandle("1", 100, 110, 100, 110),
        HistoricalCandle("2", 110, 110, 90, 95),
        HistoricalCandle("3", 95, 100, 90, 100),
        HistoricalCandle("4", 100, 120, 100, 120),
        HistoricalCandle("5", 120, 120, 80, 85),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.2,
            threshold_close=0.1,
            position_size=0.1,
            stop_loss=0.2,
            take_profit=0.1,
        )
    )

    result = environment.run_episode(agent)

    assert isinstance(result.drawdown, float)
    assert result.drawdown >= 0.0


def test_historical_environment_keeps_backward_compatibility_when_momentum_is_disabled() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 110),
        HistoricalCandle("3", 110, 110, 110, 120),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            use_momentum=False,
            momentum_threshold=0.5,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades == 1


def test_historical_environment_filters_entries_when_momentum_is_enabled() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 110),
        HistoricalCandle("3", 110, 110, 110, 111),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            use_momentum=True,
            momentum_threshold=0.2,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades == 0


def test_historical_environment_exit_momentum_does_not_break_legacy_behavior_when_disabled() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 110),
        HistoricalCandle("3", 110, 110, 100, 101),
        HistoricalCandle("4", 101, 101, 100, 100),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            use_exit_momentum=False,
            exit_momentum_threshold=-0.001,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades == 1


def test_historical_environment_can_exit_on_negative_momentum() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 110),
        HistoricalCandle("3", 110, 110, 100, 101),
        HistoricalCandle("4", 101, 101, 90, 95),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.05,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades == 1
    assert isinstance(result.profit, float)


def test_historical_environment_uses_feature_weights_when_present() -> None:
    candles = [
        HistoricalCandle("1", 100, 101, 99, 100),
        HistoricalCandle("2", 100, 103, 99, 102),
        HistoricalCandle("3", 102, 106, 101, 105),
        HistoricalCandle("4", 105, 110, 104, 109),
        HistoricalCandle("5", 109, 113, 108, 112),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.15,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            weight_ret_short=1.0,
            weight_ret_mid=1.0,
            weight_dist_ma=0.5,
            weight_range_pos=0.2,
            ret_short_window=1,
            ret_mid_window=2,
            ma_window=3,
            range_window=3,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades >= 1


def test_historical_environment_keeps_legacy_behavior_when_feature_weights_are_zero() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 105),
        HistoricalCandle("3", 105, 105, 105, 106),
    ]

    environment = HistoricalEnvironment(candles)

    legacy_agent = Agent.create(
        Genome(
            threshold_open=0.05,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        )
    )

    feature_agent = Agent.create(
        Genome(
            threshold_open=0.05,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            weight_ret_short=0.0,
            weight_ret_mid=0.0,
            weight_dist_ma=0.0,
            weight_range_pos=0.0,
            weight_vol_ratio=0.0,
        )
    )

    legacy_result = environment.run_episode(legacy_agent)
    feature_result = environment.run_episode(feature_agent)

    assert legacy_result.trades == feature_result.trades
    assert legacy_result.profit == feature_result.profit
    assert legacy_result.drawdown == feature_result.drawdown


def test_historical_environment_applies_trade_cost_to_closed_trade() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 120),
        HistoricalCandle("3", 120, 140, 120, 140),
    ]

    environment_without_cost = HistoricalEnvironment(candles, trade_cost_rate=0.0)
    environment_with_cost = HistoricalEnvironment(candles, trade_cost_rate=0.01)

    agent = Agent.create(
        Genome(
            threshold_open=0.1,
            threshold_close=0.0,
            position_size=1.0,
            stop_loss=0.5,
            take_profit=0.1,
        )
    )

    result_without_cost = environment_without_cost.run_episode(agent)
    result_with_cost = environment_with_cost.run_episode(agent)

    assert result_without_cost.trades == 1
    assert result_with_cost.trades == 1
    assert result_without_cost.profit == 20 / 120
    assert result_with_cost.profit == (20 / 120) - 0.01
    assert result_without_cost.cost == 0.0
    assert result_with_cost.cost == 0.01


def test_historical_environment_applies_trade_cost_on_forced_final_close() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 110),
        HistoricalCandle("3", 110, 120, 110, 120),
    ]

    environment = HistoricalEnvironment(candles, trade_cost_rate=0.01)

    agent = Agent.create(
        Genome(
            threshold_open=0.05,
            threshold_close=-1.0,
            position_size=1.0,
            stop_loss=0.5,
            take_profit=1.0,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades == 1
    assert result.profit == (10 / 110) - 0.01
    assert result.cost == 0.01


def test_historical_environment_uses_new_feature_weights_without_breaking_execution() -> None:
    candles = [
        HistoricalCandle("1", 100, 101, 99, 100),
        HistoricalCandle("2", 100, 104, 99, 103),
        HistoricalCandle("3", 103, 108, 102, 107),
        HistoricalCandle("4", 107, 110, 105, 106),
        HistoricalCandle("5", 106, 112, 105, 111),
        HistoricalCandle("6", 111, 115, 109, 114),
    ]

    environment = HistoricalEnvironment(candles)

    agent = Agent.create(
        Genome(
            threshold_open=0.02,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
            ma_window=4,
            vol_long_window=4,
            range_window=3,
            weight_trend_strength=1.0,
            weight_realized_volatility=1.0,
            weight_trend_long=1.0,
            weight_breakout=1.0,
        )
    )

    result = environment.run_episode(agent)

    assert result.trades >= 0
    assert isinstance(result.profit, float)


def test_historical_environment_keeps_behavior_when_regime_filter_is_disabled() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 100, 100, 104),
        HistoricalCandle("3", 104, 105, 103, 105),
        HistoricalCandle("4", 105, 106, 104, 106),
    ]

    environment_without_filter = HistoricalEnvironment(candles)
    environment_with_disabled_filter = HistoricalEnvironment(
        candles,
        regime_filter_enabled=False,
        min_trend_long_for_entry=0.8,
        min_breakout_for_entry=0.8,
        max_realized_volatility_for_entry=0.1,
    )

    agent = Agent.create(
        Genome(
            threshold_open=0.03,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        )
    )

    result_without_filter = environment_without_filter.run_episode(agent)
    result_with_disabled_filter = environment_with_disabled_filter.run_episode(agent)

    assert result_without_filter.trades == result_with_disabled_filter.trades
    assert result_without_filter.profit == result_with_disabled_filter.profit
    assert result_without_filter.drawdown == result_with_disabled_filter.drawdown


def test_historical_environment_blocks_entries_when_regime_filter_is_enabled() -> None:
    candles = [
        HistoricalCandle("1", 100, 100, 100, 100),
        HistoricalCandle("2", 100, 102, 99, 101),
        HistoricalCandle("3", 101, 103, 100, 102),
        HistoricalCandle("4", 102, 104, 101, 103),
        HistoricalCandle("5", 103, 104, 102, 103),
    ]

    environment_without_filter = HistoricalEnvironment(candles)
    environment_with_filter = HistoricalEnvironment(
        candles,
        regime_filter_enabled=True,
        min_trend_long_for_entry=0.9,
        min_breakout_for_entry=0.9,
    )

    agent = Agent.create(
        Genome(
            threshold_open=0.01,
            threshold_close=0.0,
            position_size=0.1,
            stop_loss=0.5,
            take_profit=1.0,
        )
    )

    result_without_filter = environment_without_filter.run_episode(agent)
    result_with_filter = environment_with_filter.run_episode(agent)

    assert result_without_filter.trades >= 1
    assert result_with_filter.trades == 0
