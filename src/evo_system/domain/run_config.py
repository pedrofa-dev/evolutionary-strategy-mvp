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
    dataset_mode: str = "legacy"
    dataset_catalog_id: str | None = None

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

        if self.dataset_mode not in {"legacy", "manifest"}:
            raise ValueError("dataset_mode must be either 'legacy' or 'manifest'")

        if self.dataset_mode == "manifest":
            if not isinstance(self.dataset_catalog_id, str) or not self.dataset_catalog_id.strip():
                raise ValueError("dataset_catalog_id is required when dataset_mode is 'manifest'")
