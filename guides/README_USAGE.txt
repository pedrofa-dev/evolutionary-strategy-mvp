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

The dataset builder now has a single manifest/catalog flow with integrated validation:

```bash
python scripts/build_datasets.py --help
```

- reads curated dataset catalogs from `configs/datasets/*.yaml`
- validates manifest structure and source coverage before writing anything
- builds datasets under `data/datasets/{catalog_id}/...`
- supports layers:
  - `train`
  - `validation`
  - `external`
  - `audit`

Validate only:

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --validate-only
```

Build after automatic validation:

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --datasets-dir data/datasets
```

## 3. Run Experiments

Single public entrypoint:

```bash
python scripts/run_experiment.py -h
```

Canonical workflow:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --preset standard
```

### Parallel execution

`multiseed` supports:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --preset screening --parallel-workers 4
```

Notes:

- `multiseed` can run sequentially or with process-based parallelism.
- If requested parallelism is not useful, the system falls back explicitly to sequential execution.

## Dataset Catalogs In Run Configs

Run configs now select curated datasets directly by catalog id:

```json
{
  "dataset_catalog_id": "bnb_1h_spot"
}
```

Important:

- `dataset_root` is the root containing built manifest datasets.
- the runtime resolves `train` and `validation` datasets from `dataset_root / dataset_catalog_id`.

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
python scripts/analyze_champions.py --db-path data/evolution_v2.db
```

Supported filters:

- `--run-id`
- `--config-name`
- `--champion-type`

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
python scripts/evaluate_persisted_champions.py --db-path data/evolution_v2.db --config-name "balanced_bnb fee_5bps_fees.json" --dataset-root data/datasets --external-validation-dir data/datasets/external_validation
```

Example using manifest catalogs for reevaluation:

```bash
python scripts/evaluate_persisted_champions.py --db-path data/evolution_v2.db --config-name "balanced_bnb fee_5bps_fees.json" --dataset-root data/datasets --external-dataset-catalog-id bnb_external_catalog --audit-dataset-catalog-id bnb_audit_catalog
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

- A strong individual seed is not enough.
- Validation and multiseed stability matter more than isolated peak performance.
- External and audit layers are there to reduce false confidence, not to decorate reports.
