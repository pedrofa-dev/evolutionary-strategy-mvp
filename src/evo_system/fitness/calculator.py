from evo_system.domain.episode_result import EpisodeResult


class FitnessCalculator:
    """
    Converts raw episode metrics into a fitness score.
    """

    def calculate(self, result: EpisodeResult) -> float:
        fitness =  (
            result.profit * 1.0
            - result.drawdown * 0.7
            - result.cost * 0.5
            + result.stability * 0.3
        )

        if result.trades == 0:
            fitness -= 0.2
        return fitness