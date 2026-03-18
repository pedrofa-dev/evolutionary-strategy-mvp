import pytest

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.selection.selector import Selector
from evo_system.environment.simple_environment import SimpleEnvironment



def test_run_generation_returns_fitness_for_each_agent() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]

    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(environment=SimpleEnvironment())

    results = runner.run_generation(agents)

    assert len(results) == 2
    for agent, fitness in results:
        assert isinstance(agent.id, str)
        assert isinstance(fitness, float)


def test_run_generation_is_deterministic() -> None:
    genome = Genome(0.8, 0.4, 0.2, 0.05, 0.1)
    agent = Agent.create(genome)

    runner = EvolutionRunner(environment=SimpleEnvironment())

    result_1 = runner.run_generation([agent])
    result_2 = runner.run_generation([agent])

    assert result_1[0][1] == result_2[0][1]

def test_build_next_generation_returns_expected_population_size() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(environment=SimpleEnvironment(), mutation_seed=42)
    evaluated = runner.run_generation(agents)

    next_generation = runner.build_next_generation(
        evaluated_agents=evaluated,
        survivors_count=2,
        target_population_size=4,
    )

    assert len(next_generation) == 4


def test_build_next_generation_keeps_survivors() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(environment=SimpleEnvironment(), mutation_seed=42)
    evaluated = runner.run_generation(agents)

    selector = Selector()
    survivors = selector.select_top_agents(evaluated, survivors_count=2)

    next_generation = runner.build_next_generation(
        evaluated_agents=evaluated,
        survivors_count=2,
        target_population_size=4,
    )

    assert survivors[0] in next_generation
    assert survivors[1] in next_generation


def test_build_next_generation_raises_error_when_target_population_is_too_small() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(environment=SimpleEnvironment(), mutation_seed=42)
    evaluated = runner.run_generation(agents)

    with pytest.raises(ValueError, match="target_population_size cannot be smaller than survivors_count"):
        runner.build_next_generation(
            evaluated_agents=evaluated,
            survivors_count=2,
            target_population_size=1,
        )

def test_summarize_generation_returns_expected_result() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(environment=SimpleEnvironment(), mutation_seed=42)
    evaluated = runner.run_generation(agents)

    summary = runner.summarize_generation(
        generation_number=1,
        evaluated_agents=evaluated,
    )

    assert summary.generation_number == 1
    assert len(summary.evaluated_agents) == 2
    assert summary.best_fitness >= summary.average_fitness