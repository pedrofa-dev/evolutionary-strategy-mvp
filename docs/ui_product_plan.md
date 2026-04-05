# UI Product Plan

## Purpose

The UI exists to reduce operational friction around the canonical research
workflow without creating a second backend, a second source of truth, or a
parallel experimentation model.

Its role is to make the lab easier to operate and inspect:

- prepare and review canonical run inputs without depending so heavily on
  manual file editing
- launch canonical execution entrypoints more comfortably
- inspect persisted runs, champions, analyses, and reevaluations from the
  canonical SQLite store
- make reporting and comparison easier to navigate
- support future builders for declarative experimental assets

The UI should remain a convenience and exploration layer over the existing
system, not a replacement for the canonical workflow.

## Canonical Workflow Alignment

The UI must stay aligned with the existing repo workflow:

1. datasets are built from manifest catalogs
2. active run configs live under `configs/runs/`
3. experiment execution is multiseed
4. persistence is the canonical SQLite model in `data/evolution_v2.db`
5. reporting, analysis, and reevaluation are read from that canonical
   persistence and artifact stack

That means the UI should not invent:

- an alternative dataset selection model
- a second run-definition storage model
- a custom execution engine
- a separate reporting database
- UI-only experiment semantics

## Design Principles

### UI As An Operational Layer, Not A Second Backend

The UI should orchestrate and inspect the canonical system. It should not
reimplement core experiment logic in frontend code.

### Canonical Workflow First

If the CLI workflow says “build datasets, place configs under `configs/runs/`,
run multiseed, inspect persisted results”, the UI should make that easier, not
invent a different sequence.

### Persistence Boundary Respected

The canonical database and persisted artifacts remain the source of truth for
historical runs, champions, analyses, and reevaluations.

### Low-Friction Interaction

The UI should reduce manual friction, not replace evidence discipline with
convenience shortcuts.

### Advanced Complexity Hidden By Default

Most users should not need to see internal adapters, compatibility seams,
legacy entries, or raw debug data unless they explicitly opt into advanced
inspection.

### Decision-Oriented Analysis Over Raw Clutter

The UI should prefer helping users answer:

- what was run
- what won
- why it is interesting or not
- what should be done next

rather than overwhelming them with every internal artifact at once.

## Phased UI Roadmap

### Phase 1: Run Lab

Primary goal:
- make the canonical execution workflow easier to operate

Main surfaces:
- dataset catalog selection and visibility
- active run config inspection
- multiseed launch controls
- preset selection
- execution status and artifact links

### Phase 2: Runs And Results

Primary goal:
- make persisted history readable from the canonical SQLite model

Main surfaces:
- campaign list
- run executions
- champions
- analysis summaries
- reevaluation summaries
- comparison views

### Phase 3: Builders

Primary goal:
- make structured experimental composition easier without replacing runtime
  code boundaries

Main surfaces:
- signal pack builder
- genome schema builder
- mutation profile builder
- run config builder
- reusable preset builder

### Phase 4: Advanced Analysis, Comparison, And Saved Workflows

Primary goal:
- support heavier research workflows on top of canonical persistence and
  reporting

Main surfaces:
- side-by-side campaign comparison
- champion lineage and reevaluation history
- reusable filtered views
- saved investigator workflows

## Run Lab Vision

The Run Lab should be the first serious operational UI surface.

### Problem It Solves

Today the canonical workflow is disciplined, but still file-heavy:

- build datasets from manifests
- prepare configs under `configs/runs/`
- choose a multiseed preset
- launch execution
- read outputs from persistence and artifacts

Run Lab should reduce the friction of that flow without bypassing it.

### Inputs It Needs

The Run Lab should expose, at minimum:

- available dataset catalogs
- active run configs under `configs/runs/`
- canonical multiseed presets
- selected runtime metadata already represented in run configs
- execution destination and artifact context when useful

### What It Should Simplify

The Run Lab should default and constrain aggressively where the canonical
workflow is already opinionated.

It should:

- prefer active configs under `configs/runs/`
- surface canonical presets clearly
- show dataset catalog identity explicitly
- block obviously invalid or incomplete launch attempts
- avoid presenting legacy or deprecated config lanes as normal choices

### What It Should Keep Editable

The UI should still allow controlled editing where the existing workflow
expects real investigator choice, for example:

- selecting which active configs participate in a campaign
- selecting canonical runtime preset
- choosing worker counts or similar execution knobs
- reviewing the effective config snapshot before launch

### What It Should Not Invent

The Run Lab should not:

- create a second persistent config format
- bypass run config snapshots
- store UI-only presets as if they were canonical configs
- hide execution identity from the user

### How It Should Launch Execution

The Run Lab should eventually call the same canonical execution lane already
used by the repository:

- active configs from `configs/runs/`
- multiseed execution
- canonical persistence through `PersistenceStore`
- canonical reporting and post-run analysis

That means a UI-triggered run should still produce the same run records,
artifacts, and summaries as the existing scripts.

## Results Vision

The UI should read results from canonical persistence first, not from ad hoc
frontend state or local caches.

### Primary Result Surfaces

- campaigns from `multiseed_runs`
- run executions from `run_executions`
- champions
- persisted analyses
- persisted reevaluations

### What The UI Should Make Easy

- find a campaign quickly
- understand which configs and seeds were executed
- inspect champion selection outcomes
- inspect automatic external and audit reevaluation outcomes
- compare campaigns and champions without manual artifact hunting

### Reporting Relationship

The UI should complement canonical reporting rather than replace it.

It should help users navigate:

- quick summaries
- decision-oriented analysis
- reevaluation outcomes
- relevant artifact paths when deeper inspection is needed

## Builders Vision

Builders should arrive later and stay grounded in the actual experimental-space
model already present in the repo.

### Signal Pack Builder

Should help compose declarative signal packs without pretending signals are
fully backend-defined product objects yet.

### Genome Schema Builder

Should expose structural composition and compatibility in a guided way, while
respecting the current runtime-first source of truth.

### Mutation Profile Builder

Should help create readable declarative mutation profiles without exposing raw
mutation implementation complexity by default.

### Run Config Builder

Should help generate canonical run configs that still live in the normal repo
flow, not in a hidden UI database.

### Reusable Preset Builder

Should eventually help define reusable experiment presets, while remaining
explicit about the current ambiguity between:

- runtime execution-budget presets
- declarative composition presets

## Non-Goals

This UI plan does not aim to:

- redesign scoring or evaluator logic
- replace the canonical scripts as the methodological authority
- turn the UI into a second experiment runtime
- move the whole system to declarative runtime execution
- create a trading product or trading operations dashboard
- replace canonical persistence with frontend-owned state
- hide research uncertainty behind a polished product veneer

## Open Questions

The following questions are still live and should stay explicit:

- whether `decision_policies` and `policy_engines` should eventually be merged,
  grouped, or shown differently in the UI
- whether `experiment_presets` should remain mixed or be split into runtime
  presets versus declarative composition presets
- which internal, compatibility, or example catalog entries should eventually
  move to an advanced view
- how much direct editing should be allowed versus guided generation
- how much of the reporting stack should be rendered directly in UI versus
  linked as persisted artifacts
- when the UI should expose raw persisted JSON versus curated summary views

## Practical Implication

The UI should make the canonical lab easier to operate, easier to inspect, and
easier to learn, while still preserving the discipline of the existing
research workflow.

If a future UI change would make the system easier to click but harder to
reason about, the canonical workflow should win.
