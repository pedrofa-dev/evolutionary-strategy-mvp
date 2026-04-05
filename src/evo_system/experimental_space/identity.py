from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import TYPE_CHECKING, Any

from evo_system.experimental_space import (
    get_default_market_mode,
    get_default_decision_policy,
    get_default_genome_schema,
    get_default_mutation_profile_definition,
    get_default_signal_pack,
    get_market_mode,
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
    market_mode_name: str
    leverage: float
    mutation_profile: dict[str, Any]
    experiment_preset_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_pack_name": self.signal_pack_name,
            "genome_schema_name": self.genome_schema_name,
            "gene_type_catalog_name": self.gene_type_catalog_name,
            "decision_policy_name": self.decision_policy_name,
            "mutation_profile_name": self.mutation_profile_name,
            "market_mode_name": self.market_mode_name,
            "leverage": self.leverage,
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
            market_mode_name=str(data["market_mode_name"]),
            leverage=float(data.get("leverage", 1.0)),
            mutation_profile=dict(data.get("mutation_profile") or {}),
            experiment_preset_name=(
                str(data["experiment_preset_name"])
                if data.get("experiment_preset_name") is not None
                else None
            ),
        )


UNKNOWN_MODULAR_COMPONENT = "unknown"
PERSISTED_EXPERIMENTAL_SPACE_CONFIG_KEYS = (
    "signal_pack_name",
    "genome_schema_name",
    "decision_policy_name",
    "mutation_profile_name",
    "market_mode_name",
    "leverage",
    "experiment_preset_name",
)


