import json

from evo_system.orchestration.config_loader import load_run_config


def test_load_run_config_reads_required_and_optional_fields(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "trade_cost_rate": 0.001,
                "cost_penalty_weight": 0.25,
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.mutation_seed == 42
    assert config.population_size == 12
    assert config.target_population_size == 12
    assert config.survivors_count == 4
    assert config.generations_planned == 25
    assert config.trade_cost_rate == 0.001
    assert config.cost_penalty_weight == 0.25
    assert config.trade_count_penalty_weight == 0.0


def test_load_run_config_uses_defaults_for_optional_fields(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.trade_cost_rate == 0.0
    assert config.cost_penalty_weight == 0.25
    assert config.trade_count_penalty_weight == 0.0


def test_load_run_config_reads_trade_count_penalty_weight(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "trade_count_penalty_weight": 0.001,
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.trade_count_penalty_weight == 0.001


def test_load_run_config_reads_explicit_seeds(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "seeds": [101, 102, 103],
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.seeds == [101, 102, 103]
    assert config.seed_start is None
    assert config.seed_count is None


def test_load_run_config_reads_seed_range(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "seed_start": 100,
                "seed_count": 6,
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.seeds is None
    assert config.seed_start == 100
    assert config.seed_count == 6
