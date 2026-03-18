from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.domain.episode_result import EpisodeResult
from evo_system.environment.historical_environment import HistoricalEnvironment


def test_historical_environment_runs_episode() -> None:
    candles = [
        HistoricalCandle("1", 100, 105, 99, 100),
        HistoricalCandle("2", 100, 105, 99, 110),
        HistoricalCandle("3", 110, 115, 108, 90),
    ]

    genome = Genome(
        threshold_open=105,
        threshold_close=95,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    agent = Agent.create(genome)

    env = HistoricalEnvironment(candles)

    result = env.run_episode(agent)

    assert isinstance(result, EpisodeResult)
    assert result.profit != 0.0
    assert result.cost == 0.01