from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from evo_system.data_ingestion.providers.base import OhlcvProvider
from evo_system.data_ingestion.storage.csv_storage import CsvStorage
from evo_system.data_ingestion.utils import (
    candles_to_dataframe,
    month_key_from_millis,
    sanitize_symbol,
)


@dataclass(frozen=True)
class DownloadRequest:
    symbol: str
    timeframe: str
    start_ms: int
    end_ms: int
    limit: int = 1000


class OhlcvDownloader:
    def __init__(
        self,
        provider: OhlcvProvider,
        storage: CsvStorage,
        raw_data_dir: Path = Path("data/market_data"),
        market_type: str = "spot",
    ) -> None:
        self.provider = provider
        self.storage = storage
        self.raw_data_dir = raw_data_dir
        self.market_type = market_type

    def download(self, request: DownloadRequest) -> int:
        total_rows = 0
        current_since = request.start_ms

        while current_since < request.end_ms:
            candles = self.provider.fetch_ohlcv(
                symbol=request.symbol,
                timeframe=request.timeframe,
                since_ms=current_since,
                limit=request.limit,
            )

            if not candles:
                break

            batch_df = candles_to_dataframe(candles)
            if batch_df.empty:
                break

            batch_df = batch_df[batch_df["timestamp"] < request.end_ms]
            if batch_df.empty:
                break

            self._store_batch_by_month(
                symbol=request.symbol,
                timeframe=request.timeframe,
                batch_df=batch_df,
            )

            total_rows += len(batch_df)

            last_timestamp = int(batch_df["timestamp"].max())
            next_since = last_timestamp + 1

            if next_since <= current_since:
                break

            current_since = next_since

        return total_rows

    def _store_batch_by_month(
        self,
        symbol: str,
        timeframe: str,
        batch_df: pd.DataFrame,
    ) -> None:
        clean_symbol = sanitize_symbol(symbol)

        working_df = batch_df.copy()
        working_df["month_key"] = working_df["timestamp"].apply(month_key_from_millis)

        for month_key, month_df in working_df.groupby("month_key"):
            output_path = (
                self.raw_data_dir
                / self.market_type
                / clean_symbol
                / timeframe
                / f"{clean_symbol}-{timeframe}-{month_key}.csv"
            )

            self.storage.save_dataframe_merge_dedup(
                output_path,
                month_df.drop(columns=["month_key"]).copy(),
            )
