# Persistence Redesign Specification

This document defines the target persistence model for the next storage refactor.

Scope:

- multiseed executions
- concrete per-config-per-seed executions
- persisted champions
- automatic champion analysis
- automatic champion reevaluation
- manual analysis and manual reevaluation
- execution deduplication
- logic-version invalidation

This is a design-only document.

- It does not change the current runtime.
- It does not change the current SQLite schema.
- It does not require backward compatibility with the current blob-oriented storage.
- Existing stored results are considered disposable.

## Goals

- Make persistence explicit, queryable, and reuse-friendly.
- Treat multiseed as the only canonical execution workflow.
- Persist executed config snapshots, not only config names or file paths.
- Make reevaluation independent from config files remaining on disk.
- Support both automatic post-multiseed workflows and manual later analysis.
- Allow execution deduplication based on real execution identity, not filename coincidence.
- Make invalidation explicit when core logic changes.

## Non-Goals

- No schema migration plan yet.
- No runtime refactor yet.
- No API contract for external services.
- No final storage-engine decision beyond the assumption that SQLite remains acceptable.

## Design Principles

1. Executed reality beats filesystem references.
   Persist what was actually executed: config snapshot, effective seed, dataset identity, logic version.

2. Reuse must be explicit and safe.
   A previous result is reusable only if fingerprint compatibility is exact.

3. Historical storage and reusable storage are different concepts.
   Old results may remain stored for audit/history even when they are not reusable.

4. Champions must be self-contained.
   A champion must carry enough data to be reevaluated without reopening the original config file.

5. Automatic post-multiseed outputs are first-class persistence objects.
   They are not just files on disk; they should be represented in storage as well.

6. Structured columns for filtering, JSON for snapshots.
   Fields needed for indexing, filtering, and joins should be stored as columns.
   Rich snapshots and flexible metadata can remain JSON.

## Canonical Execution Model

The canonical workflow is:

1. Build datasets from manifest catalogs.
2. Run multiseed across the active configs directory.
3. Produce one `multiseed_run`.
4. Produce many `run_execution` rows.
5. Persist zero or more `champion` rows from those executions.
6. Automatically persist one `champion_analysis` for the multiseed champion set.
7. Automatically persist one `champion_evaluation` for external datasets, if datasets exist.
8. Automatically persist one `champion_evaluation` for audit datasets, if datasets exist.

Manual tools remain supported as separate workflows that create additional `champion_analysis` and `champion_evaluation` records.

## Entity Model

Text relationship diagram:

```text
multiseed_run
  -> run_execution
    -> champion
      -> champion_evaluation

multiseed_run
  -> champion_analysis

champion_analysis
  -> champion (many-to-many via analysis membership)

champion_evaluation
  -> champion (many-to-many via evaluation membership)
```

Concrete table names chosen for implementation:

- `multiseed_runs`
- `run_executions`
- `champions`
- `champion_analyses`
- `champion_analysis_members`
- `champion_evaluations`
- `champion_evaluation_members`

## 1. Entity: `multiseed_run`

### Purpose

Represents one mass execution campaign over a set of configs and seeds.

It is the top-level orchestration object for the canonical workflow.

### Required fields

- `id`
  - Stable internal primary key.
- `multiseed_run_uid`
  - Human-facing unique identifier.
- `started_at`
- `completed_at`
- `status`
  - Example values: `running`, `completed`, `completed_with_failures`, `failed`.
- `configs_dir_snapshot`
  - Snapshot of the config discovery context.
  - Can be a JSON array of discovered config identities or a compact JSON object.
- `preset_name`
  - Nullable if no preset was used.
- `requested_parallel_workers`
- `effective_parallel_workers`
- `dataset_root`
  - Requested or canonical dataset root used by the execution campaign.
- `logic_version`
- `runs_planned`
- `runs_completed`
- `runs_failed`

### Optional fields

- `context_name`
- `notes`
- `failure_summary_json`
- `environment_snapshot_json`
  - Optional runtime metadata such as Python version, platform, git commit if later desired.

### Structured columns vs JSON

Structured columns:

- ids
- timestamps
- status
- preset
- worker counts
- dataset_root
- logic_version
- run counts

JSON:

- `configs_dir_snapshot`
- `failure_summary_json`
- `environment_snapshot_json`

### Relationships

- one-to-many with `run_execution`
- one-to-many with `champion_analysis`
- indirectly related to `champion_evaluation` through champions or analyses

### Artifact paths

Associated artifact paths should include:

