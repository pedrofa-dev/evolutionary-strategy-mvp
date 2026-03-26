# Dataset Migration Plan

## Purpose

This project is moving toward a clearer separation between reusable market source data and curated experiment datasets.

This change is incremental. The current folder structure and pipeline remain temporarily supported while the repository migrates in small safe steps.

## Why Separate `market_data` And `datasets`

Keeping market source files and experiment datasets in different locations makes the data layer easier to reason about.

- `market_data` is for reusable source market files.
- `datasets` is for curated windows prepared for experimentation and validation.

This separation helps avoid mixing download concerns with dataset assignment concerns.

## `data/market_data`

`data/market_data/` should contain reusable raw or source market files downloaded from exchanges or providers.

These files are the base material used to build experiment datasets, but they are not the same thing as train or validation splits.

## `data/datasets`

`data/datasets/` should contain curated dataset windows that are intentionally assigned to evaluation layers such as:

- `train`
- `validation`
- `external`
- `audit`

This makes it easier to evolve toward clearer dataset-layer validation without coupling those layers to the raw download layout.

## Incremental Migration

This repository is not switching everything at once.

- The old structure is still temporarily supported.
- Existing experiment logic is unchanged for now.
- Existing evaluation and champion logic is unchanged for now.
- New folders are being introduced early so future migration steps have a clear target structure.

## Intended Future Pipeline

The intended pipeline remains:

`download_data -> build_datasets -> run_experiment -> analyze_champions`

The difference is that future migration steps should make the dataset boundaries more explicit inside `data/datasets/` while keeping `data/market_data/` focused on reusable market source files.
