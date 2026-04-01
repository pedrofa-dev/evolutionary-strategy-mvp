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
        dataset_catalog_id="core_1h_spot",
    )

    assert config.mutation_seed == 42
    assert config.population_size == 12
    assert config.target_population_size == 12
    assert config.survivors_count == 4
    assert config.generations_planned == 25
    assert config.trade_cost_rate == 0.001
    assert config.cost_penalty_weight == 0.25
    assert config.trade_count_penalty_weight == 0.0
    assert config.regime_filter_enabled is False
    assert config.min_trend_long_for_entry == 0.0
    assert config.min_breakout_for_entry == 0.0
    assert config.max_realized_volatility_for_entry is None
    assert config.dataset_catalog_id == "core_1h_spot"


def test_run_config_accepts_required_dataset_catalog_id() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        dataset_catalog_id="core_1h_spot",
    )

    assert config.dataset_catalog_id == "core_1h_spot"


def test_run_config_accepts_explicit_seeds() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        dataset_catalog_id="core_1h_spot",
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
        dataset_catalog_id="core_1h_spot",
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
            dataset_catalog_id="core_1h_spot",
        )


def test_run_config_rejects_non_positive_target_population_size() -> None:
    with pytest.raises(ValueError, match="target_population_size must be greater than 0"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=0,
            survivors_count=4,
            generations_planned=25,
            dataset_catalog_id="core_1h_spot",
        )


def test_run_config_rejects_target_population_smaller_than_survivors() -> None:
    with pytest.raises(ValueError, match="target_population_size cannot be smaller than survivors_count"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=3,
            survivors_count=4,
            generations_planned=25,
            dataset_catalog_id="core_1h_spot",
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
            dataset_catalog_id="core_1h_spot",
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
            dataset_catalog_id="core_1h_spot",
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
            dataset_catalog_id="core_1h_spot",
        )


def test_run_config_accepts_regime_filter_fields() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        regime_filter_enabled=True,
        min_trend_long_for_entry=0.2,
        min_breakout_for_entry=0.1,
        max_realized_volatility_for_entry=0.4,
        dataset_catalog_id="core_1h_spot",
    )

    assert config.regime_filter_enabled is True
    assert config.min_trend_long_for_entry == 0.2
    assert config.min_breakout_for_entry == 0.1
    assert config.max_realized_volatility_for_entry == 0.4


def test_run_config_accepts_entry_trigger_overrides() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        dataset_catalog_id="core_1h_spot",
        entry_trigger_overrides={
            "entry_score_threshold": 0.55,
            "min_positive_families": 3,
            "require_trend_or_breakout": True,
        },
    )

    assert config.entry_trigger_overrides is not None
    assert config.entry_trigger_overrides["entry_score_threshold"] == 0.55


def test_run_config_requires_dataset_catalog_id() -> None:
    with pytest.raises(ValueError, match="dataset_catalog_id is required"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            dataset_catalog_id="",
        )


def test_run_config_rejects_seed_start_without_seed_count() -> None:
    with pytest.raises(ValueError, match="seed_start and seed_count must be provided together"):
        RunConfig(
            mutation_seed=42,
            population_size=12,
            target_population_size=12,
            survivors_count=4,
            generations_planned=25,
            dataset_catalog_id="core_1h_spot",
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
            dataset_catalog_id="core_1h_spot",
            seeds=[101, 102],
            seed_start=100,
            seed_count=6,
        )
