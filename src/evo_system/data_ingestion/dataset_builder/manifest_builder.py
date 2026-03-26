from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from evo_system.data_ingestion.dataset_builder.dataset_catalog import (
    DatasetManifest,
    datetime_to_millis,
    parse_date_end_exclusive_utc,
    parse_date_start_utc,
    parse_manifest,
)
from evo_system.data_ingestion.storage.csv_storage import CsvStorage
from evo_system.data_ingestion.utils import sanitize_symbol


def load_source_dataframe(
    market_data_dir: Path,
    market_type: str,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    clean_symbol = sanitize_symbol(symbol)
    source_dir = market_data_dir / market_type / clean_symbol / timeframe
    files = sorted(source_dir.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No market CSV files found in: {source_dir}")

    frames = [pd.read_csv(file_path) for file_path in files]
    full_df = pd.concat(frames, ignore_index=True)
    full_df = full_df.sort_values("timestamp")
    full_df = full_df.drop_duplicates(subset=["timestamp"], keep="last")
    full_df = full_df.reset_index(drop=True)
    return full_df


def slice_dataset_window(
    source_df: pd.DataFrame,
    start: str,
    end: str,
) -> pd.DataFrame:
    start_ms = datetime_to_millis(parse_date_start_utc(start))
    end_ms = datetime_to_millis(parse_date_end_exclusive_utc(end))

    sliced_df = source_df[
        (source_df["timestamp"] >= start_ms) & (source_df["timestamp"] < end_ms)
    ].copy()
    return sliced_df.reset_index(drop=True)


class ManifestDatasetBuilder:
    def __init__(
        self,
        storage: CsvStorage,
        market_data_dir: Path = Path("data/market_data"),
        datasets_dir: Path = Path("data/datasets"),
    ) -> None:
        self.storage = storage
        self.market_data_dir = market_data_dir
        self.datasets_dir = datasets_dir

    def build_from_manifest(self, catalog_path: Path) -> list[Path]:
        manifest = parse_manifest(catalog_path)
        built_paths: list[Path] = []
        source_frames: dict[tuple[str, str, str], pd.DataFrame] = {}

        for dataset in manifest.datasets:
            source_key = (dataset.market_type, dataset.symbol, dataset.timeframe)
            if source_key not in source_frames:
                source_frames[source_key] = load_source_dataframe(
                    market_data_dir=self.market_data_dir,
                    market_type=dataset.market_type,
                    symbol=dataset.symbol,
                    timeframe=dataset.timeframe,
                )

            sliced_df = slice_dataset_window(
                source_df=source_frames[source_key],
                start=dataset.start,
                end=dataset.end,
            )
            if sliced_df.empty:
                raise ValueError(
                    f"Dataset window produced no candles: {dataset.id}"
                )

            output_dir = self.datasets_dir / manifest.catalog_id / dataset.layer / dataset.id
            dataset_path = output_dir / "candles.csv"
            metadata_path = output_dir / "metadata.json"

            self.storage.save_dataframe(dataset_path, sliced_df)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(
                    {
                        "catalog_id": manifest.catalog_id,
                        "catalog_description": manifest.description,
                        **dataset.to_dict(),
                    },
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            built_paths.append(output_dir)

        return built_paths
