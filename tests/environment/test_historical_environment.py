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