import random

from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import Genome
from evo_system.mutation.mutator import Mutator, MutationProfile
from evo_system.selection.selector import Selector


class EvolutionRunner:
    def __init__(
        self,
        mutation_seed: int = 42,
        mutation_profile: MutationProfile | None = None,
    ) -> None:
        self._random = random.Random(mutation_seed)
        self.mutator = Mutator(seed=mutation_seed, profile=mutation_profile)
        self.selector = Selector()

    def create_initial_population(self, population_size: int) -> list[Agent]:
        if population_size <= 0:
            raise ValueError("population_size must be greater than 0")

        return [self._build_random_agent() for _ in range(population_size)]

    def summarize_generation(
        self,
        generation_number: int,
        evaluated_agents: list[tuple[Agent, float]],
    ) -> GenerationResult:
        if not evaluated_agents:
            raise ValueError("evaluated_agents cannot be empty")

        fitness_values = [fitness for _, fitness in evaluated_agents]

        return GenerationResult(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
            best_fitness=max(fitness_values),
            average_fitness=sum(fitness_values) / len(fitness_values),
        )

    def build_next_generation(
        self,
        evaluated_agents: list[tuple[Agent, float]],
        survivors_count: int,
        target_population_size: int,
    ) -> list[Agent]:
        if not evaluated_agents:
            raise ValueError("evaluated_agents cannot be empty")

        if survivors_count <= 0:
            raise ValueError("survivors_count must be greater than 0")

        if target_population_size <= 0:
            raise ValueError("target_population_size must be greater than 0")

        if survivors_count > len(evaluated_agents):
            raise ValueError("survivors_count cannot exceed evaluated_agents size")

        survivors = self.selector.select_top_agents(
            evaluated_agents=evaluated_agents,
            survivors_count=survivors_count,
        )

        next_generation = list(survivors)

        while len(next_generation) < target_population_size:
            parent = self._random.choice(survivors)
            mutated_genome = self.mutator.mutate(parent.genome)
            next_generation.append(Agent.create(mutated_genome))

        return next_generation

    def _build_random_agent(self) -> Agent:
        return Agent.create(self._build_random_genome())

    def _build_random_genome(self) -> Genome:
        threshold_open = self._random.uniform(0.2, 0.95)
        threshold_close = self._random.uniform(0.0, threshold_open)

        use_momentum = self._random.choice([True, False])
        use_trend = self._random.choice([True, False])
        use_exit_momentum = self._random.choice([True, False])

        ret_short_window = self._random.randint(1, 5)
        ret_mid_window = self._random.randint(max(2, ret_short_window + 1), 20)

        vol_short_window = self._random.randint(2, 8)
        vol_long_window = self._random.randint(max(3, vol_short_window + 1), 30)

        genome = Genome(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=self._random.uniform(0.05, 1.0),
            stop_loss=self._random.uniform(0.01, 0.2),
            take_profit=self._random.uniform(0.02, 0.3),
            use_momentum=use_momentum,
            momentum_threshold=0.0,
            use_trend=use_trend,
            trend_threshold=0.0,
            trend_window=self._random.randint(2, 8),
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=0.0,
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self._random.randint(3, 25),
            range_window=self._random.randint(3, 20),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            weight_ret_short=self._random.uniform(-1.5, 1.5),
            weight_ret_mid=self._random.uniform(-1.5, 1.5),
            weight_dist_ma=self._random.uniform(-1.5, 1.5),
            weight_range_pos=self._random.uniform(-1.5, 1.5),
            weight_vol_ratio=self._random.uniform(-1.5, 1.5),
        )

        if use_momentum:
            genome = genome.copy_with(
                momentum_threshold=self._random.uniform(-0.002, 0.002)
            )

        if use_trend:
            genome = genome.copy_with(
                trend_threshold=self._random.uniform(-0.002, 0.002)
            )

        if use_exit_momentum:
            genome = genome.copy_with(
                exit_momentum_threshold=self._random.uniform(-0.002, 0.0)
            )

        return genome