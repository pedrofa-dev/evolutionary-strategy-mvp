from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evo_system.experimental_space.base import SignalPack


POLICY_V21_FEATURE_NAMES = (
    "trend_strength_medium",
    "trend_strength_long",
    "momentum_short",
    "momentum_persistence",
    "breakout_strength_medium",
    "range_position_medium",
    "realized_volatility_medium",
    "volatility_ratio_short_long",
)

POLICY_V21_FAMILY_NAMES = (
    "trend",
    "momentum",
    "breakout",
    "range",
    "volatility",
    "realized_volatility",
)


@dataclass(frozen=True)
class DefaultSignalPack(SignalPack):
    """Canonical active signal pack for policy_v2.1.

    Why it exists:
    - This pack owns the derived signal definitions consumed by decision logic.
    - It centralizes feature and family construction so the environment no
      longer owns the active signal semantics directly.

    Constraints:
    - It must not change evaluator, mutation, scoring, or persistence rules.
    - Its outputs must remain bit-for-bit compatible with the previous runtime
      behavior for the same inputs.
    """

    name: str = "policy_v21_default"
    feature_names: tuple[str, ...] = POLICY_V21_FEATURE_NAMES
    family_names: tuple[str, ...] = POLICY_V21_FAMILY_NAMES

    def build_signal_features(self, *, environment: Any, **kwargs: Any) -> dict[str, float]:
        index = kwargs["index"]
        normalized_momentum = kwargs["normalized_momentum"]
        normalized_trend = kwargs["normalized_trend"]
        ret_short_series = kwargs["ret_short_series"]
        ret_mid_series = kwargs["ret_mid_series"]
        range_position_series = kwargs["range_position_series"]
        vol_ratio_series = kwargs["vol_ratio_series"]
        trend_strength_series = kwargs["trend_strength_series"]
        realized_volatility_series = kwargs["realized_volatility_series"]
        trend_long_series = kwargs["trend_long_series"]
        breakout_series = kwargs["breakout_series"]

        return {
            "trend_strength_medium": trend_strength_series[index],
            "trend_strength_long": trend_long_series[index],
            "momentum_short": self._clamp(
                (
                    ret_short_series[index]
                    + self._clamp(normalized_momentum * 10.0, -1.0, 1.0)
                )
                / 2.0,
                -1.0,
                1.0,
            ),
            "momentum_persistence": ret_mid_series[index],
            "breakout_strength_medium": breakout_series[index],
            "range_position_medium": range_position_series[index],
            "realized_volatility_medium": realized_volatility_series[index],
            "volatility_ratio_short_long": vol_ratio_series[index],
        }

    def build_signal_families(
        self,
        *,
        environment: Any,
        signal_features: dict[str, float],
    ) -> dict[str, float]:
        return {
            "trend": self._clamp(
                (
                    signal_features["trend_strength_medium"]
                    + signal_features["trend_strength_long"]
                )
                / 2.0,
                -1.0,
                1.0,
            ),
            "momentum": self._clamp(
                (
                    signal_features["momentum_short"]
                    + signal_features["momentum_persistence"]
                )
                / 2.0,
                -1.0,
                1.0,
            ),
            "breakout": signal_features["breakout_strength_medium"],
            "range": signal_features["range_position_medium"],
            "volatility": self._clamp(
                (
                    -signal_features["realized_volatility_medium"]
                    - signal_features["volatility_ratio_short_long"]
                )
                / 2.0,
                -1.0,
                1.0,
            ),
            "realized_volatility": signal_features["realized_volatility_medium"],
        }

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
