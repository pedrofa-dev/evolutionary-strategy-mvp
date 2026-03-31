# Research Workflow

This document describes the current operational workflow of the repository.

It is the canonical guide for running research without relying on outdated execution paths.

## Canonical Pipeline

The normal pipeline is:

1. Download market data.
2. Build curated datasets from a manifest catalog.
3. Place active run configs in `configs/runs/`.
4. Execute multiseed.
5. Review quick summary and analysis outputs.
6. Optionally run manual champion analysis or manual reevaluation.

## Step 1: Download Market Data

Use the public downloader wrapper:

```bash
python scripts/download_data.py spot --help
python scripts/download_data.py futures --help
```

The current preferred source-data root is `data/market_data`.

## Step 2: Build Datasets

Use the public dataset build wrapper:

```bash
python scripts/build_datasets.py --help
```

Building datasets now means:

1. parse manifest catalog
2. validate catalog structure
3. validate source data coverage
4. build curated dataset windows
5. fail fast if validation or build fails

Examples:

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --validate-only
```

```bash
python scripts/build_datasets.py --catalog-path configs/datasets/core_1h_spot.yaml --market-data-dir data/market_data --datasets-dir data/datasets
```

## Step 3: Prepare Run Configs

Run configs live under `configs/runs/`.

Each config selects its curated dataset catalog directly:

```json
{
  "dataset_catalog_id": "core_1h_spot"
}
```

Common current fields:

- `dataset_catalog_id`
- `mutation_seed`
- `seeds` or `seed_start` + `seed_count`
- `trade_cost_rate`
- `cost_penalty_weight`
- `trade_count_penalty_weight`
- `regime_filter_enabled`
- `min_trend_long_for_entry`
- `min_breakout_for_entry`
- `max_realized_volatility_for_entry`

## Step 4: Run Multiseed

Use the public experiment wrapper:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --preset standard
```

Optional process-based parallelism:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --preset screening --parallel-workers 4
```

Optional explicit external and audit overrides:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --external-validation-dir path/to/external --audit-dir path/to/audit
```

Without explicit overrides, automatic post-multiseed reevaluation resolves external and audit datasets from the run execution catalog context.

## Deduplication And Reuse

Multiseed automatically reuses previously completed equivalent executions.

Reuse identity is strict and based on:

- config snapshot hash
- effective seed
- dataset signature
- `logic_version`

There is no force-rerun compatibility layer in the canonical workflow. If incompatible logic changes are introduced, `logic_version` should be bumped deliberately.

## Step 5: Read Outputs In Order

Read outputs in this order:

1. `multiseed_quick_summary.txt`
2. `analysis/multiseed_champions_summary.txt`
3. `debug/` only if deeper inspection is needed

This is important. The intended workflow is to make a decision from the quick summary and analysis layer first, not from raw diagnostics.

## Step 6: Manual Follow-Up

Manual tools remain supported:

```bash
python scripts/analyze_champions.py --db-path data/evolution_v2.db
```

```bash
python scripts/evaluate_persisted_champions.py --db-path data/evolution_v2.db --config-name "example.json" --external-dataset-catalog-id some_catalog
```

Manual analysis is useful for:

- cross-run champion review
- cross-config comparison
- targeted reevaluation on external, audit, or custom datasets

## Research Discipline

Follow these rules when iterating:

- change one major variable at a time
- do not treat a single strong seed as evidence
- use multiseed consistency before structural conclusions
- do not upgrade a strategy claim if external or audit are missing
- treat `NOT_RUN` as missing evidence, not as success or failure

## Recommended Decision Loop

After each campaign:

1. Decide whether there is any edge worth continuing.
2. Decide whether the main bottleneck is signal-space, generalization, dataset coverage, or policy rigidity.
3. Make one targeted next change.
4. Run a new multiseed campaign.

## See Also

- [Datasets And Validation Rules](datasets_and_validation.md) for canonical dataset layout, validation-layer roles, and automatic versus manual reevaluation resolution.
- [Reporting And Interpretation](reporting_and_interpretation.md) for verdict semantics, `NOT_RUN`, fallback warnings, and how to read post-multiseed outputs.
