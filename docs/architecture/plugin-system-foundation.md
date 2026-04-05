# Plugin System Foundation

## Objective

Prepare the experimental-space core for a future plugin model without changing
the current runtime behavior, methodological semantics, or persistence flow.

The target direction is:

- closed core
- code plugins
- declarative assets

This phase only adds the smallest reusable foundation needed to support that
direction later.

## What Was Added

- A shared typed registry in
  `src/evo_system/experimental_space/registry.py`
  via `NamedRegistry`
- Minimal plugin-facing base protocols for:
  - signals:
    `src/evo_system/experimental_space/signals/base.py`
  - genes:
    `src/evo_system/experimental_space/genes/base.py`
  - policy engines:
    `src/evo_system/experimental_space/policy_engines/base.py`
- Unit tests for the registry behavior

## What Was Not Changed

- No runtime component was migrated to these plugin contracts yet.
- No evaluator, scoring, veto, persistence, champion, or reporting logic was
  changed.
- No plugin autodiscovery, asset loader, or external package loading was added.
- No current `SignalPack`, `GenomeSchema`, `DecisionPolicy`, or mutation flow
  was replaced.

This keeps the current system behavior fully intact while exposing future
extension seams.

## Why This Helps Future UI/API Work

Later API/UI layers will need a stable way to:

- list available experimental modules
- expose configurable module names
- validate externally selected modules
- keep the core as the source of truth for what is registered

The registry and base protocols provide that minimal internal boundary now, so
future work can register plugin-provided modules without reopening large core
refactors.

`NamedRegistry.list()` returns registered names in sorted order.
`NamedRegistry.list_names()` is kept as an explicit compatibility alias.

## Recommended Next Steps

1. Keep the current built-in components as the runtime default source of truth.
2. Introduce optional registration helpers for built-in modules to align core
   modules with the same plugin-facing contracts.
3. Add declarative metadata for plugins and assets only after the loading
   strategy is agreed.
4. Add plugin discovery/loading last, after the registration and validation
   boundaries are already stable.
