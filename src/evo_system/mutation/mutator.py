from __future__ import annotations

import random
from dataclasses import dataclass

from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
    build_policy_v2_genome,
)


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
        if genome.policy_v2_enabled:
            if self.random.random() < self.profile.strong_mutation_probability:
                return self._strong_mutate_policy_v2(genome)
            return self._small_mutate_policy_v2(genome)

        if self.random.random() < self.profile.strong_mutation_probability:
            return self._strong_mutate_legacy(genome)
        return self._small_mutate_legacy(genome)

    # =========================
    # SMALL MUTATION
    # =========================

    def _small_mutate_legacy(self, genome: Genome) -> Genome:
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
            genome.position_size + self._scaled_delta(0.03),
            0.05,
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
        weight_trend_strength = self._mutate_weight(genome.weight_trend_strength)
        weight_realized_volatility = self._mutate_weight(
            genome.weight_realized_volatility
        )
        weight_trend_long = self._mutate_weight(genome.weight_trend_long)
        weight_breakout = self._mutate_weight(genome.weight_breakout)

        return Genome(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_score_margin=genome.entry_score_margin,
            min_bars_between_entries=genome.min_bars_between_entries,
            entry_confirmation_bars=genome.entry_confirmation_bars,
            policy_v2_enabled=genome.policy_v2_enabled,
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
            weight_trend_strength=weight_trend_strength,
            weight_realized_volatility=weight_realized_volatility,
            weight_trend_long=weight_trend_long,
            weight_breakout=weight_breakout,
        )

    # =========================
    # STRONG MUTATION
    # =========================

    def _strong_mutate_legacy(self, genome: Genome) -> Genome:
        ret_short_window = self.random.randint(2, 10)
        ret_mid_window = self.random.randint(max(10, ret_short_window + 1), 50)
        vol_short_window = self.random.randint(2, 20)
        vol_long_window = self.random.randint(max(10, vol_short_window + 1), 100)

        return Genome(
            threshold_open=self.random.uniform(0.4, 1.0),
            threshold_close=self.random.uniform(0.0, 0.5),
            position_size=self.random.uniform(0.05, 1.0),
            stop_loss=self.random.uniform(0.01, 1.0),
            take_profit=self.random.uniform(0.01, 2.0),
            entry_score_margin=genome.entry_score_margin,
            min_bars_between_entries=genome.min_bars_between_entries,
            entry_confirmation_bars=genome.entry_confirmation_bars,
            policy_v2_enabled=genome.policy_v2_enabled,
            use_momentum=self.random.choice([True, False]),
            momentum_threshold=self.random.uniform(-0.01, 0.01),
            use_trend=self.random.choice([True, False]),
            trend_threshold=self.random.uniform(-0.01, 0.01),
            trend_window=self.random.randint(2, 50),
            use_exit_momentum=self.random.choice([True, False]),
            exit_momentum_threshold=self.random.uniform(-0.01, 0.01),
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self.random.randint(5, 100),
            range_window=self.random.randint(5, 50),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=self.random.uniform(-2, 2),
            weight_ret_mid=self.random.uniform(-2, 2),
            weight_dist_ma=self.random.uniform(-2, 2),
            weight_range_pos=self.random.uniform(-2, 2),
            weight_vol_ratio=self.random.uniform(-2, 2),
            weight_trend_strength=self.random.uniform(-2, 2),
            weight_realized_volatility=self.random.uniform(-2, 2),
            weight_trend_long=self.random.uniform(-2, 2),
            weight_breakout=self.random.uniform(-2, 2),
        )

    def _small_mutate_policy_v2(self, genome: Genome) -> Genome:
        main_delta = 0.03 * self.profile.numeric_delta_scale
        stop_loss_delta = 0.01 * self.profile.numeric_delta_scale

        ret_short_window = self._mutate_window(genome.ret_short_window, 2, 10)
        ret_mid_window = self._mutate_window(genome.ret_mid_window, 5, 50)
        ma_window = self._mutate_window(genome.ma_window, 5, 100)
        range_window = self._mutate_window(genome.range_window, 5, 50)
        vol_short_window = self._mutate_window(genome.vol_short_window, 2, 20)
        vol_long_window = self._mutate_window(genome.vol_long_window, 10, 100)
        trend_window = self._mutate_window(genome.trend_window, 2, 50)

        if ret_short_window >= ret_mid_window:
            ret_short_window = max(2, ret_mid_window - 1)

        if vol_short_window >= vol_long_window:
            vol_short_window = max(2, vol_long_window - 1)

        exit_policy = genome.exit_policy or ExitPolicyGene()
        entry_context = genome.entry_context or EntryContextGene()
        entry_trigger = genome.entry_trigger or EntryTriggerGene()
        trade_control = genome.trade_control or TradeControlGene()

        min_realized_volatility = self._clamp(
            entry_context.min_realized_volatility + self.random.uniform(-main_delta, main_delta),
            -1.0,
            1.0,
        )
        max_realized_volatility = self._clamp(
            entry_context.max_realized_volatility + self.random.uniform(-main_delta, main_delta),
            -1.0,
            1.0,
        )
        if min_realized_volatility > max_realized_volatility:
            min_realized_volatility, max_realized_volatility = (
                max_realized_volatility,
                min_realized_volatility,
            )

        allowed_range_position_min = self._clamp(
            entry_context.allowed_range_position_min + self.random.uniform(-main_delta, main_delta),
            -1.0,
            1.0,
        )
        allowed_range_position_max = self._clamp(
            entry_context.allowed_range_position_max + self.random.uniform(-main_delta, main_delta),
            -1.0,
            1.0,
        )
        if allowed_range_position_min > allowed_range_position_max:
            allowed_range_position_min, allowed_range_position_max = (
                allowed_range_position_max,
                allowed_range_position_min,
            )

        exit_on_signal_reversal = exit_policy.exit_on_signal_reversal
        require_trend_or_breakout = entry_trigger.require_trend_or_breakout

        if self.random.random() < self.profile.flag_flip_probability:
            exit_on_signal_reversal = not exit_on_signal_reversal

        if self.random.random() < self.profile.flag_flip_probability:
            require_trend_or_breakout = not require_trend_or_breakout

        return build_policy_v2_genome(
            position_size=self._clamp(
                genome.position_size + self._scaled_delta(0.03),
                0.05,
                1.0,
            ),
            stop_loss_pct=self._clamp(
                exit_policy.stop_loss_pct + self.random.uniform(-stop_loss_delta, stop_loss_delta),
                0.01,
                1.0,
            ),
            take_profit_pct=self._clamp(
                exit_policy.take_profit_pct + self.random.uniform(-main_delta, main_delta),
                0.01,
                2.0,
            ),
            trend_window=trend_window,
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=ma_window,
            range_window=range_window,
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            entry_context=EntryContextGene(
                min_trend_strength=self._clamp(
                    entry_context.min_trend_strength + self.random.uniform(-main_delta, main_delta),
                    -1.0,
                    1.0,
                ),
                min_breakout_strength=self._clamp(
                    entry_context.min_breakout_strength + self.random.uniform(-main_delta, main_delta),
                    -1.0,
                    1.0,
                ),
                min_realized_volatility=min_realized_volatility,
                max_realized_volatility=max_realized_volatility,
                allowed_range_position_min=allowed_range_position_min,
                allowed_range_position_max=allowed_range_position_max,
            ),
            entry_trigger=EntryTriggerGene(
                trend_weight=self._mutate_weight(entry_trigger.trend_weight),
                momentum_weight=self._mutate_weight(entry_trigger.momentum_weight),
                breakout_weight=self._mutate_weight(entry_trigger.breakout_weight),
                range_weight=self._mutate_weight(entry_trigger.range_weight),
                volatility_weight=self._mutate_weight(entry_trigger.volatility_weight),
                entry_score_threshold=self._clamp(
                    entry_trigger.entry_score_threshold + self.random.uniform(-main_delta, main_delta),
                    -5.0,
                    5.0,
                ),
                min_positive_families=max(
                    0,
                    min(
                        5,
                        entry_trigger.min_positive_families + self.random.choice([-1, 0, 1]),
                    ),
                ),
                require_trend_or_breakout=require_trend_or_breakout,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=self._clamp(
                    exit_policy.exit_score_threshold + self.random.uniform(-main_delta, main_delta),
                    -5.0,
                    5.0,
                ),
                exit_on_signal_reversal=exit_on_signal_reversal,
                max_holding_bars=max(
                    0,
                    exit_policy.max_holding_bars + self.random.choice([-2, -1, 0, 1, 2]),
                ),
                stop_loss_pct=self._clamp(
                    exit_policy.stop_loss_pct + self.random.uniform(-stop_loss_delta, stop_loss_delta),
                    0.01,
                    1.0,
                ),
                take_profit_pct=self._clamp(
                    exit_policy.take_profit_pct + self.random.uniform(-main_delta, main_delta),
                    0.01,
                    2.0,
                ),
            ),
            trade_control=TradeControlGene(
                cooldown_bars=max(0, trade_control.cooldown_bars + self.random.choice([-1, 0, 1])),
                min_holding_bars=max(0, trade_control.min_holding_bars + self.random.choice([-1, 0, 1])),
                reentry_block_bars=max(0, trade_control.reentry_block_bars + self.random.choice([-1, 0, 1])),
            ),
        )

    def _strong_mutate_policy_v2(self, genome: Genome) -> Genome:
        ret_short_window = self.random.randint(2, 10)
        ret_mid_window = self.random.randint(max(10, ret_short_window + 1), 50)
        vol_short_window = self.random.randint(2, 20)
        vol_long_window = self.random.randint(max(10, vol_short_window + 1), 100)
        min_realized_volatility = self.random.uniform(-1.0, 1.0)
        max_realized_volatility = self.random.uniform(-1.0, 1.0)
        if min_realized_volatility > max_realized_volatility:
            min_realized_volatility, max_realized_volatility = (
                max_realized_volatility,
                min_realized_volatility,
            )
        allowed_range_position_min = self.random.uniform(-1.0, 1.0)
        allowed_range_position_max = self.random.uniform(-1.0, 1.0)
        if allowed_range_position_min > allowed_range_position_max:
            allowed_range_position_min, allowed_range_position_max = (
                allowed_range_position_max,
                allowed_range_position_min,
            )

        return build_policy_v2_genome(
            position_size=self.random.uniform(0.05, 1.0),
            stop_loss_pct=self.random.uniform(0.01, 1.0),
            take_profit_pct=self.random.uniform(0.01, 2.0),
            trend_window=self.random.randint(2, 50),
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self.random.randint(5, 100),
            range_window=self.random.randint(5, 50),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            entry_context=EntryContextGene(
                min_trend_strength=self.random.uniform(-1.0, 1.0),
                min_breakout_strength=self.random.uniform(-1.0, 1.0),
                min_realized_volatility=min_realized_volatility,
                max_realized_volatility=max_realized_volatility,
                allowed_range_position_min=allowed_range_position_min,
                allowed_range_position_max=allowed_range_position_max,
            ),
            entry_trigger=EntryTriggerGene(
                trend_weight=self.random.uniform(-2, 2),
                momentum_weight=self.random.uniform(-2, 2),
                breakout_weight=self.random.uniform(-2, 2),
                range_weight=self.random.uniform(-2, 2),
                volatility_weight=self.random.uniform(-2, 2),
                entry_score_threshold=self.random.uniform(-1.0, 2.0),
                min_positive_families=self.random.randint(0, 5),
                require_trend_or_breakout=self.random.choice([True, False]),
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=self.random.uniform(-1.0, 1.0),
                exit_on_signal_reversal=self.random.choice([True, False]),
                max_holding_bars=self.random.choice([0, 6, 12, 24, 36, 48]),
                stop_loss_pct=self.random.uniform(0.01, 1.0),
                take_profit_pct=self.random.uniform(0.01, 2.0),
            ),
            trade_control=TradeControlGene(
                cooldown_bars=self.random.randint(0, 8),
                min_holding_bars=self.random.randint(0, 8),
                reentry_block_bars=self.random.randint(0, 8),
            ),
        )

    # =========================
    # HELPERS
    # =========================

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _scaled_delta(self, base_delta: float) -> float:
        delta = base_delta * self.profile.numeric_delta_scale
        return self.random.uniform(-delta, delta)

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
