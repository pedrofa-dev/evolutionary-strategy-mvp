import pytest

from evo_system.domain.run_config import RunConfig


def test_run_config_to_dict_returns_serializable_data() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=4,
        target_population_size=4,
        survivors_count=2,
        generations_planned=5,
    )

    data = config.to_dict()

    assert data == {
        "mutation_seed": 42,
        "population_size": 4,
        "target_population_size": 4,
        "survivors_count": 2,
        "generations_planned": 5,
    }


def test_run_config_validate_accepts_valid_config() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=4,
        target_population_size=4,
        survivors_count=2,
        generations_planned=5,
    )

    config.validate()


def test_run_config_validate_fails_when_target_population_is_too_small() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=4,
        target_population_size=2,
        survivors_count=3,
        generations_planned=5,
    )

    with pytest.raises(ValueError, match="target_population_size cannot be smaller than survivors_count"):
        config.validate()


def test_run_config_validate_fails_when_population_is_too_small_for_survivors() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=2,
        target_population_size=4,
        survivors_count=3,
        generations_planned=5,
    )

    with pytest.raises(ValueError, match="population_size cannot be smaller than survivors_count"):
        config.validate()