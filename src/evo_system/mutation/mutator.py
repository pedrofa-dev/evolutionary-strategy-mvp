import random

from evo_system.domain.genome import Genome


class Mutator:
    """
    Applies small controlled mutations to a genome.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def mutate(self, genome: Genome) -> Genome:
        # --- Standard mutations ---
        threshold_open = self._clamp(
            genome.threshold_open + self.random.uniform(-0.05, 0.05),
            0.0,
            1.0,
        )

        threshold_close = self._clamp(
            genome.threshold_close + self.random.uniform(-0.05, 0.05),
            0.0,
            1.0,
        )

        position_size = self._clamp(
            genome.position_size + self.random.uniform(-0.05, 0.05),
            0.01,
            1.0,
        )

        stop_loss = self._clamp(
            genome.stop_loss + self.random.uniform(-0.02, 0.02),
            0.01,
            1.0,
        )

        take_profit = self._clamp(
            genome.take_profit + self.random.uniform(-0.05, 0.05),
            0.01,
            2.0,
        )

        # --- Momentum mutation ---
        use_momentum = genome.use_momentum
        momentum_threshold = genome.momentum_threshold

        if self.random.random() < 0.1:
            use_momentum = not use_momentum

        if use_momentum:
            momentum_threshold = self._clamp(
                momentum_threshold + self.random.uniform(-0.001, 0.001),
                -0.01,
                0.01,
            )

        # --- Trend mutation ---
        use_trend = genome.use_trend
        trend_threshold = genome.trend_threshold
        trend_window = genome.trend_window

        if self.random.random() < 0.1:
            use_trend = not use_trend

        if use_trend:
            trend_threshold = self._clamp(
                trend_threshold + self.random.uniform(-0.001, 0.001),
                -0.01,
                0.01,
            )

            trend_window = int(
                self._clamp(
                    trend_window + self.random.choice([-1, 1]),
                    2,
                    20,
                )
            )

        # --- Exit momentum mutation ---
        use_exit_momentum = genome.use_exit_momentum
        exit_momentum_threshold = genome.exit_momentum_threshold

        if self.random.random() < 0.1:
            use_exit_momentum = not use_exit_momentum

        if use_exit_momentum:
            exit_momentum_threshold = self._clamp(
                exit_momentum_threshold + self.random.uniform(-0.001, 0.001),
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

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))