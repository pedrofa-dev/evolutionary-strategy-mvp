from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

CSV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def parse_iso8601_to_millis(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def millis_to_utc_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def month_key_from_millis(value: int) -> str:
    dt = millis_to_utc_datetime(value)
    return f"{dt.year:04d}-{dt.month:02d}"


def sanitize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace(":", "").upper()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def candles_to_dataframe(candles: Iterable[list]) -> pd.DataFrame:
    df = pd.DataFrame(candles, columns=CSV_COLUMNS)
    if df.empty:
        return df

    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    df = df.reset_index(drop=True)
    return df