from evo_system.domain.episode_result import EpisodeResult


class FitnessCalculator:
    """
    Converts episode results into a scalar fitness score.
    """

    def calculate(self, result: EpisodeResult) -> float:
        base_score = (
            result.profit
            - result.drawdown * 0.7
            - result.cost * 0.5
        )

        fitness = base_score

        # Penalize very low trading activity
        if result.trades == 0:
            fitness -= 2.0
        elif result.trades == 1:
            fitness -= 1.5
        elif result.trades == 2:
            fitness -= 1.0
        elif result.trades == 3:
            fitness -= 0.5

        # Penalize tiny profits or negative profits
        if result.profit <= 0:
            fitness -= 0.3

        # Stability should only help profitable agents
        if result.profit > 0:
            fitness += result.stability * 0.05

        return fitness