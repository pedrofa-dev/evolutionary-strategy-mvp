import pytest

from evo_system.domain.genome import Genome


def test_genome_to_dict_returns_serializable_data() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    result = genome.to_dict()

    assert result == {
        "threshold_open": 0.8,
        "threshold_close": 0.4,
        "position_size": 0.2,
        "stop_loss": 0.05,
        "take_profit": 0.1,
        "min_bars_between_entries": 0,
        "entry_confirmation_bars": 1,
        "entry_score_margin": 0.0,
        "use_momentum": False,
        "momentum_threshold": 0.0,
        "use_trend": False,
        "trend_threshold": 0.0,
        "trend_window": 5,
        "use_exit_momentum": False,
        "exit_momentum_threshold": 0.0,
        "ret_short_window": 3,
        "ret_mid_window": 12,
        "ma_window": 20,
        "range_window": 20,
        "vol_short_window": 5,
        "vol_long_window": 20,
        "weight_ret_short": 0.0,
        "weight_ret_mid": 0.0,
        "weight_dist_ma": 0.0,
        "weight_range_pos": 0.0,
        "weight_vol_ratio": 0.0,
        "weight_trend_strength": 0.0,
        "weight_realized_volatility": 0.0,
        "weight_trend_long": 0.0,
        "weight_breakout": 0.0,
        "policy_v2_enabled": False,
        "entry_context": {
            "min_trend_strength": -1.0,
            "min_breakout_strength": -1.0,
            "min_realized_volatility": -1.0,
            "max_realized_volatility": 1.0,
            "allowed_range_position_min": -1.0,
            "allowed_range_position_max": 1.0,
        },
        "entry_trigger": {
            "trend_weight": 0.0,
            "momentum_weight": 0.0,
            "breakout_weight": 0.0,
            "range_weight": 0.0,
            "volatility_weight": 0.0,
            "entry_score_threshold": 0.8,
            "min_positive_families": 1,
            "require_trend_or_breakout": False,
        },
        "exit_policy": {
            "exit_score_threshold": 0.4,
            "exit_on_signal_reversal": False,
            "max_holding_bars": 0,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.1,
        },
        "trade_control": {
            "cooldown_bars": 0,
            "min_holding_bars": 0,
            "reentry_block_bars": 0,
        },
    }


def test_genome_from_dict_builds_valid_genome() -> None:
    data = {
        "threshold_open": 0.8,
        "threshold_close": 0.4,
        "position_size": 0.2,
        "stop_loss": 0.05,
        "take_profit": 0.1,
        "min_bars_between_entries": 6,
        "entry_confirmation_bars": 3,
        "entry_score_margin": 0.05,
        "use_momentum": True,
        "momentum_threshold": 0.002,
        "use_trend": True,
        "trend_threshold": 0.003,
        "trend_window": 7,
        "use_exit_momentum": True,
        "exit_momentum_threshold": -0.002,
        "ret_short_window": 4,
        "ret_mid_window": 16,
        "ma_window": 25,
        "range_window": 18,
        "vol_short_window": 6,
        "vol_long_window": 24,
        "weight_ret_short": 0.7,
        "weight_ret_mid": 1.2,
        "weight_dist_ma": -0.4,
        "weight_range_pos": 0.5,
        "weight_vol_ratio": -0.3,
        "weight_trend_strength": 0.6,
        "weight_realized_volatility": -0.2,
        "weight_trend_long": 0.4,
        "weight_breakout": -0.7,
    }

    genome = Genome.from_dict(data)

    assert genome.threshold_open == 0.8
    assert genome.threshold_close == 0.4
    assert genome.position_size == 0.2
    assert genome.stop_loss == 0.05
    assert genome.take_profit == 0.1
    assert genome.min_bars_between_entries == 6
    assert genome.entry_confirmation_bars == 3
    assert genome.entry_score_margin == 0.05
    assert genome.use_momentum is True
    assert genome.momentum_threshold == 0.002
    assert genome.use_trend is True
    assert genome.trend_threshold == 0.003
    assert genome.trend_window == 7
    assert genome.use_exit_momentum is True
    assert genome.exit_momentum_threshold == -0.002
    assert genome.ret_short_window == 4
    assert genome.ret_mid_window == 16
    assert genome.ma_window == 25
    assert genome.range_window == 18
    assert genome.vol_short_window == 6
    assert genome.vol_long_window == 24
    assert genome.weight_ret_short == 0.7
    assert genome.weight_ret_mid == 1.2
    assert genome.weight_dist_ma == -0.4
    assert genome.weight_range_pos == 0.5
    assert genome.weight_vol_ratio == -0.3
    assert genome.weight_trend_strength == 0.6
    assert genome.weight_realized_volatility == -0.2
    assert genome.weight_trend_long == 0.4
    assert genome.weight_breakout == -0.7


