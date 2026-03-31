# Datasets And Validation Rules

This document describes the canonical dataset layout and the rules that protect evaluation discipline.

## Canonical Dataset Workflow

The repository uses manifest/catalog datasets only.

There is no separate legacy split workflow.

Dataset catalogs live under:

- `configs/datasets/*.yaml`

Built dataset windows live under:

- `data/datasets/{catalog_id}/{layer}/{dataset_id}/`

Expected layers:

- `train`
- `validation`
- `external`
- `audit`

Each dataset directory contains at least:

- `candles.csv`
- `metadata.json`

## Dataset Root

`dataset_root` is the root directory that contains curated manifest datasets.

In normal operation this is `data/datasets`.

The runtime resolves train and validation datasets from:

- `dataset_root / dataset_catalog_id / train`
- `dataset_root / dataset_catalog_id / validation`

Automatic post-multiseed reevaluation resolves from:

- `dataset_root / dataset_catalog_id / external`
- `dataset_root / dataset_catalog_id / audit`

## Why Layers Exist

Layer separation is an epistemic control, not just a storage convention.

- `train` exists for exploration
- `validation` exists for selection and champion classification
- `external` exists for stronger out-of-loop checking
- `audit` exists for additional out-of-loop challenge batteries

External and audit are not part of the optimization loop.

## Validation Principles

The builder validates catalogs before writing datasets.

At minimum it checks:

- duplicate dataset ids
- invalid fields
- invalid date ranges
- invalid layer names
- missing source data
- very small windows
- cross-layer temporal overlap

Cross-layer overlap is dangerous because it can create leakage between train, validation, external, and audit interpretations.

## Interpreting Missing Layers

Not every catalog must necessarily contain useful external or audit windows at all times.

If external or audit datasets are absent:

- that should be reported explicitly
- it should weaken the strength of conclusions
- it must not be collapsed into a false "strategy failed" message

## Automatic Resolution Versus Manual Overrides

There are two different reevaluation contexts:

Automatic post-multiseed:

- uses the persisted run execution context
- resolves catalog-scoped external and audit datasets by default
- may fall back defensively to `data/datasets` if persisted dataset-root context is missing
- reports that fallback explicitly

Manual reevaluation:

- may use explicit directories
- may use explicit external or audit dataset catalogs
- is more flexible by design

These are not the same thing and should not be documented as the same thing.

## Dataset Regime Labels

The repository keeps a small descriptive taxonomy for curated dataset windows.

Current label dimensions:

- `regime_primary`
- `regime_secondary`
- `volatility`
- `event_tag`

These labels are descriptive metadata only.

They are not part of trading logic, champion policy, or evaluation scoring.

## Practical Rules

- prefer stable catalog ids over ad hoc dataset naming
- do not treat dataset layout as a convenience detail; it is part of evaluation discipline
- if a catalog is too narrow, report dataset coverage limits rather than overclaiming
- if automatic resolution had to fall back, treat later conclusions more cautiously
