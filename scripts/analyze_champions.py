from __future__ import annotations

import argparse
from pathlib import Path

from evo_system.reporting import DEFAULT_DB_PATH, analyze_champions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze persisted champions from SQLite.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database. Default: data/evolution.db",
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
        default=None,
        help="Optional run_id filter.",
    )
    parser.add_argument(
        "--config-name",
        type=str,
        default=None,
        help="Optional config_name filter.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze_champions(
        db_path=args.db_path,
        output_dir=args.output_dir,
        run_id=args.run_id,
        config_name=args.config_name,
    )

    if result is None:
        print("No champions found with the provided filters.")
        return

    print(f"Champions loaded: {result['champion_count']}")
    print(f"CSV exported to: {result['csv_path']}")
    print(f"Report exported to: {result['report_path']}")
    print(f"Patterns exported to: {result['patterns_path']}")
    print(f"Champion card exported to: {result['champion_card_path']}")


if __name__ == "__main__":
    main()
