from __future__ import annotations

from dataclasses import dataclass

from evo_system.experimental_space.base import MarketMode


FLAT_POSITION = "flat"
LONG_POSITION = "long"
SHORT_POSITION = "short"
POSITION_STATES = (
    FLAT_POSITION,
    LONG_POSITION,
    SHORT_POSITION,
)
SUPPORTED_V1_LEVERAGE = 1.0


def _validate_position_state(position: str) -> None:
    if position not in POSITION_STATES:
        raise ValueError(f"Unsupported position state: {position}")


def _validate_v1_leverage(*, leverage: float, market_mode_name: str) -> None:
    if leverage <= 0.0:
        raise ValueError("leverage must be greater than 0.0")
    if leverage != SUPPORTED_V1_LEVERAGE:
        raise ValueError(
            f"{market_mode_name} currently supports leverage={SUPPORTED_V1_LEVERAGE} only"
        )


@dataclass(frozen=True)
class SpotMarketMode(MarketMode):
    """Canonical spot execution mode.

    Why it exists:
    - This component makes current long-only spot semantics explicit.
    - It is the compatibility anchor for the pre-market-mode runtime.

    v1 assumptions:
    - Spot remains flat/long/flat only.
    - Leverage is explicitly part of the runtime model for architectural
      stability, but spot v1 only accepts leverage=1.0.
    """

    name: str = "spot"
    flat_position: str = FLAT_POSITION
    supported_positions: tuple[str, ...] = POSITION_STATES

    def get_default_entry_position(self) -> str:
        return LONG_POSITION

    def can_transition(self, current_position: str, next_position: str) -> bool:
        _validate_position_state(current_position)
        _validate_position_state(next_position)
        allowed = {
            FLAT_POSITION: {LONG_POSITION},
            LONG_POSITION: {FLAT_POSITION},
            SHORT_POSITION: set(),
        }
        return next_position in allowed[current_position]

    def validate_runtime_config(self, *, leverage: float) -> None:
        _validate_v1_leverage(leverage=leverage, market_mode_name=self.name)

    def calculate_trade_return(
        self,
        *,
        entry_price: float,
        current_price: float,
        position: str,
    ) -> float:
        if entry_price <= 0.0:
            return 0.0
        if position == LONG_POSITION:
            return (current_price - entry_price) / entry_price
        if position == SHORT_POSITION:
            raise ValueError("spot does not support short positions")
        return 0.0

    def close_trade(
        self,
        *,
        trade_return: float,
        position_size: float,
        trade_cost_rate: float,
        position: str,
        leverage: float,
    ) -> tuple[float, float]:
        self.validate_runtime_config(leverage=leverage)
        if position != LONG_POSITION:
            return 0.0, 0.0
        gross_profit = trade_return * position_size
        trade_cost = trade_cost_rate * position_size
        net_profit = gross_profit - trade_cost
        return net_profit, trade_cost


@dataclass(frozen=True)
class FuturesMarketMode(MarketMode):
    """Futures scaffold for market semantics v1.

    Why it exists:
    - The core now needs an explicit home for long/short semantics even before
      full futures execution is enabled.
    - This leaves the runtime ready for later futures expansion without
      spreading branchy spot assumptions across the environment.

    v1 assumptions:
    - Futures v1 accepts leverage=1.0 only.
    - Funding, maintenance margin, liquidation, and cross/isolated margin are
      intentionally not implemented yet.

    Future extension point:
    - Funding belongs to a future CostModel extension.
    - Maintenance margin and liquidation belong to a future RiskModel
      extension.
    - Higher leverage belongs to future market-mode-aware execution once the
      cost and risk layers exist explicitly.
    """

    name: str = "futures"
    flat_position: str = FLAT_POSITION
    supported_positions: tuple[str, ...] = POSITION_STATES

    def get_default_entry_position(self) -> str:
        # v1 keeps entry direction aligned with current policy behavior. Future
        # DecisionPolicy variants may request SHORT_POSITION explicitly.
        return LONG_POSITION

    def can_transition(self, current_position: str, next_position: str) -> bool:
        _validate_position_state(current_position)
        _validate_position_state(next_position)
        allowed = {
            FLAT_POSITION: {LONG_POSITION, SHORT_POSITION},
            LONG_POSITION: {FLAT_POSITION},
            SHORT_POSITION: {FLAT_POSITION},
        }
        return next_position in allowed[current_position]

    def validate_runtime_config(self, *, leverage: float) -> None:
        _validate_v1_leverage(leverage=leverage, market_mode_name=self.name)

    def calculate_trade_return(
        self,
        *,
        entry_price: float,
        current_price: float,
        position: str,
    ) -> float:
        if entry_price <= 0.0:
            return 0.0
        if position == LONG_POSITION:
            return (current_price - entry_price) / entry_price
        if position == SHORT_POSITION:
            return (entry_price - current_price) / entry_price
        return 0.0

    def close_trade(
        self,
        *,
        trade_return: float,
        position_size: float,
        trade_cost_rate: float,
        position: str,
        leverage: float,
    ) -> tuple[float, float]:
        self.validate_runtime_config(leverage=leverage)
        if position not in {LONG_POSITION, SHORT_POSITION}:
            return 0.0, 0.0
        gross_profit = trade_return * position_size * leverage
        trade_cost = trade_cost_rate * position_size
        net_profit = gross_profit - trade_cost
        return net_profit, trade_cost
