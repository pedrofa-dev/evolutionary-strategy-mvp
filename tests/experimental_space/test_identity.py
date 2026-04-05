from evo_system.domain.run_config import RunConfig
from evo_system.experimental_space.identity import (
    ExperimentalSpaceSnapshot,
    build_experimental_space_snapshot,
    build_experimental_space_snapshot_from_config_snapshot,
    build_runtime_component_fingerprint,
    format_experimental_space_stack_label,
    format_experimental_space_summary_label,
    list_experimental_space_stack_labels,
    normalize_experimental_space_snapshot,
    select_primary_experimental_space_snapshot,
    summarize_experimental_space_snapshots,
)


def test_build_experimental_space_snapshot_is_stable_and_serializable() -> None:
    config = RunConfig(
        mutation_seed=42,
        population_size=12,
        target_population_size=12,
        survivors_count=4,
        generations_planned=25,
        dataset_catalog_id="core_1h_spot",
        genome_schema_name="modular_genome_v1",
    )

    snapshot = build_experimental_space_snapshot(
        config,
        experiment_preset_name="standard",
    )

    assert snapshot.signal_pack_name == "policy_v21_default"
    assert snapshot.genome_schema_name == "modular_genome_v1"
    assert snapshot.gene_type_catalog_name == "modular_genome_v1_gene_catalog"
    assert snapshot.decision_policy_name == "policy_v2_default"
    assert snapshot.mutation_profile_name == "default_runtime_profile"
    assert snapshot.market_mode_name == "spot"
    assert snapshot.leverage == 1.0
    assert snapshot.experiment_preset_name == "standard"

    roundtrip = ExperimentalSpaceSnapshot.from_dict(snapshot.to_dict())

    assert roundtrip == snapshot


def test_build_experimental_space_snapshot_from_config_snapshot_uses_explicit_names() -> None:
    snapshot = build_experimental_space_snapshot_from_config_snapshot(
        {
            "signal_pack_name": "policy_v21_default",
            "genome_schema_name": "modular_genome_v1",
            "decision_policy_name": "policy_v2_default",
            "mutation_profile_name": "default_runtime_profile",
            "mutation_profile": {"numeric_delta_scale": 1.25},
            "market_mode_name": "spot",
            "leverage": 1.0,
        },
        experiment_preset_name="standard",
    )

    assert snapshot.signal_pack_name == "policy_v21_default"
    assert snapshot.genome_schema_name == "modular_genome_v1"
    assert snapshot.gene_type_catalog_name == "modular_genome_v1_gene_catalog"
    assert snapshot.decision_policy_name == "policy_v2_default"
    assert snapshot.mutation_profile_name == "default_runtime_profile"
    assert snapshot.mutation_profile == {"numeric_delta_scale": 1.25}
    assert snapshot.market_mode_name == "spot"
    assert snapshot.leverage == 1.0
    assert snapshot.experiment_preset_name == "standard"


def test_build_experimental_space_snapshot_from_config_snapshot_uses_registry_defaults() -> None:
    snapshot = build_experimental_space_snapshot_from_config_snapshot(
        {"mutation_profile": {}},
        experiment_preset_name=None,
    )

    assert snapshot.signal_pack_name == "policy_v21_default"
    assert snapshot.genome_schema_name == "policy_v2_default"
    assert snapshot.gene_type_catalog_name == "modular_genome_v1_gene_catalog"
    assert snapshot.decision_policy_name == "policy_v2_default"
    assert snapshot.mutation_profile_name == "default_runtime_profile"
    assert snapshot.market_mode_name == "spot"
    assert snapshot.leverage == 1.0
    assert snapshot.experiment_preset_name is None


def test_summarize_experimental_space_snapshots_is_stable() -> None:
    summary = summarize_experimental_space_snapshots(
        [
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "modular_genome_v1",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "standard",
            },
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "modular_genome_v1",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "standard",
            },
        ]
    )

    assert summary["stack_mode"] == "single_stack"
    assert summary["signal_pack_names"] == ["policy_v21_default"]
    assert summary["genome_schema_names"] == ["modular_genome_v1"]
    assert summary["decision_policy_names"] == ["policy_v2_default"]
    assert summary["mutation_profile_names"] == ["default_runtime_profile"]
    assert summary["market_mode_names"] == ["spot"]
    assert summary["leverage_values"] == [1.0]
    assert summary["experiment_preset_names"] == ["standard"]
    assert summary["primary_signal_pack_name"] == "policy_v21_default"
    assert summary["primary_decision_policy_name"] == "policy_v2_default"
    assert summary["primary_market_mode_name"] == "spot"
    assert summary["primary_leverage"] == 1.0
    assert summary["primary_stack_label"] == (
        "signal_pack=policy_v21_default | genome_schema=modular_genome_v1 | gene_catalog=modular_genome_v1_gene_catalog | decision_policy=policy_v2_default | mutation_profile=default_runtime_profile | market_mode=spot | leverage=1.0 | preset=standard"
    )
    assert summary["stack_labels"] == [
        "signal_pack=policy_v21_default | genome_schema=modular_genome_v1 | gene_catalog=modular_genome_v1_gene_catalog | decision_policy=policy_v2_default | mutation_profile=default_runtime_profile | market_mode=spot | leverage=1.0 | preset=standard"
    ]


