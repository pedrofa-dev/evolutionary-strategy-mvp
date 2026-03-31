from __future__ import annotations

import json
from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import Genome
from evo_system.experimentation.external_validation import (
    build_external_validation_metrics,
    run_external_validation,
)
from evo_system.reporting.champion_loader import ChampionRow, load_champions
from evo_system.storage import DEFAULT_PERSISTENCE_DB_PATH


DEFAULT_DB_PATH = DEFAULT_PERSISTENCE_DB_PATH
DEFAULT_DATASET_ROOT = Path("data/datasets")
SUPPORTED_DATASET_LAYERS = {"external", "audit"}


def load_champion_by_id(db_path: Path, champion_id: int) -> ChampionRow:
    for champion in load_champions(db_path):
        if champion.id == champion_id:
            return champion

    raise ValueError(f"Champion id not found: {champion_id}")


def load_genome_from_json(genome_json_path: Path) -> Genome:
    data = json.loads(genome_json_path.read_text(encoding="utf-8"))

    if isinstance(data, dict) and "genome" in data:
        data = data["genome"]

    if not isinstance(data, dict):
        raise ValueError("genome JSON must contain an object")

    return Genome.from_dict(data)


def load_genome(
    *,
    db_path: Path,
    champion_id: int | None,
    genome_json_path: Path | None,
) -> tuple[Genome, str]:
    if champion_id is not None:
        champion = load_champion_by_id(db_path, champion_id)
        return Genome.from_dict(champion.genome), f"champion_id={champion_id}"

    if genome_json_path is not None:
        return load_genome_from_json(genome_json_path), str(genome_json_path)

    raise ValueError("either champion_id or genome_json_path is required")


def resolve_dataset_paths(
    *,
    dataset_root: Path,
    dataset_catalog_id: str | None,
    dataset_layer: str | None,
    direct_dataset_paths: list[Path] | None,
) -> list[Path]:
    if direct_dataset_paths:
        return [path for path in direct_dataset_paths]

    if dataset_catalog_id is None or dataset_layer is None:
        raise ValueError(
            "dataset_catalog_id and dataset_layer are required when dataset paths are not provided"
        )

    if dataset_layer not in SUPPORTED_DATASET_LAYERS:
        raise ValueError(
            f"dataset_layer must be one of: {', '.join(sorted(SUPPORTED_DATASET_LAYERS))}"
        )

    layer_root = dataset_root / dataset_catalog_id / dataset_layer
    dataset_paths = sorted(layer_root.rglob("candles.csv"))

    if not dataset_paths:
        raise FileNotFoundError(f"No datasets found under {layer_root}")

    return dataset_paths


def evaluate_genome_on_datasets(
    *,
    genome: Genome,
    dataset_paths: list[Path],
    cost_penalty_weight: float,
    trade_cost_rate: float,
) -> AgentEvaluation:
    return run_external_validation(
        agent=Agent.create(genome),
        external_dataset_paths=dataset_paths,
        cost_penalty_weight=cost_penalty_weight,
        trade_cost_rate=trade_cost_rate,
    )


def build_evaluation_output(
    *,
    evaluation: AgentEvaluation,
    dataset_paths: list[Path],
    dataset_root: Path,
) -> dict:
    return build_external_validation_metrics(
        evaluation=evaluation,
        dataset_paths=dataset_paths,
        dataset_root=dataset_root,
    )
