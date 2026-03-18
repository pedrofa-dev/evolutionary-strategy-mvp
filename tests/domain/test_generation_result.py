from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome


def test_generation_result_to_dict_returns_serializable_data() -> None:
    agent = Agent.create(
        Genome(
            threshold_open=0.8,
            threshold_close=0.4,
            position_size=0.2,
            stop_loss=0.05,
            take_profit=0.1,
        )
    )

    result = GenerationResult(
        generation_number=1,
        evaluated_agents=[(agent, 0.75)],
        best_fitness=0.75,
        average_fitness=0.75,
    )

    data = result.to_dict()

    assert data["generation_number"] == 1
    assert data["best_fitness"] == 0.75
    assert data["average_fitness"] == 0.75
    assert len(data["evaluated_agents"]) == 1
    assert data["evaluated_agents"][0]["fitness"] == 0.75
    assert data["evaluated_agents"][0]["agent"]["id"] == agent.id