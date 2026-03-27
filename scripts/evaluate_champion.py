from __future__ import annotations

import argparse
from pathlib import Path

from evo_system.experimentation.champion_evaluation import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_DB_PATH,
    SUPPORTED_DATASET_LAYERS,
    build_evaluation_output,
    evaluate_genome_on_datasets,
    load_genome,
    resolve_dataset_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a persisted champion or genome on external/audit datasets.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--champion-id",
        type=int,
        default=None,
        help="Champion id from SQLite.",
    )
    source_group.add_argument(
        "--genome-json",
        type=Path,
        default=None,
        help="Path to a genome JSON file or an agent/champion JSON containing a genome field.",
    )

    dataset_group = parser.add_mutually_exclusive_group(required=True)
    dataset_group.add_argument(
        "--dataset-catalog-id",
        type=str,
        default=None,
        help="Manifest dataset catalog id under data/datasets.",
    )
    dataset_group.add_argument(
        "--dataset-paths",
        type=Path,
        nargs="+",
        default=None,
        help="Direct dataset CSV paths to evaluate.",
    )

    parser.add_argument(
        "--dataset-layer",
        type=str,
        choices=sorted(SUPPORTED_DATASET_LAYERS),
        default=None,
        help="Dataset layer to evaluate when using a catalog id.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root directory for manifest catalogs.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database when loading a champion by id.",
    )
    parser.add_argument(
        "--trade-cost-rate",
        type=float,
        default=0.0,
        help="Trade cost rate used during evaluation.",
    )
    parser.add_argument(
        "--cost-penalty-weight",
        type=float,
        default=0.0,
        help="Cost penalty weight used by AgentEvaluator.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    genome, genome_source = load_genome(
        db_path=args.db_path,
        champion_id=args.champion_id,
        genome_json_path=args.genome_json,
    )

    dataset_paths = resolve_dataset_paths(
        dataset_root=args.dataset_root,
        dataset_catalog_id=args.dataset_catalog_id,
        dataset_layer=args.dataset_layer,
        direct_dataset_paths=args.dataset_paths,
    )

    dataset_root = (
        args.dataset_root / args.dataset_catalog_id / args.dataset_layer
        if args.dataset_catalog_id and args.dataset_layer
        else Path(dataset_paths[0]).parent
    )

    evaluation = evaluate_genome_on_datasets(
        genome=genome,
        dataset_paths=dataset_paths,
        cost_penalty_weight=args.cost_penalty_weight,
        trade_cost_rate=args.trade_cost_rate,
    )
    metrics = build_evaluation_output(
        evaluation=evaluation,
        dataset_paths=dataset_paths,
        dataset_root=dataset_root,
    )

    print(f"Genome source: {genome_source}")
    print(f"Dataset count: {metrics['external_validation_dataset_count']}")
    print(f"Selection: {metrics['external_validation_selection']:.6f}")
    print(f"Profit: {metrics['external_validation_profit']:.6f}")
    print(f"Drawdown: {metrics['external_validation_drawdown']:.6f}")
    print(f"Trades: {metrics['external_validation_trades']:.2f}")
    print(f"Dataset profits: {metrics['external_validation_profits']}")


if __name__ == "__main__":
    main()
