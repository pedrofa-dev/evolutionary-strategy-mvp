# Contributor Guidelines

This document is for maintainers, contributors, and coding agents working inside the repository.

## Core Constraints

- do not treat this repository as a finished trading product
- do not overclaim what the evidence supports
- keep evaluation as the source of truth
- validation matters more than isolated optimization
- external and audit must remain outside the optimization loop
- one substantial experimental change at a time is preferred
- a missing validation layer is not the same as a failed strategy
- a good single seed is not a strong conclusion
- prefer clarity over cleverness
- keep documentation aligned with the actual code, not with plans

## Documentation Rules

- prefer one canonical explanation over several overlapping notes
- if a document is obsolete, remove or archive it
- if a document is operational and current, keep it close to the active workflow
- do not preserve outdated execution paths "just in case"
- use English for documentation and code comments
- do not add a new top-level guide unless the existing canonical docs clearly cannot absorb the topic

## Reporting Rules

- optimize for decision usefulness first
- keep deep diagnostics available, but move them under `debug/`
- avoid wording that sounds stronger than the evidence
- be explicit about `NOT_RUN`, missing datasets, and fallback resolution
- keep missing data separate from failed-strategy conclusions

## Dataset And Validation Rules

- preserve the manifest/catalog model
- do not blur train, validation, external, and audit roles
- document any new dataset-layer behavior in the dataset rules doc
- if a resolution path changes, update both runtime help and documentation

## Persistence Rules

- treat persisted snapshots as the stable source of truth
- avoid reintroducing dependence on config files remaining on disk
- keep fingerprint semantics strict
- bump `logic_version` intentionally when compatibility changes

## Before Merging

- README still matches the actual public workflow
- the canonical docs still point to the right commands and artifact names
- no obsolete execution mode references remain
- no stale "legacy" guidance survives by accident
- tests still reflect the canonical workflow rather than historical ones

## Known Terminology Debt

- `historical_run` remains an internal module name even though the canonical execution workflow is multiseed. Treat this as naming debt, not as a prompt to rename it casually.
- Some code and artifacts may still say "post-run external validation" where the canonical workflow meaning is now "post-multiseed validation". Treat this as terminology debt and normalize wording when touching related docs or help text.

Do not rename modules, files, or commands in routine documentation-only changes.
