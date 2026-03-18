import csv

from evo_system.domain.historical_candle import HistoricalCandle


def load_historical_candles(csv_path: str) -> list[HistoricalCandle]:
    candles: list[HistoricalCandle] = []

    with open(csv_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            candle = HistoricalCandle(
                timestamp=str(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
            candles.append(candle)

    return candles