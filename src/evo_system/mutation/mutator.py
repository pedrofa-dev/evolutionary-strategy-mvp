import random

from evo_system.domain.genome import Genome


class Mutator:
    """
    Applies small controlled mutations to a genome.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def mutate(self, genome: Genome) -> Genome:
        mutated = genome.copy_with(
            threshold_open=self._clamp(
                genome.threshold_open + self.random.uniform(-0.05, 0.05),
                0.0,
                1.0,
            ),
            threshold_close=self._clamp(
                genome.threshold_close + self.random.uniform(-0.05, 0.05),
                0.0,
                1.0,
            ),
            position_size=self._clamp(
                genome.position_size + self.random.uniform(-0.05, 0.05),
                0.01,
                1.0,
            ),
            stop_loss=self._clamp(
                genome.stop_loss + self.random.uniform(-0.02, 0.02),
                0.01,
                1.0,
            ),
            take_profit=self._clamp(
                genome.take_profit + self.random.uniform(-0.05, 0.05),
                0.01,
                2.0,
            ),
        )

        if mutated.threshold_close > mutated.threshold_open:
            mutated = mutated.copy_with(
                threshold_close=mutated.threshold_open
            )

        return mutated

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))