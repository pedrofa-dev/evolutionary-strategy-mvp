from __future__ import annotations

import csv
from pathlib import Path

from evo_system.data_ingestion.dataset_builder.dataset_catalog import (
    DatasetManifest,
    ManifestDatasetEntry,
    datetime_to_millis,
    parse_date_end_exclusive_utc,
    parse_date_start_utc,
)
from evo_system.data_ingestion.utils import sanitize_symbol


ALLOWED_LAYERS = {"train", "validation", "external", "audit"}
REQUIRED_DATASET_FIELDS = (
    "id",
    "symbol",
    "market_type",
    "timeframe",
    "start",
    "end",
    "layer",
    "regime_primary",
    "regime_secondary",
    "volatility",
    "event_tag",
    "notes",
)


def validate_manifest(manifest: DatasetManifest) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for dataset in manifest.datasets:
        if dataset.id in seen_ids:
            errors.append(f"Duplicate dataset id: {dataset.id}")
        seen_ids.add(dataset.id)

        errors.extend(validate_dataset_fields(dataset))
        errors.extend(validate_dataset_date_range(dataset))

    errors.extend(validate_cross_layer_overlaps(manifest.datasets))
    return errors


def validate_dataset_fields(dataset: ManifestDatasetEntry) -> list[str]:
    errors: list[str] = []

    for field_name in REQUIRED_DATASET_FIELDS:
        value = getattr(dataset, field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"Dataset {dataset.id or '<missing id>'} has invalid field: {field_name}"
            )

    if dataset.layer not in ALLOWED_LAYERS:
        errors.append(
            f"Dataset {dataset.id} has invalid layer: {dataset.layer}"
        )

    return errors


def validate_dataset_date_range(dataset: ManifestDatasetEntry) -> list[str]:
    errors: list[str] = []

    try:
        start_dt = parse_date_start_utc(dataset.start)
        end_dt = parse_date_start_utc(dataset.end)
    except ValueError as exc:
        return [f"Dataset {dataset.id} has invalid date format: {exc}"]

    if start_dt >= end_dt:
        errors.append(
            f"Dataset {dataset.id} has invalid date range: {dataset.start} >= {dataset.end}"
        )

    return errors


def validate_cross_layer_overlaps(datasets: list[ManifestDatasetEntry]) -> list[str]:
    errors: list[str] = []

    for index, left in enumerate(datasets):
        left_start = parse_date_start_utc(left.start)
        left_end = parse_date_end_exclusive_utc(left.end)

        for right in datasets[index + 1 :]:
            if left.layer == right.layer:
                continue
            if left.symbol != right.symbol:
                continue
            if left.market_type != right.market_type:
                continue
            if left.timeframe != right.timeframe:
                continue

            right_start = parse_date_start_utc(right.start)
            right_end = parse_date_end_exclusive_utc(right.end)

            if left_start < right_end and right_start < left_end:
                errors.append(
                    "Cross-layer overlap detected: "
                    f"{left.id} ({left.layer}) overlaps with {right.id} ({right.layer})"
                )

    return errors


def validate_manifest_source_data(
    manifest: DatasetManifest,
    market_data_dir: Path,
    minimum_candles: int = 24,
) -> list[str]:
    errors: list[str] = []

    for dataset in manifest.datasets:
        source_dir = (
            market_data_dir
            / dataset.market_type
            / sanitize_symbol(dataset.symbol)
            / dataset.timeframe
        )
        files = sorted(source_dir.glob("*.csv"))
        if not files:
            errors.append(f"Missing source data for dataset {dataset.id}: {source_dir}")
            continue

        start_ms = datetime_to_millis(parse_date_start_utc(dataset.start))
        end_ms = datetime_to_millis(parse_date_end_exclusive_utc(dataset.end))
        candle_count = count_candles_in_range(files, start_ms, end_ms)

        if candle_count == 0:
            errors.append(
                f"Dataset {dataset.id} has no source candles in the requested range"
            )
        elif candle_count < minimum_candles:
            errors.append(
                f"Dataset {dataset.id} is very small: {candle_count} candles found"
            )

    return errors


def count_candles_in_range(files: list[Path], start_ms: int, end_ms: int) -> int:
    candle_count = 0

    for file_path in files:
        with file_path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                timestamp = int(row["timestamp"])
                if start_ms <= timestamp < end_ms:
                    candle_count += 1

    return candle_count
