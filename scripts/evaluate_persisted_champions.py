from __future__ import annotations

import argparse
from pathlib import Path

from evo_system.experimentation.persisted_champion_reevaluation import (
    DEFAULT_DB_PATH,
    reevaluate_persisted_champions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reevaluate persisted champions from SQLite on external validation "
            "and optional audit datasets without rerunning evolution."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database. Default: data/evolution.db",
    )
    parser.add_argument(
        "--config-name",
        type=str,
        default=None,
        help="Optional config_name filter.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run_id filter.",
    )
    parser.add_argument(
        "--champion-type",
        type=str,
        choices=["robust", "specialist"],
        default=None,
        help="Optional champion type filter.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        required=True,
        help="Path to the original run config JSON.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help=(
            "Optional dataset root used when resolving manifest/catalog-based "
            "external or audit datasets."
        ),
    )
    parser.add_argument(
        "--external-validation-dir",
        type=Path,
        default=None,
        help="Optional direct directory containing external validation CSV datasets.",
    )
    parser.add_argument(
        "--external-dataset-mode",
        type=str,
        choices=["legacy", "manifest"],
        default=None,
        help="Optional dataset mode for external reevaluation when using a catalog id.",
    )
    parser.add_argument(
        "--external-dataset-catalog-id",
        type=str,
        default=None,
        help="Optional catalog id for external reevaluation datasets.",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=None,
        help="Optional direct directory containing audit CSV datasets.",
    )
    parser.add_argument(
        "--audit-dataset-mode",
        type=str,
        choices=["legacy", "manifest"],
        default=None,
        help="Optional dataset mode for audit reevaluation when using a catalog id.",
    )
    parser.add_argument(
        "--audit-dataset-catalog-id",
        type=str,
        default=None,
        help="Optional catalog id for audit reevaluation datasets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Default: artifacts/analysis/reevaluated_champions_<timestamp>",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional champion limit for debugging.",
    )
    parser.add_argument(
        "--fail-on-missing-datasets",
        action="store_true",
        help="Fail instead of skipping when a requested dataset directory is missing or empty.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = reevaluate_persisted_champions(
        db_path=args.db_path,
        config_path=args.config_path,
        dataset_root=args.dataset_root,
        config_name=args.config_name,
        run_id=args.run_id,
        champion_type=args.champion_type,
        external_validation_dir=args.external_validation_dir,
        external_dataset_mode=args.external_dataset_mode,
        external_dataset_catalog_id=args.external_dataset_catalog_id,
        audit_dir=args.audit_dir,
        audit_dataset_mode=args.audit_dataset_mode,
        audit_dataset_catalog_id=args.audit_dataset_catalog_id,
        output_dir=args.output_dir,
        limit=args.limit,
        fail_on_missing_datasets=args.fail_on_missing_datasets,
    )

    print(f"Champions matched: {result['matched_count']}")
    print(f"External evaluations run: {result['external_evaluations_run']}")
    print(f"Audit evaluations run: {result['audit_evaluations_run']}")
    print(f"CSV exported to: {result['csv_path']}")
    print(f"JSON exported to: {result['json_path']}")
    print(f"Report exported to: {result['report_path']}")


if __name__ == "__main__":
    main()
