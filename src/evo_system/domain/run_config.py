from dataclasses import dataclass, field

from evo_system.mutation.mutator import MutationProfile


@dataclass(frozen=True)
class RunConfig:
    mutation_seed: int
    population_size: int
    target_population_size: int
    survivors_count: int
    generations_planned: int
    mutation_profile: MutationProfile = field(default_factory=MutationProfile)
    trade_cost_rate: float = 0.0
    cost_penalty_weight: float = 0.25
    trade_count_penalty_weight: float = 0.0
    regime_filter_enabled: bool = False
    min_trend_long_for_entry: float = 0.0
    min_breakout_for_entry: float = 0.0
    max_realized_volatility_for_entry: float | None = None
    dataset_mode: str = "legacy"
    dataset_catalog_id: str | None = None
    seeds: list[int] | None = None
    seed_start: int | None = None
    seed_count: int | None = None

    def __post_init__(self) -> None:
        if self.population_size <= 0:
            raise ValueError("population_size must be greater than 0")

        if self.target_population_size <= 0:
            raise ValueError("target_population_size must be greater than 0")

        if self.survivors_count <= 0:
            raise ValueError("survivors_count must be greater than 0")

        if self.generations_planned <= 0:
            raise ValueError("generations_planned must be greater than 0")

        if self.target_population_size < self.survivors_count:
            raise ValueError("target_population_size cannot be smaller than survivors_count")

        if self.trade_cost_rate < 0.0:
            raise ValueError("trade_cost_rate must be greater than or equal to 0.0")

        if self.cost_penalty_weight < 0.0:
            raise ValueError("cost_penalty_weight must be greater than or equal to 0.0")

        if self.trade_count_penalty_weight < 0.0:
            raise ValueError(
                "trade_count_penalty_weight must be greater than or equal to 0.0"
            )

        if not -1.0 <= self.min_trend_long_for_entry <= 1.0:
            raise ValueError("min_trend_long_for_entry must be between -1.0 and 1.0")

        if not -1.0 <= self.min_breakout_for_entry <= 1.0:
            raise ValueError("min_breakout_for_entry must be between -1.0 and 1.0")

        if self.max_realized_volatility_for_entry is not None:
            if not 0.0 <= self.max_realized_volatility_for_entry <= 1.0:
                raise ValueError(
                    "max_realized_volatility_for_entry must be between 0.0 and 1.0"
                )

        if self.dataset_mode not in {"legacy", "manifest"}:
            raise ValueError("dataset_mode must be either 'legacy' or 'manifest'")

        if self.dataset_mode == "manifest":
            if not isinstance(self.dataset_catalog_id, str) or not self.dataset_catalog_id.strip():
                raise ValueError("dataset_catalog_id is required when dataset_mode is 'manifest'")

        if self.seeds is not None:
            if not self.seeds:
                raise ValueError("seeds cannot be empty when provided")
            if any(not isinstance(seed, int) for seed in self.seeds):
                raise ValueError("seeds must contain integers only")
            if self.seed_start is not None or self.seed_count is not None:
                raise ValueError("seed_start/seed_count cannot be combined with seeds")

        if self.seed_start is not None or self.seed_count is not None:
            if self.seed_start is None or self.seed_count is None:
                raise ValueError("seed_start and seed_count must be provided together")
            if self.seed_count <= 0:
                raise ValueError("seed_count must be greater than 0")
