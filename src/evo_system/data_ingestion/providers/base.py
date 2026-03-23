from __future__ import annotations

from abc import ABC, abstractmethod


class OhlcvProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
        limit: int,
    ) -> list[list]:
        """
        Return candles in this format:
        [timestamp, open, high, low, close, volume]
        """
        raise NotImplementedError