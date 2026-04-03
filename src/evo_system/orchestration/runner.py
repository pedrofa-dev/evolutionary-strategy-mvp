import random

from evo_system.domain.agent import Agent
from evo_system.domain.generation_result import GenerationResult
from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
)
from evo_system.experimental_space import (
    get_default_genome_schema,
    get_mutation_profile_definition,
    get_default_mutation_profile_definition,
    get_genome_schema,
)
from evo_system.mutation.mutator import Mutator, MutationProfile
from evo_system.selection.selector import Selector


class EvolutionRunner:
    """Coordinate selection plus mutation for one generation step.

    Responsibility boundary:
    - This class orchestrates evolution, but it should not own signal or gene
      semantics directly.

    TODO: candidate for modularization
    - Population creation and schema-aware mutation dispatch could later be
      driven by factories once the experimental space is modularized.

    Phase 1 modularization note:
    - `genome_schema` and `mutation_profile_definition` are compatibility
      adapters. The current helper functions and mutator still define behavior.
    """
    def __init__(
        self,
        mutation_seed: int = 42,
        mutation_profile: MutationProfile | None = None,
        entry_trigger_constraints: dict[str, float] | None = None,
        genome_schema_name: str | None = None,
        mutation_profile_name: str | None = None,
    ) -> None:
        self._random = random.Random(mutation_seed)
        self.genome_schema = (
            get_genome_schema(genome_schema_name)
            if genome_schema_name is not None
            else get_default_genome_schema()
        )
        self.mutation_profile_definition = (
            get_mutation_profile_definition(mutation_profile_name)
            if mutation_profile_name is not None
            else get_default_mutation_profile_definition()
        )
        self.mutator = Mutator(
            seed=mutation_seed,
            profile=self.mutation_profile_definition.resolve_runtime_profile(
                mutation_profile
            ),
            entry_trigger_constraints=entry_trigger_constraints,
            genome_schema=self.genome_schema,
        )
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
        # TODO: candidate for modularization
        # Initial random population seeding is tightly coupled to the current
        # policy_v2 genome schema and would be a good candidate for a genome
        # factory once multiple experimental schemas coexist.
        ret_short_window = self._random.randint(1, 5)
        ret_mid_window = self._random.randint(max(2, ret_short_window + 1), 20)
        vol_short_window = self._random.randint(2, 8)
        vol_long_window = self._random.randint(max(3, vol_short_window + 1), 30)

        return self.genome_schema.build_genome(
            position_size=self._random.uniform(0.05, 1.0),
            stop_loss_pct=self._random.uniform(0.01, 0.2),
            take_profit_pct=self._random.uniform(0.02, 0.3),
            trend_window=self._random.randint(2, 8),
            ret_short_window=ret_short_window,
            ret_mid_window=ret_mid_window,
            ma_window=self._random.randint(3, 25),
            range_window=self._random.randint(3, 20),
            vol_short_window=vol_short_window,
            vol_long_window=vol_long_window,
            entry_context=EntryContextGene(),
            entry_trigger=EntryTriggerGene(
                trend_weight=self._random.uniform(-1.5, 1.5),
                momentum_weight=self._random.uniform(-1.5, 1.5),
                breakout_weight=self._random.uniform(-1.5, 1.5),
                range_weight=self._random.uniform(-1.5, 1.5),
                volatility_weight=self._random.uniform(-1.5, 1.5),
                entry_score_threshold=self._random.uniform(0.2, 0.95),
                min_positive_families=self._random.randint(1, 3),
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=self._random.uniform(-0.10, 0.30),
                exit_on_signal_reversal=self._random.choice([True, False]),
                max_holding_bars=self._random.choice([0, 12, 24, 36]),
                stop_loss_pct=self._random.uniform(0.01, 0.2),
                take_profit_pct=self._random.uniform(0.02, 0.3),
            ),
            trade_control=TradeControlGene(),
        )