def test_genome_from_dict_supports_legacy_data_without_feature_fields() -> None:
    data = {
        "threshold_open": 0.8,
        "threshold_close": 0.4,
        "position_size": 0.2,
        "stop_loss": 0.05,
        "take_profit": 0.1,
        "use_momentum": True,
        "momentum_threshold": 0.002,
        "use_trend": True,
        "trend_threshold": 0.003,
        "trend_window": 7,
    }

    genome = Genome.from_dict(data)

    assert genome.threshold_open == 0.8
    assert genome.threshold_close == 0.4
    assert genome.position_size == 0.2
    assert genome.stop_loss == 0.05
    assert genome.take_profit == 0.1
    assert genome.min_bars_between_entries == 0
    assert genome.entry_confirmation_bars == 1
    assert genome.entry_score_margin == 0.0
    assert genome.use_momentum is True
    assert genome.momentum_threshold == 0.002
    assert genome.use_trend is True
    assert genome.trend_threshold == 0.003
    assert genome.trend_window == 7
    assert genome.use_exit_momentum is False
    assert genome.exit_momentum_threshold == 0.0
    assert genome.ret_short_window == 3
    assert genome.ret_mid_window == 12
    assert genome.ma_window == 20
    assert genome.range_window == 20
    assert genome.vol_short_window == 5
    assert genome.vol_long_window == 20
    assert genome.weight_ret_short == 0.0
    assert genome.weight_ret_mid == 0.0
    assert genome.weight_dist_ma == 0.0
    assert genome.weight_range_pos == 0.0
    assert genome.weight_vol_ratio == 0.0
    assert genome.weight_trend_strength == 0.0
    assert genome.weight_realized_volatility == 0.0
    assert genome.weight_trend_long == 0.0
    assert genome.weight_breakout == 0.0


def test_genome_validation_fails_when_close_threshold_is_greater_than_open() -> None:
    with pytest.raises(ValueError, match="threshold_close must be less than or equal to threshold_open"):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.8,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
            }
        )


def test_genome_validation_fails_when_min_bars_between_entries_is_negative() -> None:
    with pytest.raises(
        ValueError,
        match="min_bars_between_entries must be an integer greater than or equal to 0",
    ):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.2,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "min_bars_between_entries": -1,
            }
        )


def test_genome_policy_v2_does_not_enforce_legacy_threshold_order() -> None:
    genome = Genome.from_dict(
        {
            "threshold_open": 0.2,
            "threshold_close": 0.8,
            "position_size": 0.2,
            "stop_loss": 0.05,
            "take_profit": 0.1,
            "policy_v2_enabled": True,
            "entry_trigger": {
                "entry_score_threshold": 0.35,
                "min_positive_families": 2,
                "require_trend_or_breakout": True,
            },
            "exit_policy": {
                "exit_score_threshold": 0.05,
                "stop_loss_pct": 0.04,
                "take_profit_pct": 0.12,
            },
        }
    )

    assert genome.policy_v2_enabled is True
    assert genome.threshold_open == 0.2
    assert genome.threshold_close == 0.8


def test_genome_validation_fails_when_entry_confirmation_bars_is_less_than_one() -> None:
    with pytest.raises(
        ValueError,
        match="entry_confirmation_bars must be an integer greater than or equal to 1",
    ):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.2,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "entry_confirmation_bars": 0,
            }
        )


def test_genome_validation_fails_when_entry_score_margin_is_negative() -> None:
    with pytest.raises(
        ValueError,
        match="entry_score_margin must be a finite number greater than or equal to 0.0",
    ):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.2,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "entry_score_margin": -0.01,
            }
        )


def test_genome_validation_fails_when_v2_context_range_is_inverted() -> None:
    with pytest.raises(
        ValueError,
        match="allowed_range_position_min must be less than or equal to allowed_range_position_max",
    ):
        Genome.from_dict(
            {
                "threshold_open": 0.4,
                "threshold_close": 0.2,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "policy_v2_enabled": True,
                "entry_context": {
                    "allowed_range_position_min": 0.5,
                    "allowed_range_position_max": -0.5,
                },
            }
        )


def test_genome_from_dict_supports_explicit_policy_v2_blocks() -> None:
    genome = Genome.from_dict(
        {
            "threshold_open": 0.4,
            "threshold_close": 0.2,
            "position_size": 0.2,
            "stop_loss": 0.05,
            "take_profit": 0.1,
            "policy_v2_enabled": True,
            "entry_context": {
                "min_trend_strength": 0.1,
                "min_breakout_strength": 0.0,
            },
            "entry_trigger": {
                "trend_weight": 1.0,
                "momentum_weight": 0.8,
                "entry_score_threshold": 0.35,
                "min_positive_families": 2,
                "require_trend_or_breakout": True,
            },
            "exit_policy": {
                "exit_score_threshold": 0.05,
                "exit_on_signal_reversal": True,
                "max_holding_bars": 12,
                "stop_loss_pct": 0.04,
                "take_profit_pct": 0.12,
            },
            "trade_control": {
                "cooldown_bars": 3,
                "min_holding_bars": 2,
                "reentry_block_bars": 4,
            },
        }
    )

    assert genome.policy_v2_enabled is True
    assert genome.entry_context.min_trend_strength == 0.1
    assert genome.entry_trigger.entry_score_threshold == 0.35
    assert genome.exit_policy.max_holding_bars == 12
    assert genome.trade_control.reentry_block_bars == 4


