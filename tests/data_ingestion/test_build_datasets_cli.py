from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DATASETS_SCRIPT = REPO_ROOT / "scripts" / "build_datasets.py"


def write_catalog(catalog_path: Path, dataset_blocks: list[list[str]]) -> None:
    lines = [
        "catalog_id: test_catalog",
        "description: Test catalog",
        "market_type: spot",
        "timeframe: 1h",
        "datasets:",
    ]
    for block in dataset_blocks:
        lines.extend(block)
    catalog_path.write_text("\n".join(lines), encoding="utf-8")


def write_market_csv(csv_path: Path, timestamps: list[int]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,open,high,low,close,volume"]
    for index, timestamp in enumerate(timestamps, start=1):
        price = 100 + index
        lines.append(f"{timestamp},{price},{price},{price},{price},1")
    csv_path.write_text("\n".join(lines), encoding="utf-8")


def utc_millis(value: str) -> int:
    return int(datetime.fromisoformat(f"{value}T00:00:00+00:00").timestamp() * 1000)


def run_build_datasets(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else src_path
    )
    return subprocess.run(
        [sys.executable, str(BUILD_DATASETS_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_build_datasets_validate_only_succeeds_for_valid_manifest(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    market_data_dir = tmp_path / "market_data"
    datasets_dir = tmp_path / "datasets"

    write_catalog(
        catalog_path,
        [
            [
                "  - id: BTCUSDT_1h_2020-10-01_2020-10-02",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-01",
                "    end: 2020-10-02",
                "    layer: train",
                "    regime_primary: bull",
                "    regime_secondary: trend",
                "    volatility: medium",
                "    event_tag: none",
                "    notes: test",
            ]
        ],
    )
    write_market_csv(
        market_data_dir / "spot" / "BTCUSDT" / "1h" / "BTCUSDT-1h-2020-10.csv",
        [utc_millis("2020-10-01")],
    )

    result = run_build_datasets(
        "--catalog-path",
        str(catalog_path),
        "--market-data-dir",
        str(market_data_dir),
        "--datasets-dir",
        str(datasets_dir),
        "--minimum-candles",
        "1",
        "--validate-only",
    )

    assert result.returncode == 0
    assert "Catalog validation passed" in result.stdout
    assert "Validation only -> dataset build skipped." in result.stdout
    assert not datasets_dir.exists()


def test_build_datasets_fails_on_invalid_manifest_before_build(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    market_data_dir = tmp_path / "market_data"
    datasets_dir = tmp_path / "datasets"

    write_catalog(
        catalog_path,
        [
            [
                "  - id: duplicate_id",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-01",
                "    end: 2020-10-02",
                "    layer: train",
                "    regime_primary: bull",
                "    regime_secondary: trend",
                "    volatility: medium",
                "    event_tag: none",
                "    notes: test",
            ],
            [
                "  - id: duplicate_id",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-03",
                "    end: 2020-10-04",
                "    layer: validation",
                "    regime_primary: bear",
                "    regime_secondary: range",
                "    volatility: high",
                "    event_tag: none",
                "    notes: test",
            ],
        ],
    )
    write_market_csv(
        market_data_dir / "spot" / "BTCUSDT" / "1h" / "BTCUSDT-1h-2020-10.csv",
        [utc_millis("2020-10-01"), utc_millis("2020-10-03")],
    )

    result = run_build_datasets(
        "--catalog-path",
        str(catalog_path),
        "--market-data-dir",
        str(market_data_dir),
        "--datasets-dir",
        str(datasets_dir),
        "--minimum-candles",
        "1",
    )

    assert result.returncode == 1
    assert "Catalog validation failed" in result.stdout
    assert "Duplicate dataset id: duplicate_id" in result.stdout
    assert not datasets_dir.exists()


def test_build_datasets_fails_on_insufficient_source_coverage(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    market_data_dir = tmp_path / "market_data"
    datasets_dir = tmp_path / "datasets"

    write_catalog(
        catalog_path,
        [
            [
                "  - id: BTCUSDT_1h_2020-10-01_2020-10-03",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-01",
                "    end: 2020-10-03",
                "    layer: train",
                "    regime_primary: bull",
                "    regime_secondary: trend",
                "    volatility: medium",
                "    event_tag: none",
                "    notes: test",
            ]
        ],
    )
    write_market_csv(
        market_data_dir / "spot" / "BTCUSDT" / "1h" / "BTCUSDT-1h-2020-10.csv",
        [utc_millis("2020-10-01")],
    )

    result = run_build_datasets(
        "--catalog-path",
        str(catalog_path),
        "--market-data-dir",
        str(market_data_dir),
        "--datasets-dir",
        str(datasets_dir),
        "--minimum-candles",
        "2",
    )

    assert result.returncode == 1
    assert "Catalog validation failed" in result.stdout
    assert "is very small: 1 candles found" in result.stdout
    assert not datasets_dir.exists()


def test_build_datasets_builds_expected_manifest_structure(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.yaml"
    market_data_dir = tmp_path / "market_data"
    datasets_dir = tmp_path / "datasets"

    write_catalog(
        catalog_path,
        [
            [
                "  - id: BTCUSDT_1h_2020-10-01_2020-10-03",
                "    symbol: BTCUSDT",
                "    market_type: spot",
                "    timeframe: 1h",
                "    start: 2020-10-01",
                "    end: 2020-10-03",
                "    layer: train",
                "    regime_primary: bull",
                "    regime_secondary: trend",
                "    volatility: medium",
                "    event_tag: none",
                "    notes: test",
            ]
        ],
    )
    write_market_csv(
        market_data_dir / "spot" / "BTCUSDT" / "1h" / "BTCUSDT-1h-2020-10.csv",
        [utc_millis("2020-10-01"), utc_millis("2020-10-02")],
    )

    result = run_build_datasets(
        "--catalog-path",
        str(catalog_path),
        "--market-data-dir",
        str(market_data_dir),
        "--datasets-dir",
        str(datasets_dir),
        "--minimum-candles",
        "1",
    )

    dataset_dir = datasets_dir / "test_catalog" / "train" / "BTCUSDT_1h_2020-10-01_2020-10-03"
    assert result.returncode == 0
    assert "Catalog validation passed" in result.stdout
    assert "Catalog built" in result.stdout
    assert (dataset_dir / "candles.csv").exists()
    assert (dataset_dir / "metadata.json").exists()
