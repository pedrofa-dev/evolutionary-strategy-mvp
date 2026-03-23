from __future__ import annotations

from pathlib import Path

import pandas as pd

from evo_system.data_ingestion.utils import CSV_COLUMNS, ensure_parent_directory


class CsvStorage:
    def save_dataframe_merge_dedup(self, path: Path, incoming_df: pd.DataFrame) -> None:
        if incoming_df.empty:
            return

        ensure_parent_directory(path)

        if path.exists():
            existing_df = pd.read_csv(path)
            merged_df = pd.concat([existing_df, incoming_df], ignore_index=True)
        else:
            merged_df = incoming_df.copy()

        merged_df = merged_df[CSV_COLUMNS]
        merged_df = merged_df.sort_values("timestamp")
        merged_df = merged_df.drop_duplicates(subset=["timestamp"], keep="last")
        merged_df.to_csv(path, index=False)

    def save_dataframe(self, path: Path, df: pd.DataFrame) -> None:
        if df.empty:
            return

        ensure_parent_directory(path)

        clean_df = df[CSV_COLUMNS].copy()
        clean_df = clean_df.sort_values("timestamp")
        clean_df = clean_df.drop_duplicates(subset=["timestamp"], keep="last")
        clean_df.to_csv(path, index=False)

    def load_dataframe(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=CSV_COLUMNS)
        return pd.read_csv(path)