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
                "dataset_catalog_id": "core_1h_spot",
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
    assert config.min_bars_between_entries == 0
    assert config.entry_confirmation_bars == 1
    assert config.entry_score_margin == 0.0
    assert config.regime_filter_enabled is False
    assert config.min_trend_long_for_entry == 0.0
    assert config.min_breakout_for_entry == 0.0
    assert config.max_realized_volatility_for_entry is None
    assert config.signal_pack_name == "policy_v21_default"
    assert config.genome_schema_name == "policy_v2_default"
    assert config.decision_policy_name == "policy_v2_default"
    assert config.mutation_profile_name == "default_runtime_profile"
    assert config.market_mode_name == "spot"
    assert config.leverage == 1.0


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
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.trade_cost_rate == 0.0
    assert config.cost_penalty_weight == 0.25
    assert config.trade_count_penalty_weight == 0.0
    assert config.min_bars_between_entries == 0
    assert config.entry_confirmation_bars == 1
    assert config.entry_score_margin == 0.0
    assert config.regime_filter_enabled is False
    assert config.max_realized_volatility_for_entry is None


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
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.trade_count_penalty_weight == 0.001


def test_load_run_config_reads_min_bars_between_entries(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "min_bars_between_entries": 6,
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.min_bars_between_entries == 6


def test_load_run_config_reads_entry_confirmation_bars(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "entry_confirmation_bars": 3,
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.entry_confirmation_bars == 3


def test_load_run_config_reads_entry_score_margin(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "entry_score_margin": 0.05,
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.entry_score_margin == 0.05


def test_load_run_config_reads_regime_filter_fields(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "regime_filter_enabled": True,
                "min_trend_long_for_entry": 0.2,
                "min_breakout_for_entry": 0.1,
                "max_realized_volatility_for_entry": 0.4,
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.regime_filter_enabled is True
    assert config.min_trend_long_for_entry == 0.2
    assert config.min_breakout_for_entry == 0.1
    assert config.max_realized_volatility_for_entry == 0.4


def test_load_run_config_reads_entry_trigger_overrides(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "dataset_catalog_id": "core_1h_spot",
                "entry_trigger": {
                    "entry_score_threshold": 0.55,
                    "min_positive_families": 3,
                    "require_trend_or_breakout": True,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.entry_trigger_overrides == {
        "entry_score_threshold": 0.55,
        "min_positive_families": 3,
        "require_trend_or_breakout": True,
    }


def test_load_run_config_reads_policy_v2_override_blocks(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "dataset_catalog_id": "core_1h_spot",
                "exit_policy": {
                    "max_holding_bars": 24,
                    "stop_loss_pct": 0.04,
                    "take_profit_pct": 0.12,
                },
                "trade_control": {
                    "cooldown_bars": 2,
                    "min_holding_bars": 2,
                    "reentry_block_bars": 2,
                },
                "entry_trigger_constraints": {
                    "min_trend_weight": 0.0,
                    "min_breakout_weight": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.exit_policy_overrides == {
        "max_holding_bars": 24,
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.12,
    }
    assert config.trade_control_overrides == {
        "cooldown_bars": 2,
        "min_holding_bars": 2,
        "reentry_block_bars": 2,
    }
    assert config.entry_trigger_constraints == {
        "min_trend_weight": 0.0,
        "min_breakout_weight": 0.0,
    }


def test_load_run_config_reads_explicit_modular_component_names(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "dataset_catalog_id": "core_1h_spot",
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "modular_genome_v1",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "market_mode_name": "spot",
                "leverage": 1.0,
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.signal_pack_name == "policy_v21_default"
    assert config.genome_schema_name == "modular_genome_v1"
    assert config.decision_policy_name == "policy_v2_default"
    assert config.mutation_profile_name == "default_runtime_profile"
    assert config.market_mode_name == "spot"
    assert config.leverage == 1.0


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
                "dataset_catalog_id": "core_1h_spot",
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
                "dataset_catalog_id": "core_1h_spot",
            }
        ),
        encoding="utf-8",
    )

    config = load_run_config(str(config_path))

    assert config.seeds is None
    assert config.seed_start == 100
    assert config.seed_count == 6


def test_load_run_config_preserves_null_catalog_id_for_validation(tmp_path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mutation_seed": 42,
                "population_size": 12,
                "target_population_size": 12,
                "survivors_count": 4,
                "generations_planned": 25,
                "dataset_catalog_id": None,
            }
        ),
        encoding="utf-8",
    )

    try:
        load_run_config(str(config_path))
    except ValueError as exc:
        assert "dataset_catalog_id is required" in str(exc)
    else:
        raise AssertionError("Expected dataset_catalog_id validation to fail for null.")
