import random

from evo_system.domain.genome import Genome


class Mutator:
    """
    Applies controlled mutations to a genome.

    It uses:
    - local mutations for exploitation
    - occasional strong mutations for exploration
    """

    STRONG_MUTATION_PROBABILITY = 0.10
    FLAG_FLIP_PROBABILITY = 0.08
    TREND_WINDOW_MUTATION_PROBABILITY = 0.35

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def mutate(self, genome: Genome) -> Genome:
        if self.random.random() < self.STRONG_MUTATION_PROBABILITY:
            return self._strong_mutate(genome)

        return self._small_mutate(genome)

    def _small_mutate(self, genome: Genome) -> Genome:
        threshold_open = self._clamp(
            genome.threshold_open + self.random.uniform(-0.03, 0.03),
            0.0,
            1.0,
        )

        threshold_close = self._clamp(
            genome.threshold_close + self.random.uniform(-0.03, 0.03),
            0.0,
            1.0,
        )

        position_size = self._clamp(
            genome.position_size + self.random.uniform(-0.03, 0.03),
            0.01,
            1.0,
        )

        stop_loss = self._clamp(
            genome.stop_loss + self.random.uniform(-0.01, 0.01),
            0.01,
            1.0,
        )

        take_profit = self._clamp(
            genome.take_profit + self.random.uniform(-0.03, 0.03),
            0.01,
            2.0,
        )

        use_momentum = genome.use_momentum
        momentum_threshold = genome.momentum_threshold

        if self.random.random() < self.FLAG_FLIP_PROBABILITY:
            use_momentum = not use_momentum

        if use_momentum:
            momentum_threshold = self._clamp(
                momentum_threshold + self.random.uniform(-0.0008, 0.0008),
                -0.01,
                0.01,
            )

        use_trend = genome.use_trend
        trend_threshold = genome.trend_threshold
        trend_window = genome.trend_window

        if self.random.random() < self.FLAG_FLIP_PROBABILITY:
            use_trend = not use_trend

        if use_trend:
            trend_threshold = self._clamp(
                trend_threshold + self.random.uniform(-0.0008, 0.0008),
                -0.01,
                0.01,
            )

            if self.random.random() < self.TREND_WINDOW_MUTATION_PROBABILITY:
                trend_window = int(
                    self._clamp(
                        trend_window + self.random.choice([-1, 1]),
                        2,
                        20,
                    )
                )

        use_exit_momentum = genome.use_exit_momentum
        exit_momentum_threshold = genome.exit_momentum_threshold

        if self.random.random() < self.FLAG_FLIP_PROBABILITY:
            use_exit_momentum = not use_exit_momentum

        if use_exit_momentum:
            exit_momentum_threshold = self._clamp(
                exit_momentum_threshold + self.random.uniform(-0.0008, 0.0008),
                -0.01,
                0.0,
            )

        mutated = genome.copy_with(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            use_momentum=use_momentum,
            momentum_threshold=momentum_threshold,
            use_trend=use_trend,
            trend_threshold=trend_threshold,
            trend_window=trend_window,
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=exit_momentum_threshold,
        )

        if mutated.threshold_close > mutated.threshold_open:
            mutated = mutated.copy_with(
                threshold_close=mutated.threshold_open
            )

        return mutated

    def _strong_mutate(self, genome: Genome) -> Genome:
        threshold_open = self.random.uniform(0.45, 0.90)
        threshold_close = self.random.uniform(0.15, threshold_open)

        position_size = self.random.uniform(0.05, 0.25)
        stop_loss = self.random.uniform(0.01, 0.06)
        take_profit = self.random.uniform(0.03, 0.18)

        use_momentum = self.random.choice([True, False])
        momentum_threshold = (
            self.random.uniform(-0.002, 0.002) if use_momentum else 0.0
        )

        use_trend = self.random.choice([True, False])
        trend_threshold = (
            self.random.uniform(-0.002, 0.002) if use_trend else 0.0
        )
        trend_window = self.random.randint(2, 8)

        use_exit_momentum = self.random.choice([True, False])
        exit_momentum_threshold = (
            self.random.uniform(-0.002, 0.0) if use_exit_momentum else 0.0
        )

        return genome.copy_with(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            use_momentum=use_momentum,
            momentum_threshold=momentum_threshold,
            use_trend=use_trend,
            trend_threshold=trend_threshold,
            trend_window=trend_window,
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=exit_momentum_threshold,
        )

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))