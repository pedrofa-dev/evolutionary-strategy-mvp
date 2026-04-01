from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class EntryContextGene:
    min_trend_strength: float = -1.0
    min_breakout_strength: float = -1.0
    min_realized_volatility: float = -1.0
    max_realized_volatility: float = 1.0
    allowed_range_position_min: float = -1.0
    allowed_range_position_max: float = 1.0

    def validate(self) -> None:
        for field_name, value in (
            ("min_trend_strength", self.min_trend_strength),
            ("min_breakout_strength", self.min_breakout_strength),
            ("min_realized_volatility", self.min_realized_volatility),
            ("max_realized_volatility", self.max_realized_volatility),
            ("allowed_range_position_min", self.allowed_range_position_min),
            ("allowed_range_position_max", self.allowed_range_position_max),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")

        if self.min_trend_strength < -1.0 or self.min_trend_strength > 1.0:
            raise ValueError("min_trend_strength must be between -1.0 and 1.0")

        if self.min_breakout_strength < -1.0 or self.min_breakout_strength > 1.0:
            raise ValueError("min_breakout_strength must be between -1.0 and 1.0")

        if self.min_realized_volatility < -1.0 or self.min_realized_volatility > 1.0:
            raise ValueError("min_realized_volatility must be between -1.0 and 1.0")

        if self.max_realized_volatility < -1.0 or self.max_realized_volatility > 1.0:
            raise ValueError("max_realized_volatility must be between -1.0 and 1.0")

        if self.allowed_range_position_min < -1.0 or self.allowed_range_position_min > 1.0:
            raise ValueError("allowed_range_position_min must be between -1.0 and 1.0")

        if self.allowed_range_position_max < -1.0 or self.allowed_range_position_max > 1.0:
            raise ValueError("allowed_range_position_max must be between -1.0 and 1.0")

        if self.allowed_range_position_min > self.allowed_range_position_max:
            raise ValueError(
                "allowed_range_position_min must be less than or equal to allowed_range_position_max"
            )

        if self.min_realized_volatility > self.max_realized_volatility:
            raise ValueError(
                "min_realized_volatility must be less than or equal to max_realized_volatility"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryContextGene":
        gene = cls(
            min_trend_strength=float(data.get("min_trend_strength", -1.0)),
            min_breakout_strength=float(data.get("min_breakout_strength", -1.0)),
            min_realized_volatility=float(data.get("min_realized_volatility", -1.0)),
            max_realized_volatility=float(data.get("max_realized_volatility", 1.0)),
            allowed_range_position_min=float(data.get("allowed_range_position_min", -1.0)),
            allowed_range_position_max=float(data.get("allowed_range_position_max", 1.0)),
        )
        gene.validate()
        return gene


@dataclass(frozen=True)
class EntryTriggerGene:
    trend_weight: float = 0.0
    momentum_weight: float = 0.0
    breakout_weight: float = 0.0
    range_weight: float = 0.0
    volatility_weight: float = 0.0
    entry_score_threshold: float = 0.5
    min_positive_families: int = 1
    require_trend_or_breakout: bool = False

    def validate(self) -> None:
        for field_name, value in (
            ("trend_weight", self.trend_weight),
            ("momentum_weight", self.momentum_weight),
            ("breakout_weight", self.breakout_weight),
            ("range_weight", self.range_weight),
            ("volatility_weight", self.volatility_weight),
            ("entry_score_threshold", self.entry_score_threshold),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")

        for field_name, value in (
            ("trend_weight", self.trend_weight),
            ("momentum_weight", self.momentum_weight),
            ("breakout_weight", self.breakout_weight),
            ("range_weight", self.range_weight),
            ("volatility_weight", self.volatility_weight),
        ):
            if value < -3.0 or value > 3.0:
                raise ValueError(f"{field_name} must be between -3.0 and 3.0")

        if self.entry_score_threshold < -5.0 or self.entry_score_threshold > 5.0:
            raise ValueError("entry_score_threshold must be between -5.0 and 5.0")

        if type(self.min_positive_families) is not int or self.min_positive_families < 0:
            raise ValueError("min_positive_families must be an integer greater than or equal to 0")

        if self.min_positive_families > 5:
            raise ValueError("min_positive_families cannot exceed the number of signal families")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryTriggerGene":
        gene = cls(
            trend_weight=float(data.get("trend_weight", 0.0)),
            momentum_weight=float(data.get("momentum_weight", 0.0)),
            breakout_weight=float(data.get("breakout_weight", 0.0)),
            range_weight=float(data.get("range_weight", 0.0)),
            volatility_weight=float(data.get("volatility_weight", 0.0)),
            entry_score_threshold=float(data.get("entry_score_threshold", 0.5)),
            min_positive_families=int(data.get("min_positive_families", 1)),
            require_trend_or_breakout=bool(data.get("require_trend_or_breakout", False)),
        )
        gene.validate()
        return gene


@dataclass(frozen=True)
class ExitPolicyGene:
    exit_score_threshold: float = 0.1
    exit_on_signal_reversal: bool = False
    max_holding_bars: int = 0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10

    def validate(self) -> None:
        for field_name, value in (
            ("exit_score_threshold", self.exit_score_threshold),
            ("stop_loss_pct", self.stop_loss_pct),
            ("take_profit_pct", self.take_profit_pct),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")

        if self.exit_score_threshold < -5.0 or self.exit_score_threshold > 5.0:
            raise ValueError("exit_score_threshold must be between -5.0 and 5.0")

        if type(self.max_holding_bars) is not int or self.max_holding_bars < 0:
            raise ValueError("max_holding_bars must be an integer greater than or equal to 0")

        if not 0.0 < self.stop_loss_pct <= 1.0:
            raise ValueError("stop_loss_pct must be between 0.0 and 1.0")

        if not 0.0 < self.take_profit_pct <= 2.0:
            raise ValueError("take_profit_pct must be between 0.0 and 2.0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExitPolicyGene":
        gene = cls(
            exit_score_threshold=float(data.get("exit_score_threshold", 0.1)),
            exit_on_signal_reversal=bool(data.get("exit_on_signal_reversal", False)),
            max_holding_bars=int(data.get("max_holding_bars", 0)),
            stop_loss_pct=float(data.get("stop_loss_pct", 0.05)),
            take_profit_pct=float(data.get("take_profit_pct", 0.10)),
        )
        gene.validate()
        return gene


@dataclass(frozen=True)
class TradeControlGene:
    cooldown_bars: int = 0
    min_holding_bars: int = 0
    reentry_block_bars: int = 0

    def validate(self) -> None:
        for field_name, value in (
            ("cooldown_bars", self.cooldown_bars),
            ("min_holding_bars", self.min_holding_bars),
            ("reentry_block_bars", self.reentry_block_bars),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be an integer greater than or equal to 0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeControlGene":
        gene = cls(
            cooldown_bars=int(data.get("cooldown_bars", 0)),
            min_holding_bars=int(data.get("min_holding_bars", 0)),
            reentry_block_bars=int(data.get("reentry_block_bars", 0)),
        )
        gene.validate()
        return gene


@dataclass(frozen=True)
class Genome:
    threshold_open: float
    threshold_close: float
    position_size: float
    stop_loss: float
    take_profit: float
    entry_score_margin: float = 0.0
    min_bars_between_entries: int = 0
    entry_confirmation_bars: int = 1

    # Legacy signal fields kept for backward compatibility with the current
    # environment, reporting layer and persisted genome snapshots.
    use_momentum: bool = False
    momentum_threshold: float = 0.0
    use_trend: bool = False
    trend_threshold: float = 0.0
    trend_window: int = 5
    use_exit_momentum: bool = False
    exit_momentum_threshold: float = 0.0

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

    policy_v2_enabled: bool = False
    entry_context: EntryContextGene | None = None
    entry_trigger: EntryTriggerGene | None = None
    exit_policy: ExitPolicyGene | None = None
    trade_control: TradeControlGene | None = None

    def __post_init__(self) -> None:
        self._synchronize_policy_blocks()
        self.validate()

    def _synchronize_policy_blocks(self) -> None:
        if self.policy_v2_enabled:
            entry_context = self.entry_context or self._build_entry_context_from_legacy()
            entry_trigger = self.entry_trigger or self._build_entry_trigger_from_legacy()
            exit_policy = self.exit_policy or self._build_exit_policy_from_legacy()
            trade_control = self.trade_control or self._build_trade_control_from_legacy()

            entry_context.validate()
            entry_trigger.validate()
            exit_policy.validate()
            trade_control.validate()

            object.__setattr__(self, "entry_context", entry_context)
            object.__setattr__(self, "entry_trigger", entry_trigger)
            object.__setattr__(self, "exit_policy", exit_policy)
            object.__setattr__(self, "trade_control", trade_control)

            # Keep a narrow compatibility mirror for persisted snapshots and
            # evaluation code that still inspects position/take-profit fields.
            object.__setattr__(self, "stop_loss", exit_policy.stop_loss_pct)
            object.__setattr__(self, "take_profit", exit_policy.take_profit_pct)
            return

        object.__setattr__(self, "entry_context", self._build_entry_context_from_legacy())
        object.__setattr__(self, "entry_trigger", self._build_entry_trigger_from_legacy())
        object.__setattr__(self, "exit_policy", self._build_exit_policy_from_legacy())
        object.__setattr__(self, "trade_control", self._build_trade_control_from_legacy())

    def _build_entry_context_from_legacy(self) -> EntryContextGene:
        min_trend_strength = self.trend_threshold if self.use_trend else -1.0
        gene = EntryContextGene(
            min_trend_strength=min_trend_strength,
            min_breakout_strength=-1.0,
            min_realized_volatility=-1.0,
            max_realized_volatility=1.0,
            allowed_range_position_min=-1.0,
            allowed_range_position_max=1.0,
        )
        return gene

    def _build_entry_trigger_from_legacy(self) -> EntryTriggerGene:
        trend_components = [
            self.weight_dist_ma,
            self.weight_trend_strength,
            self.weight_trend_long,
        ]
        momentum_components = [
            self.weight_ret_short,
            self.weight_ret_mid,
        ]
        volatility_components = [
            self.weight_vol_ratio,
            -self.weight_realized_volatility,
        ]

        gene = EntryTriggerGene(
            trend_weight=sum(trend_components) / len(trend_components),
            momentum_weight=sum(momentum_components) / len(momentum_components),
            breakout_weight=self.weight_breakout,
            range_weight=self.weight_range_pos,
            volatility_weight=sum(volatility_components) / len(volatility_components),
            entry_score_threshold=self.threshold_open + self.entry_score_margin,
            min_positive_families=1,
            require_trend_or_breakout=False,
        )
        return gene

    def _build_exit_policy_from_legacy(self) -> ExitPolicyGene:
        gene = ExitPolicyGene(
            exit_score_threshold=self.threshold_close,
            exit_on_signal_reversal=self.use_exit_momentum,
            max_holding_bars=0,
            stop_loss_pct=self.stop_loss,
            take_profit_pct=self.take_profit,
        )
        return gene

    def _build_trade_control_from_legacy(self) -> TradeControlGene:
        gene = TradeControlGene(
            cooldown_bars=self.min_bars_between_entries,
            min_holding_bars=0,
            reentry_block_bars=0,
        )
        return gene

    def validate(self) -> None:
        if not 0.0 < self.position_size <= 1.0:
            raise ValueError("position_size must be between 0.0 and 1.0")

        if not 0.0 < self.stop_loss <= 1.0:
            raise ValueError("stop_loss must be between 0.0 and 1.0")

        if not 0.0 < self.take_profit <= 2.0:
            raise ValueError("take_profit must be between 0.0 and 2.0")

        if not math.isfinite(self.entry_score_margin) or self.entry_score_margin < 0.0:
            raise ValueError(
                "entry_score_margin must be a finite number greater than or equal to 0.0"
            )

        if type(self.min_bars_between_entries) is not int or self.min_bars_between_entries < 0:
            raise ValueError(
                "min_bars_between_entries must be an integer greater than or equal to 0"
            )

        if type(self.entry_confirmation_bars) is not int or self.entry_confirmation_bars < 1:
            raise ValueError(
                "entry_confirmation_bars must be an integer greater than or equal to 1"
            )

        if self.policy_v2_enabled:
            assert self.entry_context is not None
            assert self.entry_trigger is not None
            assert self.exit_policy is not None
            assert self.trade_control is not None
            self.entry_context.validate()
            self.entry_trigger.validate()
            self.exit_policy.validate()
            self.trade_control.validate()
            return

        if not 0.0 <= self.threshold_open <= 5.0:
            raise ValueError("threshold_open must be between 0.0 and 5.0")

        if not -5.0 <= self.threshold_close <= 5.0:
            raise ValueError("threshold_close must be between -5.0 and 5.0")

        if self.threshold_close > self.threshold_open:
            raise ValueError("threshold_close must be less than or equal to threshold_open")

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
            entry_score_margin=float(data.get("entry_score_margin", 0.0)),
            min_bars_between_entries=int(data.get("min_bars_between_entries", 0)),
            entry_confirmation_bars=int(data.get("entry_confirmation_bars", 1)),
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
            policy_v2_enabled=bool(data.get("policy_v2_enabled", False)),
            entry_context=(
                EntryContextGene.from_dict(data["entry_context"])
                if "entry_context" in data and data["entry_context"] is not None
                else None
            ),
            entry_trigger=(
                EntryTriggerGene.from_dict(data["entry_trigger"])
                if "entry_trigger" in data and data["entry_trigger"] is not None
                else None
            ),
            exit_policy=(
                ExitPolicyGene.from_dict(data["exit_policy"])
                if "exit_policy" in data and data["exit_policy"] is not None
                else None
            ),
            trade_control=(
                TradeControlGene.from_dict(data["trade_control"])
                if "trade_control" in data and data["trade_control"] is not None
                else None
            ),
        )
        genome.validate()
        return genome

    def copy_with(self, **changes: Any) -> "Genome":
        data = self.to_dict()
        data.update(changes)
        return self.from_dict(data)


def build_policy_v2_genome(
    *,
    position_size: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    trend_window: int = 5,
    ret_short_window: int = 3,
    ret_mid_window: int = 12,
    ma_window: int = 20,
    range_window: int = 20,
    vol_short_window: int = 5,
    vol_long_window: int = 20,
    entry_context: EntryContextGene | None = None,
    entry_trigger: EntryTriggerGene | None = None,
    exit_policy: ExitPolicyGene | None = None,
    trade_control: TradeControlGene | None = None,
) -> Genome:
    resolved_exit_policy = exit_policy or ExitPolicyGene(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
    )

    return Genome(
        threshold_open=0.0,
        threshold_close=0.0,
        position_size=position_size,
        stop_loss=resolved_exit_policy.stop_loss_pct,
        take_profit=resolved_exit_policy.take_profit_pct,
        trend_window=trend_window,
        ret_short_window=ret_short_window,
        ret_mid_window=ret_mid_window,
        ma_window=ma_window,
        range_window=range_window,
        vol_short_window=vol_short_window,
        vol_long_window=vol_long_window,
        policy_v2_enabled=True,
        entry_context=entry_context or EntryContextGene(),
        entry_trigger=entry_trigger or EntryTriggerGene(),
        exit_policy=resolved_exit_policy,
        trade_control=trade_control or TradeControlGene(),
    )
