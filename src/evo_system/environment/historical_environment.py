from __future__ import annotations

from statistics import pstdev

from evo_system.domain.agent import Agent
from evo_system.domain.episode_result import EpisodeResult
from evo_system.domain.historical_candle import HistoricalCandle
from evo_system.experimental_space.base import EntryDecision, ExitDecision
from evo_system.experimental_space import (
    get_decision_policy,
    get_default_decision_policy,
    get_default_signal_pack,
    get_signal_pack,
)


class HistoricalEnvironment:
    """Replay one candle series under the current trading-policy semantics.

    Context:
    - Evaluation and reevaluation both depend on this environment being the
      execution authority for net-after-cost episode behavior.

    Invariants:
    - Fees must always be applied here, not guessed later.
    - Active policy_v2 entry/exit semantics must remain centralized here.

    Phase 1 modularization note:
    - `signal_pack` and `decision_policy` are thin adapters over the current
      methods below. They make future modular extraction explicit without
      replacing the current runtime authority.
    """
    def __init__(
        self,
        candles: list[HistoricalCandle],
        trade_cost_rate: float = 0.0,
        regime_filter_enabled: bool = False,
        min_trend_long_for_entry: float = 0.0,
        min_breakout_for_entry: float = 0.0,
        max_realized_volatility_for_entry: float | None = None,
        signal_pack_name: str | None = None,
        decision_policy_name: str | None = None,
    ) -> None:
        if not candles:
            raise ValueError("candles cannot be empty")

        if trade_cost_rate < 0.0:
            raise ValueError("trade_cost_rate must be greater than or equal to 0.0")

        self.candles = candles
        self.trade_cost_rate = trade_cost_rate
        self.regime_filter_enabled = regime_filter_enabled
        self.min_trend_long_for_entry = min_trend_long_for_entry
        self.min_breakout_for_entry = min_breakout_for_entry
        self.max_realized_volatility_for_entry = max_realized_volatility_for_entry
        self.signal_pack = (
            get_signal_pack(signal_pack_name)
            if signal_pack_name is not None
            else get_default_signal_pack()
        )
        self.decision_policy = (
            get_decision_policy(decision_policy_name)
            if decision_policy_name is not None
            else get_default_decision_policy()
        )

        self._closes = [candle.close for candle in candles]
        self._highs = [candle.high for candle in candles]
        self._lows = [candle.low for candle in candles]

        self._normalized_momentum_series = self._build_normalized_momentum_series()

        self._trend_cache: dict[int, list[float]] = {}
        self._return_cache: dict[int, list[float]] = {}
        self._ma_distance_cache: dict[int, list[float]] = {}
        self._range_position_cache: dict[int, list[float]] = {}
        self._returns_cache: dict[int, list[float]] = {}
        self._vol_ratio_cache: dict[tuple[int, int], list[float]] = {}
        self._trend_strength_cache: dict[int, list[float]] = {}
        self._realized_volatility_cache: dict[int, list[float]] = {}
        self._trend_long_cache: dict[int, list[float]] = {}
        self._breakout_cache: dict[int, list[float]] = {}

    def run_episode(self, agent: Agent) -> EpisodeResult:
        metrics = self.get_episode_diagnostics(agent)

        return EpisodeResult(
            profit=float(metrics["profit"]),
            drawdown=float(metrics["drawdown"]),
            trades=int(metrics["trades"]),
            cost=float(metrics["cost"]),
            stability=0.0,
        )

    def get_episode_diagnostics(self, agent: Agent) -> dict[str, float | int]:
        """Run one full episode and return the metrics used by evaluation.

        Why it exists:
        - This is the decision-loop runtime used to turn a genome into profit,
          drawdown, trade count, and cost.

        Invariants:
        - Entry, exit, and trade-control decisions must stay net-of-cost aware.
        - Experimental layers may change genome values, but not bypass this loop.
        """
        # Responsibility boundary:
        # - This loop is the current decision-policy runtime.
        # - Signals, gene blocks, and costs come together here to produce
        #   actions and episode outcomes.
        # TODO: candidate for modularization
        # - Entry/exit policy evaluation could later move into dedicated
        #   decision-policy objects, but this loop remains the execution source
        #   of truth for evaluation.
        in_position = False
        entry_price = 0.0
        entry_index: int | None = None
        last_closed_index: int | None = None
        consecutive_entry_signal_bars = 0
        profit = 0.0
        trades = 0
        total_cost = 0.0

        equity = 0.0
        peak_equity = 0.0
        max_drawdown = 0.0

        genome = agent.genome

        trend_series = self._get_trend_series(genome.trend_window)
        ret_short_series = self._get_return_series(genome.ret_short_window)
        ret_mid_series = self._get_return_series(genome.ret_mid_window)
        ma_distance_series = self._get_ma_distance_series(genome.ma_window)
        range_position_series = self._get_range_position_series(genome.range_window)
        vol_ratio_series = self._get_vol_ratio_series(
            genome.vol_short_window,
            genome.vol_long_window,
        )
        trend_strength_series = self._get_trend_strength_series(genome.ma_window)
        realized_volatility_series = self._get_realized_volatility_series(
            genome.vol_long_window
        )
        trend_long_series = self._get_trend_long_series(genome.ma_window)
        breakout_series = self._get_breakout_series(genome.range_window)

        for index, candle in enumerate(self.candles):
            normalized_momentum = self._normalized_momentum_series[index]
            normalized_trend = trend_series[index]
            signal_features = self.signal_pack.build_signal_features(
                environment=self,
                index=index,
                normalized_momentum=normalized_momentum,
                normalized_trend=normalized_trend,
                ret_short_series=ret_short_series,
                ret_mid_series=ret_mid_series,
                ma_distance_series=ma_distance_series,
                range_position_series=range_position_series,
                vol_ratio_series=vol_ratio_series,
                trend_strength_series=trend_strength_series,
                realized_volatility_series=realized_volatility_series,
                trend_long_series=trend_long_series,
                breakout_series=breakout_series,
            )
            signal_families = self.signal_pack.build_signal_families(
                environment=self,
                signal_features=signal_features,
            )
            regime_filter_ok = (
                not self.regime_filter_enabled
                or self._passes_regime_filter(
                    trend_long=signal_features["trend_strength_long"],
                    breakout=signal_features["breakout_strength_medium"],
                    realized_volatility=signal_features["realized_volatility_medium"],
                )
            )
            if genome.policy_v2_enabled:
                entry_decision = self.decision_policy.evaluate_entry(
                    environment=self,
                    genome=agent.genome,
                    signal_families=signal_families,
                    regime_filter_ok=regime_filter_ok,
                )
                trigger_score = entry_decision.trigger_score
                entry_signal_ok = entry_decision.should_enter
                required_confirmation_bars = 1
            else:
                setup_ok = self._is_legacy_setup_ok(
                    agent=agent,
                    index=index,
                    normalized_momentum=normalized_momentum,
                    normalized_trend=normalized_trend,
                    trend_long_series=trend_long_series,
                    breakout_series=breakout_series,
                    realized_volatility_series=realized_volatility_series,
                )
                trigger_score = self._get_legacy_trigger_score(
                    agent=agent,
                    index=index,
                    ret_short_series=ret_short_series,
                    ret_mid_series=ret_mid_series,
                    ma_distance_series=ma_distance_series,
                    range_position_series=range_position_series,
                    vol_ratio_series=vol_ratio_series,
                    trend_strength_series=trend_strength_series,
                    realized_volatility_series=realized_volatility_series,
                    trend_long_series=trend_long_series,
                    breakout_series=breakout_series,
                )
                context_ok = True
                trigger_ok = (
                    trigger_score
                    >= genome.threshold_open + genome.entry_score_margin
                )
                entry_signal_ok = setup_ok and trigger_ok
                required_confirmation_bars = genome.entry_confirmation_bars

            if not in_position:
                if entry_signal_ok:
                    consecutive_entry_signal_bars += 1
                else:
                    consecutive_entry_signal_bars = 0

                cooldown_ok = self._passes_entry_cooldown(
                    current_index=index,
                    last_closed_index=last_closed_index,
                    cooldown_bars=genome.trade_control.cooldown_bars,
                    reentry_block_bars=genome.trade_control.reentry_block_bars,
                )
                should_open = (
                    entry_signal_ok
                    and consecutive_entry_signal_bars >= required_confirmation_bars
                    and cooldown_ok
                )

                if should_open:
                    in_position = True
                    entry_price = candle.close
                    entry_index = index
                    trades += 1
                    consecutive_entry_signal_bars = 0

            else:
                consecutive_entry_signal_bars = 0
                trade_return = self._get_trade_return(entry_price, candle.close)
                holding_bars = 0 if entry_index is None else index - entry_index

                if genome.policy_v2_enabled:
                    exit_decision = self.decision_policy.evaluate_exit(
                        environment=self,
                        genome=genome,
                        signal_families=signal_families,
                        normalized_momentum=normalized_momentum,
                        trade_return=trade_return,
                        holding_bars=holding_bars,
                    )
                    should_close = exit_decision.should_close
                    hit_stop_loss = exit_decision.hit_stop_loss
                    hit_take_profit = exit_decision.hit_take_profit
                else:
                    hit_stop_loss = trade_return <= -genome.stop_loss
                    hit_take_profit = trade_return >= genome.take_profit
                    should_close = trigger_score <= genome.threshold_close

                    if genome.use_exit_momentum:
                        should_close = should_close or (
                            normalized_momentum <= genome.exit_momentum_threshold
                        )

                if hit_stop_loss or hit_take_profit or should_close:
                    net_trade_profit, trade_cost = self._close_trade(
                        trade_return=trade_return,
                        position_size=genome.position_size,
                    )
                    profit += net_trade_profit
                    total_cost += trade_cost
                    in_position = False
                    entry_price = 0.0
                    entry_index = None
                    last_closed_index = index

            unrealized = 0.0
            if in_position:
                unrealized = (
                    self._get_trade_return(entry_price, candle.close)
                    * genome.position_size
                )

            equity = profit + unrealized
            peak_equity = max(peak_equity, equity)
            max_drawdown = max(max_drawdown, peak_equity - equity)

        if in_position:
            final_close = self.candles[-1].close
            final_return = self._get_trade_return(entry_price, final_close)
            net_trade_profit, trade_cost = self._close_trade(
                trade_return=final_return,
                position_size=genome.position_size,
            )
            profit += net_trade_profit
            total_cost += trade_cost

        return {
            "profit": profit,
            "drawdown": max_drawdown,
            "trades": trades,
            "cost": total_cost,
        }

    def _close_trade(self, trade_return: float, position_size: float) -> tuple[float, float]:
        gross_profit = trade_return * position_size
        trade_cost = self.trade_cost_rate * position_size
        net_profit = gross_profit - trade_cost
        return net_profit, trade_cost

    @staticmethod
    def _passes_entry_cooldown(
        *,
        current_index: int,
        last_closed_index: int | None,
        cooldown_bars: int,
        reentry_block_bars: int,
    ) -> bool:
        required_bars = max(cooldown_bars, reentry_block_bars)
        if required_bars <= 0 or last_closed_index is None:
            return True

        bars_since_close = current_index - last_closed_index - 1
        return bars_since_close >= required_bars

    def _passes_regime_filter(
        self,
        trend_long: float,
        breakout: float,
        realized_volatility: float,
    ) -> bool:
        if trend_long < self.min_trend_long_for_entry:
            return False

        if breakout < self.min_breakout_for_entry:
            return False

        if self.max_realized_volatility_for_entry is not None:
            if realized_volatility > self.max_realized_volatility_for_entry:
                return False

        return True

    def _is_legacy_setup_ok(
        self,
        agent: Agent,
        index: int,
        normalized_momentum: float,
        normalized_trend: float,
        trend_long_series: list[float],
        breakout_series: list[float],
        realized_volatility_series: list[float],
    ) -> bool:
        genome = agent.genome
        setup_ok = True

        if genome.use_momentum:
            setup_ok = setup_ok and (
                normalized_momentum >= genome.momentum_threshold
            )

        if genome.use_trend:
            setup_ok = setup_ok and (normalized_trend >= genome.trend_threshold)

        if self.regime_filter_enabled:
            setup_ok = setup_ok and self._passes_regime_filter(
                trend_long=trend_long_series[index],
                breakout=breakout_series[index],
                realized_volatility=realized_volatility_series[index],
            )

        return setup_ok

    def _passes_entry_context(
        self,
        genome,
        signal_families: dict[str, float],
    ) -> bool:
        """Compatibility wrapper over the active DecisionPolicy context gate."""
        return self.decision_policy.passes_entry_context(
            environment=self,
            genome=genome,
            signal_families=signal_families,
        )

    def _passes_entry_trigger(
        self,
        genome,
        signal_families: dict[str, float],
        trigger_score: float,
    ) -> bool:
        """Compatibility wrapper over the active DecisionPolicy trigger gate."""
        return self.decision_policy.passes_entry_trigger(
            environment=self,
            genome=genome,
            signal_families=signal_families,
            trigger_score=trigger_score,
        )

    def _should_enter_policy_v2(
        self,
        *,
        genome,
        signal_families: dict[str, float],
        trigger_score: float,
        regime_filter_ok: bool,
    ) -> bool:
        """Compatibility wrapper over the active DecisionPolicy entry decision."""
        return self.decision_policy.should_enter(
            environment=self,
            genome=genome,
            signal_families=signal_families,
            trigger_score=trigger_score,
            regime_filter_ok=regime_filter_ok,
        )

    def _should_exit_policy_v2(
        self,
        *,
        genome,
        signal_families: dict[str, float],
        trigger_score: float,
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> bool:
        """Compatibility wrapper over the active DecisionPolicy exit decision."""
        return self.decision_policy.should_exit(
            environment=self,
            genome=genome,
            signal_families=signal_families,
            trigger_score=trigger_score,
            normalized_momentum=normalized_momentum,
            trade_return=trade_return,
            holding_bars=holding_bars,
        )

    def _evaluate_policy_v2_entry(
        self,
        *,
        genome,
        signal_families: dict[str, float],
        regime_filter_ok: bool,
    ) -> EntryDecision:
        """Compatibility wrapper over the active DecisionPolicy entry evaluation."""
        return self.decision_policy.evaluate_entry(
            environment=self,
            genome=genome,
            signal_families=signal_families,
            regime_filter_ok=regime_filter_ok,
        )

    def _evaluate_policy_v2_exit(
        self,
        *,
        genome,
        signal_families: dict[str, float],
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> ExitDecision:
        """Compatibility wrapper over the active DecisionPolicy exit evaluation."""
        return self.decision_policy.evaluate_exit(
            environment=self,
            genome=genome,
            signal_families=signal_families,
            normalized_momentum=normalized_momentum,
            trade_return=trade_return,
            holding_bars=holding_bars,
        )

    def _get_policy_v21_signal_features(
        self,
        *,
        index: int,
        normalized_momentum: float,
        normalized_trend: float,
        ret_short_series: list[float],
        ret_mid_series: list[float],
        ma_distance_series: list[float],
        range_position_series: list[float],
        vol_ratio_series: list[float],
        trend_strength_series: list[float],
        realized_volatility_series: list[float],
        trend_long_series: list[float],
        breakout_series: list[float],
    ) -> dict[str, float]:
        """Compatibility wrapper over the active SignalPack feature builder."""
        return self.signal_pack.build_signal_features(
            environment=self,
            index=index,
            normalized_momentum=normalized_momentum,
            normalized_trend=normalized_trend,
            ret_short_series=ret_short_series,
            ret_mid_series=ret_mid_series,
            ma_distance_series=ma_distance_series,
            range_position_series=range_position_series,
            vol_ratio_series=vol_ratio_series,
            trend_strength_series=trend_strength_series,
            realized_volatility_series=realized_volatility_series,
            trend_long_series=trend_long_series,
            breakout_series=breakout_series,
        )

    def _get_signal_families(
        self,
        *,
        signal_features: dict[str, float],
    ) -> dict[str, float]:
        """Compatibility wrapper over the active SignalPack family builder."""
        return self.signal_pack.build_signal_families(
            environment=self,
            signal_features=signal_features,
        )

    def _get_entry_trigger_score(self, genome, signal_families: dict[str, float]) -> float:
        """Compatibility wrapper over the active DecisionPolicy trigger score."""
        return self.decision_policy.get_entry_trigger_score(
            environment=self,
            genome=genome,
            signal_families=signal_families,
        )

    def _get_legacy_trigger_score(
        self,
        agent: Agent,
        index: int,
        ret_short_series: list[float],
        ret_mid_series: list[float],
        ma_distance_series: list[float],
        range_position_series: list[float],
        vol_ratio_series: list[float],
        trend_strength_series: list[float],
        realized_volatility_series: list[float],
        trend_long_series: list[float],
        breakout_series: list[float],
    ) -> float:
        # TODO: candidate for modularization
        # Legacy trigger scoring is tightly coupled to historical flat weights.
        # It can later move into a separate legacy decision-policy adapter.
        genome = agent.genome

        if not self._has_legacy_feature_weights(agent):
            return 0.0

        return (
            genome.weight_ret_short * ret_short_series[index]
            + genome.weight_ret_mid * ret_mid_series[index]
            + genome.weight_dist_ma * ma_distance_series[index]
            + genome.weight_range_pos * range_position_series[index]
            + genome.weight_vol_ratio * vol_ratio_series[index]
            + genome.weight_trend_strength * trend_strength_series[index]
            + genome.weight_realized_volatility * realized_volatility_series[index]
            + genome.weight_trend_long * trend_long_series[index]
            + genome.weight_breakout * breakout_series[index]
        )

    @staticmethod
    def _has_legacy_feature_weights(agent: Agent) -> bool:
        genome = agent.genome

        return any(
            weight != 0.0
            for weight in (
                genome.weight_ret_short,
                genome.weight_ret_mid,
                genome.weight_dist_ma,
                genome.weight_range_pos,
                genome.weight_vol_ratio,
                genome.weight_trend_strength,
                genome.weight_realized_volatility,
                genome.weight_trend_long,
                genome.weight_breakout,
            )
        )

    def _build_normalized_momentum_series(self) -> list[float]:
        series = [0.0]

        for index in range(1, len(self._closes)):
            previous_close = self._closes[index - 1]
            current_close = self._closes[index]
            series.append(
                self._safe_ratio(current_close - previous_close, previous_close)
            )

        return series

    def _get_trend_series(self, window: int) -> list[float]:
        # Signal-definition boundary:
        # - Cached normalized series builders below are the raw ingredients used
        #   by the active signal set and should remain side-effect free.
        cached = self._trend_cache.get(window)
        if cached is not None:
            return cached

        series: list[float] = []

        for index in range(len(self._closes)):
            if index < window:
                series.append(0.0)
                continue

            current_close = self._closes[index]
            reference_close = self._closes[index - window]
            value = self._safe_ratio(current_close - reference_close, reference_close)
            series.append(value)

        self._trend_cache[window] = series
        return series

    def _get_return_series(self, window: int) -> list[float]:
        cached = self._return_cache.get(window)
        if cached is not None:
            return cached

        series: list[float] = []

        for index in range(len(self._closes)):
            if index < window:
                series.append(0.0)
                continue

            current_close = self._closes[index]
            reference_close = self._closes[index - window]
            raw_return = self._safe_ratio(current_close - reference_close, reference_close)
            series.append(self._clamp(raw_return * 10.0, -1.0, 1.0))

        self._return_cache[window] = series
        return series

    def _get_ma_distance_series(self, window: int) -> list[float]:
        cached = self._ma_distance_cache.get(window)
        if cached is not None:
            return cached

        series: list[float] = []
        rolling_sum = 0.0

        for index, close in enumerate(self._closes):
            rolling_sum += close

            if index >= window:
                rolling_sum -= self._closes[index - window]

            current_window_size = min(index + 1, window)
            moving_average = rolling_sum / current_window_size
            distance = self._safe_ratio(close - moving_average, moving_average)

            series.append(self._clamp(distance * 10.0, -1.0, 1.0))

        self._ma_distance_cache[window] = series
        return series

    def _get_range_position_series(self, window: int) -> list[float]:
        cached = self._range_position_cache.get(window)
        if cached is not None:
            return cached

        series: list[float] = []

        for index in range(len(self._closes)):
            start = max(0, index - window + 1)

            highest = max(self._highs[start : index + 1])
            lowest = min(self._lows[start : index + 1])
            span = highest - lowest

            if span <= 0.0:
                series.append(0.0)
                continue

            pos_01 = (self._closes[index] - lowest) / span
            centered = (pos_01 - 0.5) * 2.0
            series.append(self._clamp(centered, -1.0, 1.0))

        self._range_position_cache[window] = series
        return series

    def _get_returns_series(self, window: int) -> list[float]:
        cached = self._returns_cache.get(window)
        if cached is not None:
            return cached

        series = [0.0] * len(self._closes)

        for index in range(1, len(self._closes)):
            previous_close = self._closes[index - 1]
            current_close = self._closes[index]
            series[index] = self._safe_ratio(current_close - previous_close, previous_close)

        self._returns_cache[window] = series
        return series

    def _get_trend_strength_series(self, ma_window: int) -> list[float]:
        cached = self._trend_strength_cache.get(ma_window)
        if cached is not None:
            return cached

        ma_short_window = max(2, ma_window // 2)
        series: list[float] = []

        for index, current_close in enumerate(self._closes):
            if current_close == 0.0:
                series.append(0.0)
                continue

            short_start = max(0, index - ma_short_window + 1)
            long_start = max(0, index - ma_window + 1)

            short_closes = self._closes[short_start : index + 1]
            long_closes = self._closes[long_start : index + 1]

            if not short_closes or not long_closes:
                series.append(0.0)
                continue

            ma_short = sum(short_closes) / len(short_closes)
            ma_long = sum(long_closes) / len(long_closes)
            raw_strength = self._safe_ratio(ma_short - ma_long, current_close)
            series.append(self._clamp(raw_strength * 20.0, -1.0, 1.0))

        self._trend_strength_cache[ma_window] = series
        return series

    def _get_realized_volatility_series(self, vol_window: int) -> list[float]:
        cached = self._realized_volatility_cache.get(vol_window)
        if cached is not None:
            return cached

        returns_series = self._get_returns_series(vol_window)
        series: list[float] = []

        for index in range(len(self._closes)):
            recent_returns = self._get_recent_returns_from_series(
                returns_series,
                index=index,
                window=vol_window,
            )

            if len(recent_returns) < 2:
                series.append(0.0)
                continue

            realized_volatility = pstdev(recent_returns)
            series.append(self._clamp(realized_volatility * 50.0, -1.0, 1.0))

        self._realized_volatility_cache[vol_window] = series
        return series

    def _get_trend_long_series(self, ma_window: int) -> list[float]:
        cached = self._trend_long_cache.get(ma_window)
        if cached is not None:
            return cached

        short_window = max(5, ma_window)
        long_window = max(short_window + 1, ma_window * 4)
        series: list[float] = []

        for index, current_close in enumerate(self._closes):
            if current_close == 0.0:
                series.append(0.0)
                continue

            short_start = max(0, index - short_window + 1)
            long_start = max(0, index - long_window + 1)

            short_closes = self._closes[short_start : index + 1]
            long_closes = self._closes[long_start : index + 1]

            if not short_closes or not long_closes:
                series.append(0.0)
                continue

            ma_short = sum(short_closes) / len(short_closes)
            ma_long = sum(long_closes) / len(long_closes)
            raw_trend = self._safe_ratio(ma_short - ma_long, current_close)
            series.append(self._clamp(raw_trend * 25.0, -1.0, 1.0))

        self._trend_long_cache[ma_window] = series
        return series

    def _get_breakout_series(self, range_window: int) -> list[float]:
        cached = self._breakout_cache.get(range_window)
        if cached is not None:
            return cached

        breakout_window = max(20, range_window * 3)
        series: list[float] = []

        for index, current_close in enumerate(self._closes):
            if index == 0 or current_close == 0.0:
                series.append(0.0)
                continue

            start = max(0, index - breakout_window)
            prior_highs = self._highs[start:index]
            prior_lows = self._lows[start:index]

            if not prior_highs or not prior_lows:
                series.append(0.0)
                continue

            prior_high = max(prior_highs)
            prior_low = min(prior_lows)

            upside_breakout = self._safe_ratio(current_close - prior_high, prior_high)
            downside_breakout = self._safe_ratio(prior_low - current_close, prior_low)
            raw_breakout = upside_breakout - downside_breakout
            series.append(self._clamp(raw_breakout * 30.0, -1.0, 1.0))

        self._breakout_cache[range_window] = series
        return series

    def _get_vol_ratio_series(self, short_window: int, long_window: int) -> list[float]:
        cache_key = (short_window, long_window)
        cached = self._vol_ratio_cache.get(cache_key)
        if cached is not None:
            return cached

        returns_series = self._get_returns_series(max(short_window, long_window))
        series: list[float] = []

        for index in range(len(self._closes)):
            short_returns = self._get_recent_returns_from_series(
                returns_series,
                index=index,
                window=short_window,
            )
            long_returns = self._get_recent_returns_from_series(
                returns_series,
                index=index,
                window=long_window,
            )

            if not short_returns or not long_returns:
                series.append(0.0)
                continue

            short_vol = pstdev(short_returns) if len(short_returns) > 1 else 0.0
            long_vol = pstdev(long_returns) if len(long_returns) > 1 else 0.0

            if long_vol <= 0.0:
                series.append(0.0)
                continue

            ratio = short_vol / long_vol
            centered = ratio - 1.0
            series.append(self._clamp(centered, -1.0, 1.0))

        self._vol_ratio_cache[cache_key] = series
        return series

    @staticmethod
    def _get_recent_returns_from_series(
        returns_series: list[float],
        index: int,
        window: int,
    ) -> list[float]:
        if index <= 0:
            return []

        start = max(1, index - window + 1)
        return returns_series[start : index + 1]

    @staticmethod
    def _get_trade_return(entry_price: float, current_price: float) -> float:
        if entry_price <= 0.0:
            return 0.0

        return (current_price - entry_price) / entry_price

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if denominator == 0.0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
