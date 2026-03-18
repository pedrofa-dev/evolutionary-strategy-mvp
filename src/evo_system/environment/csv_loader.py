import csv

from evo_system.domain.historical_candle import HistoricalCandle


def load_historical_candles(csv_path: str) -> list[HistoricalCandle]:
    candles: list[HistoricalCandle] = []

    with open(csv_path, "r", encoding="utf-8") as file:
        reader = csv.reader(file)

        for row in reader:
            candle = HistoricalCandle(
                timestamp=str(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
            )
            candles.append(candle)

    return candles