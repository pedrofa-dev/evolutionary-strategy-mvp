from evo_system.domain.agent import Agent
from evo_system.environment.simple_environment import SimpleEnvironment
from evo_system.fitness.calculator import FitnessCalculator
from evo_system.mutation.mutator import Mutator
from evo_system.selection.selector import Selector
from evo_system.domain.generation_result import GenerationResult


class EvolutionRunner:
    def summarize_generation(
        self,
        generation_number: int,
        evaluated_agents: list[tuple[Agent, float]],
    ) -> GenerationResult:
        fitness_values = [fitness for _, fitness in evaluated_agents]

        return GenerationResult(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
            best_fitness=max(fitness_values),
            average_fitness=sum(fitness_values) / len(fitness_values),
        )
    
    def __init__(self, mutation_seed: int | None = None) -> None:
        self.environment = SimpleEnvironment()
        self.fitness_calculator = FitnessCalculator()
        self.selector = Selector()
        self.mutator = Mutator(seed=mutation_seed)

    def run_generation(self, agents: list[Agent]) -> list[tuple[Agent, float]]:
        results = []

        for agent in agents:
            episode_result = self.environment.run(agent.genome)
            fitness = self.fitness_calculator.calculate(episode_result)
            results.append((agent, fitness))

        return results

    def build_next_generation(
        self,
        evaluated_agents: list[tuple[Agent, float]],
        survivors_count: int,
        target_population_size: int,
    ) -> list[Agent]:
        if target_population_size < survivors_count:
            raise ValueError("target_population_size cannot be smaller than survivors_count")

        survivors = self.selector.select_top_agents(
            evaluated_agents=evaluated_agents,
            survivors_count=survivors_count,
        )
        

        next_generation = list(survivors)

        survivor_index = 0
        while len(next_generation) < target_population_size:
            parent = survivors[survivor_index % len(survivors)]
            mutated_genome = self.mutator.mutate(parent.genome)
            child = Agent.create(mutated_genome)
            next_generation.append(child)
            survivor_index += 1

        return next_generation
    