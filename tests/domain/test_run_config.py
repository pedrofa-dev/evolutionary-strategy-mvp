import pytest

from evo_system.domain.run_config import RunConfig


def test_run_config_builds_valid_instance() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        trade_cost_rate=0.001,
        cost_penalty_weight=0.25,
    )

    assert config.mutation_seed == 42
    assert config.population_size == 12
    assert config.target_population_size == 12
    assert config.survivors_count == 4
    assert config.generations_planned == 25
    assert config.trade_cost_rate == 0.001
    assert config.cost_penalty_weight == 0.25


def test_run_config_rejects_non_positive_population_size() -> None:
    with pytest.raises(ValueError, match="population_size must be greater than 0"):
        RunConfig(
            mutation_seed=42,
            population_size=0,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
        )


def test_run_config_rejects_non_positive_target_population_size() -> None:
    with pytest.raises(ValueError, match="target_population_size must be greater than 0"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=0,
            survivors_count=4,
            generations_planned=25,
        )


def test_run_config_rejects_target_population_smaller_than_survivors() -> None:
    with pytest.raises(ValueError, match="target_population_size cannot be smaller than survivors_count"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=3,
            survivors_count=4,
            generations_planned=25,
        )


def test_run_config_rejects_negative_trade_cost_rate() -> None:
    with pytest.raises(ValueError, match="trade_cost_rate must be greater than or equal to 0.0"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            trade_cost_rate=-0.001,
        )


def test_run_config_rejects_negative_cost_penalty_weight() -> None:
    with pytest.raises(ValueError, match="cost_penalty_weight must be greater than or equal to 0.0"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            cost_penalty_weight=-0.1,
        )