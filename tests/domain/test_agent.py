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