def test_summarize_experimental_space_snapshots_reports_mixed_stacks() -> None:
    summary = summarize_experimental_space_snapshots(
        [
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "modular_genome_v1",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "standard",
            },
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "policy_v2_default",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "screening",
            },
        ]
    )

    assert summary["stack_mode"] == "mixed_stacks"
    assert summary["genome_schema_names"] == ["modular_genome_v1", "policy_v2_default"]
    assert summary["experiment_preset_names"] == ["screening", "standard"]
    assert len(summary["stack_labels"]) == 2


def test_select_primary_experimental_space_snapshot_is_frequency_then_label_stable() -> None:
    snapshots = [
        {
            "signal_pack_name": "z_pack",
            "genome_schema_name": "schema_b",
            "gene_type_catalog_name": "catalog_b",
            "decision_policy_name": "policy_b",
            "mutation_profile_name": "profile_b",
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "screening",
        },
        {
            "signal_pack_name": "a_pack",
            "genome_schema_name": "schema_a",
            "gene_type_catalog_name": "catalog_a",
            "decision_policy_name": "policy_a",
            "mutation_profile_name": "profile_a",
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "standard",
        },
        {
            "signal_pack_name": "a_pack",
            "genome_schema_name": "schema_a",
            "gene_type_catalog_name": "catalog_a",
            "decision_policy_name": "policy_a",
            "mutation_profile_name": "profile_a",
            "market_mode_name": "spot",
            "leverage": 1.0,
            "experiment_preset_name": "standard",
        },
    ]

    primary = select_primary_experimental_space_snapshot(snapshots)

    assert primary is not None
    assert primary["signal_pack_name"] == "a_pack"
    assert primary["genome_schema_name"] == "schema_a"


def test_summarize_experimental_space_snapshots_primary_fields_are_order_independent() -> None:
    first_order = summarize_experimental_space_snapshots(
        [
            {
                "signal_pack_name": "z_pack",
                "genome_schema_name": "schema_b",
                "gene_type_catalog_name": "catalog_b",
                "decision_policy_name": "policy_b",
                "mutation_profile_name": "profile_b",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "screening",
            },
            {
                "signal_pack_name": "a_pack",
                "genome_schema_name": "schema_a",
                "gene_type_catalog_name": "catalog_a",
                "decision_policy_name": "policy_a",
                "mutation_profile_name": "profile_a",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "standard",
            },
        ]
    )
    second_order = summarize_experimental_space_snapshots(
        [
            {
                "signal_pack_name": "a_pack",
                "genome_schema_name": "schema_a",
                "gene_type_catalog_name": "catalog_a",
                "decision_policy_name": "policy_a",
                "mutation_profile_name": "profile_a",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "standard",
            },
            {
                "signal_pack_name": "z_pack",
                "genome_schema_name": "schema_b",
                "gene_type_catalog_name": "catalog_b",
                "decision_policy_name": "policy_b",
                "mutation_profile_name": "profile_b",
                "market_mode_name": "spot",
                "leverage": 1.0,
                "experiment_preset_name": "screening",
            },
        ]
    )

    assert first_order["primary_stack_label"] == second_order["primary_stack_label"]
    assert first_order["primary_signal_pack_name"] == second_order["primary_signal_pack_name"]
    assert first_order["primary_genome_schema_name"] == second_order["primary_genome_schema_name"]


def test_normalize_experimental_space_snapshot_fills_missing_fields() -> None:
    normalized = normalize_experimental_space_snapshot(
        {"signal_pack_name": "policy_v21_default"}
    )

    assert normalized == {
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "unknown",
        "gene_type_catalog_name": "unknown",
        "decision_policy_name": "unknown",
        "mutation_profile_name": "unknown",
        "market_mode_name": "unknown",
        "leverage": 1.0,
        "mutation_profile": {},
        "experiment_preset_name": None,
    }


def test_format_experimental_space_labels_are_stable_for_missing_metadata() -> None:
    assert format_experimental_space_stack_label(None) == "unknown"
    assert format_experimental_space_stack_label(
        {"signal_pack_name": "policy_v21_default"}
    ) == (
        "signal_pack=policy_v21_default | genome_schema=unknown | "
        "gene_catalog=unknown | decision_policy=unknown | "
        "mutation_profile=unknown | market_mode=unknown | leverage=1.0 | preset=none"
    )
    assert format_experimental_space_summary_label(None) == "unknown | unknown"
    assert list_experimental_space_stack_labels(None) == ["unknown"]


def test_runtime_component_fingerprint_is_stable_and_market_mode_sensitive() -> None:
    base_snapshot = {
        "signal_pack_name": "policy_v21_default",
        "genome_schema_name": "modular_genome_v1",
        "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
        "decision_policy_name": "policy_v2_default",
        "mutation_profile_name": "default_runtime_profile",
        "mutation_profile": {},
        "market_mode_name": "spot",
        "leverage": 1.0,
        "experiment_preset_name": "standard",
    }

    assert build_runtime_component_fingerprint(base_snapshot) == build_runtime_component_fingerprint(
        dict(base_snapshot)
    )
    assert build_runtime_component_fingerprint(base_snapshot) != build_runtime_component_fingerprint(
        {**base_snapshot, "market_mode_name": "futures"}
    )
    assert build_runtime_component_fingerprint(base_snapshot) != build_runtime_component_fingerprint(
        {**base_snapshot, "leverage": 2.0}
    )
