from __future__ import annotations

import argparse
from pathlib import Path

from evo_system.reporting import analyze_champions
from evo_system.storage import DEFAULT_PERSISTENCE_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze persisted champions from the canonical persistence database."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_PERSISTENCE_DB_PATH,
        help="Path to persistence SQLite database. Default: data/evolution_v2.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Default: artifacts/analysis/champions_<timestamp>",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        action="append",
        default=None,
        help="Optional run_id filter. Repeat the flag to analyze multiple runs.",
    )
    parser.add_argument(
        "--config-name",
        type=str,
        default=None,
        help="Optional config_name filter.",
    )
    parser.add_argument(
        "--champion-type",
        type=str,
        choices=["robust", "specialist"],
        default=None,
        help="Optional champion_type filter.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze_champions(
        db_path=args.db_path,
        output_dir=args.output_dir,
        run_id=args.run_id[0] if args.run_id and len(args.run_id) == 1 else None,
        run_ids=args.run_id if args.run_id and len(args.run_id) > 1 else None,
        config_name=args.config_name,
        champion_type=args.champion_type,
    )

    if result is None:
        print("No champions found with the provided filters.")
        return

    print(f"Champions loaded: {result['champion_count']}")
    print(f"CSV exported to: {result['csv_path']}")
    print(f"Report exported to: {result['report_path']}")
    print(f"Patterns exported to: {result['patterns_path']}")
    print(f"Champion card exported to: {result['champion_card_path']}")
