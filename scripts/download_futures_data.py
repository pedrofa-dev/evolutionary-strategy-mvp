from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evo_system.data_ingestion.downloader import DownloadRequest, OhlcvDownloader
from evo_system.data_ingestion.providers.ccxt_binance_usdm_futures_provider import (
    CcxtBinanceUsdmFuturesProvider,
)
from evo_system.data_ingestion.storage.csv_storage import CsvStorage
from evo_system.data_ingestion.utils import parse_iso8601_to_millis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Binance USD-M Futures OHLCV data into monthly CSV files."
    )
    parser.add_argument("--symbol", required=True, help="Example: BTC/USDT:USDT")
    parser.add_argument("--timeframe", required=True, help="Example: 1h")
    parser.add_argument("--start", required=True, help="Example: 2024-01-01T00:00:00+00:00")
    parser.add_argument("--end", required=True, help="Example: 2025-01-01T00:00:00+00:00")
    parser.add_argument("--limit", type=int, default=1000, help="Candles per request")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    request = DownloadRequest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_ms=parse_iso8601_to_millis(args.start),
        end_ms=parse_iso8601_to_millis(args.end),
        limit=args.limit,
    )

    provider = CcxtBinanceUsdmFuturesProvider()
    storage = CsvStorage()
    downloader = OhlcvDownloader(provider=provider, storage=storage)

    rows = downloader.download(request)
    print(f"Futures download completed. Rows processed: {rows}")


if __name__ == "__main__":
    main()