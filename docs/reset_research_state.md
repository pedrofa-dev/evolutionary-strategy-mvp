# Reset Research State

This document defines what a future research-state reset means in this repository.

It is intentionally conservative.

It does **not** describe a source-code reset.
It does **not** delete datasets or market data.
It does **not** run automatically as part of normal development workflows.

Reset must remain a conscious operational action.

## Why This Exists

Old persisted campaigns are currently still useful for UI hardening and failure-mode inspection.

In particular, historical state can still expose:

- incomplete campaigns
- missing reporting artifacts
- stale persistence rows
- UI behavior under imperfect research history

That means a reset is **not** the right default action today.

This document exists so that, once the UI and operational flow feel stable enough,
the repository already has a clear and safe way to start a fresh research cycle.

## Canonical Research State

The current canonical persistence model is centered on:

- `data/evolution_v2.db`
- `artifacts/multiseed/`

These hold the main research history:

- multiseed campaigns
- per-seed run executions
- persisted champions
- persisted analyses
- persisted reevaluations
- quick summaries and campaign-level artifacts

The canonical workflow is documented in:

- [Research Workflow](research_workflow.md)
- [Persistence Model](persistence_model.md)
- [Reporting And Interpretation](reporting_and_interpretation.md)

## What Counts As Research-State Reset

For this repository, a research-state reset should mean:

- clearing persisted campaign history
- clearing canonical multiseed output artifacts tied to that history
- optionally clearing UI staging artifacts
- optionally clearing manual analysis outputs that were generated from old persisted state

It should **not** mean:

- deleting source code
- deleting documentation
- deleting declarative experimental assets
- deleting dataset manifests under `configs/datasets/`
- deleting market data under `data/market_data/`
- deleting built datasets under `data/datasets/`

## Audited Persistent Areas

### Canonical SQLite database

Canonical database:

- `data/evolution_v2.db`

Canonical tables:

- `multiseed_runs`
- `run_executions`
- `champions`
- `champion_analyses`
- `champion_analysis_members`
- `champion_evaluations`
- `champion_evaluation_members`

If the goal is a truly fresh research history, this database must be cleared.

### Canonical multiseed artifacts

Canonical campaign artifacts live under:

- `artifacts/multiseed/`

These include:

- quick summaries
- campaign summaries
- per-seed logs
- automatic post-multiseed analysis
- automatic external and audit reevaluation artifacts

If the database is reset but these directories are left in place, the repo keeps
old campaign artifacts that no longer match the fresh persistence state.

For a clean research restart, these should normally be cleared together with the
canonical database.

### UI staging artifacts

Run Lab writes staging outputs under:

- `artifacts/ui_run_lab/`

These are operational UI helper outputs, not canonical research history.

They are safe to remove during a reset.

### Manual reporting outputs

Manual tools write optional outputs under:

- `artifacts/analysis/`

Examples:

- manual champion analysis outputs
- manual persisted champion reevaluation outputs

These are useful artifacts, but they are derivative of persisted research state.

If the goal is a completely fresh research workspace, they may also be cleared.
If the goal is only to restart execution history while keeping previous manual
reports for reference, they may be preserved.

### Active run configs

Active canonical configs live under:

- `configs/runs/`

These should generally be **preserved** across resets.

They are operator-authored canonical inputs, not generated research history.

Current Run Lab behavior saves canonical configs there on purpose, so a reset
should not casually delete them.

### Temporary execution config sets

Run Lab creates temporary copied config sets under:

- `artifacts/ui_run_lab/config_sets/`

These are staging artifacts and should be considered resettable.

### Dataset and market data

These should **not** be part of a research reset:

- `data/market_data/`
- `data/datasets/`
- `configs/datasets/`

They are inputs to research, not the persisted research history itself.

## Ambiguous Or Historical Areas

The following areas exist in the repository but should not be deleted by default
in the canonical reset path:

### `data/evolution.db`

This file exists on disk, but the active runtime and documentation point to:

- `data/evolution_v2.db`

No active canonical code path currently uses `data/evolution.db`.

That makes it a likely historical or legacy database artifact.

It should **not** be deleted by default in a canonical reset until the operator
explicitly confirms that it is no longer needed for historical reference.

### `artifacts/runs/`

This directory is still referenced by `historical_run.py` as a run-log output
location, but it is not the main canonical multiseed research lane documented in
the current workflow.

Treat it as historical or compatibility-oriented output unless there is a clear
active operational need to clear it.

It should not be part of the default reset.

### `artifacts/batches/`

This directory exists, but this audit did not find it in the current canonical
research workflow documentation.

It should not be deleted automatically without manual review.

## Proposed Reset Modes

### Soft reset

Purpose:

- start a fresh research history
- keep operator-authored configs and supporting inputs
- avoid touching ambiguous legacy files

Clear:

- `data/evolution_v2.db`
- `artifacts/multiseed/`
- `artifacts/ui_run_lab/`

Preserve:

- `configs/runs/`
- `configs/datasets/`
- `data/market_data/`
- `data/datasets/`
- `artifacts/analysis/`
- `data/evolution.db`
- `artifacts/runs/`
- `artifacts/batches/`

### Hard research reset

Purpose:

- start a fresh research history
- also clear manual analysis outputs derived from older research state

Clear:

- everything in soft reset
- `artifacts/analysis/`

Preserve:

- `configs/runs/`
- `configs/datasets/`
- `data/market_data/`
- `data/datasets/`
- `data/evolution.db` by default
- `artifacts/runs/` by default
- `artifacts/batches/` by default

## Optional Legacy Cleanup

Legacy cleanup should stay explicit and opt-in.

Possible opt-in targets:

- `data/evolution.db`
- `artifacts/runs/`
- `artifacts/batches/`

These should require an additional explicit flag or manual confirmation because
they are not part of the current canonical reset definition.

## Operational Script

This repository now includes a dedicated reset helper:

- `python scripts/reset_research_state.py --help`

Key safety properties:

- dry-run by default
- requires explicit `--execute` to perform deletions
- prints exactly which paths would be cleared
- separates canonical reset targets from optional legacy cleanup targets

## When To Use Reset

Use a reset only when:

- the UI and operational flow are stable enough to begin a fresh research phase
- old persisted campaigns are no longer needed for debugging or hardening
- the team explicitly wants a clean baseline for new experiments

Do not use it casually while:

- validating Results behavior against incomplete historical state
- debugging persistence/reporting edge cases
- comparing new behavior against old campaigns

## Why We Are Not Doing It Yet

Current persisted state still provides useful test pressure for:

- partial campaign handling
- missing artifact behavior
- Results resilience
- UI and API hardening

That is why this repository now has a reset plan and a reset tool, but this pass
does **not** execute any destructive action.
