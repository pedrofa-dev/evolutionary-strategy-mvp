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
        trade_count_penalty_weight=float(data.get("trade_count_penalty_weight", 0.0)),
        regime_filter_enabled=bool(data.get("regime_filter_enabled", False)),
        min_trend_long_for_entry=float(data.get("min_trend_long_for_entry", 0.0)),
        min_breakout_for_entry=float(data.get("min_breakout_for_entry", 0.0)),
        max_realized_volatility_for_entry=(
            float(data["max_realized_volatility_for_entry"])
            if "max_realized_volatility_for_entry" in data
            and data["max_realized_volatility_for_entry"] is not None
            else None
        ),
        mutation_profile=mutation_profile,
        dataset_catalog_id=data["dataset_catalog_id"],
        seeds=(
            [int(seed) for seed in data["seeds"]]
            if "seeds" in data and data["seeds"] is not None
            else None
        ),
        seed_start=(
            int(data["seed_start"])
            if "seed_start" in data and data["seed_start"] is not None
            else None
        ),
        seed_count=(
            int(data["seed_count"])
            if "seed_count" in data and data["seed_count"] is not None
            else None
        ),
    )