def test_genome_validation_fails_when_trend_window_is_not_positive() -> None:
    with pytest.raises(ValueError, match="trend_window must be greater than 0"):
        Genome.from_dict(
            {
                "threshold_open": 0.8,
                "threshold_close": 0.4,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "trend_window": 0,
            }
        )


def test_genome_validation_fails_when_ret_short_window_is_not_less_than_ret_mid_window() -> None:
    with pytest.raises(ValueError, match="ret_short_window must be less than ret_mid_window"):
        Genome.from_dict(
            {
                "threshold_open": 0.8,
                "threshold_close": 0.4,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "ret_short_window": 12,
                "ret_mid_window": 12,
            }
        )


def test_genome_validation_fails_when_vol_short_window_is_not_less_than_vol_long_window() -> None:
    with pytest.raises(ValueError, match="vol_short_window must be less than vol_long_window"):
        Genome.from_dict(
            {
                "threshold_open": 0.8,
                "threshold_close": 0.4,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "vol_short_window": 20,
                "vol_long_window": 10,
            }
        )


def test_genome_validation_fails_when_weight_is_out_of_range() -> None:
    with pytest.raises(ValueError, match="weight_ret_short must be between -3.0 and 3.0"):
        Genome.from_dict(
            {
                "threshold_open": 0.8,
                "threshold_close": 0.4,
                "position_size": 0.2,
                "stop_loss": 0.05,
                "take_profit": 0.1,
                "weight_ret_short": 3.5,
            }
        )


def test_genome_copy_with_returns_new_valid_genome() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    updated = genome.copy_with(
        position_size=0.3,
        min_bars_between_entries=6,
        entry_confirmation_bars=2,
        entry_score_margin=0.05,
    )

    assert updated.position_size == 0.3
    assert updated.min_bars_between_entries == 6
    assert updated.entry_confirmation_bars == 2
    assert updated.entry_score_margin == 0.05
    assert genome.position_size == 0.2


def test_genome_copy_with_can_update_signal_and_feature_fields() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    updated = genome.copy_with(
        use_momentum=True,
        momentum_threshold=0.001,
        use_trend=True,
        trend_threshold=0.002,
        trend_window=7,
        use_exit_momentum=True,
        exit_momentum_threshold=-0.001,
        ret_short_window=4,
        ret_mid_window=14,
        ma_window=30,
        range_window=15,
        vol_short_window=6,
        vol_long_window=18,
        weight_ret_short=0.8,
        weight_ret_mid=1.1,
        weight_dist_ma=-0.2,
        weight_range_pos=0.4,
        weight_vol_ratio=-0.5,
        weight_trend_strength=0.3,
        weight_realized_volatility=-0.6,
        weight_trend_long=0.9,
        weight_breakout=-0.8,
    )

    assert updated.use_momentum is True
    assert updated.momentum_threshold == 0.001
    assert updated.use_trend is True
    assert updated.trend_threshold == 0.002
    assert updated.trend_window == 7
    assert updated.use_exit_momentum is True
    assert updated.exit_momentum_threshold == -0.001
    assert updated.ret_short_window == 4
    assert updated.ret_mid_window == 14
    assert updated.ma_window == 30
    assert updated.range_window == 15
    assert updated.vol_short_window == 6
    assert updated.vol_long_window == 18
    assert updated.weight_ret_short == 0.8
    assert updated.weight_ret_mid == 1.1
    assert updated.weight_dist_ma == -0.2
    assert updated.weight_range_pos == 0.4
    assert updated.weight_vol_ratio == -0.5
    assert updated.weight_trend_strength == 0.3
    assert updated.weight_realized_volatility == -0.6
    assert updated.weight_trend_long == 0.9
    assert updated.weight_breakout == -0.8

    assert genome.use_momentum is False
    assert genome.momentum_threshold == 0.0
    assert genome.use_trend is False
    assert genome.trend_threshold == 0.0
    assert genome.trend_window == 5
    assert genome.use_exit_momentum is False
    assert genome.exit_momentum_threshold == 0.0
    assert genome.weight_trend_strength == 0.0
    assert genome.weight_realized_volatility == 0.0
    assert genome.weight_trend_long == 0.0
    assert genome.weight_breakout == 0.0
    assert genome.ret_short_window == 3
    assert genome.ret_mid_window == 12
    assert genome.ma_window == 20
    assert genome.range_window == 20
    assert genome.vol_short_window == 5
    assert genome.vol_long_window == 20
    assert genome.weight_ret_short == 0.0
    assert genome.weight_ret_mid == 0.0
    assert genome.weight_dist_ma == 0.0
    assert genome.weight_range_pos == 0.0
    assert genome.weight_vol_ratio == 0.0
