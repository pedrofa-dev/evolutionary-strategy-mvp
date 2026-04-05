# Run Lab Design Note

## Scope

Run Lab is the first operational UI surface above the current catalog browser.

Its purpose is not to redesign the experiment system. It exists to reduce
friction around the canonical workflow that already exists in the repository.

## Canonical Connection

Run Lab stays attached to the current workflow:

- dataset catalogs come from `configs/datasets/`
- saved run configs go to `configs/runs/`
- execution uses the canonical multiseed entrypoint
- persistence and reporting remain unchanged

The UI does not create a second persistence model, a second config format, or a
UI-only execution engine.

## Minimal Support Added

This phase adds only the smallest support layer needed to make Run Lab usable:

- dataset-catalog summaries for selection and review
- runtime strategy selectors for signal pack, genome schema, mutation profile,
  and decision policy
- runtime execution presets for multiseed budgeting
- canonical config save under `configs/runs/`
- save-and-execute support through the same `scripts/run_experiment.py`
  entrypoint already used by the CLI

## UX Simplifications

The first version deliberately makes a few conservative simplifications:

- `decision policy` is the primary decision-logic selector
- `policy engine` is shown only as secondary metadata when helpful
- runtime-selectable items are the main path
- example or future-facing catalog assets are treated as reference material,
  not as the main executable path
- a saved config is based on an existing active config template so Run Lab does
  not need to invent dozens of hidden numeric defaults

## Execution Behavior

`Save run config` writes the selected config to `configs/runs/`.

`Save and execute` then launches the canonical experiment script using a
temporary one-config execution directory. This keeps the saved config canonical
while avoiding accidental execution of every active config already present under
`configs/runs/`.

That tradeoff is intentional for this phase:

- canonical config save is preserved
- canonical execution codepath is preserved
- accidental broad execution is avoided

## What This Phase Does Not Solve

- no results view yet
- no live execution monitoring beyond basic launch metadata
- no builder-grade editing for advanced runtime internals
- no catalog taxonomy redesign
- no replacement of CLI authority
