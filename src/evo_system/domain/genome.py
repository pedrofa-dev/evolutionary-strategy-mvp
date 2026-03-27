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

    # Legacy signal fields kept for backward compatibility with the current
    # environment, mutator and tests.
    use_momentum: bool = False
    momentum_threshold: float = 0.0
    use_trend: bool = False
    trend_threshold: float = 0.0
    trend_window: int = 5
    use_exit_momentum: bool = False
    exit_momentum_threshold: float = 0.0

    # New feature-oriented fields for phase 4.
    ret_short_window: int = 3
    ret_mid_window: int = 12
    ma_window: int = 20
    range_window: int = 20
    vol_short_window: int = 5
    vol_long_window: int = 20

    weight_ret_short: float = 0.0
    weight_ret_mid: float = 0.0
    weight_dist_ma: float = 0.0
    weight_range_pos: float = 0.0
    weight_vol_ratio: float = 0.0
    weight_trend_strength: float = 0.0
    weight_realized_volatility: float = 0.0
    weight_trend_long: float = 0.0
    weight_breakout: float = 0.0

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

        if self.ret_short_window <= 0:
            raise ValueError("ret_short_window must be greater than 0")

        if self.ret_mid_window <= 0:
            raise ValueError("ret_mid_window must be greater than 0")

        if self.ma_window <= 0:
            raise ValueError("ma_window must be greater than 0")

        if self.range_window <= 0:
            raise ValueError("range_window must be greater than 0")

        if self.vol_short_window <= 0:
            raise ValueError("vol_short_window must be greater than 0")

        if self.vol_long_window <= 0:
            raise ValueError("vol_long_window must be greater than 0")

        if self.ret_short_window >= self.ret_mid_window:
            raise ValueError("ret_short_window must be less than ret_mid_window")

        if self.vol_short_window >= self.vol_long_window:
            raise ValueError("vol_short_window must be less than vol_long_window")

        self._validate_weight(self.weight_ret_short, "weight_ret_short")
        self._validate_weight(self.weight_ret_mid, "weight_ret_mid")
        self._validate_weight(self.weight_dist_ma, "weight_dist_ma")
        self._validate_weight(self.weight_range_pos, "weight_range_pos")
        self._validate_weight(self.weight_vol_ratio, "weight_vol_ratio")
        self._validate_weight(self.weight_trend_strength, "weight_trend_strength")
        self._validate_weight(
            self.weight_realized_volatility,
            "weight_realized_volatility",
        )
        self._validate_weight(self.weight_trend_long, "weight_trend_long")
        self._validate_weight(self.weight_breakout, "weight_breakout")

    @staticmethod
    def _validate_weight(value: float, field_name: str) -> None:
        if not -3.0 <= value <= 3.0:
            raise ValueError(f"{field_name} must be between -3.0 and 3.0")

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
            ret_short_window=int(data.get("ret_short_window", 3)),
            ret_mid_window=int(data.get("ret_mid_window", 12)),
            ma_window=int(data.get("ma_window", 20)),
            range_window=int(data.get("range_window", 20)),
            vol_short_window=int(data.get("vol_short_window", 5)),
            vol_long_window=int(data.get("vol_long_window", 20)),
            weight_ret_short=float(data.get("weight_ret_short", 0.0)),
            weight_ret_mid=float(data.get("weight_ret_mid", 0.0)),
            weight_dist_ma=float(data.get("weight_dist_ma", 0.0)),
            weight_range_pos=float(data.get("weight_range_pos", 0.0)),
            weight_vol_ratio=float(data.get("weight_vol_ratio", 0.0)),
            weight_trend_strength=float(data.get("weight_trend_strength", 0.0)),
            weight_realized_volatility=float(
                data.get("weight_realized_volatility", 0.0)
            ),
            weight_trend_long=float(data.get("weight_trend_long", 0.0)),
            weight_breakout=float(data.get("weight_breakout", 0.0)),
        )
        genome.validate()
        return genome

    def copy_with(self, **changes: Any) -> "Genome":
        data = self.to_dict()
        data.update(changes)
        return self.from_dict(data)