def normalize_experimental_space_snapshot(
    snapshot: dict[str, Any] | ExperimentalSpaceSnapshot | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, ExperimentalSpaceSnapshot):
        snapshot_dict = snapshot.to_dict()
    else:
        snapshot_dict = dict(snapshot)

    normalized = {
        "signal_pack_name": str(
            snapshot_dict.get("signal_pack_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "genome_schema_name": str(
            snapshot_dict.get("genome_schema_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "gene_type_catalog_name": str(
            snapshot_dict.get("gene_type_catalog_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "decision_policy_name": str(
            snapshot_dict.get("decision_policy_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "mutation_profile_name": str(
            snapshot_dict.get("mutation_profile_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "market_mode_name": str(
            snapshot_dict.get("market_mode_name") or UNKNOWN_MODULAR_COMPONENT
        ),
        "leverage": float(snapshot_dict.get("leverage", 1.0)),
        "mutation_profile": dict(snapshot_dict.get("mutation_profile") or {}),
        "experiment_preset_name": (
            str(snapshot_dict["experiment_preset_name"])
            if snapshot_dict.get("experiment_preset_name") is not None
            else None
        ),
    }
    return normalized


def resolve_persisted_experimental_space_snapshot(
    *,
    experimental_space_snapshot: dict[str, Any] | ExperimentalSpaceSnapshot | None,
    config_json_snapshot: dict[str, Any] | None,
    experiment_preset_name: str | None = None,
) -> dict[str, Any] | None:
    """Resolve persisted modular identity without inventing it for truly legacy rows.

    Resolution rule:
    - Prefer the explicit persisted experimental-space snapshot.
    - Fall back to config-based reconstruction only when the persisted config
      already carries explicit modular identity fields.
    - Return None for older rows that lack both, so reporting can keep showing
      ``unknown`` instead of silently assigning modern defaults retroactively.
    """
    normalized_snapshot = normalize_experimental_space_snapshot(
        experimental_space_snapshot
    )
    if normalized_snapshot is not None:
        return normalized_snapshot

    if not config_json_snapshot or not any(
        key in config_json_snapshot
        for key in PERSISTED_EXPERIMENTAL_SPACE_CONFIG_KEYS
    ):
        return None

    try:
        return normalize_experimental_space_snapshot(
            build_experimental_space_snapshot_from_config_snapshot(
                config_json_snapshot,
                experiment_preset_name=experiment_preset_name,
            )
        )
    except (KeyError, TypeError, ValueError):
        return None


def format_experimental_space_stack_label(
    snapshot: dict[str, Any] | ExperimentalSpaceSnapshot | None,
) -> str:
    normalized_snapshot = normalize_experimental_space_snapshot(snapshot)
    if normalized_snapshot is None:
        return UNKNOWN_MODULAR_COMPONENT
    return " | ".join(
        [
            f"signal_pack={normalized_snapshot['signal_pack_name']}",
            f"genome_schema={normalized_snapshot['genome_schema_name']}",
            f"gene_catalog={normalized_snapshot['gene_type_catalog_name']}",
            f"decision_policy={normalized_snapshot['decision_policy_name']}",
            f"mutation_profile={normalized_snapshot['mutation_profile_name']}",
            f"market_mode={normalized_snapshot['market_mode_name']}",
            f"leverage={normalized_snapshot['leverage']}",
            f"preset={normalized_snapshot.get('experiment_preset_name') or 'none'}",
        ]
    )


def build_runtime_component_fingerprint(
    snapshot: dict[str, Any] | ExperimentalSpaceSnapshot | None,
) -> str:
    normalized_snapshot = normalize_experimental_space_snapshot(snapshot)
    if normalized_snapshot is None:
        return UNKNOWN_MODULAR_COMPONENT
    import hashlib
    import json

    payload = {
        "signal_pack_name": normalized_snapshot["signal_pack_name"],
        "genome_schema_name": normalized_snapshot["genome_schema_name"],
        "gene_type_catalog_name": normalized_snapshot["gene_type_catalog_name"],
        "decision_policy_name": normalized_snapshot["decision_policy_name"],
        "mutation_profile_name": normalized_snapshot["mutation_profile_name"],
        "market_mode_name": normalized_snapshot["market_mode_name"],
        "leverage": normalized_snapshot["leverage"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def format_experimental_space_summary_label(
    experimental_space_summary: dict[str, Any] | None,
) -> str:
    summary = experimental_space_summary or {}
    stack_mode = str(summary.get("stack_mode") or UNKNOWN_MODULAR_COMPONENT)
    stack_labels = summary.get("stack_labels") or []
    if not stack_labels and summary.get("primary_stack_label"):
        stack_labels = [str(summary["primary_stack_label"])]
    primary_stack_label = stack_labels[0] if stack_labels else UNKNOWN_MODULAR_COMPONENT
    return f"{stack_mode} | {primary_stack_label}"


def list_experimental_space_stack_labels(
    experimental_space_summary: dict[str, Any] | None,
) -> list[str]:
    summary = experimental_space_summary or {}
    raw_stack_labels = summary.get("stack_labels") or []
    if not raw_stack_labels and summary.get("primary_stack_label"):
        raw_stack_labels = [summary["primary_stack_label"]]
    stack_labels = [
        str(label)
        for label in raw_stack_labels
        if str(label).strip()
    ]
    return stack_labels or [UNKNOWN_MODULAR_COMPONENT]


def select_primary_experimental_space_snapshot(
    snapshots: list[dict[str, Any] | ExperimentalSpaceSnapshot | None],
) -> dict[str, Any] | None:
    """Select a deterministic representative snapshot for reporting.

    Selection rule:
    - Prefer the most frequent normalized snapshot in the input set.
    - Break ties by canonical stack-label lexical order.

    This keeps reporting stable even when callers provide the same effective
    stack set in different incidental orders.
    """
    normalized_snapshots = [
        normalized_snapshot
        for snapshot in snapshots
        for normalized_snapshot in [normalize_experimental_space_snapshot(snapshot)]
        if normalized_snapshot is not None
    ]
    if not normalized_snapshots:
        return None

    counts = Counter(
        format_experimental_space_stack_label(snapshot)
        for snapshot in normalized_snapshots
    )
    primary_stack_label = min(
        counts,
        key=lambda label: (-counts[label], label),
    )
    for snapshot in sorted(
        normalized_snapshots,
        key=format_experimental_space_stack_label,
    ):
        if format_experimental_space_stack_label(snapshot) == primary_stack_label:
            return snapshot
    return None


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
    default_market_mode_name = get_default_market_mode().name
    leverage = float(config_json_snapshot.get("leverage", 1.0))

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
    market_mode = get_market_mode(
        str(config_json_snapshot.get("market_mode_name", default_market_mode_name))
    )
    market_mode.validate_runtime_config(leverage=leverage)

    return ExperimentalSpaceSnapshot(
        signal_pack_name=signal_pack.name,
        genome_schema_name=genome_schema.name,
        gene_type_catalog_name=genome_schema.get_gene_type_catalog().name,
        decision_policy_name=decision_policy.name,
        mutation_profile_name=mutation_profile_definition.name,
        market_mode_name=market_mode.name,
        leverage=leverage,
        mutation_profile=dict(config_json_snapshot.get("mutation_profile") or {}),
        experiment_preset_name=experiment_preset_name,
    )


def summarize_experimental_space_snapshots(
    snapshots: list[dict[str, Any] | None],
) -> dict[str, Any]:
    normalized_snapshots = [
        normalized_snapshot
        for snapshot in snapshots
        for normalized_snapshot in [normalize_experimental_space_snapshot(snapshot)]
        if normalized_snapshot is not None
    ]
    if not normalized_snapshots:
        return {
            "stack_mode": UNKNOWN_MODULAR_COMPONENT,
            "signal_pack_names": [],
            "genome_schema_names": [],
            "gene_type_catalog_names": [],
            "decision_policy_names": [],
            "mutation_profile_names": [],
            "market_mode_names": [],
            "leverage_values": [],
            "experiment_preset_names": [],
            "stack_labels": [],
            "primary_stack_label": UNKNOWN_MODULAR_COMPONENT,
            "primary_signal_pack_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_genome_schema_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_gene_type_catalog_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_decision_policy_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_mutation_profile_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_market_mode_name": UNKNOWN_MODULAR_COMPONENT,
            "primary_leverage": 1.0,
            "primary_experiment_preset_name": None,
        }

    def unique_values(key: str) -> list[str]:
        return sorted(
            {
                str(snapshot[key])
                for snapshot in normalized_snapshots
                if snapshot.get(key) is not None
            }
        )

    stack_labels = sorted(
        {format_experimental_space_stack_label(snapshot) for snapshot in normalized_snapshots}
    )
    primary_snapshot = select_primary_experimental_space_snapshot(normalized_snapshots)
    assert primary_snapshot is not None

    return {
        "stack_mode": "single_stack" if len(stack_labels) == 1 else "mixed_stacks",
        "signal_pack_names": unique_values("signal_pack_name"),
        "genome_schema_names": unique_values("genome_schema_name"),
        "gene_type_catalog_names": unique_values("gene_type_catalog_name"),
        "decision_policy_names": unique_values("decision_policy_name"),
        "mutation_profile_names": unique_values("mutation_profile_name"),
        "market_mode_names": unique_values("market_mode_name"),
        "leverage_values": sorted(
            {float(snapshot["leverage"]) for snapshot in normalized_snapshots}
        ),
        "experiment_preset_names": unique_values("experiment_preset_name"),
        "stack_labels": stack_labels,
        "primary_stack_label": format_experimental_space_stack_label(primary_snapshot),
        "primary_signal_pack_name": primary_snapshot["signal_pack_name"],
        "primary_genome_schema_name": primary_snapshot["genome_schema_name"],
        "primary_gene_type_catalog_name": primary_snapshot["gene_type_catalog_name"],
        "primary_decision_policy_name": primary_snapshot["decision_policy_name"],
        "primary_mutation_profile_name": primary_snapshot["mutation_profile_name"],
        "primary_market_mode_name": primary_snapshot["market_mode_name"],
        "primary_leverage": primary_snapshot["leverage"],
        "primary_experiment_preset_name": primary_snapshot["experiment_preset_name"],
    }
