from evo_system.domain.genome import Genome
from evo_system.domain.episode_result import EpisodeResult


class SimpleEnvironment:
    """
    A deterministic environment for testing.
    """

    def run(self, genome: Genome) -> EpisodeResult:
        """
        Simulates execution of a genome and returns metrics.
        """

        # Deterministic "fake" logic
        profit = (
            genome.take_profit * genome.position_size
            - genome.stop_loss * 0.5
        )

        drawdown = genome.stop_loss * (1.0 - genome.position_size)

        cost = 0.01 * genome.position_size

        stability = 1.0 - abs(genome.threshold_open - genome.threshold_close)

        return EpisodeResult(
            profit=profit,
            drawdown=drawdown,
            cost=cost,
            stability=stability,
        )