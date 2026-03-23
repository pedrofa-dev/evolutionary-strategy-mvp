from __future__ import annotations

from pathlib import Path

import pandas as pd

from evo_system.data_ingestion.storage.csv_storage import CsvStorage
from evo_system.data_ingestion.utils import sanitize_symbol


class DatasetBuilder:
    def __init__(
        self,
        storage: CsvStorage,
        raw_data_dir: Path = Path("data/raw"),
        processed_data_dir: Path = Path("data/processed"),
    ) -> None:
        self.storage = storage
        self.raw_data_dir = raw_data_dir
        self.processed_data_dir = processed_data_dir

    def build_train_validation(
        self,
        symbol: str,
        timeframe: str,
        validation_ratio: float = 0.2,
    ) -> tuple[Path, Path]:
        clean_symbol = sanitize_symbol(symbol)
        source_dir = self.raw_data_dir / clean_symbol / timeframe

        files = sorted(source_dir.glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"No raw CSV files found in: {source_dir}")

        frames = [pd.read_csv(file_path) for file_path in files]
        full_df = pd.concat(frames, ignore_index=True)

        full_df = full_df.sort_values("timestamp")
        full_df = full_df.drop_duplicates(subset=["timestamp"], keep="last")
        full_df = full_df.reset_index(drop=True)

        split_index = int(len(full_df) * (1 - validation_ratio))
        if split_index <= 0 or split_index >= len(full_df):
            raise ValueError("Invalid split. Adjust validation_ratio or provide more data.")

        train_df = full_df.iloc[:split_index].copy()
        validation_df = full_df.iloc[split_index:].copy()

        train_path = (
            self.processed_data_dir
            / "train"
            / clean_symbol
            / timeframe
            / f"{clean_symbol}-{timeframe}-train.csv"
        )

        validation_path = (
            self.processed_data_dir
            / "validation"
            / clean_symbol
            / timeframe
            / f"{clean_symbol}-{timeframe}-validation.csv"
        )

        self.storage.save_dataframe(train_path, train_df)
        self.storage.save_dataframe(validation_path, validation_df)

        return train_path, validation_path