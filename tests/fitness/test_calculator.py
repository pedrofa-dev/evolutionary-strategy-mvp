from evo_system.domain.episode_result import EpisodeResult
from evo_system.fitness.calculator import FitnessCalculator


def test_calculate_returns_expected_fitness_score_for_profitable_agent() -> None:
    result = EpisodeResult(
        profit=1.0,
        drawdown=0.5,
        cost=0.2,
        stability=0.8,
        trades=5,
    )

    calculator = FitnessCalculator()

    fitness = calculator.calculate(result)

    expected = (
        1.0
        - 0.5 * 0.7
        - 0.2 * 0.5
        + 0.8 * 0.05
    )

    assert fitness == expected


def test_fitness_penalizes_zero_trades() -> None:
    calculator = FitnessCalculator()

    result = EpisodeResult(
        profit=0.0,
        drawdown=0.0,
        cost=0.0,
        stability=1.0,
        trades=0,
    )

    fitness = calculator.calculate(result)

    assert fitness == -2.3


def test_fitness_penalizes_one_trade() -> None:
    calculator = FitnessCalculator()

    result = EpisodeResult(
        profit=0.0,
        drawdown=0.0,
        cost=0.0,
        stability=1.0,
        trades=1,
    )

    fitness = calculator.calculate(result)

    assert fitness == -1.8


def test_fitness_penalizes_two_trades() -> None:
    calculator = FitnessCalculator()

    result = EpisodeResult(
        profit=0.0,
        drawdown=0.0,
        cost=0.0,
        stability=1.0,
        trades=2,
    )

    fitness = calculator.calculate(result)

    assert fitness == -1.3


def test_fitness_penalizes_three_trades() -> None:
    calculator = FitnessCalculator()

    result = EpisodeResult(
        profit=0.0,
        drawdown=0.0,
        cost=0.0,
        stability=1.0,
        trades=3,
    )

    fitness = calculator.calculate(result)

    assert fitness == -0.8


def test_negative_profit_does_not_receive_stability_bonus() -> None:
    calculator = FitnessCalculator()

    result = EpisodeResult(
        profit=-0.1,
        drawdown=0.0,
        cost=0.0,
        stability=1.0,
        trades=5,
    )

    fitness = calculator.calculate(result)

    assert fitness == -0.4