from __future__ import annotations

import argparse
import sys
from pathlib import Path

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build datasets using either the legacy split builder or the new manifest builder."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    legacy_parser = subparsers.add_parser(
        "legacy",
        help="Build train/validation datasets using the legacy split-based builder.",
    )
    legacy_parser.add_argument("--symbol", required=True, help="Example: BTC/USDT")
    legacy_parser.add_argument("--timeframe", required=True, help="Example: 1h")
    legacy_parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.2,
        help="Validation split ratio. Example: 0.2",
    )
    legacy_parser.add_argument(
        "--raw-data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Legacy raw input directory. Default: data/raw",
    )
    legacy_parser.add_argument(
        "--processed-data-dir",
        type=Path,
        default=Path("data/processed"),
        help="Legacy processed output directory. Default: data/processed",
    )

    manifest_parser = subparsers.add_parser(
        "manifest",
        help="Build curated datasets from a manifest catalog.",
    )
    manifest_parser.add_argument(
        "--catalog-path",
        type=Path,
        default=Path("configs/datasets/core_1h_spot.yaml"),
        help="Path to the dataset catalog YAML file.",
    )
    manifest_parser.add_argument(
        "--market-data-dir",
        type=Path,
        default=Path("data/market_data"),
        help="Input root containing downloaded market files.",
    )
    manifest_parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=Path("data/datasets"),
        help="Output root for curated dataset windows.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a dataset catalog before building datasets.",
    )
    validate_parser.add_argument(
        "--catalog-path",
        type=Path,
        default=Path("configs/datasets/core_1h_spot.yaml"),
        help="Path to the dataset catalog YAML file.",
    )
    validate_parser.add_argument(
        "--market-data-dir",
        type=Path,
        default=Path("data/market_data"),
        help="Input root containing downloaded market files for source coverage checks.",
    )
    validate_parser.add_argument(
        "--minimum-candles",
        type=int,
        default=24,
        help="Minimum expected candle count for a dataset window.",
    )

    return parser


def normalize_argv(argv: list[str] | None) -> list[str] | None:
    if argv is None:
        return None
    if not argv:
        return argv
    if argv[0] in {"legacy", "manifest", "validate", "-h", "--help"}:
        return argv
    return ["legacy", *argv]


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    effective_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(normalize_argv(effective_argv))

    if args.mode == "legacy":
        from evo_system.data_ingestion.dataset_builder.split_builder import DatasetBuilder
        from evo_system.data_ingestion.storage.csv_storage import CsvStorage

        builder = DatasetBuilder(
            storage=CsvStorage(),
            raw_data_dir=args.raw_data_dir,
            processed_data_dir=args.processed_data_dir,
        )
        train_path, validation_path = builder.build_train_validation(
            symbol=args.symbol,
            timeframe=args.timeframe,
            validation_ratio=args.validation_ratio,
        )

        print(f"Train dataset: {train_path}")
        print(f"Validation dataset: {validation_path}")
        return

    if args.mode == "validate":
        from evo_system.data_ingestion.dataset_builder.dataset_catalog import (
            parse_manifest,
        )
        from evo_system.data_ingestion.dataset_builder.dataset_validator import (
            validate_manifest,
            validate_manifest_source_data,
        )

        manifest = parse_manifest(args.catalog_path)
        errors = validate_manifest(manifest)
        errors.extend(
            validate_manifest_source_data(
                manifest=manifest,
                market_data_dir=args.market_data_dir,
                minimum_candles=args.minimum_candles,
            )
        )

        if errors:
            print(f"Catalog validation failed: {args.catalog_path}")
            for error in errors:
                print(f"- {error}")
            raise SystemExit(1)

        print(f"Catalog validation passed: {args.catalog_path}")
        return

    from evo_system.data_ingestion.dataset_builder.manifest_builder import (
        ManifestDatasetBuilder,
    )
    from evo_system.data_ingestion.storage.csv_storage import CsvStorage

    builder = ManifestDatasetBuilder(
        storage=CsvStorage(),
        market_data_dir=args.market_data_dir,
        datasets_dir=args.datasets_dir,
    )
    built_paths = builder.build_from_manifest(args.catalog_path)

    print(f"Catalog built: {args.catalog_path}")
    print(f"Datasets created: {len(built_paths)}")
    for path in built_paths:
        print(f"Dataset directory: {path}")


if __name__ == "__main__":
    main()
