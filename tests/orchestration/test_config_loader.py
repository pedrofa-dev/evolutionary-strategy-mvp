import json
from pathlib import Path

from evo_system.orchestration.config_loader import load_run_config


def test_load_run_config_from_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    data = {
        "mutation_seed": 42,
        "population_size": 4,
        "target_population_size": 4,
        "survivors_count": 2,
        "generations_planned": 5,
    }

    config_path.write_text(json.dumps(data))

    config = load_run_config(str(config_path))

    assert config.mutation_seed == 42
    assert config.population_size == 4
    assert config.target_population_size == 4
    assert config.survivors_count == 2
    assert config.generations_planned == 5