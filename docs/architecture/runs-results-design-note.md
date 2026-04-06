# Runs / Results Design Note

## Scope

This note captures the first narrow UI slice for persisted runs and research
results.

The goal is not to build a dashboard or a new analysis engine. The goal is to
make the canonical persisted workflow easier to inspect:

- multiseed campaigns
- champion selection results
- train, validation, and external evaluation summaries
- side by side campaign comparison

## Components Touched

- `src/application/runs_results/`
- `src/api/routes/runs_results.py`
- `src/api/main.py`
- `ui/web/src/services/runsResultsApi.ts`
- `ui/web/src/pages/ResultsPage.tsx`

## Canonical Workflow Alignment

The Runs / Results tab stays aligned with the current repository workflow:

1. Run Lab saves canonical configs under `configs/runs/`.
2. The canonical multiseed entrypoint executes those configs.
3. Results are persisted in SQLite and reporting artifacts.
4. The UI reads those persisted outputs without recalculating them.

This means the tab remains a read layer over canonical persistence rather than a
parallel execution or analytics path.

## UX Simplifications

The UI keeps a narrow shape on purpose:

- campaigns list first
- champion block visually dominant
- evaluation summary visible without opening raw artifacts
- multiseed behavior shown as a persisted execution list
- comparison only for user-selected campaigns

When persisted data is incomplete, the tab should prefer explicit absence over
fake precision. In practice this means labels such as:

- `Not persisted`
- `Not reevaluated`
- `No champion selected`
- `Incomplete`

Quick summary notes such as verdict, likely limit, and next action should be
presented as persisted reporting guidance from the quick summary artifact, not
as a new source of truth created by the UI or application layer.

Advanced details such as per-run execution rows stay secondary. The primary
question is still research decision quality:

- Is this robust?
- Does it depend on the seed?
- Does it generalize?

## Decision Policy vs Infrastructure

This tab does not re-open taxonomy cleanup. It reads the persisted campaign
surface as it exists today and presents it with the smallest useful amount of
structure.

## Explicit Non-Goals

- no score recomputation
- no re-evaluation
- no new persistence model
- no backend redesign
- no dashboard-style derived analytics
