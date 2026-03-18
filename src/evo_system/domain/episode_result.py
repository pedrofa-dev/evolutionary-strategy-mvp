from dataclasses import dataclass


@dataclass(frozen=True)
class EpisodeResult:
    profit: float
    drawdown: float
    cost: float
    stability: float