from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def load_champions(db_path: Path, run_id: str | None = None) -> list[ChampionRow]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    query = """
        SELECT
            id,
            run_id,
            generation_number,
            mutation_seed,
            config_name,
            genome_json,
            metrics_json,
            created_at
        FROM champions
    """
    conditions: list[str] = []
    params: list[Any] = []

    if run_id is not None:
        conditions.append("run_id = ?")
        params.append(run_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id ASC"

    rows: list[ChampionRow] = []
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(query, tuple(params))
        for db_row in cursor.fetchall():
            rows.append(
                ChampionRow(
                    id=int(db_row[0]),
                    run_id=str(db_row[1]),
                    generation_number=db_row[2],
                    mutation_seed=db_row[3],
                    config_name=db_row[4],
                    genome=json.loads(db_row[5]),
                    metrics=json.loads(db_row[6]),
                    created_at=db_row[7],
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
    champion_type = champion.metrics.get("champion_type")
    if isinstance(champion_type, str) and champion_type.strip():
        return champion_type
    return None


def flatten_champion(champion: ChampionRow) -> dict[str, Any]:
    stored_config_name = resolve_config_name(champion)

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
        **champion.genome,
    }
