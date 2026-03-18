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
            drawdown=0.0,
            cost=metrics["cost"],
            stability=metrics["stability"],
            trades=metrics["trades"],
        )

    def get_episode_diagnostics(self, agent: Agent) -> dict[str, float | int]:
        in_position = False
        entry_price = 0.0
        profit = 0.0
        trades = 0

        for candle in self.candles:
            normalized_price = self._normalize_price(candle.close)

            if not in_position and normalized_price > agent.genome.threshold_open:
                in_position = True
                entry_price = candle.close
                continue

            if in_position and normalized_price < agent.genome.threshold_close:
                trade_return = (candle.close - entry_price) / entry_price
                profit += trade_return * agent.genome.position_size
                in_position = False
                trades += 1

        if in_position and normalized_price < agent.genome.threshold_close:
            trade_return = (candle.close - entry_price) / entry_price
            profit += trade_return * agent.genome.position_size
            in_position = False
            trades += 1

        cost = trades * 0.01
        stability = 1.0 if trades <= 1 else 1.0 / trades

        return {
            "profit": profit,
            "trades": trades,
            "cost": cost,
            "stability": stability,
        }

    def _normalize_price(self, price: float) -> float:
        if self.max_close == self.min_close:
            return 0.5

        return (price - self.min_close) / (self.max_close - self.min_close)