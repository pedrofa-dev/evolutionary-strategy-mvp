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
    assert agent.genome.use_momentum is True
    assert agent.genome.momentum_threshold == 0.002
    assert agent.genome.use_trend is True
    assert agent.genome.trend_threshold == 0.003
    assert agent.genome.trend_window == 7
    assert agent.genome.use_exit_momentum is True
    assert agent.genome.exit_momentum_threshold == -0.002