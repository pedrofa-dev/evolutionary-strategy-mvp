from __future__ import annotations

import random
from dataclasses import dataclass

from evo_system.domain.genome import Genome


@dataclass(frozen=True)
class MutationProfile:
    strong_mutation_probability: float = 0.10
    numeric_delta_scale: float = 1.0
    flag_flip_probability: float = 0.05
    weight_delta: float = 0.20
    window_step_mode: str = "default"  # "small", "default", "wide"


class Mutator:
    def __init__(
        self,
        seed: int | None = None,
        profile: MutationProfile | None = None,
    ) -> None:
        self.random = random.Random(seed)
        self.profile = profile or MutationProfile()

    def mutate(self, genome: Genome) -> Genome:
        if self.random.random() < self.profile.strong_mutation_probability:
            return self._strong_mutate(genome)
        return self._small_mutate(genome)

    # =========================
    # SMALL MUTATION
    # =========================

    def _small_mutate(self, genome: Genome) -> Genome:
        main_delta = 0.03 * self.profile.numeric_delta_scale
        stop_loss_delta = 0.01 * self.profile.numeric_delta_scale
        signal_delta = 0.001 * self.profile.numeric_delta_scale

        threshold_open = self._clamp(
            genome.threshold_open + self.random.uniform(-main_delta, main_delta),
            0.0,
            1.0,
        )

        threshold_close = self._clamp(
            genome.threshold_close + self.random.uniform(-main_delta, main_delta),
            0.0,
            1.0,
        )

        position_size = self._clamp(
            genome.position_size + self.random.uniform(-main_delta, main_delta),
            0.01,
            1.0,
        )

        stop_loss = self._clamp(
            genome.stop_loss + self.random.uniform(-stop_loss_delta, stop_loss_delta),
            0.01,
            1.0,
        )

        take_profit = self._clamp(
            genome.take_profit + self.random.uniform(-main_delta, main_delta),
            0.01,
            2.0,
        )

        use_momentum = genome.use_momentum
        if self.random.random() < self.profile.flag_flip_probability:
            use_momentum = not use_momentum

        use_trend = genome.use_trend
        if self.random.random() < self.profile.flag_flip_probability:
            use_trend = not use_trend

        use_exit_momentum = genome.use_exit_momentum
        if self.random.random() < self.profile.flag_flip_probability:
            use_exit_momentum = not use_exit_momentum

        momentum_threshold = genome.momentum_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )
        trend_threshold = genome.trend_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )
        exit_momentum_threshold = genome.exit_momentum_threshold + self.random.uniform(
            -signal_delta,
            signal_delta,
        )

        trend_window = self._mutate_window(genome.trend_window, 2, 50)

        ret_short_window = self._mutate_window(genome.ret_short_window, 2, 10)
        ret_mid_window = self._mutate_window(genome.ret_mid_window, 5, 50)
        ma_window = self._mutate_window(genome.ma_window, 5, 100)
        range_window = self._mutate_window(genome.range_window, 5, 50)
        vol_short_window = self._mutate_window(genome.vol_short_window, 2, 20)
        vol_long_window = self._mutate_window(genome.vol_long_window, 10, 100)

        if ret_short_window >= ret_mid_window:
            ret_short_window = max(2, ret_mid_window - 1)

        if vol_short_window >= vol_long_window:
            vol_short_window = max(2, vol_long_window - 1)

        weight_ret_short = self._mutate_weight(genome.weight_ret_short)
        weight_ret_mid = self._mutate_weight(genome.weight_ret_mid)
        weight_dist_ma = self._mutate_weight(genome.weight_dist_ma)
        weight_range_pos = self._mutate_weight(genome.weight_range_pos)
        weight_vol_ratio = self._mutate_weight(genome.weight_vol_ratio)

        return Genome(
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
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=ma_window,
            range_window=range_window,
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=weight_ret_short,
            weight_ret_mid=weight_ret_mid,
            weight_dist_ma=weight_dist_ma,
            weight_range_pos=weight_range_pos,
            weight_vol_ratio=weight_vol_ratio,
        )

    # =========================
    # STRONG MUTATION
    # =========================

    def _strong_mutate(self, genome: Genome) -> Genome:
        return Genome(
            threshold_open=self.random.uniform(0.4, 1.0),
            threshold_close=self.random.uniform(0.0, 0.5),
            position_size=self.random.uniform(0.01, 1.0),
            stop_loss=self.random.uniform(0.01, 1.0),
            take_profit=self.random.uniform(0.01, 2.0),
            use_momentum=self.random.choice([True, False]),
            momentum_threshold=self.random.uniform(-0.01, 0.01),
            use_trend=self.random.choice([True, False]),
            trend_threshold=self.random.uniform(-0.01, 0.01),
            trend_window=self.random.randint(2, 50),
            use_exit_momentum=self.random.choice([True, False]),
            exit_momentum_threshold=self.random.uniform(-0.01, 0.01),
            ret_short_window=self.random.randint(2, 10),
            ret_mid_window=self.random.randint(10, 50),
            ma_window=self.random.randint(5, 100),
            range_window=self.random.randint(5, 50),
            vol_short_window=self.random.randint(2, 20),
            vol_long_window=self.random.randint(10, 100),
            weight_ret_short=self.random.uniform(-2, 2),
            weight_ret_mid=self.random.uniform(-2, 2),
            weight_dist_ma=self.random.uniform(-2, 2),
            weight_range_pos=self.random.uniform(-2, 2),
            weight_vol_ratio=self.random.uniform(-2, 2),
        )

    # =========================
    # HELPERS
    # =========================

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _mutate_weight(self, value: float) -> float:
        delta = self.profile.weight_delta
        return self._clamp(value + self.random.uniform(-delta, delta), -3.0, 3.0)

    def _mutate_window(self, value: int, min_value: int, max_value: int) -> int:
        if self.profile.window_step_mode == "small":
            choices = [-1, 1]
        elif self.profile.window_step_mode == "wide":
            choices = [-3, -2, -1, 1, 2, 3]
        else:
            choices = [-2, -1, 1, 2]

        step = self.random.choice(choices)
        return int(self._clamp(value + step, min_value, max_value))