- `summary_artifact_path`
- `quick_summary_artifact_path`
- `champions_summary_artifact_path`
- `artifacts_root_path`

These should point to the persisted multiseed artifact directory, for example under `artifacts/multiseed/...`.

## 2. Entity: `run_execution`

### Purpose

Represents one concrete executed unit.

One `run_execution` means:

- one executed config snapshot
- one effective seed
- one dataset context
- one logic version

This is the unit eligible for deduplication/reuse.

### Required fields

- `id`
- `run_execution_uid`
- `multiseed_run_id`
  - Nullable only if manual execution persistence is ever introduced later.
- `run_id`
  - Runtime-facing identifier used in logs and champion association.
- `config_name`
  - Human-friendly name only, not identity.
- `config_json_snapshot`
  - Full executed config payload after any preset/effective override is applied.
- `config_hash`
  - Hash of `config_json_snapshot`.
- `effective_seed`
- `dataset_catalog_id`
- `dataset_signature`
  - Concrete dataset identity used for train/validation.
- `dataset_context_json`
  - Resolved dataset metadata such as train paths, validation paths, counts, optional root.
- `logic_version`
- `execution_fingerprint`
- `status`
  - Example values: `completed`, `failed`, `reused`.
- `started_at`
- `completed_at`

### Optional fields

- `context_name`
- `preset_name`
- `requested_dataset_root`
- `resolved_dataset_root`
- `failure_reason`
- `log_artifact_path`
- `summary_json`
  - Compact structured summary of final metrics.

### Structured columns vs JSON

Structured columns:

- ids
- foreign keys
- `run_id`
- `config_name`
- `config_hash`
- `effective_seed`
- `dataset_catalog_id`
- `dataset_signature`
- `logic_version`
- `execution_fingerprint`
- status
- timestamps
- artifact path fields

JSON:

- `config_json_snapshot`
- `dataset_context_json`
- `summary_json`

### Relationships

- many-to-one with `multiseed_run`
- one-to-many with `champion`

### Artifact paths

- `log_artifact_path`
- optional `progress_snapshot_artifact_path`
- optional `per_run_summary_artifact_path`

## 3. Entity: `champion`

### Purpose

Represents one persisted champion snapshot produced by one `run_execution`.

It must be self-contained enough for later reevaluation without reading the original config file from disk.

### Required fields

- `id`
- `champion_uid`
- `run_execution_id`
- `run_id`
- `config_name`
- `config_hash`
- `logic_version`
- `generation_number`
- `mutation_seed`
- `champion_type`
  - Example: `robust`, `specialist`.
- `genome_json_snapshot`
- `genome_hash`
- `config_json_snapshot`
  - Stored directly on the champion for independence from disk and simplified reevaluation.
- `dataset_catalog_id`
- `dataset_signature`
- `train_metrics_json`
- `validation_metrics_json`
- `persisted_at`

### Optional fields

- `context_name`
- `champion_metrics_json`
  - Unified flattened metrics payload if desired.
- `notes`

### Structured columns vs JSON

Structured columns:

- ids
- foreign key
- `run_id`
- `config_name`
- `config_hash`
- `logic_version`
- `generation_number`
- `mutation_seed`
- `champion_type`
- `genome_hash`
- `dataset_catalog_id`
- `dataset_signature`
- `persisted_at`

JSON:

- `genome_json_snapshot`
- `config_json_snapshot`
- `train_metrics_json`
- `validation_metrics_json`
- `champion_metrics_json`

### Relationships

- many-to-one with `run_execution`
- many-to-many with `champion_analysis`
- many-to-many with `champion_evaluation`

### Artifact paths

Optional associated paths:

- `champion_card_artifact_path`
- `serialized_snapshot_artifact_path`

These are secondary and should not replace structured storage.

## 4. Entity: `champion_analysis`

### Purpose

Represents one analysis run over a chosen set of champions.

This must support:

- automatic post-multiseed champion analysis
- manual cross-run or cross-config analysis later

### Required fields

- `id`
- `champion_analysis_uid`
- `analysis_type`
  - Example values: `automatic_post_multiseed`, `manual_cross_run`, `manual_cross_config`.
- `logic_version`
- `started_at`
- `completed_at`
- `champion_count`
- `selection_scope_json`
  - Describes how champions were selected.
- `analysis_summary_json`

### Optional fields

- `multiseed_run_id`
  - Present for automatic post-multiseed analysis.
- `requested_by`
  - Optional later if operator identity matters.
- `notes`

### Structured columns vs JSON

Structured columns:

