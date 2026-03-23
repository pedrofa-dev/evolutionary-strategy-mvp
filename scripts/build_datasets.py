from __future__ import annotations

import argparse

from evo_system.data_ingestion.dataset_builder.split_builder import DatasetBuilder
from evo_system.data_ingestion.storage.csv_storage import CsvStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build train/validation datasets from raw CSV files.")
    parser.add_argument("--symbol", required=True, help="Example: BTC/USDT")
    parser.add_argument("--timeframe", required=True, help="Example: 1h")
    parser.add_argument("--validation-ratio", type=float, default=0.2, help="Example: 0.2")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    builder = DatasetBuilder(storage=CsvStorage())
    train_path, validation_path = builder.build_train_validation(
        symbol=args.symbol,
        timeframe=args.timeframe,
        validation_ratio=args.validation_ratio,
    )

    print(f"Train dataset: {train_path}")
    print(f"Validation dataset: {validation_path}")


if __name__ == "__main__":
    main()