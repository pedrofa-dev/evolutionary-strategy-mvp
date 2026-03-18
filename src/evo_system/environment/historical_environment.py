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
        in_position = False
        entry_price = 0.0
        profit = 0.0
        trades = 0

        for candle in self.candles:
            normalized_price = self._normalize_price(candle.close)

            # Open position
            if not in_position and normalized_price > agent.genome.threshold_open:
                in_position = True
                entry_price = candle.close
                continue

            # Close position
            if in_position and normalized_price < agent.genome.threshold_close:
                profit += candle.close - entry_price
                in_position = False
                trades += 1

        # Close at end if still open
        if in_position:
            last_price = self.candles[-1].close
            profit += last_price - entry_price
            trades += 1

        cost = trades * 0.01
        stability = 1.0 if trades <= 1 else 1.0 / trades

        return EpisodeResult(
            profit=profit,
            drawdown=0.0,
            cost=cost,
            stability=stability,
        )

    def _normalize_price(self, price: float) -> float:
        if self.max_close == self.min_close:
            return 0.5

        return (price - self.min_close) / (self.max_close - self.min_close)