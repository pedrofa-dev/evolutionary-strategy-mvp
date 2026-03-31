# Dataset Validation

Dataset validation is part of the manifest build flow. The builder checks whether a catalog is structurally correct and safe to use before writing curated datasets.

## What Is Validated

The validator checks at least:

- duplicate dataset IDs
- missing or invalid fields
- invalid date ranges
- invalid layer names
- cross-layer temporal overlap for the same symbol, market type, and timeframe
- missing source data
- very small dataset windows

## Why Overlap Is Dangerous

If two datasets from different layers overlap in time, the validation boundaries become unreliable.

For example, overlap between `train` and `validation`, or between `validation` and `external`, can create leakage across evaluation layers and make later results harder to trust.

## How To Interpret Errors

- Duplicate ID errors mean the catalog is ambiguous and should be fixed before building.
- Invalid field or layer errors mean the catalog shape is inconsistent.
- Date range errors mean the window definition itself is wrong.
- Overlap errors mean two different layers share the same time window for the same instrument.
- Missing source data errors mean the expected market files are not available under `data/market_data`.
- Very small dataset errors mean the window exists but likely contains too little data to be useful.

## Example Commands

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --validate-only
```

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --datasets-dir data/datasets
```
