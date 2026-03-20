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

    assert isinstance(result.profit, float)
    assert isinstance(result.drawdown, float)
    assert result.drawdown >= 0.0