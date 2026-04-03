from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evo_system.domain.genome import Genome
from evo_system.experimental_space.base import DecisionPolicy, EntryDecision, ExitDecision


@dataclass(frozen=True)
class DefaultDecisionPolicy(DecisionPolicy):
    """Canonical active decision policy for policy_v2 genomes.

    Responsibility boundary:
    - This component consumes normalized signal families plus genome blocks and
      turns them into entry/exit decisions.
    - It must not own signal derivation, mutation behavior, or evaluator rules.

    Compatibility constraint:
    - Its outputs must remain functionally equivalent to the previous runtime
      decision helpers so existing runs stay reproducible.
    """

    name: str = "policy_v2_default"

    def get_entry_trigger_score(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> float:
        trigger = genome.entry_trigger
        return (
            trigger.trend_weight * signal_families["trend"]
            + trigger.momentum_weight * signal_families["momentum"]
            + trigger.breakout_weight * signal_families["breakout"]
            + trigger.range_weight * signal_families["range"]
            + trigger.volatility_weight * signal_families["volatility"]
        )

    def passes_entry_context(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
    ) -> bool:
        context = genome.entry_context
        return (
            signal_families["trend"] >= context.min_trend_strength
            and signal_families["breakout"] >= context.min_breakout_strength
            and signal_families["realized_volatility"] >= context.min_realized_volatility
            and signal_families["realized_volatility"] <= context.max_realized_volatility
            and signal_families["range"] >= context.allowed_range_position_min
            and signal_families["range"] <= context.allowed_range_position_max
        )

    def passes_entry_trigger(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
    ) -> bool:
        if not self._has_trigger_weights(genome):
            return genome.entry_trigger.entry_score_threshold <= 0.0

        positive_family_count = sum(
            1
            for key in ("trend", "momentum", "breakout", "range", "volatility")
            if signal_families[key] > 0.0
        )
        trend_or_breakout_ok = (
            not genome.entry_trigger.require_trend_or_breakout
            or signal_families["trend"] > 0.0
            or signal_families["breakout"] > 0.0
        )

        return (
            trigger_score >= genome.entry_trigger.entry_score_threshold
            and positive_family_count >= genome.entry_trigger.min_positive_families
            and trend_or_breakout_ok
        )

    def should_enter(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
        regime_filter_ok: bool,
    ) -> bool:
        return (
            regime_filter_ok
            and self.passes_entry_context(
                environment=environment,
                genome=genome,
                signal_families=signal_families,
            )
            and self.passes_entry_trigger(
                environment=environment,
                genome=genome,
                signal_families=signal_families,
                trigger_score=trigger_score,
            )
        )

    def should_exit(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        trigger_score: float,
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> bool:
        return self.evaluate_exit(
            environment=environment,
            genome=genome,
            signal_families=signal_families,
            normalized_momentum=normalized_momentum,
            trade_return=trade_return,
            holding_bars=holding_bars,
        ).should_close

    def evaluate_entry(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        regime_filter_ok: bool,
    ) -> EntryDecision:
        trigger_score = self.get_entry_trigger_score(
            environment=environment,
            genome=genome,
            signal_families=signal_families,
        )
        context_ok = self.passes_entry_context(
            environment=environment,
            genome=genome,
            signal_families=signal_families,
        )
        trigger_ok = self.passes_entry_trigger(
            environment=environment,
            genome=genome,
            signal_families=signal_families,
            trigger_score=trigger_score,
        )
        return EntryDecision(
            trigger_score=trigger_score,
            context_ok=context_ok,
            trigger_ok=trigger_ok,
            regime_filter_ok=regime_filter_ok,
            should_enter=regime_filter_ok and context_ok and trigger_ok,
        )

    def evaluate_exit(
        self,
        *,
        environment: Any,
        genome: Genome,
        signal_families: dict[str, float],
        normalized_momentum: float,
        trade_return: float,
        holding_bars: int,
    ) -> ExitDecision:
        trigger_score = self.get_entry_trigger_score(
            environment=environment,
            genome=genome,
            signal_families=signal_families,
        )
        hit_stop_loss = trade_return <= -genome.exit_policy.stop_loss_pct
        hit_take_profit = trade_return >= genome.exit_policy.take_profit_pct

        min_holding_ok = holding_bars >= genome.trade_control.min_holding_bars
        should_close_by_score = (
            min_holding_ok
            and trigger_score <= genome.exit_policy.exit_score_threshold
        )
        should_close_on_reversal = (
            min_holding_ok
            and genome.exit_policy.exit_on_signal_reversal
            and (
                signal_families["trend"] < 0.0
                or signal_families["momentum"] < 0.0
                or trigger_score < 0.0
            )
        )
        should_close_on_holding_limit = (
            genome.exit_policy.max_holding_bars > 0
            and holding_bars >= genome.exit_policy.max_holding_bars
        )
        should_close = (
            hit_stop_loss
            or hit_take_profit
            or should_close_by_score
            or should_close_on_reversal
            or should_close_on_holding_limit
        )

        if genome.use_exit_momentum:
            should_close = should_close or (
                min_holding_ok
                and normalized_momentum <= genome.exit_momentum_threshold
            )

        return ExitDecision(
            hit_stop_loss=hit_stop_loss,
            hit_take_profit=hit_take_profit,
            should_close_by_score=should_close_by_score,
            should_close_on_reversal=should_close_on_reversal,
            should_close_on_holding_limit=should_close_on_holding_limit,
            should_close=should_close,
        )

    @staticmethod
    def _has_trigger_weights(genome: Genome) -> bool:
        trigger = genome.entry_trigger
        return any(
            weight != 0.0
            for weight in (
                trigger.trend_weight,
                trigger.momentum_weight,
                trigger.breakout_weight,
                trigger.range_weight,
                trigger.volatility_weight,
            )
        )
