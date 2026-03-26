from pathlib import Path

import json

from evo_system.data_ingestion.dataset_builder.manifest_builder import (
    ManifestDatasetBuilder,
    parse_manifest,
)
from evo_system.data_ingestion.storage.csv_storage import CsvStorage


def test_parse_manifest_reads_catalog_metadata() -> None:
    manifest = parse_manifest(Path("configs/datasets/core_1h_spot.yaml"))

    assert manifest.catalog_id == "core_1h_spot"
    assert manifest.market_type == "spot"
    assert manifest.timeframe == "1h"
    assert len(manifest.datasets) == 20
    assert manifest.datasets[0].layer == "train"


def test_manifest_builder_creates_dataset_and_metadata(tmp_path: Path) -> None:
    market_data_dir = tmp_path / "market_data"
    datasets_dir = tmp_path / "datasets"
    source_dir = market_data_dir / "spot" / "BTCUSDT" / "1h"
    source_dir.mkdir(parents=True)

    source_file = source_dir / "BTCUSDT-1h-2020-10.csv"
    source_file.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "1601510400000,100,110,95,105,1",
                "1601596800000,105,115,100,110,1",
                "1609545600000,110,120,108,118,1",
                "1612051200000,118,125,115,122,1",
                "1612137600000,122,130,120,128,1",
            ]
        ),
        encoding="utf-8",
    )

    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        "\n".join(
            [
                "catalog_id: test_catalog",
                "description: Test catalog",
                "market_type: spot",
                "timeframe: 1h",
                "datasets:",
                "  - id: BTCUSDT_1h_2020-10-01_2021-01-31",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-01",
                "    end: 2021-01-31",
                "    layer: train",
                "    regime_primary: bull",
                "    regime_secondary: trend",
                "    volatility: high",
                "    event_tag: none",
                "    notes: Test window",
            ]
        ),
        encoding="utf-8",
    )

    builder = ManifestDatasetBuilder(
        storage=CsvStorage(),
        market_data_dir=market_data_dir,
        datasets_dir=datasets_dir,
    )
    built_paths = builder.build_from_manifest(catalog_path)

    assert len(built_paths) == 1

    dataset_dir = datasets_dir / "test_catalog" / "train" / "BTCUSDT_1h_2020-10-01_2021-01-31"
    candles_path = dataset_dir / "candles.csv"
    metadata_path = dataset_dir / "metadata.json"

    assert candles_path.exists()
    assert metadata_path.exists()

    candles_lines = candles_path.read_text(encoding="utf-8").splitlines()
    assert len(candles_lines) == 5
    assert "1612137600000" not in candles_path.read_text(encoding="utf-8")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["catalog_id"] == "test_catalog"
    assert metadata["layer"] == "train"
    assert metadata["id"] == "BTCUSDT_1h_2020-10-01_2021-01-31"
