from evo_system.data_ingestion.dataset_builder.dataset_catalog import (
    DatasetManifest,
    ManifestDatasetEntry,
)
from evo_system.data_ingestion.dataset_builder.dataset_validator import (
    validate_manifest,
)


def build_dataset(
    dataset_id: str,
    layer: str,
    start: str,
    end: str,
) -> ManifestDatasetEntry:
    return ManifestDatasetEntry(
        id=dataset_id,
        symbol="BTCUSDT",
        market_type="spot",
        timeframe="1h",
        start=start,
        end=end,
        layer=layer,
        regime_primary="bull",
        regime_secondary="trend",
        volatility="high",
        event_tag="none",
        notes="test",
    )


def test_validate_manifest_detects_duplicate_ids() -> None:
    manifest = DatasetManifest(
        catalog_id="test",
        description="test",
        market_type="spot",
        timeframe="1h",
        datasets=[
            build_dataset("duplicate_id", "train", "2024-01-01", "2024-01-10"),
            build_dataset("duplicate_id", "validation", "2024-02-01", "2024-02-10"),
        ],
    )

    errors = validate_manifest(manifest)

    assert any("Duplicate dataset id: duplicate_id" == error for error in errors)


def test_validate_manifest_detects_cross_layer_overlap() -> None:
    manifest = DatasetManifest(
        catalog_id="test",
        description="test",
        market_type="spot",
        timeframe="1h",
        datasets=[
            build_dataset("train_window", "train", "2024-01-01", "2024-01-10"),
            build_dataset("validation_window", "validation", "2024-01-05", "2024-01-12"),
        ],
    )

    errors = validate_manifest(manifest)

    assert any("Cross-layer overlap detected:" in error for error in errors)
