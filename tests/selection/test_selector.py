import pytest

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.selection.selector import Selector


def test_select_top_agents_returns_best_agents_by_fitness() -> None:
    agent_1 = Agent.create(Genome(0.8, 0.4, 0.2, 0.05, 0.1))
    agent_2 = Agent.create(Genome(0.7, 0.3, 0.3, 0.04, 0.15))
    agent_3 = Agent.create(Genome(0.6, 0.2, 0.1, 0.03, 0.08))

    evaluated_agents = [
        (agent_1, 0.5),
        (agent_2, 0.9),
        (agent_3, 0.3),
    ]

    selector = Selector()

    survivors = selector.select_top_agents(evaluated_agents, survivors_count=2)

    assert len(survivors) == 2
    assert survivors[0] == agent_2
    assert survivors[1] == agent_1


def test_select_top_agents_raises_error_when_survivors_count_is_invalid() -> None:
    agent = Agent.create(Genome(0.8, 0.4, 0.2, 0.05, 0.1))
    evaluated_agents = [(agent, 0.5)]

    selector = Selector()

    with pytest.raises(ValueError, match="survivors_count must be greater than 0"):
        selector.select_top_agents(evaluated_agents, survivors_count=0)


def test_select_top_agents_raises_error_when_survivors_count_is_too_large() -> None:
    agent = Agent.create(Genome(0.8, 0.4, 0.2, 0.05, 0.1))
    evaluated_agents = [(agent, 0.5)]

    selector = Selector()

    with pytest.raises(ValueError, match="survivors_count cannot be greater than the number of evaluated agents"):
        selector.select_top_agents(evaluated_agents, survivors_count=2)