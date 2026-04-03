from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from evo_system.experimental_space import (
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
    signal_pack = get_signal_pack(run_config.signal_pack_name)
    genome_schema = get_genome_schema(run_config.genome_schema_name)
    decision_policy = get_decision_policy(run_config.decision_policy_name)
    mutation_profile_definition = get_mutation_profile_definition(
        run_config.mutation_profile_name
    )

    return ExperimentalSpaceSnapshot(
        signal_pack_name=signal_pack.name,
        genome_schema_name=genome_schema.name,
        gene_type_catalog_name=genome_schema.get_gene_type_catalog().name,
        decision_policy_name=decision_policy.name,
        mutation_profile_name=mutation_profile_definition.name,
        mutation_profile=run_config.mutation_profile.to_dict(),
        experiment_preset_name=experiment_preset_name,
    )
