from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evo_system.experimental_space.identity import (
    format_experimental_space_stack_label,
    resolve_persisted_experimental_space_snapshot,
)
from evo_system.storage import DEFAULT_PERSISTENCE_DB_PATH, PersistenceStore


@dataclass
class ChampionRow:
    id: int
    run_id: str
    generation_number: int | None
    mutation_seed: int | None
    config_name: str | None
    genome: dict[str, Any]
    metrics: dict[str, Any]
    created_at: str | None
    champion_type: str | None
    config_snapshot: dict[str, Any]
    dataset_catalog_id: str | None
    dataset_signature: str | None
    experimental_space_snapshot: dict[str, Any] | None


def build_normalized_metrics(champion_row: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(champion_row.get("champion_metrics_json") or {})
    train_metrics = champion_row.get("train_metrics_json") or {}
    validation_metrics = champion_row.get("validation_metrics_json") or {}
    config_snapshot = champion_row.get("config_json_snapshot") or {}

    metrics.setdefault("config_name", champion_row.get("config_name"))
    metrics.setdefault("dataset_catalog_id", champion_row.get("dataset_catalog_id"))
    metrics.setdefault("dataset_signature", champion_row.get("dataset_signature"))
    metrics.setdefault("champion_type", champion_row.get("champion_type"))
    metrics.setdefault("dataset_root", config_snapshot.get("dataset_root"))

    train_field_map = {
        "train_selection": "selection_score",
        "train_profit": "median_profit",
        "train_drawdown": "median_drawdown",
        "train_trades": "median_trades",
        "train_dataset_scores": "dataset_scores",
        "train_dataset_profits": "dataset_profits",
        "train_dataset_drawdowns": "dataset_drawdowns",
        "train_violations": "violations",
        "train_is_valid": "is_valid",
    }
    validation_field_map = {
        "validation_selection": "selection_score",
        "validation_profit": "median_profit",
        "validation_drawdown": "median_drawdown",
        "validation_trades": "median_trades",
        "validation_dispersion": "dispersion",
        "validation_dataset_scores": "dataset_scores",
        "validation_dataset_profits": "dataset_profits",
        "validation_dataset_drawdowns": "dataset_drawdowns",
        "validation_violations": "violations",
        "validation_is_valid": "is_valid",
    }

    for target_field, source_field in train_field_map.items():
        metrics.setdefault(target_field, train_metrics.get(source_field))
    for target_field, source_field in validation_field_map.items():
        metrics.setdefault(target_field, validation_metrics.get(source_field))

    for list_field in (
        "train_dataset_scores",
        "train_dataset_profits",
        "train_dataset_drawdowns",
        "train_violations",
        "validation_dataset_scores",
        "validation_dataset_profits",
        "validation_dataset_drawdowns",
        "validation_violations",
        "all_train_dataset_names",
        "all_validation_dataset_names",
        "sampled_train_dataset_names",
        "validation_dataset_names",
        "train_dataset_names",
    ):
        if metrics.get(list_field) is None:
            metrics[list_field] = []

    return metrics


def resolve_experimental_space_snapshot(champion_row: dict[str, Any]) -> dict[str, Any] | None:
    return resolve_persisted_experimental_space_snapshot(
        experimental_space_snapshot=champion_row.get("experimental_space_snapshot_json"),
        config_json_snapshot=champion_row.get("config_json_snapshot"),
    )


def load_champions(
    db_path: Path = DEFAULT_PERSISTENCE_DB_PATH,
    run_id: str | None = None,
    run_ids: list[str] | None = None,
) -> list[ChampionRow]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    resolved_run_ids = list(run_ids or [])
    if run_id is not None:
        resolved_run_ids.append(run_id)

    store = PersistenceStore(db_path)
    store.initialize()
    rows: list[ChampionRow] = []
    for champion_row in store.load_champions(run_ids=resolved_run_ids or None):
        rows.append(
            ChampionRow(
                id=int(champion_row["id"]),
                run_id=str(champion_row["run_id"]),
                generation_number=champion_row.get("generation_number"),
                mutation_seed=champion_row.get("mutation_seed"),
                config_name=champion_row.get("config_name"),
                genome=dict(champion_row.get("genome_json_snapshot") or {}),
                metrics=build_normalized_metrics(champion_row),
                created_at=champion_row.get("persisted_at"),
                champion_type=champion_row.get("champion_type"),
                config_snapshot=dict(champion_row.get("config_json_snapshot") or {}),
                dataset_catalog_id=champion_row.get("dataset_catalog_id"),
                dataset_signature=champion_row.get("dataset_signature"),
                experimental_space_snapshot=resolve_experimental_space_snapshot(
                    champion_row
                ),
            )
        )
    return rows


def resolve_config_name(champion: ChampionRow) -> str | None:
    metrics_config_name = champion.metrics.get("config_name")
    if isinstance(metrics_config_name, str) and metrics_config_name.strip():
        return metrics_config_name
    return champion.config_name


def resolve_dataset_root(champion: ChampionRow) -> str | None:
    dataset_root = champion.metrics.get("dataset_root")
    if isinstance(dataset_root, str) and dataset_root.strip():
        return dataset_root
    return None


def resolve_context_name(champion: ChampionRow) -> str | None:
    context_name = champion.metrics.get("context_name")
    if isinstance(context_name, str) and context_name.strip():
        return context_name
    return None


def resolve_dataset_signature(champion: ChampionRow) -> str | None:
    dataset_signature = champion.metrics.get("dataset_signature")
    if isinstance(dataset_signature, str) and dataset_signature.strip():
        return dataset_signature
    return None


def resolve_champion_type(champion: ChampionRow) -> str | None:
    if isinstance(champion.champion_type, str) and champion.champion_type.strip():
        return champion.champion_type
    champion_type = champion.metrics.get("champion_type")
    if isinstance(champion_type, str) and champion_type.strip():
        return champion_type
    return None


def flatten_champion(champion: ChampionRow) -> dict[str, Any]:
    stored_config_name = resolve_config_name(champion)
    normalized_snapshot = resolve_persisted_experimental_space_snapshot(
        experimental_space_snapshot=champion.experimental_space_snapshot,
        config_json_snapshot=champion.config_snapshot,
    )

    return {
        "id": champion.id,
        "run_id": champion.run_id,
        "generation_number": champion.generation_number,
        "mutation_seed": champion.mutation_seed,
        "config_name": stored_config_name,
        "champion_type": resolve_champion_type(champion),
        "stored_config_name": champion.config_name,
        "created_at": champion.created_at,
        "context_name": resolve_context_name(champion),
        "dataset_root": resolve_dataset_root(champion),
        "dataset_signature": resolve_dataset_signature(champion),
        "train_sample_size": champion.metrics.get("train_sample_size"),
        "train_dataset_count_available": champion.metrics.get(
            "train_dataset_count_available"
        ),
        "validation_dataset_count_available": champion.metrics.get(
            "validation_dataset_count_available"
        ),
        "all_train_dataset_names": champion.metrics.get("all_train_dataset_names", []),
        "all_validation_dataset_names": champion.metrics.get(
            "all_validation_dataset_names",
            [],
        ),
        "sampled_train_dataset_names": champion.metrics.get(
            "sampled_train_dataset_names",
            [],
        ),
        "validation_dataset_names": champion.metrics.get("validation_dataset_names", []),
        "train_selection": champion.metrics.get("train_selection"),
        "train_profit": champion.metrics.get("train_profit"),
        "train_drawdown": champion.metrics.get("train_drawdown"),
        "train_trades": champion.metrics.get("train_trades"),
        "validation_selection": champion.metrics.get("validation_selection"),
        "validation_profit": champion.metrics.get("validation_profit"),
        "validation_drawdown": champion.metrics.get("validation_drawdown"),
        "validation_trades": champion.metrics.get("validation_trades"),
        "selection_gap": champion.metrics.get("selection_gap"),
        "validation_dispersion": champion.metrics.get("validation_dispersion"),
        "positive_validation_datasets": champion.metrics.get(
            "positive_validation_datasets"
        ),
        "negative_validation_datasets": champion.metrics.get(
            "negative_validation_datasets"
        ),
        "train_dataset_scores": champion.metrics.get("train_dataset_scores", []),
        "train_dataset_profits": champion.metrics.get("train_dataset_profits", []),
        "train_dataset_drawdowns": champion.metrics.get("train_dataset_drawdowns", []),
        "validation_dataset_scores": champion.metrics.get(
            "validation_dataset_scores",
            [],
        ),
        "validation_dataset_profits": champion.metrics.get(
            "validation_dataset_profits",
            [],
        ),
        "validation_dataset_drawdowns": champion.metrics.get(
            "validation_dataset_drawdowns",
            [],
        ),
        "train_dataset_names": champion.metrics.get("train_dataset_names", []),
        "train_violations": champion.metrics.get("train_violations", []),
        "validation_violations": champion.metrics.get("validation_violations", []),
        "train_is_valid": champion.metrics.get("train_is_valid"),
        "validation_is_valid": champion.metrics.get("validation_is_valid"),
        "signal_pack_name": (
            normalized_snapshot["signal_pack_name"]
            if normalized_snapshot is not None
            else "unknown"
        ),
        "genome_schema_name": (
            normalized_snapshot["genome_schema_name"]
            if normalized_snapshot is not None
            else "unknown"
        ),
        "gene_type_catalog_name": (
            normalized_snapshot["gene_type_catalog_name"]
            if normalized_snapshot is not None
            else "unknown"
        ),
        "decision_policy_name": (
            normalized_snapshot["decision_policy_name"]
            if normalized_snapshot is not None
            else "unknown"
        ),
        "mutation_profile_name": (
            normalized_snapshot["mutation_profile_name"]
            if normalized_snapshot is not None
            else "unknown"
        ),
        "experiment_preset_name": (
            normalized_snapshot.get("experiment_preset_name")
            if normalized_snapshot is not None
            else None
        ),
        "modular_stack_label": format_experimental_space_stack_label(normalized_snapshot),
        **champion.genome,
    }