- ids
- type
- timestamps
- champion_count
- optional foreign key to `multiseed_run`
- logic_version

JSON:

- `selection_scope_json`
- `analysis_summary_json`

### Relationships

- optional many-to-one with `multiseed_run`
- many-to-many with `champion`

This likely needs a membership table such as `champion_analysis_member`.

### Artifact paths

- `output_dir_artifact_path`
- `flat_csv_artifact_path`
- `report_artifact_path`
- `patterns_artifact_path`
- `champion_card_artifact_path`

## 5. Entity: `champion_evaluation`

### Purpose

Represents reevaluation of one chosen set of champions on one chosen evaluation dataset set.

This must support:

- automatic post-multiseed external evaluation
- automatic post-multiseed audit evaluation
- manual reevaluation later on custom datasets

### Required fields

- `id`
- `champion_evaluation_uid`
- `evaluation_type`
  - Example values: `external`, `audit`, `custom`.
- `evaluation_origin`
  - Example values: `automatic_post_multiseed`, `manual`.
- `logic_version`
- `started_at`
- `completed_at`
- `champion_count`
- `dataset_source_type`
  - Example values: `catalog`, `directory`, `custom_snapshot`.
- `dataset_set_name`
  - Human-facing name of the evaluated dataset set.
- `dataset_catalog_id`
  - Nullable for direct/custom datasets.
- `dataset_root`
  - Nullable if represented differently.
- `dataset_signature`
  - Signature of the reevaluation dataset set.
- `selection_scope_json`
  - Which champions were evaluated.
- `evaluation_summary_json`

### Optional fields

- `multiseed_run_id`
  - Present for automatic post-multiseed evaluation.
- `requested_by`
- `notes`

### Structured columns vs JSON

Structured columns:

- ids
- evaluation type
- origin
- timestamps
- champion_count
- dataset source type
- dataset_set_name
- dataset_catalog_id
- dataset_root
- dataset_signature
- logic_version
- optional foreign key to `multiseed_run`

JSON:

- `selection_scope_json`
- `evaluation_summary_json`

### Relationships

- optional many-to-one with `multiseed_run`
- many-to-many with `champion`

This likely needs a membership table such as `champion_evaluation_member`.

### Artifact paths

- `output_dir_artifact_path`
- `flat_csv_artifact_path`
- `json_artifact_path`
- `report_artifact_path`
- `per_champion_dir_artifact_path`

## Membership Tables

The spec expects explicit many-to-many membership tables.

Recommended tables:

- `champion_analysis_member`
  - `champion_analysis_id`
  - `champion_id`
- `champion_evaluation_member`
  - `champion_evaluation_id`
  - `champion_id`

These avoid hiding set membership inside JSON only.

## Config Snapshot Persistence

This is mandatory in the redesigned model.

Every `run_execution` must persist:

- `config_name`
- `config_json_snapshot`
- `config_hash`

Every `champion` must also persist:

- `config_name`
- `config_json_snapshot`
- `config_hash`

Rationale:

- reevaluation must not depend on the original config file still existing
- config filenames are not stable identity
- later analysis needs the executed reality, not a possibly edited file on disk

The persisted config snapshot must be the effective executed config, after preset effects and seed resolution are applied.

## Execution Fingerprint

The redesigned system must define one canonical execution fingerprint for `run_execution`.

Purpose:

- detect already-executed equivalent runs
- support reuse or explicit skip in future refactors
- prevent false reuse across incompatible logic or datasets

The fingerprint must not depend only on config name.

Conceptually, it must include at least:

- `config_hash`
- `effective_seed`
- `dataset_signature`
- `logic_version`

Optionally it may also include:

- normalized context name
- resolved dataset root if relevant to dataset identity

Recommended conceptual formula:

```text
execution_fingerprint =
  hash(
    config_hash +
    effective_seed +
    dataset_signature +
    logic_version
  )
```

## Logic Version and Invalidation

The redesigned model must include a manual compatibility field:

- `logic_version`

Purpose:

- invalidate reuse when core execution semantics change
- preserve old records historically without pretending they are compatible

Examples of changes that should require a new `logic_version`:

- entry or exit decision logic changes
- signal set changes
- feature engineering changes
- genome structure changes
- evaluation compatibility changes
- champion classification compatibility changes

Rules:

- old rows may remain stored
- old rows are historical
- old rows are not reusable across incompatible `logic_version`
- fingerprint compatibility requires matching `logic_version`

This version is intentionally manual and explicit.
It is not inferred automatically from git state.

