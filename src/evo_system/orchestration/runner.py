import random

from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome
from evo_system.fitness.calculator import FitnessCalculator
from evo_system.mutation.mutator import Mutator
from evo_system.selection.selector import Selector


class EvolutionRunner:
    RANDOM_INJECTION_COUNT = 1

    def __init__(self, environment, mutation_seed: int | None = None) -> None:
        self.environment = environment
        self.fitness_calculator = FitnessCalculator()
        self.selector = Selector()
        self.mutator = Mutator(seed=mutation_seed)
        self.random = random.Random(mutation_seed)

    def run_generation(self, agents: list[Agent]) -> list[tuple[Agent, float]]:
        results = []

        for agent in agents:
            episode_result = self._run_agent(agent)
            fitness = self.fitness_calculator.calculate(episode_result)
            results.append((agent, fitness))

        return results

    def _run_agent(self, agent: Agent):
        if hasattr(self.environment, "run"):
            return self.environment.run(agent.genome)

        return self.environment.run_episode(agent)

    def build_next_generation(
        self,
        evaluated_agents: list[tuple[Agent, float]],
        survivors_count: int,
        target_population_size: int,
    ) -> list[Agent]:
        if survivors_count <= 0:
            raise ValueError("survivors_count must be greater than 0")

        if target_population_size < survivors_count:
            raise ValueError("target_population_size cannot be smaller than survivors_count")

        survivors = self.selector.select_top_agents(
            evaluated_agents=evaluated_agents,
            survivors_count=survivors_count,
        )

        next_generation = list(survivors)

        random_injection_count = min(
            self.RANDOM_INJECTION_COUNT,
            max(0, target_population_size - len(next_generation)),
        )
        offspring_target_size = target_population_size - random_injection_count

        survivor_index = 0
        while len(next_generation) < offspring_target_size:
            parent = survivors[survivor_index % len(survivors)]
            mutated_genome = self.mutator.mutate(parent.genome)
            child = Agent.create(mutated_genome)
            next_generation.append(child)
            survivor_index += 1

        while len(next_generation) < target_population_size:
            next_generation.append(self._build_random_agent())

        return next_generation

    def _build_random_agent(self) -> Agent:
        return Agent.create(self._build_random_genome())

    def _build_random_genome(self) -> Genome:
        threshold_open = self.random.uniform(0.35, 0.90)
        threshold_close = self.random.uniform(0.05, min(0.45, threshold_open))

        use_momentum = self.random.choice([True, False])
        use_trend = self.random.choice([True, False])
        use_exit_momentum = self.random.choice([True, False])

        ret_short_window = self.random.randint(1, 5)
        ret_mid_window = self.random.randint(max(2, ret_short_window + 1), 20)

        vol_short_window = self.random.randint(2, 8)
        vol_long_window = self.random.randint(max(3, vol_short_window + 1), 30)

        genome = Genome(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=self.random.uniform(0.05, 0.25),
            stop_loss=self.random.uniform(0.01, 0.06),
            take_profit=self.random.uniform(0.03, 0.18),
            use_momentum=use_momentum,
            momentum_threshold=0.0,
            use_trend=use_trend,
            trend_threshold=0.0,
            trend_window=self.random.randint(2, 8),
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=0.0,
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self.random.randint(3, 25),
            range_window=self.random.randint(3, 20),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=self.random.uniform(-1.5, 1.5),
            weight_ret_mid=self.random.uniform(-1.5, 1.5),
            weight_dist_ma=self.random.uniform(-1.5, 1.5),
            weight_range_pos=self.random.uniform(-1.5, 1.5),
            weight_vol_ratio=self.random.uniform(-1.5, 1.5),
        )

        if use_momentum:
            genome = genome.copy_with(
                momentum_threshold=self.random.uniform(-0.002, 0.002)
            )

        if use_trend:
            genome = genome.copy_with(
                trend_threshold=self.random.uniform(-0.002, 0.002)
            )

        if use_exit_momentum:
            genome = genome.copy_with(
                exit_momentum_threshold=self.random.uniform(-0.002, 0.0)
            )

        return genome

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