# Persistence Model

This document describes the current canonical persistence model.

It is based on the persistence redesign that is now active in runtime.

## Purpose

Persistence exists to make research state explicit, queryable, and reusable.

The database is not just a blob dump of past runs. It stores execution identity, self-contained champions, and later analysis or reevaluation results.

## Canonical Database

Current canonical database:

- `data/evolution_v2.db`

Canonical tables:

- `multiseed_runs`
- `run_executions`
- `champions`
- `champion_analyses`
- `champion_analysis_members`
- `champion_evaluations`
- `champion_evaluation_members`

## Core Entities

`multiseed_runs`

- one mass execution campaign
- tracks campaign status, counts, artifact paths, and post-run status fields

`run_executions`

- one config snapshot plus one effective seed plus one dataset context
- this is the reusable execution unit

`champions`

- one self-contained persisted champion
- includes genome snapshot, config snapshot, dataset identity, and metric snapshots
- may include either legacy-compatible fields or policy v2 block fields, depending on when the champion was produced

`champion_analyses`

- persisted analysis over a selected champion set
- supports both automatic post-multiseed analysis and manual analysis

`champion_evaluations`

- persisted reevaluation over a selected champion set and dataset set
- supports automatic post-multiseed external and audit validation as well as manual reevaluation

## Why Config Snapshots Matter

The system persists the executed config snapshot, not just the config file name.

That is required so later reevaluation does not depend on the original config file still existing or still matching what was executed.

## Execution Identity

Execution identity is strict.

A reusable execution is defined by:

- config snapshot hash
- effective seed
- dataset signature
- `logic_version`

These values are combined into an `execution_fingerprint`.

Equivalent completed executions are reused automatically by multiseed instead of rerun.

## Logic Version

`logic_version` is a manual compatibility token.

It exists so incompatible logic changes can invalidate reuse cleanly without deleting historical data.

Old rows may remain stored for history, but they should not be treated as reusable if `logic_version` changes.

Current runtime value:

- `CURRENT_LOGIC_VERSION = "v7"`

This value was bumped deliberately when the active policy v2 runtime moved to the v2.1 family-based signal set. That changes the effective execution semantics of new runs, so reuse across the previous logic version would be misleading.

## Dataset Context Persistence

`run_executions` persist:

- `dataset_catalog_id`
- `dataset_signature`
- `dataset_context_json`

`dataset_context_json` includes the resolved train and validation paths plus counts and relevant root context.

This stored context is also used later by post-multiseed validation and reevaluation workflows.

## Champion Self-Containment

Each champion persists:

- `config_json_snapshot`
- `genome_json_snapshot`
- `dataset_catalog_id`
- `dataset_signature`
- train metrics
- validation metrics

This is what makes later reevaluation independent from original config files on disk.

## Automatic Post-Multiseed Persistence

If a multiseed campaign finds champions:

- automatic champion analysis is persisted
- automatic external reevaluation is persisted when applicable
- automatic audit reevaluation is persisted when applicable

If no champions exist:

- no champion analysis row is created
- no champion evaluation row is created
- the `multiseed_runs` status fields record that explicitly

## Manual Tool Persistence

Manual tools still write into the same canonical model:

- `scripts/analyze_champions.py`
- `scripts/evaluate_persisted_champions.py`

That means manual and automatic workflows now share the same source of truth.

## Artifact Paths

Artifact paths are persisted as repo-relative paths.

Artifacts remain useful for inspection, but the structured persistence model is the primary source of truth.

## Practical Implication

When debugging a past campaign:

- start from `multiseed_runs`
- inspect the linked `run_executions`
- inspect `champions`
- then inspect linked `champion_analyses` and `champion_evaluations`

The database should now tell a coherent story of what was executed and what was concluded later.
