# Architecture

This document describes the current architecture of the repository.

It is a canonical reference for how the system is organized today.

## System Purpose

The repository is an evolutionary trading-research lab.

Its goal is to search for rule-based strategy parameterizations under disciplined validation, then persist and reevaluate the resulting champions without mixing those later validation layers back into optimization.

The system is not:

- an LLM trader
- a direct price predictor
- a production execution engine

## Stable Architectural Boundaries

The codebase is intentionally split into a small set of responsibilities:

- `src/evo_system/domain`
  - Core entities such as `Genome`, `Agent`, `AgentEvaluation`, and run summaries.
- `src/evo_system/environment`
  - Dataset loading and historical environment construction.
- `src/evo_system/evaluation`
  - Scoring, penalties, vetoes, and evaluation logic.
- `src/evo_system/champions`
  - Champion classification, comparison, persistence eligibility, and champion metrics.
- `src/evo_system/experimentation`
  - Historical execution, multiseed orchestration, dataset resolution, post-multiseed validation, and reevaluation helpers.
- `src/evo_system/reporting`
  - Champion loading, statistics, decision-oriented reporting, and manual analysis support.
- `src/evo_system/storage`
  - Canonical SQLite persistence for campaigns, executions, champions, analyses, and reevaluations.

## Canonical Execution Model

The repository now has one canonical experiment execution workflow:

1. Build curated datasets from a manifest catalog.
2. Run multiseed execution across the active configs directory.
3. Persist one `multiseed_run`.
4. Persist one `run_execution` per config and seed.
5. Persist at most one champion per completed run execution.
6. Run automatic post-multiseed analysis and reevaluation if champions exist.

There are no parallel public execution modes such as `single` or `batch`.

## Persistence Model

The canonical persistence backend is the redesigned SQLite model in `data/evolution_v2.db`.

It persists:

- `multiseed_runs`
- `run_executions`
- `champions`
- `champion_analyses`
- `champion_analysis_members`
- `champion_evaluations`
- `champion_evaluation_members`

Persistence design principles:

- executed config snapshots are persisted, not just config names
- champions are self-contained enough for later reevaluation
- reuse is governed by execution fingerprint plus `logic_version`
- artifacts are secondary outputs; evaluation and persistence remain the source of truth

See [Persistence Model](persistence_model.md).

## Dataset Resolution Model

The repository uses manifest/catalog datasets as the only canonical dataset workflow.

Run configs select datasets through `dataset_catalog_id`.

The runtime resolves curated datasets from:

- `dataset_root / dataset_catalog_id / train`
- `dataset_root / dataset_catalog_id / validation`

Automatic post-multiseed reevaluation resolves from the same catalog context by default:

- `dataset_root / dataset_catalog_id / external`
- `dataset_root / dataset_catalog_id / audit`

Explicit manual overrides remain supported for reevaluation workflows, but they are overrides rather than the default model.

## Research Discipline

These architectural rules are intentional:

- evaluation is the authority
- validation matters more than optimization
- external and audit validation must not influence training optimization
- missing evidence is different from negative evidence
- reporting should reduce ambiguity rather than create it

## Artifact Philosophy

Artifacts exist to support human inspection and downstream parsing, but they do not replace evaluation outputs or persisted snapshots.

The current multiseed reporting model has three levels:

- Level 1: quick summary
- Level 2: decision-oriented analysis
- Level 3: debug diagnostics

See [Reporting And Interpretation](reporting_and_interpretation.md).
