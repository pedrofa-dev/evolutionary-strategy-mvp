from __future__ import annotations

import argparse
from pathlib import Path

from evo_system.storage import DEFAULT_PERSISTENCE_DB_PATH
from evo_system.storage.run_read_repository import RunReadRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read persisted runs from the canonical SQLite database."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_PERSISTENCE_DB_PATH,
        help="Path to persistence SQLite database. Default: data/evolution_v2.db",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of latest runs to list when --run-id is not provided.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run_id to show a detailed summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = RunReadRepository(args.db_path)

    if args.run_id:
        summary = repository.get_run_summary(args.run_id)
        if summary is None:
            print(f"Run not found: {args.run_id}")
            return

        print(f"Run ID: {summary.run_id}")
        print(f"Config: {summary.config_name}")
        print(f"Seed: {summary.effective_seed}")
        print(f"Status: {summary.status}")
        print(f"Dataset catalog: {summary.dataset_catalog_id or 'unknown'}")
        print(f"Dataset signature: {summary.dataset_signature or 'unknown'}")
        print(f"Execution fingerprint: {summary.execution_fingerprint}")
        print(
            "Runtime component fingerprint: "
            f"{summary.runtime_component_fingerprint or 'unknown'}"
        )
        print(f"Logic version: {summary.logic_version}")
        print(f"Market mode: {summary.market_mode_name or 'unknown'}")
        print(
            "Leverage: "
            f"{summary.leverage if summary.leverage is not None else 'unknown'}"
        )
        print(f"Modules: {summary.stack_label}")
        print(f"Champion persisted: {summary.champion_persisted}")
        print(
            "Final validation selection: "
            f"{summary.final_validation_selection_score if summary.final_validation_selection_score is not None else 'n/a'}"
        )
        print(
            "Final validation profit: "
            f"{summary.final_validation_profit if summary.final_validation_profit is not None else 'n/a'}"
        )
        if summary.best_genome is not None:
            print(
                "Best genome generation: "
                f"{summary.best_genome.generation_number if summary.best_genome.generation_number is not None else 'n/a'}"
            )
            print(
                "Best genome snapshot available: "
                f"{summary.best_genome.genome_snapshot is not None}"
            )
        return

    for item in repository.list_runs(limit=args.limit):
        print(
            f"{item.run_id} | config={item.config_name} | seed={item.effective_seed} | "
            f"status={item.status} | champion={item.champion_persisted} | "
            f"market={item.market_mode_name or 'unknown'} | leverage={item.leverage if item.leverage is not None else 'unknown'} | "
            f"modules={item.stack_label} | "
            f"runtime_fp={item.runtime_component_fingerprint or 'unknown'}"
        )
