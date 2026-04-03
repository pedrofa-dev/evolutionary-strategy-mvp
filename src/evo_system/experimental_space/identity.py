from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from evo_system.experimental_space import (
    get_default_decision_policy,
    get_default_genome_schema,
    get_default_mutation_profile_definition,
    get_default_signal_pack,
    get_decision_policy,
    get_genome_schema,
    get_mutation_profile_definition,
    get_signal_pack,
)

if TYPE_CHECKING:
    from evo_system.domain.run_config import RunConfig


@dataclass(frozen=True)
class ExperimentalSpaceSnapshot:
    """Stable, serializable identity of the modular runtime components in use.

    Why it exists:
    - The runtime is already modularizing signals, schemas, decision logic, and
      mutation profiles.
    - This snapshot makes those choices explicit and stable in summaries/logs
      without changing the canonical execution fingerprint in this phase.
    """

    signal_pack_name: str
    genome_schema_name: str
    gene_type_catalog_name: str
    decision_policy_name: str
    mutation_profile_name: str
    mutation_profile: dict[str, Any]
    experiment_preset_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_pack_name": self.signal_pack_name,
            "genome_schema_name": self.genome_schema_name,
            "gene_type_catalog_name": self.gene_type_catalog_name,
            "decision_policy_name": self.decision_policy_name,
            "mutation_profile_name": self.mutation_profile_name,
            "mutation_profile": dict(self.mutation_profile),
            "experiment_preset_name": self.experiment_preset_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentalSpaceSnapshot":
        return cls(
            signal_pack_name=str(data["signal_pack_name"]),
            genome_schema_name=str(data["genome_schema_name"]),
            gene_type_catalog_name=str(data["gene_type_catalog_name"]),
            decision_policy_name=str(data["decision_policy_name"]),
            mutation_profile_name=str(data["mutation_profile_name"]),
            mutation_profile=dict(data.get("mutation_profile") or {}),
            experiment_preset_name=(
                str(data["experiment_preset_name"])
                if data.get("experiment_preset_name") is not None
                else None
            ),
        )


def build_experimental_space_snapshot(
    run_config: "RunConfig",
    *,
    experiment_preset_name: str | None = None,
) -> ExperimentalSpaceSnapshot:
    return build_experimental_space_snapshot_from_config_snapshot(
        run_config.to_dict(),
        experiment_preset_name=experiment_preset_name,
    )


def build_experimental_space_snapshot_from_config_snapshot(
    config_json_snapshot: dict[str, Any],
    *,
    experiment_preset_name: str | None = None,
) -> ExperimentalSpaceSnapshot:
    """Build modular runtime identity from a persisted config snapshot.

    Why it exists:
    - Persisted run rows often reconstruct identity from the executed config
      snapshot rather than from an in-memory RunConfig instance.

    Compatibility boundary:
    - This snapshot is traceability metadata only. It must not redefine reuse
      semantics or replace the execution fingerprint.
    """
    default_signal_pack_name = get_default_signal_pack().name
    default_genome_schema_name = get_default_genome_schema().name
    default_decision_policy_name = get_default_decision_policy().name
    default_mutation_profile_name = get_default_mutation_profile_definition().name

    signal_pack = get_signal_pack(
        str(config_json_snapshot.get("signal_pack_name", default_signal_pack_name))
    )
    genome_schema = get_genome_schema(
        str(config_json_snapshot.get("genome_schema_name", default_genome_schema_name))
    )
    decision_policy = get_decision_policy(
        str(
            config_json_snapshot.get(
                "decision_policy_name",
                default_decision_policy_name,
            )
        )
    )
    mutation_profile_definition = get_mutation_profile_definition(
        str(
            config_json_snapshot.get(
                "mutation_profile_name",
                default_mutation_profile_name,
            )
        )
    )

    return ExperimentalSpaceSnapshot(
        signal_pack_name=signal_pack.name,
        genome_schema_name=genome_schema.name,
        gene_type_catalog_name=genome_schema.get_gene_type_catalog().name,
        decision_policy_name=decision_policy.name,
        mutation_profile_name=mutation_profile_definition.name,
        mutation_profile=dict(config_json_snapshot.get("mutation_profile") or {}),
        experiment_preset_name=experiment_preset_name,
    )


def summarize_experimental_space_snapshots(
    snapshots: list[dict[str, Any] | None],
) -> dict[str, Any]:
    normalized_snapshots = [dict(snapshot) for snapshot in snapshots if snapshot]
    if not normalized_snapshots:
        return {
            "stack_mode": "unknown",
            "signal_pack_names": [],
            "genome_schema_names": [],
            "gene_type_catalog_names": [],
            "decision_policy_names": [],
            "mutation_profile_names": [],
            "experiment_preset_names": [],
            "stack_labels": [],
        }

    def unique_values(key: str) -> list[str]:
        return sorted(
            {
                str(snapshot[key])
                for snapshot in normalized_snapshots
                if snapshot.get(key) is not None
            }
        )

    def build_stack_label(snapshot: dict[str, Any]) -> str:
        return " | ".join(
            [
                f"signal_pack={snapshot.get('signal_pack_name', 'unknown')}",
                f"genome_schema={snapshot.get('genome_schema_name', 'unknown')}",
                f"gene_catalog={snapshot.get('gene_type_catalog_name', 'unknown')}",
                f"decision_policy={snapshot.get('decision_policy_name', 'unknown')}",
                f"mutation_profile={snapshot.get('mutation_profile_name', 'unknown')}",
                f"preset={snapshot.get('experiment_preset_name') or 'none'}",
            ]
        )

    stack_labels = sorted({build_stack_label(snapshot) for snapshot in normalized_snapshots})

    return {
        "stack_mode": "single_stack" if len(stack_labels) == 1 else "mixed_stacks",
        "signal_pack_names": unique_values("signal_pack_name"),
        "genome_schema_names": unique_values("genome_schema_name"),
        "gene_type_catalog_names": unique_values("gene_type_catalog_name"),
        "decision_policy_names": unique_values("decision_policy_name"),
        "mutation_profile_names": unique_values("mutation_profile_name"),
        "experiment_preset_names": unique_values("experiment_preset_name"),
        "stack_labels": stack_labels,
    }
