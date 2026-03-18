import json

from evo_system.domain.run_config import RunConfig


def load_run_config(path: str) -> RunConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    config = RunConfig(
        mutation_seed=data.get("mutation_seed"),
        population_size=data["population_size"],
        target_population_size=data["target_population_size"],
        survivors_count=data["survivors_count"],
        generations_planned=data["generations_planned"],
    )

    config.validate()
    return config