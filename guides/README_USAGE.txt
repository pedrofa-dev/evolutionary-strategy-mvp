# Usage Guide

This guide reflects the current public workflow of the repository.

## Main Pipeline

Typical pipeline:

`download_data -> build_datasets -> run_experiment -> analyze_champions`

Optional follow-up:

`evaluate_persisted_champions`

## 1. Download Market Data

Unified entrypoint for spot and futures:

```bash
python scripts/download_data.py spot --help
python scripts/download_data.py futures --help
```

Current preferred download root is `data/market_data`.

Typical example:

```bash
python scripts/download_data.py spot --symbol BTC/USDT --timeframe 1h --start 2020-10-01T00:00:00+00:00 --end 2024-08-16T00:00:00+00:00
```

## 2. Build Datasets

Public modes:

```bash
python scripts/build_datasets.py legacy --help
python scripts/build_datasets.py manifest --help
python scripts/build_datasets.py validate --help
```

### Legacy builder

- older split-based builder
- uses the older train/validation flow

### Manifest builder

- reads curated dataset catalogs from `configs/datasets/*.yaml`
- builds datasets under `data/datasets/{catalog_id}/...`
- supports layers:
  - `train`
  - `validation`
  - `external`
  - `audit`

Example:

```bash
python scripts/build_datasets.py validate --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data
```

```bash
python scripts/build_datasets.py manifest --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --datasets-dir data/datasets
```

## 3. Run Experiments

Single public entrypoint:

```bash
python scripts/run_experiment.py -h
```

Modes:

- `single`
- `batch`
- `multiseed`

### Single

```bash
python scripts/run_experiment.py single --config-path configs/run_balanced_manifest.json
```

### Batch

```bash
python scripts/run_experiment.py batch --configs-dir configs/runs
```

### Multiseed

```bash
python scripts/run_experiment.py multiseed --configs-dir configs/runs --preset standard
```

### Parallel execution

`batch` and `multiseed` support:

```bash
python scripts/run_experiment.py multiseed --configs-dir configs/runs --preset screening --parallel-workers 4
```

Notes:

- `single` remains sequential.
- `batch` and `multiseed` can use process-based parallelism.
- If requested parallelism is not useful, the system falls back explicitly to sequential execution.

## Dataset Modes In Run Configs

The current run-config dataset modes are:

- `legacy`
- `manifest`

Example manifest config fragment:

```json
{
  "dataset_mode": "manifest",
  "dataset_catalog_id": "bnb_1h_spot"
}
```

Important:

- `dataset_root` is the requested root from the CLI.
- the effective dataset root may differ after resolution
- when the legacy default root is requested in `manifest` mode, the effective root becomes `data/datasets`

## Validation Layers

Current layers in practice:

- `train`
- `validation`
- `external`
- `audit`

Current runtime usage:

- `train` and `validation` are part of the main experiment loop
- `external` is used in post-run external validation of the persisted champion
- `audit` is currently used outside the main loop through persisted champion reevaluation

## 4. Analyze Champions

Analyze persisted champions from SQLite:

```bash
python scripts/analyze_champions.py --db-path data/evolution.db
```

Supported filters:

- `--run-id`
- `--config-name`

## 5. Reevaluate Persisted Champions

Reevaluate stored champions on external and/or audit datasets without rerunning evolution:

```bash
python scripts/evaluate_persisted_champions.py -h
```

Supports both:

- direct directory datasets
- manifest/catalog-based external and audit datasets

Example using direct external directory:

```bash
python scripts/evaluate_persisted_champions.py --db-path data/evolution.db --config-name "balanced_bnb fee_5bps_fees.json" --config-path "configs/runs/balanced_bnb fee_5bps_fees.json" --dataset-root data/datasets --external-validation-dir data/datasets/external_validation
```

Example using manifest catalogs for reevaluation:

```bash
python scripts/evaluate_persisted_champions.py --db-path data/evolution.db --config-name "balanced_bnb fee_5bps_fees.json" --config-path "configs/runs/balanced_bnb fee_5bps_fees.json" --dataset-root data/datasets --external-dataset-mode manifest --external-dataset-catalog-id bnb_external_catalog --audit-dataset-mode manifest --audit-dataset-catalog-id bnb_audit_catalog
```

## Presets

Current multiseed presets:

- `quick`
- `screening`
- `standard`
- `extended`
- `full`

Current intent:

- `screening`: fast comparison
- `standard`: baseline multiseed validation
- `extended`: broader multiseed validation
- `full`: longest and most demanding preset

## Practical Notes

- A strong single run is not enough.
- Validation and multiseed stability matter more than isolated peak performance.
- External and audit layers are there to reduce false confidence, not to decorate reports.
