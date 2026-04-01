from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome


def test_agent_create_builds_agent_with_id_and_genome() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    agent = Agent.create(genome)

    assert agent.id
    assert isinstance(agent.id, str)
    assert agent.genome == genome


def test_agent_to_dict_returns_serializable_data() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )
    agent = Agent(
        id="agent-001",
        genome=genome,
    )

    result = agent.to_dict()

    assert result == {
        "id": "agent-001",
        "genome": {
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
        },
    }

def test_agent_from_dict_rebuilds_agent() -> None:
    data = {
        "id": "agent-001",
        "genome": {
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
            "use_exit_momentum": True,
            "exit_momentum_threshold": -0.002,
        },
    }

    agent = Agent.from_dict(data)

    assert agent.id == "agent-001"
    assert agent.genome.threshold_open == 0.8
    assert agent.genome.threshold_close == 0.4
    assert agent.genome.position_size == 0.2
    assert agent.genome.stop_loss == 0.05
    assert agent.genome.take_profit == 0.1
    assert agent.genome.min_bars_between_entries == 0
    assert agent.genome.entry_confirmation_bars == 1
    assert agent.genome.entry_score_margin == 0.0
    assert agent.genome.use_momentum is True
    assert agent.genome.momentum_threshold == 0.002
    assert agent.genome.use_trend is True
    assert agent.genome.trend_threshold == 0.003
    assert agent.genome.trend_window == 7
    assert agent.genome.use_exit_momentum is True
    assert agent.genome.exit_momentum_threshold == -0.002
