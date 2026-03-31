from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def parse_iso8601_to_millis(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def add_common_download_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbol", required=True, help="Example: BTC/USDT")
    parser.add_argument("--timeframe", required=True, help="Example: 1h")
    parser.add_argument(
        "--start",
        required=True,
        help="Example: 2025-01-01T00:00:00+00:00",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="Example: 2025-04-01T00:00:00+00:00",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Candles per request")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/market_data"),
        help=(
            "Root directory for downloaded market files. "
            "Default: data/market_data."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download OHLCV data into monthly CSV files.",
    )
    subparsers = parser.add_subparsers(dest="market", required=True)

    spot_parser = subparsers.add_parser(
        "spot",
        help="Download Binance spot OHLCV data.",
        description="Download Binance spot OHLCV data into monthly CSV files.",
    )
    add_common_download_arguments(spot_parser)
    spot_parser.set_defaults(mode_label="spot")

    futures_parser = subparsers.add_parser(
        "futures",
        help="Download Binance USD-M Futures OHLCV data.",
        description="Download Binance USD-M Futures OHLCV data into monthly CSV files.",
    )
    add_common_download_arguments(futures_parser)
    futures_parser.set_defaults(mode_label="futures")

    return parser


def build_download_request(args: argparse.Namespace):
    from evo_system.data_ingestion.downloader import DownloadRequest

    return DownloadRequest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_ms=parse_iso8601_to_millis(args.start),
        end_ms=parse_iso8601_to_millis(args.end),
        limit=args.limit,
    )


def run_download(args: argparse.Namespace) -> int:
    from evo_system.data_ingestion.downloader import OhlcvDownloader
    from evo_system.data_ingestion.providers.ccxt_binance_provider import (
        CcxtBinanceProvider,
    )
    from evo_system.data_ingestion.providers.ccxt_binance_usdm_futures_provider import (
        CcxtBinanceUsdmFuturesProvider,
    )
    from evo_system.data_ingestion.storage.csv_storage import CsvStorage

    request = build_download_request(args)

    if args.market == "futures":
        provider = CcxtBinanceUsdmFuturesProvider()
        completion_label = "Futures"
    else:
        provider = CcxtBinanceProvider()
        completion_label = "Spot"

    storage = CsvStorage()
    downloader = OhlcvDownloader(
        provider=provider,
        storage=storage,
        raw_data_dir=args.output_root,
        market_type=args.market,
    )
    rows = downloader.download(request)
    print(
        f"{completion_label} download completed. "
        f"Rows processed: {rows} | output_root={args.output_root}"
    )
    return rows


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_download(args)
