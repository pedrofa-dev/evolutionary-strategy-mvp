# evolutionary-strategy-mvp

Evolutionary trading research lab focused on validation, robustness, and reducing self-deception.

## What This Project Is

- A rule-based evolutionary experimentation system for historical trading research.
- A lab for searching strategy parameterizations under train/validation discipline.
- A persistence and reporting workflow for analyzing champions after runs.

## What This Project Is Not

- Not an LLM trader.
- Not a direct price predictor.
- Not a production trading engine.
- Not a guarantee of tradable edge after fees and slippage.

The practical philosophy is simple: validation matters more than isolated optimization, and robustness matters more than a single impressive run.

## Current Capabilities

Implemented now:

- Modular architecture split across `domain`, `environment`, `evaluation`, `champions`, `experimentation`, `storage`, and `reporting`.
- Historical single, batch, and multiseed experiment execution through `scripts/run_experiment.py`.
- Optional process-based parallelism for `batch` and `multiseed`.
- Champion classification and persistence policy extracted into `src/evo_system/champions`.
- Train/validation separation during experiment runs.
- Cost-aware evaluation through `trade_cost_rate` and `cost_penalty_weight`.
- Optional trade-count penalty through `trade_count_penalty_weight`.
- Optional regime-entry filter using long-trend, breakout, and realized-volatility thresholds.
- Best persistable champion tracking across the whole run, with only one champion persisted per run.
- Post-run external validation for the persisted champion.
- Manifest/catalog dataset mode for curated `train` / `validation` datasets.
- Reevaluation of persisted champions on external and audit datasets without rerunning evolution.
- Champion reporting and flat exports from SQLite.

Partially implemented or limited on purpose:

- The manifest dataset system supports `train`, `validation`, `external`, and `audit`, but the main experiment runtime currently uses only `train` and `validation`.
- `external` is integrated into the post-run validation layer.
- `audit` is currently used through reevaluation workflows, not the main evolutionary loop.

Future work:

- Stronger fee-surviving signal design.
- Better dataset curation and coverage expansion.
- More disciplined audit workflows across specialized catalog batteries.

## Architecture Summary

Main execution and analysis areas:

- `src/evo_system/domain`
  - Core entities such as `Genome`, `Agent`, `AgentEvaluation`, and run summaries.
- `src/evo_system/environment`
  - Historical environment and dataset loading.
- `src/evo_system/evaluation`
  - Scoring, penalties, vetoes, and the `AgentEvaluator`.
- `src/evo_system/champions`
  - Champion type rules, comparison, persistence eligibility, and champion metrics.
- `src/evo_system/experimentation`
  - Single-run, batch, multiseed, presets, CLI wiring, external validation, and persisted champion reevaluation.
- `src/evo_system/storage`
  - SQLite persistence for runs, generations, and champions.
- `src/evo_system/reporting`
  - Champion loading, filtering, reporting, and exports.

Entry points kept in `scripts/`:

- `download_data.py`
- `build_datasets.py`
- `run_experiment.py`
- `analyze_champions.py`
- `evaluate_champion.py`
- `evaluate_persisted_champions.py`

## Core Workflow

Typical workflow:

1. Download market data.
2. Build datasets.
3. Run experiments.
4. Analyze persisted champions.
5. Optionally reevaluate persisted champions on external or audit datasets.

## Dataset Modes

The project currently supports two dataset modes in run configs:

- `legacy`
- `manifest`

### Legacy mode

- Uses the older train/validation layout under the requested dataset root.
- The historical default requested root is `data/processed`.

### Manifest mode

- Uses curated catalog datasets under `data/datasets/{catalog_id}/...`.
- When the requested dataset root is the legacy default, the effective dataset root resolves to `data/datasets`.
- Run configs specify:

```json
{
  "dataset_mode": "manifest",
  "dataset_catalog_id": "core_1h_spot"
}
```

Important terminology:

- `dataset_root` is the requested root passed from CLI or code.
- `effective dataset root` is the resolved root actually used after applying dataset-mode rules.

## Validation Flow

During a normal experiment run:

- `train` datasets drive evolutionary search.
- `validation` datasets are used for selection and champion classification.

After a run:

- The best persistable champion of the run may receive post-run external validation.

Outside the main run loop:

- Persisted champions can be reevaluated on external and/or audit datasets with `scripts/evaluate_persisted_champions.py`.

This separation is intentional: the project tries to avoid mixing optimization and evaluation layers more than necessary.

## Experiment Modes

Public experiment CLI:

```bash
python scripts/run_experiment.py single ...
python scripts/run_experiment.py batch ...
python scripts/run_experiment.py multiseed ...
```

Notes:

- `single` stays sequential.
- `batch` and `multiseed` support optional process-based parallel execution with `--parallel-workers`.
- If parallelism is requested but not useful, the system falls back explicitly to sequential execution.
- Sequential mode keeps detailed generation-level output.
- Parallel mode can show job-level progress and active-run progress snapshots.

## Run Configuration Concepts

Common config fields in current use:

- `trade_cost_rate`
- `cost_penalty_weight`
- `trade_count_penalty_weight`
- `dataset_mode`
- `dataset_catalog_id`
- `seeds` or `seed_start` + `seed_count`
- `regime_filter_enabled`
- `min_trend_long_for_entry`
- `min_breakout_for_entry`
- `max_realized_volatility_for_entry`

Example:

```json
{
  "population_size": 18,
  "target_population_size": 18,
  "survivors_count": 4,
  "generations_planned": 40,
  "mutation_seed": 42,
  "trade_cost_rate": 0.0005,
  "cost_penalty_weight": 0.25,
  "trade_count_penalty_weight": 0.001,
  "dataset_mode": "manifest",
  "dataset_catalog_id": "bnb_1h_spot",
  "regime_filter_enabled": true,
  "min_trend_long_for_entry": 0.20,
  "min_breakout_for_entry": 0.10,
  "max_realized_volatility_for_entry": 0.45
}
```

## Persistence And Reporting

What gets persisted:

- Run records
- Generation summaries
- At most one champion per run

Champion persistence behavior:

- The system tracks the best persistable champion seen across the run.
- Persistence is not limited to the final generation.

Reporting flow:

- `scripts/analyze_champions.py` analyzes persisted champions from SQLite.
- `scripts/evaluate_persisted_champions.py` reevaluates stored champions on external/audit datasets and exports flat CSV, JSON, and report artifacts.

## Current Practical Focus

The current research focus is not "find any profitable strategy in backtest."

The current practical focus is:

- understand whether discovered edge survives validation
- understand whether edge survives friction
- reduce weak-context entries
- improve strategy robustness before claiming anything meaningful

## Useful Guides

- `guides/README_USAGE.txt`
- `guides/manifest_dataset_builder.md`
- `guides/dataset_validation.md`
- `guides/dataset_regime_taxonomy.md`
- `guides/parallel_experiment_execution.md`
- `guides/DESIGN_EXPERIMENT.txt`

## Status

This is an active research repo.

It already supports a substantial experimentation workflow, but it should still be treated as a research laboratory rather than a finished trading product.
