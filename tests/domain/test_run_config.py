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
    assert config.trade_count_penalty_weight == 0.0
    assert config.dataset_mode == "legacy"
    assert config.dataset_catalog_id is None


def test_run_config_accepts_manifest_mode_with_catalog_id() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        dataset_mode="manifest",
        dataset_catalog_id="core_1h_spot",
    )

    assert config.dataset_mode == "manifest"
    assert config.dataset_catalog_id == "core_1h_spot"


def test_run_config_accepts_explicit_seeds() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        seeds=[101, 102, 103],
    )

    assert config.seeds == [101, 102, 103]
    assert config.seed_start is None
    assert config.seed_count is None


def test_run_config_accepts_seed_start_and_seed_count() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        seed_start=100,
        seed_count=6,
    )

    assert config.seeds is None
    assert config.seed_start == 100
    assert config.seed_count == 6


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


def test_run_config_rejects_negative_trade_count_penalty_weight() -> None:
    with pytest.raises(
        ValueError,
        match="trade_count_penalty_weight must be greater than or equal to 0.0",
    ):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            trade_count_penalty_weight=-0.001,
        )


def test_run_config_rejects_invalid_dataset_mode() -> None:
    with pytest.raises(ValueError, match="dataset_mode must be either 'legacy' or 'manifest'"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            dataset_mode="unknown",
        )


def test_run_config_requires_catalog_id_for_manifest_mode() -> None:
    with pytest.raises(ValueError, match="dataset_catalog_id is required when dataset_mode is 'manifest'"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            dataset_mode="manifest",
        )


def test_run_config_rejects_seed_start_without_seed_count() -> None:
    with pytest.raises(ValueError, match="seed_start and seed_count must be provided together"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            seed_start=100,
        )


def test_run_config_rejects_combining_seeds_with_seed_range() -> None:
    with pytest.raises(ValueError, match="seed_start/seed_count cannot be combined with seeds"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            seeds=[101, 102],
            seed_start=100,
            seed_count=6,
        )
