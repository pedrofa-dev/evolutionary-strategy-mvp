from evo_system.domain.run_config import RunConfig
from evo_system.experimental_space.identity import (
    ExperimentalSpaceSnapshot,
    build_experimental_space_snapshot,
    build_experimental_space_snapshot_from_config_snapshot,
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
        },
        experiment_preset_name="standard",
    )

    assert snapshot.signal_pack_name == "policy_v21_default"
    assert snapshot.genome_schema_name == "modular_genome_v1"
    assert snapshot.gene_type_catalog_name == "modular_genome_v1_gene_catalog"
    assert snapshot.decision_policy_name == "policy_v2_default"
    assert snapshot.mutation_profile_name == "default_runtime_profile"
    assert snapshot.mutation_profile == {"numeric_delta_scale": 1.25}
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
                "experiment_preset_name": "standard",
            },
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "modular_genome_v1",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "experiment_preset_name": "standard",
            },
        ]
    )

    assert summary["stack_mode"] == "single_stack"
    assert summary["signal_pack_names"] == ["policy_v21_default"]
    assert summary["genome_schema_names"] == ["modular_genome_v1"]
    assert summary["decision_policy_names"] == ["policy_v2_default"]
    assert summary["mutation_profile_names"] == ["default_runtime_profile"]
    assert summary["experiment_preset_names"] == ["standard"]
    assert summary["stack_labels"] == [
        "signal_pack=policy_v21_default | genome_schema=modular_genome_v1 | gene_catalog=modular_genome_v1_gene_catalog | decision_policy=policy_v2_default | mutation_profile=default_runtime_profile | preset=standard"
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
                "experiment_preset_name": "standard",
            },
            {
                "signal_pack_name": "policy_v21_default",
                "genome_schema_name": "policy_v2_default",
                "gene_type_catalog_name": "modular_genome_v1_gene_catalog",
                "decision_policy_name": "policy_v2_default",
                "mutation_profile_name": "default_runtime_profile",
                "experiment_preset_name": "screening",
            },
        ]
    )

    assert summary["stack_mode"] == "mixed_stacks"
    assert summary["genome_schema_names"] == ["modular_genome_v1", "policy_v2_default"]
    assert summary["experiment_preset_names"] == ["screening", "standard"]
    assert len(summary["stack_labels"]) == 2
