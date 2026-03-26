from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ManifestDatasetEntry:
    id: str
    symbol: str
    market_type: str
    timeframe: str
    start: str
    end: str
    layer: str
    regime_primary: str
    regime_secondary: str
    volatility: str
    event_tag: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "timeframe": self.timeframe,
            "start": self.start,
            "end": self.end,
            "layer": self.layer,
            "regime_primary": self.regime_primary,
            "regime_secondary": self.regime_secondary,
            "volatility": self.volatility,
            "event_tag": self.event_tag,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class DatasetManifest:
    catalog_id: str
    description: str
    market_type: str
    timeframe: str
    datasets: list[ManifestDatasetEntry]


def parse_manifest(path: Path) -> DatasetManifest:
    lines = path.read_text(encoding="utf-8").splitlines()

    top_level: dict[str, str] = {}
    datasets: list[dict[str, str]] = []
    current_dataset: dict[str, str] | None = None
    in_datasets = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "datasets:":
            in_datasets = True
            continue

        if not in_datasets:
            key, value = split_yaml_line(stripped)
            top_level[key] = value
            continue

        if stripped.startswith("- "):
            if current_dataset is not None:
                datasets.append(current_dataset)
            current_dataset = {}
            key, value = split_yaml_line(stripped[2:].strip())
            current_dataset[key] = value
            continue

        if current_dataset is None:
            raise ValueError(f"Invalid dataset manifest structure in {path}")

        key, value = split_yaml_line(stripped)
        current_dataset[key] = value

    if current_dataset is not None:
        datasets.append(current_dataset)

    return DatasetManifest(
        catalog_id=top_level["catalog_id"],
        description=top_level["description"],
        market_type=top_level["market_type"],
        timeframe=top_level["timeframe"],
        datasets=[ManifestDatasetEntry(**dataset) for dataset in datasets],
    )


def split_yaml_line(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def parse_date_start_utc(value: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(value),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )


def parse_date_end_exclusive_utc(value: str) -> datetime:
    end_date = date.fromisoformat(value) + timedelta(days=1)
    return datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)


def datetime_to_millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)
