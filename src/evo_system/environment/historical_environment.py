from __future__ import annotations

from statistics import pstdev

from evo_system.domain.agent import Agent
from evo_system.domain.episode_result import EpisodeResult
from evo_system.domain.historical_candle import HistoricalCandle


class HistoricalEnvironment:
    def __init__(self, candles: list[HistoricalCandle]) -> None:
        if not candles:
            raise ValueError("candles cannot be empty")

        self.candles = candles
        self._base_price = candles[0].close

    def run_episode(self, agent: Agent) -> EpisodeResult:
        metrics = self.get_episode_diagnostics(agent)

        return EpisodeResult(
            profit=float(metrics["profit"]),
            drawdown=float(metrics["drawdown"]),
            trades=int(metrics["trades"]),
            cost=0.0,
            stability=0.0,
        )

    def get_episode_diagnostics(self, agent: Agent) -> dict[str, float | int]:
        in_position = False
        entry_price = 0.0
        profit = 0.0
        trades = 0

        equity = 0.0
        peak_equity = 0.0
        max_drawdown = 0.0

        for index, candle in enumerate(self.candles):
            normalized_price = self._normalize_price(candle.close)
            normalized_momentum = self._get_normalized_momentum(index)
            normalized_trend = self._get_normalized_trend(
                index=index,
                window=agent.genome.trend_window,
            )

            entry_signal = self._get_entry_signal(
                index=index,
                candle=candle,
                agent=agent,
                normalized_price=normalized_price,
            )

            if not in_position:
                should_open = entry_signal >= agent.genome.threshold_open

                if agent.genome.use_momentum:
                    should_open = should_open and (
                        normalized_momentum >= agent.genome.momentum_threshold
                    )

                if agent.genome.use_trend:
                    should_open = should_open and (
                        normalized_trend >= agent.genome.trend_threshold
                    )

                if should_open:
                    in_position = True
                    entry_price = candle.close
                    trades += 1

            else:
                trade_return = self._get_trade_return(entry_price, candle.close)

                hit_stop_loss = trade_return <= -agent.genome.stop_loss
                hit_take_profit = trade_return >= agent.genome.take_profit

                should_close = normalized_price <= agent.genome.threshold_close

                if agent.genome.use_exit_momentum:
                    should_close = should_close or (
                        normalized_momentum <= agent.genome.exit_momentum_threshold
                    )

                if hit_stop_loss or hit_take_profit or should_close:
                    profit += trade_return * agent.genome.position_size
                    in_position = False
                    entry_price = 0.0

            unrealized = 0.0
            if in_position:
                unrealized = (
                    self._get_trade_return(entry_price, candle.close)
                    * agent.genome.position_size
                )

            equity = profit + unrealized
            peak_equity = max(peak_equity, equity)
            max_drawdown = max(max_drawdown, peak_equity - equity)

        if in_position:
            final_close = self.candles[-1].close
            final_return = self._get_trade_return(entry_price, final_close)
            profit += final_return * agent.genome.position_size

        return {
            "profit": profit,
            "drawdown": max_drawdown,
            "trades": trades,
        }

    def _get_entry_signal(
        self,
        index: int,
        candle: HistoricalCandle,
        agent: Agent,
        normalized_price: float,
    ) -> float:
        """
        Transitional entry signal.

        If all new feature weights are zero, behavior remains legacy:
        entry signal == normalized_price

        Once feature weights are introduced, the signal becomes:
        normalized_price + weighted feature score
        """
        feature_score = self._get_feature_score(index=index, candle=candle, agent=agent)

        if self._has_feature_weights(agent):
            return normalized_price + feature_score

        return normalized_price

    def _has_feature_weights(self, agent: Agent) -> bool:
        genome = agent.genome

        return any(
            weight != 0.0
            for weight in (
                genome.weight_ret_short,
                genome.weight_ret_mid,
                genome.weight_dist_ma,
                genome.weight_range_pos,
                genome.weight_vol_ratio,
            )
        )

    def _get_feature_score(
        self,
        index: int,
        candle: HistoricalCandle,
        agent: Agent,
    ) -> float:
        genome = agent.genome

        ret_short = self._get_return_feature(index, genome.ret_short_window)
        ret_mid = self._get_return_feature(index, genome.ret_mid_window)
        dist_ma = self._get_distance_to_ma_feature(index, genome.ma_window)
        range_pos = self._get_range_position_feature(index, genome.range_window)
        vol_ratio = self._get_vol_ratio_feature(
            index=index,
            short_window=genome.vol_short_window,
            long_window=genome.vol_long_window,
        )

        return (
            genome.weight_ret_short * ret_short
            + genome.weight_ret_mid * ret_mid
            + genome.weight_dist_ma * dist_ma
            + genome.weight_range_pos * range_pos
            + genome.weight_vol_ratio * vol_ratio
        )

    def _normalize_price(self, close_price: float) -> float:
        return self._safe_ratio(close_price - self._base_price, self._base_price)

    def _get_normalized_momentum(self, index: int) -> float:
        if index == 0:
            return 0.0

        previous_close = self.candles[index - 1].close
        current_close = self.candles[index].close

        return self._safe_ratio(current_close - previous_close, previous_close)

    def _get_normalized_trend(self, index: int, window: int) -> float:
        if index < window:
            return 0.0

        current_close = self.candles[index].close
        reference_close = self.candles[index - window].close

        return self._safe_ratio(current_close - reference_close, reference_close)

    def _get_return_feature(self, index: int, window: int) -> float:
        if index < window:
            return 0.0

        current_close = self.candles[index].close
        reference_close = self.candles[index - window].close
        raw_return = self._safe_ratio(current_close - reference_close, reference_close)

        return self._clamp(raw_return * 10.0, -1.0, 1.0)

    def _get_distance_to_ma_feature(self, index: int, window: int) -> float:
        start = max(0, index - window + 1)
        closes = [c.close for c in self.candles[start : index + 1]]

        if not closes:
            return 0.0

        moving_average = sum(closes) / len(closes)
        distance = self._safe_ratio(self.candles[index].close - moving_average, moving_average)

        return self._clamp(distance * 10.0, -1.0, 1.0)

    def _get_range_position_feature(self, index: int, window: int) -> float:
        start = max(0, index - window + 1)
        window_candles = self.candles[start : index + 1]

        if not window_candles:
            return 0.0

        highest = max(c.high for c in window_candles)
        lowest = min(c.low for c in window_candles)
        span = highest - lowest

        if span <= 0.0:
            return 0.0

        pos_01 = (self.candles[index].close - lowest) / span
        centered = (pos_01 - 0.5) * 2.0

        return self._clamp(centered, -1.0, 1.0)

    def _get_vol_ratio_feature(self, index: int, short_window: int, long_window: int) -> float:
        short_returns = self._get_recent_returns(index=index, window=short_window)
        long_returns = self._get_recent_returns(index=index, window=long_window)

        if not short_returns or not long_returns:
            return 0.0

        short_vol = pstdev(short_returns) if len(short_returns) > 1 else 0.0
        long_vol = pstdev(long_returns) if len(long_returns) > 1 else 0.0

        if long_vol <= 0.0:
            return 0.0

        ratio = short_vol / long_vol

        # Center around 1.0 so "similar volatility" becomes 0.0.
        centered = ratio - 1.0

        return self._clamp(centered, -1.0, 1.0)

    def _get_recent_returns(self, index: int, window: int) -> list[float]:
        if index <= 0:
            return []

        start = max(1, index - window + 1)
        returns: list[float] = []

        for i in range(start, index + 1):
            prev_close = self.candles[i - 1].close
            curr_close = self.candles[i].close
            returns.append(self._safe_ratio(curr_close - prev_close, prev_close))

        return returns

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