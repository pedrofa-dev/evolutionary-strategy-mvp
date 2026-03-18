from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalCandle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float