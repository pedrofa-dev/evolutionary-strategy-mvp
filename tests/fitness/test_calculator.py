from evo_system.domain.episode_result import EpisodeResult
from evo_system.fitness.calculator import FitnessCalculator


def test_calculate_returns_expected_fitness_score() -> None:
    result = EpisodeResult(
        profit=1.0,
        drawdown=0.5,
        cost=0.2,
        stability=0.8,
    )

    calculator = FitnessCalculator()

    fitness = calculator.calculate(result)

    expected = (
        1.0 * 1.0
        - 0.5 * 0.7
        - 0.2 * 0.5
        + 0.8 * 0.3
    )

    assert fitness == expected