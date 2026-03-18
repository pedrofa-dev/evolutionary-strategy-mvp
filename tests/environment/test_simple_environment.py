from evo_system.domain.genome import Genome
from evo_system.domain.episode_result import EpisodeResult
from evo_system.environment.simple_environment import SimpleEnvironment


def test_simple_environment_run_returns_episode_result() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    environment = SimpleEnvironment()

    result = environment.run(genome)

    assert isinstance(result, EpisodeResult)


def test_simple_environment_run_is_deterministic() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    environment = SimpleEnvironment()

    result_1 = environment.run(genome)
    result_2 = environment.run(genome)

    assert result_1 == result_2


def test_simple_environment_run_returns_expected_metrics() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    environment = SimpleEnvironment()

    result = environment.run(genome)

    assert result.profit == 0.1 * 0.2 - 0.05 * 0.5
    assert result.drawdown == 0.05 * (1.0 - 0.2)
    assert result.cost == 0.01 * 0.2
    assert result.stability == 1.0 - abs(0.8 - 0.4)
    assert result.trades == 1