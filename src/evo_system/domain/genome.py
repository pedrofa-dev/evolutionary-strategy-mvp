from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Genome:
    threshold_open: float
    threshold_close: float
    position_size: float
    stop_loss: float
    take_profit: float
    use_momentum: bool = False
    momentum_threshold: float = 0.0
    use_trend: bool = False
    trend_threshold: float = 0.0
    trend_window: int = 5
    use_exit_momentum: bool = False
    exit_momentum_threshold: float = 0.0

    def validate(self) -> None:
        if not 0.0 <= self.threshold_open <= 1.0:
            raise ValueError("threshold_open must be between 0.0 and 1.0")

        if not 0.0 <= self.threshold_close <= 1.0:
            raise ValueError("threshold_close must be between 0.0 and 1.0")

        if self.threshold_close > self.threshold_open:
            raise ValueError("threshold_close must be less than or equal to threshold_open")

        if not 0.0 < self.position_size <= 1.0:
            raise ValueError("position_size must be between 0.0 and 1.0")

        if not 0.0 < self.stop_loss <= 1.0:
            raise ValueError("stop_loss must be between 0.0 and 1.0")

        if not 0.0 < self.take_profit <= 2.0:
            raise ValueError("take_profit must be between 0.0 and 2.0")

        if self.trend_window <= 0:
            raise ValueError("trend_window must be greater than 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Genome":
        genome = cls(
            threshold_open=float(data["threshold_open"]),
            threshold_close=float(data["threshold_close"]),
            position_size=float(data["position_size"]),
            stop_loss=float(data["stop_loss"]),
            take_profit=float(data["take_profit"]),
            use_momentum=bool(data.get("use_momentum", False)),
            momentum_threshold=float(data.get("momentum_threshold", 0.0)),
            use_trend=bool(data.get("use_trend", False)),
            trend_threshold=float(data.get("trend_threshold", 0.0)),
            trend_window=int(data.get("trend_window", 5)),
            use_exit_momentum=bool(data.get("use_exit_momentum", False)),
            exit_momentum_threshold=float(data.get("exit_momentum_threshold", 0.0)),
        )
        genome.validate()
        return genome

    def copy_with(self, **changes: Any) -> "Genome":
        data = self.to_dict()
        data.update(changes)
        return self.from_dict(data)