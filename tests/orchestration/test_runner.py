import pytest

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.mutation.mutator import MutationProfile


def test_create_initial_population_returns_expected_size() -> None:
    runner = EvolutionRunner(mutation_seed=42)

    population = runner.create_initial_population(population_size=5)

    assert len(population) == 5
    assert all(isinstance(agent, Agent) for agent in population)


def test_create_initial_population_is_deterministic_with_same_seed() -> None:
    runner_a = EvolutionRunner(mutation_seed=42)
    runner_b = EvolutionRunner(mutation_seed=42)

    population_a = runner_a.create_initial_population(population_size=3)
    population_b = runner_b.create_initial_population(population_size=3)

    genomes_a = [agent.genome for agent in population_a]
    genomes_b = [agent.genome for agent in population_b]

    assert genomes_a == genomes_b


def test_runner_passes_mutation_profile_to_mutator() -> None:
    profile = MutationProfile(
        strong_mutation_probability=0.20,
        numeric_delta_scale=1.25,
        flag_flip_probability=0.08,
        weight_delta=0.30,
        window_step_mode="small",
    )

    runner = EvolutionRunner(mutation_seed=42, mutation_profile=profile)

    assert runner.mutator.profile == profile


def test_create_initial_population_raises_error_when_population_size_is_not_positive() -> None:
    runner = EvolutionRunner(mutation_seed=42)

    with pytest.raises(ValueError, match="population_size must be greater than 0"):
        runner.create_initial_population(population_size=0)


def test_build_next_generation_returns_expected_population_size() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
        (agents[2], 1.0),
    ]

    next_generation = runner.build_next_generation(
        evaluated_agents=evaluated_agents,
        survivors_count=2,
        target_population_size=5,
    )

    assert len(next_generation) == 5


def test_build_next_generation_keeps_survivors() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
        (agents[2], 1.0),
    ]

    next_generation = runner.build_next_generation(
        evaluated_agents=evaluated_agents,
        survivors_count=2,
        target_population_size=4,
    )

    survivor_ids = {agents[0].id, agents[1].id}
    next_generation_ids = {agent.id for agent in next_generation[:2]}

    assert next_generation_ids == survivor_ids


def test_build_next_generation_creates_new_agents_from_mutation() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
        (agents[2], 1.0),
    ]

    next_generation = runner.build_next_generation(
        evaluated_agents=evaluated_agents,
        survivors_count=2,
        target_population_size=5,
    )

    survivor_ids = {agents[0].id, agents[1].id}
    mutated_agents = next_generation[2:]

    assert len(mutated_agents) == 3
    assert all(agent.id not in survivor_ids for agent in mutated_agents)


def test_build_next_generation_raises_error_when_evaluated_agents_is_empty() -> None:
    runner = EvolutionRunner(mutation_seed=42)

    with pytest.raises(ValueError, match="evaluated_agents cannot be empty"):
        runner.build_next_generation(
            evaluated_agents=[],
            survivors_count=1,
            target_population_size=2,
        )


def test_build_next_generation_raises_error_when_target_population_is_not_positive() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
    ]

    with pytest.raises(ValueError, match="target_population_size must be greater than 0"):
        runner.build_next_generation(
            evaluated_agents=evaluated_agents,
            survivors_count=1,
            target_population_size=0,
        )


def test_build_next_generation_raises_error_when_survivors_count_is_not_positive() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
    ]

    with pytest.raises(ValueError, match="survivors_count must be greater than 0"):
        runner.build_next_generation(
            evaluated_agents=evaluated_agents,
            survivors_count=0,
            target_population_size=2,
        )


def test_build_next_generation_raises_error_when_survivors_count_exceeds_population() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 5.0),
    ]

    with pytest.raises(ValueError, match="survivors_count cannot exceed evaluated_agents size"):
        runner.build_next_generation(
            evaluated_agents=evaluated_agents,
            survivors_count=3,
            target_population_size=4,
        )


def test_build_random_agent_uses_feature_fields() -> None:
    runner = EvolutionRunner(mutation_seed=42)

    agent = runner._build_random_agent()

    genome = agent.genome

    assert isinstance(genome.ret_short_window, int)
    assert isinstance(genome.ret_mid_window, int)
    assert isinstance(genome.ma_window, int)
    assert isinstance(genome.range_window, int)
    assert isinstance(genome.vol_short_window, int)
    assert isinstance(genome.vol_long_window, int)

    assert isinstance(genome.weight_ret_short, float)
    assert isinstance(genome.weight_ret_mid, float)
    assert isinstance(genome.weight_dist_ma, float)
    assert isinstance(genome.weight_range_pos, float)
    assert isinstance(genome.weight_vol_ratio, float)


def test_summarize_generation_returns_expected_result() -> None:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
    ]
    agents = [Agent.create(genome) for genome in genomes]

    runner = EvolutionRunner(mutation_seed=42)

    evaluated_agents = [
        (agents[0], 10.0),
        (agents[1], 6.0),
    ]

    result = runner.summarize_generation(
        generation_number=3,
        evaluated_agents=evaluated_agents,
    )

    assert result.generation_number == 3
    assert result.best_fitness == 10.0
    assert result.average_fitness == 8.0


def test_summarize_generation_raises_error_when_evaluated_agents_is_empty() -> None:
    runner = EvolutionRunner(mutation_seed=42)

    with pytest.raises(ValueError, match="evaluated_agents cannot be empty"):
        runner.summarize_generation(
            generation_number=1,
            evaluated_agents=[],
        )
