from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build curated datasets from a manifest catalog. Validation runs "
            "automatically before dataset windows are written."
        )
    )
    parser.add_argument(
        "--catalog-path",
        type=Path,
        default=Path("configs/datasets/core_1h_spot.yaml"),
        help="Path to the dataset catalog YAML file.",
    )
    parser.add_argument(
        "--market-data-dir",
        type=Path,
        default=Path("data/market_data"),
        help="Input root containing downloaded market files.",
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=Path("data/datasets"),
        help="Output root for curated dataset windows.",
    )
    parser.add_argument(
        "--minimum-candles",
        type=int,
        default=24,
        help="Minimum expected candle count for each dataset window.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the manifest and source coverage without writing datasets.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    from evo_system.data_ingestion.dataset_builder.dataset_catalog import (
        parse_manifest,
    )
    from evo_system.data_ingestion.dataset_builder.dataset_validator import (
        validate_manifest,
        validate_manifest_source_data,
    )
    from evo_system.data_ingestion.dataset_builder.manifest_builder import (
        ManifestDatasetBuilder,
    )
    from evo_system.data_ingestion.storage.csv_storage import CsvStorage

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

    if args.validate_only:
        print("Validation only -> dataset build skipped.")
        return

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
