# Gene Catalog And Genome Schema

## Objective

Clarify the separation between:

- signals
- genes
- genome schemas
- structural metadata
- runtime behavior

This phase does not change the active runtime semantics. It only makes the
structural side of the genome model easier to describe, inspect, and eventually
expose to a future UI.

## What Is A Signal

A signal is a normalized runtime input derived from market data.

Examples in the current architecture:

- raw derived features inside a `SignalPack`
- aggregated signal families consumed by genes and decision logic

Signals belong to runtime data interpretation, not to genome structure.

## What Is A Gene

A gene is a persisted configuration block that parameterizes behavior.

In the current policy-v2 lane, genes include blocks such as:

- entry context
- entry trigger
- exit policy
- trade control

Genes are configuration payloads. They are not the same thing as raw signals.

## What Is A Genome Schema

A genome schema defines how genes are composed into a valid genome shape.

It answers questions like:

- which modules exist
- what schema-level fields exist
- how those pieces combine into a canonical genome object

The schema is structural. It should not become a second home for evaluator or
decision semantics.

## What Role Does `GeneTypeCatalog` Play

`GeneTypeCatalog` is the structural metadata layer for gene-owned modules.

It currently provides:

- gene block names
- field-level mutation metadata
- schema-level structural fields
- structural normalization hooks
- genome assembly hooks already used by the runtime

This phase adds explicit descriptive DTOs so the same catalog can also expose:

- `GeneTypeDefinition`
- `GenomeSchemaSlot`
- `StructuralCompatibility`

These are descriptive metadata only. They do not replace the current runtime.

## What Role Does `GenomeSchema` Play

`GenomeSchema` is the structural composition contract for a valid genome.

In the current runtime it still owns questions such as:

- which modules belong to the schema
- how default modules are built
- how schema fields and gene blocks assemble into a valid `Genome`
- whether a concrete genome instance belongs to the schema

`GenomeSchema` should stay structural. It must not become a second home for:

- decision semantics
- signal semantics
- evaluator logic
- scoring logic

`GenomeSchemaSlot` is a derived descriptive view of schema composition, useful
for inspection and future UI work. In the current lane, every active slot is a
required single-instance gene block, so `required=true` and cardinality `1..1`
are explicit in the DTO even though the runtime still enforces the shape
through built-in code.

## Source Of Truth And Temporary Compatibility

### Current source of truth

The current structural source of truth is still the built-in runtime pair:

- `GeneTypeCatalog`
- `GenomeSchema`

More concretely:

- `GeneTypeCatalog` owns structural metadata about gene-owned blocks, schema
  fields, normalization hooks, and genome assembly hooks
- `GenomeSchema` owns the schema identity and valid composition contract for a
  runtime genome

### Derived compatibility views

The following dataclasses are currently derived views, not independent sources
of truth:

- `GeneTypeDefinition`
- `GenomeSchemaSlot`
- `StructuralCompatibility`

They exist to make the current runtime structure easier to inspect, serialize,
document, and eventually expose in a UI or declarative asset layer.

### Temporary compatibility reality

Today the codebase still contains a mix of:

- runtime-first built-in classes and helpers
- descriptive DTOs layered on top of them

That is intentional for now. The DTOs clarify the target structure without
forcing a risky migration of the active runtime semantics.

## Structural Metadata Vs Runtime

### Structural / metadata side

- field names
- slot/module names
- required/optional slot intent
- slot cardinality
- schema field names
- builder labels
- compatibility descriptions
- serializable metadata for future UI or assets

### Runtime side

- actual gene classes
- genome validation
- mutation execution
- decision-policy logic
- evaluator/scoring behavior

The runtime still uses the existing built-in classes and mutation engine.

## Why This Helps A Future UI

A future UI for experimental composition will need to answer questions like:

- which genome modules exist
- which fields belong to each module
- which fields are schema-level
- which schema and gene catalog are structurally compatible

These answers can now come from explicit metadata objects without forcing the
UI to inspect runtime mutation code or decision logic.

The future UI-facing representation should prefer the descriptive DTO layer:

- `GeneTypeDefinition`
- `GenomeSchemaSlot`
- `StructuralCompatibility`

rather than raw runtime callables or ad hoc dictionaries.

## What Has Not Changed Yet

- gene catalogs are not loaded from declarative assets yet
- genome schemas are not driven by declarative assets yet
- mutation still uses the current runtime catalog/schema path
- no scoring, evaluator, persistence, or champion behavior changed

This keeps the change small, reversible, and compatible with the current core.
