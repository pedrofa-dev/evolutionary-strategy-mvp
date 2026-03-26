# Manifest Dataset Builder

The manifest dataset builder creates curated dataset windows from an explicit catalog file.

It is additive and does not replace the legacy split-based builder yet.

## What It Does

The manifest builder:

- reads dataset definitions from a catalog such as `configs/datasets/core_1h_spot.yaml`
- loads source market files from `data/market_data/{market_type}/{symbol}/{timeframe}/`
- slices the exact date windows defined in the catalog
- writes curated outputs under `data/datasets/{catalog_id}/{layer}/{dataset_id}/`

Each dataset directory contains:

- `candles.csv`
- `metadata.json`

## How It Differs From The Legacy Builder

The legacy builder:

- reads from `data/raw`
- concatenates all source candles for one symbol/timeframe
- splits by ratio into train and validation
- writes to `data/processed`

The manifest builder:

- reads from a catalog file
- uses explicit windows and explicit dataset layers
- supports `train`, `validation`, `external`, and `audit`
- writes curated dataset directories to `data/datasets`

## Expected Input Layout

The manifest builder expects downloaded market files under paths like:

- `data/market_data/spot/BTCUSDT/1h/...`
- `data/market_data/spot/ETHUSDT/1h/...`

## Expected Output Layout

The builder writes curated outputs like:

- `data/datasets/core_1h_spot/train/BTCUSDT_1h_2020-10-01_2021-01-31/`
- `data/datasets/core_1h_spot/validation/BTCUSDT_1h_2021-08-01_2021-11-15/`
- `data/datasets/core_1h_spot/external/BTCUSDT_1h_2022-11-01_2022-12-15/`
- `data/datasets/core_1h_spot/audit/BTCUSDT_1h_2024-02-01_2024-04-15/`

## Example Commands

Legacy split builder:

```bash
python scripts/build_datasets.py legacy --symbol BTC/USDT --timeframe 1h --validation-ratio 0.2
```

Manifest builder:

```bash
python scripts/build_datasets.py manifest --catalog-path configs/datasets/core_1h_spot.yaml
```

Backward-compatible legacy shortcut:

```bash
python scripts/build_datasets.py --symbol BTC/USDT --timeframe 1h --validation-ratio 0.2
```

## Using Manifest Datasets In Experiments

Experiments can continue using legacy datasets, or they can switch to curated manifest datasets.

Add these fields to a run config:

```json
{
  "dataset_mode": "manifest",
  "dataset_catalog_id": "core_1h_spot"
}
```

Expected folder layout:

- `data/datasets/core_1h_spot/train/.../candles.csv`
- `data/datasets/core_1h_spot/validation/.../candles.csv`

Notes:

- `train` datasets are used only for training.
- `validation` datasets are used only for validation.
- `external` and `audit` are not used by the main experiment loop yet.
- Legacy experiments continue to work unchanged.

## End-To-End Manifest Workflow

Minimal workflow using the manifest system:

1. Download market data into the new market data layout.
2. Validate the dataset catalog.
3. Build curated datasets from the manifest.
4. Run experiments using a manifest-enabled config.

Example commands:

```bash
python scripts/download_data.py spot \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2020-10-01T00:00:00+00:00 \
  --end 2024-08-16T00:00:00+00:00
```

```bash
python scripts/download_data.py spot \
  --symbol ETH/USDT \
  --timeframe 1h \
  --start 2020-10-01T00:00:00+00:00 \
  --end 2024-08-16T00:00:00+00:00
```

```bash
python scripts/build_datasets.py validate \
  --catalog-path configs/datasets/core_1h_spot.yaml \
  --market-data-dir data/market_data
```

```bash
python scripts/build_datasets.py manifest \
  --catalog-path configs/datasets/core_1h_spot.yaml \
  --market-data-dir data/market_data \
  --datasets-dir data/datasets
```

```bash
python scripts/run_experiment.py single \
  --config-path configs/runs/run_balanced_manifest.json
```

```bash
python scripts/run_experiment.py batch \
  --configs-dir configs/runs
```

Manifest mode uses:

- `data/datasets/{catalog_id}/train/.../candles.csv`
- `data/datasets/{catalog_id}/validation/.../candles.csv`

For now:

- `train` and `validation` are part of the main evolutionary runtime
- `external` and `audit` remain outside the main runtime
- `external` can still be used later for post-run validation flows
