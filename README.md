# evolutionary-strategy-mvp

Evolutionary trading research lab focused on validation, robustness, and reducing self-deception.

## What This Repository Is

- A rule-based historical trading-research system.
- A multiseed experimentation workflow over curated dataset catalogs.
- A persistence and reporting stack for analyzing and reevaluating persisted champions.

## What It Is Not

- Not an LLM trader.
- Not a direct price predictor.
- Not a production trading engine.
- Not a claim that robust edge has already been found.

The working philosophy is simple:

- evaluation is the authority
- validation matters more than isolated optimization
- external and audit layers must not leak into training optimization
- missing evidence is different from negative evidence

## Canonical Workflow

1. Download market data.
2. Build curated datasets from a manifest catalog.
3. Place active run configs under `configs/runs/`.
4. Run multiseed.
5. Read the quick summary and decision-oriented analysis.
6. Use manual champion analysis or reevaluation only when needed.

Public entrypoints:

- `python scripts/download_data.py --help`
- `python scripts/build_datasets.py --help`
- `python scripts/run_experiment.py --help`
- `python scripts/analyze_champions.py --help`
- `python scripts/evaluate_persisted_champions.py --help`

## Current Stable Realities

- Manifest/catalog datasets are the only canonical dataset workflow.
- Multiseed is the only canonical experiment execution workflow.
- Automatic execution reuse is governed by strict execution fingerprints plus `logic_version`.
- Champions are persisted self-contained in the canonical SQLite store.
- Automatic post-multiseed external and audit validation resolve catalog-scoped datasets by default.
- Reporting is organized into:
  - Level 1 quick summary
  - Level 2 decision-oriented analysis
  - Level 3 debug diagnostics

## Documentation Map

Canonical documents:

- [Architecture](docs/architecture.md)
- [Research Workflow](docs/research_workflow.md)
- [Datasets And Validation Rules](docs/datasets_and_validation.md)
- [Reporting And Interpretation](docs/reporting_and_interpretation.md)
- [Persistence Model](docs/persistence_model.md)
- [UI Product Plan](docs/ui_product_plan.md)
- [Contributor Guidelines](docs/contributor_guidelines.md)

Historical notes, if any are preserved later, belong under [docs/archive](docs/archive/README.md) and are not canonical guidance.

## Status

This repository is an active research codebase.

It should be treated as a disciplined experimentation lab, not as evidence of a finished or validated trading product.
