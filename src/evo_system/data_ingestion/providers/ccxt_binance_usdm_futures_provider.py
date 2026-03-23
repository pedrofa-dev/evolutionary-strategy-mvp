from __future__ import annotations

import time

import ccxt

from evo_system.data_ingestion.providers.base import OhlcvProvider


class CcxtBinanceUsdmFuturesProvider(OhlcvProvider):
    def __init__(
        self,
        rate_limit_ms: int = 300,
        default_limit: int = 1000,
    ) -> None:
        self.rate_limit_ms = rate_limit_ms
        self.default_limit = default_limit

        self.exchange = ccxt.binance(
            {
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",
                },
            }
        )
        self.exchange.load_markets()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since_ms: int,
        limit: int,
    ) -> list[list]:
        effective_limit = limit or self.default_limit

        candles = self.exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=since_ms,
            limit=effective_limit,
        )

        time.sleep(self.rate_limit_ms / 1000)
        return candles