Current implementation default:

- `CURRENT_LOGIC_VERSION = "v1"`

## Automatic Multiseed Outputs

Every completed `multiseed_run` must persist, at minimum:

Always:

- multiseed summary
- run index or execution summary

If champions exist:

- champion analysis
- external validation result, if external datasets are available
- audit validation result, if audit datasets are available

If no champions exist:

- that fact must be explicit in the multiseed summary
- automatic champion analysis may still exist as an empty/no-champions record, or may be skipped with explicit summary status

Recommended persisted status behavior:

- automatic champion analysis: optional if no champions, but explicit in summary
- automatic external/audit evaluation: skip with explicit reason if no champions or datasets

## Automatic vs Manual Workflows

### Automatic workflows

Required core workflow:

- one `multiseed_run`
- many `run_execution`
- zero or more `champion`
- one automatic `champion_analysis` over champions produced by that multiseed
- one automatic `champion_evaluation` for external, if applicable
- one automatic `champion_evaluation` for audit, if applicable

### Manual workflows

Still supported:

- manual cross-run champion analysis
- manual cross-config champion analysis
- manual champion reevaluation on custom datasets

These are secondary tools.
They must not be required for the canonical multiseed flow.

## Artifact Model

Artifacts remain useful, but should be treated as associated outputs, not the primary source of truth.

Recommended principle:

- structured DB rows store identity, filtering metadata, and summarized payloads
- artifact files store human-readable or export-heavy outputs

Artifacts should always be associated back to:

- one `multiseed_run`
- one `champion_analysis`
- one `champion_evaluation`
- optionally one `run_execution`

Concrete implementation decision:

- artifact paths are stored as repo-relative text paths

## Storage Guidance: Structured Columns vs JSON

Use structured columns for:

- ids and foreign keys
- hashes and fingerprints
- logic version
- timestamps
- config_name
- seed
- dataset catalog id
- dataset signature
- status
- champion_type
- artifact paths

Use JSON for:

- full config snapshots
- full genome snapshots
- full metric snapshots
- selection scopes
- summarized analysis payloads
- optional environment snapshots

Do not rely only on blobs for fields that must be filtered or indexed frequently.

Concrete implementation decisions:

- timestamps are stored as ISO-8601 UTC text
- `config_hash` uses SHA-256 hex
- `genome_hash` uses SHA-256 hex
- `execution_fingerprint` uses SHA-256 hex

## Required Query Capabilities

The redesigned model should support these queries cleanly:

- all `run_execution` rows belonging to one `multiseed_run`
- all champions from one `multiseed_run`
- all champions from one `config_name`
- all champions from one `logic_version`
- all reusable `run_execution` rows matching a fingerprint
- all automatic external evaluations for one `multiseed_run`
- manual analysis over arbitrary selected champion sets

## Suggested Minimal Indexes

For later implementation, likely indexes include:

- `run_execution(execution_fingerprint)`
- `run_execution(run_id)`
- `run_execution(config_hash)`
- `run_execution(logic_version)`
- `champion(run_execution_id)`
- `champion(run_id)`
- `champion(champion_type)`
- `champion(config_hash)`
- `champion(logic_version)`
- `champion_analysis(multiseed_run_id)`
- `champion_evaluation(multiseed_run_id)`

## Open Decisions

These are intentionally deferred:

1. Whether some summary JSON fields should later be normalized further.
2. Whether `run_execution` reuse should be silent, explicit, or operator-controlled.
3. Whether `dataset_context_json` should store all dataset paths or only a signature plus counts.
4. Whether `logic_version` should remain a simple string like `v1` or evolve into a richer compatibility token.

## Recommended Next Refactor Order

When implementation starts later, a reasonable order is:

1. Define new schema.
2. Implement `logic_version` and execution fingerprint generation.
3. Refactor `run_execution` persistence around config snapshots.
4. Refactor champion persistence to become self-contained.
5. Refactor automatic post-multiseed analysis/evaluation persistence.
6. Refactor manual analysis and reevaluation tools to use the new model.

## Summary

The target persistence model is:

- `multiseed_run` as top-level campaign
- `run_execution` as deduplicable executed unit
- `champion` as fully self-contained persisted result
- `champion_analysis` as persisted analysis over champion sets
- `champion_evaluation` as persisted reevaluation over chosen dataset sets

The key invariants are:

- persist config snapshots
- persist dataset identity
- persist logic version
- derive execution fingerprint from real execution identity
- keep champions reevaluable without filesystem config dependency
