from evo_system.domain.run_config import RunConfig
from evo_system.experimental_space.identity import (
    ExperimentalSpaceSnapshot,
    build_experimental_space_snapshot,
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
