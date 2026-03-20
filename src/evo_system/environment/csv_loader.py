import csv
from pathlib import Path

from evo_system.domain.historical_candle import HistoricalCandle


def load_historical_candles(path: str | Path) -> list[HistoricalCandle]:
    candles: list[HistoricalCandle] = []

    with open(path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            candles.append(
                HistoricalCandle(
                    timestamp=str(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                )
            )

    if not candles:
        raise ValueError(f"No candles found in dataset: {path}")

    return candles