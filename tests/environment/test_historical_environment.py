from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
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
