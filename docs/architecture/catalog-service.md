# Catalog Service

## Objective

Provide one small internal read surface that exposes experimental-space modules
and declarative assets in a form that is easy to serialize and easy for a
future CLI, API, or UI to consume.

This service does not change runtime behavior. It only aggregates metadata that
already exists in registries, structural DTOs, and asset files.

## What The Catalog Exposes

The current `CatalogService` exposes:

- signal plugins
- policy engines
- gene type definitions
- signal packs
- genome schemas
- decision policies
- mutation profiles
- experiment presets

Each entry is returned as a small serializable record with fields such as:

- `id`
- `type`
- `origin`
- `file_path`
- `description`
- `payload`

## Why This Matters For Future UI

A future UI will need a stable place to ask questions like:

- which built-in modules exist
- which declarative assets exist
- which parts come from runtime code versus asset files
- which structural definitions can be shown to a user without executing the
  evaluator

The catalog service provides that boundary without forcing UI code to know
about registries, asset directories, or internal metadata helpers.

## Relationship To Traceability And Research Assets

The catalog is not a persistence or reporting replacement.

Instead, it complements those layers:

- persistence records what a run actually used
- reporting explains results and traceability after execution
- the catalog lists what the repo currently makes available for composition and
  inspection

That distinction matters for research workflows. A researcher or UI can inspect
available assets first, then choose what to run, and later compare that choice
with persisted run metadata.

## What It Does Not Do Yet

- it does not run experiments
- it does not resolve deep compatibility between assets
- it does not replace registries or the asset loader
- it does not provide HTTP endpoints
- it does not guarantee that every listed asset is runtime-operational today

## Design Notes

This catalog intentionally prioritizes clarity over completeness.

That means:

- categories may be empty when no real source exists yet
- `origin` is explicit so callers can distinguish runtime code, plugin-facing
  code, and declarative assets
- validation remains shallow here; deeper compatibility checks belong to later
  layers closer to composition or execution

This keeps the service safe and useful without turning it into a second runtime
or a hidden resolver layer.
