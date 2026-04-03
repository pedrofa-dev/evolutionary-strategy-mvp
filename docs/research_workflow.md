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

The current active research line uses the policy v2.1 genome layout:

- `EntryContextGene`
- `EntryTriggerGene`
- `ExitPolicyGene`
- `TradeControlGene`

These blocks live inside the genome and are mutated as part of the policy search. New campaigns now execute only through these policy v2.1 blocks. Legacy flat fields remain only as a bounded historical compatibility lane for loading older snapshots and reevaluating older results.

The current signal set for policy v2.1 is grouped into reusable market families:

- Trend
  - `trend_strength_medium`
  - `trend_strength_long`
- Momentum
  - `momentum_short`
  - `momentum_persistence`
- Breakout
  - `breakout_strength_medium`
- Range
  - `range_position_medium`
- Volatility
  - `realized_volatility_medium`
  - `volatility_ratio_short_long`

These features were chosen because they are portable across future environments and do not depend on a specific platform indicator catalog. The goal is to describe reusable market structure, not to optimize around named retail indicators.

The active v2.1 family now compares five `EntryTriggerGene` variants:

- conservative
- baseline
- permissive
- recovery
- recovery_trend

They differ only in:

- `entry_score_threshold`
- `min_positive_families`

`require_trend_or_breakout` stays fixed at `true` for the canonical conservative / baseline / permissive lane. The two recovery probes are intentionally narrower experiments that relax this flag while adding explicit anti-churn trade controls.

In this phase, signals, scoring, datasets, and architecture remain fixed. The recovery probes still vary trigger conviction first, while adding bounded trade-control guardrails to avoid reopening the fee-destroyed micro-trading regime.

Current active values:

- conservative
  - `entry_score_threshold = 0.55`
  - `min_positive_families = 3`
- baseline
  - `entry_score_threshold = 0.45`
  - `min_positive_families = 2`
- permissive
  - `entry_score_threshold = 0.40`
  - `min_positive_families = 1`
- recovery
  - `entry_score_threshold = 0.43`
  - `min_positive_families = 1`
  - `require_trend_or_breakout = false`
  - `cooldown_bars = 2`
  - `min_holding_bars = 2`
  - `reentry_block_bars = 2`
- recovery_trend
  - same as recovery
  - `trend_weight >= 0.0`
  - `breakout_weight >= 0.0`

The previous `min_bars_between_entries`, `entry_confirmation_bars`, `entry_score_margin`, and earlier `policy_v2_*` configs are kept under `configs/runs/deprecated/` as historical runs. The code support remains available for compatibility, but the active run set has moved to policy v2.1.

Legacy retirement criteria:

- do not retire legacy until policy v2 has been validated across multiple campaigns
- do not retire legacy while it is still needed for historical reevaluation or reproducibility
- prefer explicit deprecation over early deletion

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

There is no force-rerun compatibility layer in the canonical workflow. If incompatible logic changes are introduced, `logic_version` should be bumped deliberately. The current policy v2 genome rollout is one such compatibility change.

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
