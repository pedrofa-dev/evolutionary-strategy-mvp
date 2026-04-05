# Persistence Model

This document describes the current canonical persistence model.

It is based on the persistence redesign that is now active in runtime.

## Purpose

Persistence exists to make research state explicit, queryable, and reusable.

The database is not just a blob dump of past runs. It stores execution identity, self-contained champions, and later analysis or reevaluation results.

## Canonical Database

Current canonical database:

- `data/evolution_v2.db`

There is no parallel legacy SQLite writer in the active runtime. New runs,
champions, analyses, and reevaluations persist through the canonical
`PersistenceStore` only.

Direct SQLite writes are intentionally centralized there. Runtime,
experimentation, reevaluation, and reporting layers should call
`PersistenceStore` rather than opening alternative write paths.

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

- `CURRENT_LOGIC_VERSION = "v15"`

This value is bumped deliberately whenever runtime semantics change in a way
that would make execution reuse unsafe.

This modular identity consolidation phase does not change `logic_version`.
It adds traceability metadata and reporting only, so reuse compatibility
remains governed by the existing runtime semantics.

## Dataset Context Persistence

`run_executions` persist:

- `dataset_catalog_id`
- `dataset_signature`
- `dataset_context_json`

`dataset_context_json` includes the resolved train and validation paths plus counts and relevant root context.

This stored context is also used later by post-multiseed validation and reevaluation workflows.

## Modular Runtime Identity

The runtime now persists explicit modular identity for the active experimental
space.

At minimum, canonical run persistence can record:

- `signal_pack`
- `genome_schema`
- `gene_type_catalog`
- `decision_policy`
- `mutation_profile`
- `market_mode`
- `leverage`
- `experiment_preset` when applicable

This identity appears in:

- `run_executions.experimental_space_snapshot_json`
- `champions.experimental_space_snapshot_json`
- `run_executions.summary_json.experimental_space_snapshot`
- multiseed environment snapshots and top-level reporting summaries

Reporting and artifact generation should surface this identity through a stable
human-readable modular stack label. Older persisted rows that do not carry the
snapshot must degrade gracefully to `unknown` labels instead of failing
analysis or summary paths.

This same canonical stack label is now reused across:

- run logs
- run summary payloads
- multiseed summaries
- champion analysis reports and champion cards

This is additive metadata for traceability. In this phase it does not replace
the canonical execution fingerprint, which remains:

- config snapshot hash
- effective seed
- dataset signature
- `logic_version`

In other words:

- `execution_fingerprint` answers whether two executions are reusable
- `logic_version` answers whether runtime semantics stayed compatible
- `experimental_space_snapshot` answers which modular components were used

The runtime can also persist a derived `runtime_component_fingerprint` built
from the active modular stack:

- `signal_pack`
- `genome_schema`
- `gene_type_catalog`
- `decision_policy`
- `mutation_profile`
- `market_mode`
- `leverage`

This is traceability metadata for runtime composition. It does not replace
`execution_fingerprint`, and it does not change reuse semantics by itself.

For reporting, the primary modular stack is selected deterministically:

- prefer the most frequent normalized stack in the input set
- break ties by canonical stack-label lexical order

This keeps summaries stable even when equivalent rows are loaded in a
different incidental order.

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

## Read Layer

The repository now also exposes a read-only run repository on top of the same
canonical database:

- `RunReadRepository`

It reconstructs persisted run summaries, champion-backed genomes, and
train/validation breakdowns from stored rows only. It does not re-execute
evaluation logic and it does not mutate persistence state.

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
