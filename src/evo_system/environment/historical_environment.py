from evo_system.domain.agent import Agent
from evo_system.domain.episode_result import EpisodeResult
from evo_system.domain.historical_candle import HistoricalCandle


class HistoricalEnvironment:
    """
    Evaluates an agent using historical OHLC data.
    """

    def __init__(self, candles: list[HistoricalCandle]) -> None:
        if not candles:
            raise ValueError("candles cannot be empty")

        self.candles = candles
        self.min_close = min(candle.close for candle in candles)
        self.max_close = max(candle.close for candle in candles)

    def run_episode(self, agent: Agent) -> EpisodeResult:
        metrics = self.get_episode_diagnostics(agent)

        return EpisodeResult(
            profit=metrics["profit"],
            drawdown=metrics["drawdown"],
            cost=metrics["cost"],
            stability=metrics["stability"],
            trades=metrics["trades"],
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

            open_signal = normalized_price > agent.genome.threshold_open

            if agent.genome.use_momentum:
                open_signal = (
                    open_signal
                    and normalized_momentum > agent.genome.momentum_threshold
                )

            if agent.genome.use_trend:
                open_signal = (
                    open_signal
                    and normalized_trend > agent.genome.trend_threshold
                )

            if not in_position and open_signal:
                in_position = True
                entry_price = candle.close
                continue

            if in_position:
                stop_price = entry_price * (1.0 - agent.genome.stop_loss)
                take_price = entry_price * (1.0 + agent.genome.take_profit)

                # Conservative rule:
                # if both are reachable in the same candle, stop loss wins
                if candle.low <= stop_price:
                    trade_return = (stop_price - entry_price) / entry_price
                    realized_profit = trade_return * agent.genome.position_size

                    profit += realized_profit
                    equity += realized_profit
                    peak_equity = max(peak_equity, equity)
                    max_drawdown = max(max_drawdown, peak_equity - equity)

                    in_position = False
                    trades += 1
                    continue

                if candle.high >= take_price:
                    trade_return = (take_price - entry_price) / entry_price
                    realized_profit = trade_return * agent.genome.position_size

                    profit += realized_profit
                    equity += realized_profit
                    peak_equity = max(peak_equity, equity)
                    max_drawdown = max(max_drawdown, peak_equity - equity)

                    in_position = False
                    trades += 1
                    continue

                if (
                    agent.genome.use_exit_momentum
                    and normalized_momentum < agent.genome.exit_momentum_threshold
                ):
                    trade_return = (candle.close - entry_price) / entry_price
                    realized_profit = trade_return * agent.genome.position_size

                    profit += realized_profit
                    equity += realized_profit
                    peak_equity = max(peak_equity, equity)
                    max_drawdown = max(max_drawdown, peak_equity - equity)

                    in_position = False
                    trades += 1
                    continue

                if normalized_price < agent.genome.threshold_close:
                    trade_return = (candle.close - entry_price) / entry_price
                    realized_profit = trade_return * agent.genome.position_size

                    profit += realized_profit
                    equity += realized_profit
                    peak_equity = max(peak_equity, equity)
                    max_drawdown = max(max_drawdown, peak_equity - equity)

                    in_position = False
                    trades += 1

        if in_position:
            last_price = self.candles[-1].close
            trade_return = (last_price - entry_price) / entry_price
            realized_profit = trade_return * agent.genome.position_size

            profit += realized_profit
            equity += realized_profit
            peak_equity = max(peak_equity, equity)
            max_drawdown = max(max_drawdown, peak_equity - equity)

            trades += 1

        cost = trades * 0.01
        stability = 1.0 if trades <= 1 else 1.0 / trades

        return {
            "profit": profit,
            "drawdown": max_drawdown,
            "trades": trades,
            "cost": cost,
            "stability": stability,
        }

    def _normalize_price(self, price: float) -> float:
        if self.max_close == self.min_close:
            return 0.5

        return (price - self.min_close) / (self.max_close - self.min_close)

    def _get_normalized_momentum(self, index: int) -> float:
        if index == 0:
            return 0.0

        previous_close = self.candles[index - 1].close
        current_close = self.candles[index].close

        if previous_close == 0.0:
            return 0.0

        return (current_close - previous_close) / previous_close

    def _get_normalized_trend(self, index: int, window: int) -> float:
        if window <= 0:
            return 0.0

        start_index = max(0, index - window + 1)
        closes = [candle.close for candle in self.candles[start_index:index + 1]]

        if not closes:
            return 0.0

        sma = sum(closes) / len(closes)
        current_close = self.candles[index].close

        if sma == 0.0:
            return 0.0

        return (current_close - sma) / sma