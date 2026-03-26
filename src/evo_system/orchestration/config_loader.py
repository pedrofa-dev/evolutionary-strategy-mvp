import json
from pathlib import Path

from evo_system.domain.run_config import RunConfig
from evo_system.mutation.mutator import MutationProfile


def load_run_config(config_path: str) -> RunConfig:
    path = Path(config_path)

    with path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)

    mutation_profile_data = data.get("mutation_profile", {})
    mutation_profile = MutationProfile(**mutation_profile_data)

    return RunConfig(
        mutation_seed=int(data["mutation_seed"]),
        population_size=int(data["population_size"]),
        target_population_size=int(data["target_population_size"]),
        survivors_count=int(data["survivors_count"]),
        generations_planned=int(data["generations_planned"]),
        trade_cost_rate=float(data.get("trade_cost_rate", 0.0)),
        cost_penalty_weight=float(data.get("cost_penalty_weight", 0.25)),
        mutation_profile=mutation_profile,
        dataset_mode=str(data.get("dataset_mode", "legacy")),
        dataset_catalog_id=data.get("dataset_catalog_id"),
    )
