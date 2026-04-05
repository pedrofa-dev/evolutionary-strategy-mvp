# Catalog Audit And Clarification

## Purpose

This document records what the current experimental catalog actually exposes,
how each category should be interpreted, and which items are active,
transitional, example-only, or still unclear.

The goal of this phase is clarification, not cleanup by force. If an item
cannot be classified safely from the current codebase, it should stay visible
as `unknown` or `needs manual review` rather than receiving an invented story.

## Scope

This audit covers the current catalog surfaced through:

- `experimental_space.catalog_service`
- the application catalog layer
- the minimal HTTP catalog API
- the minimal React catalog UI

It does not change the methodological core or runtime semantics.

## Conservative Cleanup Applied

This audit led to a small cleanup pass, not a redesign.

Removed:

- dead alias `CurrentPolicyV21SignalPack`
- dead alias `CurrentPolicyV2DecisionPolicy`

Renamed for clarity:

- `CurrentPolicyV2GenomeSchema` -> `PolicyV2CompatibilityGenomeSchema`
- `CurrentMutationProfileDefinition` -> `RuntimeMutationProfileAdapter`

Clarified:

- declarative example assets now include explicit descriptions so they no
  longer appear as unexplained `asset` entries with missing context

## Category-Level Clarification

### `signal_plugins`

What it represents:
- Python code plugins that would provide signal-related behavior.

How it differs from `signal_packs`:
- `signal_plugins` are code extension points.
- `signal_packs` are named bundles of signal definitions or signal metadata.

Current role:
- The category exists as part of the future plugin model.
- It is currently empty in the live catalog.

Current interpretation:
- Empty is expected.
- This is a future-facing category, not a broken runtime lane.

### `signal_packs`

What it represents:
- Bundles of signals or signal-family metadata consumed by strategies.

How it differs from `signal_plugins`:
- A signal pack describes which signals are used together.
- A signal plugin would implement signal-side behavior in code.

Current role:
- Runtime signal packs are part of the active execution model.
- Declarative signal-pack assets are examples and future UI-facing compositions.

### `policy_engines`

What it represents:
- Code engines that build or provide runtime decision policies.

How it differs from `decision_policies`:
- `policy_engines` live in code and own how a runtime policy is constructed.
- `decision_policies` are the runtime contract that the environment actually
  consumes.

Current role:
- This is a compatibility seam introduced to separate code-side policy
  construction from future declarative policy definitions.

### `decision_policies`

What it represents:
- Named policies that decide entry and exit behavior at runtime, or declarative
  policy definitions that point toward those runtime semantics.

How it differs from `policy_engines`:
- Engines build policies.
- Policies are what the environment uses.

Current role:
- The runtime default policy is active and canonical.
- Declarative decision-policy assets are examples and future-facing metadata,
  not the main runtime source of truth yet.

### `genome_schemas`

What it represents:
- Structural definitions of how a valid genome is composed.

How it differs from `gene_type_definitions`:
- `gene_type_definitions` describe individual gene/module blocks.
- `genome_schemas` describe how those blocks fit together as a whole.

Current role:
- Runtime schemas remain the active structural contract.
- Declarative schema assets are examples and future-facing structural metadata.

### `mutation_profiles`

What it represents:
- Named mutation behavior definitions or references to mutation settings.

How it differs from `experiment_presets`:
- A mutation profile shapes search perturbation behavior.
- An experiment preset composes several assets plus dataset context.

Current role:
- The runtime default mutation profile is still an adapter over the active
  dataclass-based runtime settings.
- Declarative mutation profiles are examples, not yet the execution default.

### `experiment_presets`

What it represents:
- Named experiment starting points.

How it differs from runtime multiseed presets:
- Declarative preset assets compose signal pack, genome schema, decision
  policy, mutation profile, and dataset metadata.
- Runtime presets such as `quick` or `full` are execution-budget helpers for
  generations and seed counts.

Current role:
- This category currently mixes two related but different things:
  - runtime execution-budget presets
  - declarative composition presets

Current interpretation:
- That mixture is intentional for now, but it should likely be split or tagged
  more clearly in a future cleanup phase.

## Origin Clarification

### `origin = "runtime"`

Meaning:
- The item is produced from active runtime code or runtime registries.

Important nuance:
- `runtime` does not automatically mean “user-facing canonical”.
- Some runtime items are active.
- Some runtime items are adapters kept for compatibility.
- Some runtime items are internal helpers that happen to be exposed today.

### `origin = "asset"`

Meaning:
- The item comes from a declarative JSON asset on disk.

Important nuance:
- Asset origin does not automatically mean the item is active in execution.
- In the current phase, many asset entries are examples or future-facing
  compositions.

### `origin = "plugin"`

Meaning:
- The item comes from code registered as a plugin-style extension point.

Important nuance:
- In the current catalog, `policy_v2_default_engine` is exposed this way even
  though it is a built-in code engine, not an externally discovered third-party
  plugin.

## Payload `null`

Observed case:
- `policy_v2_default_engine` previously appeared with `payload = null`.

Interpretation:
- That was not a runtime bug, but it was an exposure gap.
- The engine was visible but did not tell the UI what it actually provided.

Current improvement:
- The catalog now exposes a small payload for policy engines:
  - `name`
  - `builds_decision_policy`

This keeps the change small while making the item understandable.

## Item Classification

The following classifications use these meanings:

- `active`: actively part of the current supported runtime lane
- `legacy`: kept mainly for backward continuity with older naming or shape
- `adapter`: transitional bridge between old and new architecture layers
- `example`: intentionally illustrative, not the main runtime source of truth
- `internal`: useful for system internals or advanced inspection, not ideal as
  a default UI-facing concept
- `unknown`: not safely classifiable from current evidence alone

### Policy Engines And Decision Policies

#### `policy_v2_default_engine`

- classification: `adapter`, `internal`, `active`
- used now: yes
- role now: built-in code seam that constructs the canonical runtime decision
  policy
- should stay visible in normal UI: probably only in advanced/internal views

#### `policy_v2_default`

- classification: `active`
- used now: yes
- role now: canonical runtime decision policy actually consumed by the
  environment
- should stay visible in normal UI: yes

#### `weighted_policy_v2_v1`

- classification: `example`
- used now: not as the main runtime decision policy
- role now: declarative example showing how a policy asset can point at a code
  engine
- should stay visible in normal UI: yes, but clearly marked as example or asset

### Experiment Presets

#### `btc_1h_probe_v1`

- classification: `example`
- used now: only if explicitly selected in future-facing asset flows
- role now: declarative composition example for UI/API/catalog exploration
- should stay visible in normal UI: yes

#### `quick`

- classification: `active`, `internal`
- used now: yes
- role now: runtime execution-budget preset for very fast iteration
- should stay visible in normal UI: yes, but clearly described as runtime preset

#### `screening`

- classification: `active`, `internal`
- used now: yes
- role now: runtime execution-budget preset for lightweight candidate screening
- should stay visible in normal UI: yes, but clearly described as runtime preset

#### `standard`

- classification: `active`, `internal`
- used now: yes
- role now: balanced runtime execution-budget preset
- should stay visible in normal UI: yes, but clearly described as runtime preset

#### `extended`

- classification: `active`, `internal`
- used now: yes
- role now: broader runtime execution-budget preset before promotion
- should stay visible in normal UI: yes, but clearly described as runtime preset

#### `full`

- classification: `active`, `internal`
- used now: yes
- role now: heaviest built-in runtime execution-budget preset
- should stay visible in normal UI: yes, but clearly described as runtime preset

### Genome Schemas

#### `policy_v2_default`

- classification: `adapter`, `legacy`, `active`
- used now: yes
- role now: compatibility adapter over the current block-based genome builder
- should stay visible in normal UI: advanced/internal view preferred

#### `modular_genome_v1`

- classification: `active`
- used now: available in the modular lane
- role now: explicit runtime schema for the active modular block layout
- should stay visible in normal UI: yes

#### `modular_policy_v2_schema_v1`

- classification: `example`
- used now: not as the main runtime schema source of truth
- role now: declarative schema example aligned with the active block layout
- should stay visible in normal UI: yes, as example/asset

### Mutation Profiles

#### `default_runtime_profile`

- classification: `adapter`, `active`
- used now: yes
- role now: resolves the current runtime mutation profile dataclass
- should stay visible in normal UI: advanced/internal view preferred

#### `balanced_runtime_profile_v1`

- classification: `example`
- used now: only as declarative example
- role now: shows how a mutation profile asset could be described
- should stay visible in normal UI: yes, if marked as asset/example

### Signal Packs

#### `policy_v21_default`

- classification: `active`
- used now: yes
- role now: canonical active runtime signal pack
- should stay visible in normal UI: yes

#### `core_policy_v21_signals_v1`

- classification: `example`
- used now: not as the active runtime signal pack
- role now: declarative example of a signal-pack asset aligned with the current
  signal vocabulary
- should stay visible in normal UI: yes, if marked as asset/example

### Signal Plugins

#### current category state

- classification: `unknown` for specific items because there are no items
- used now: no concrete plugin entries are currently exposed
- role now: reserved category for future plugin discovery
- should stay visible in normal UI: yes, but empty state should explain that
  this is future-facing rather than broken

## Recommendations

### Keep Visible

- `policy_v2_default`
- `modular_genome_v1`
- `policy_v21_default`
- declarative example assets such as `weighted_policy_v2_v1`,
  `modular_policy_v2_schema_v1`, `balanced_runtime_profile_v1`,
  `core_policy_v21_signals_v1`, `btc_1h_probe_v1`
- runtime presets such as `quick`, `screening`, `standard`, `extended`, `full`
  if clearly labeled as runtime presets

### Mark More Clearly

- `policy_v2_default_engine` as internal/adapter
- `policy_v2_default` genome schema as legacy adapter
- `default_runtime_profile` as runtime adapter
- the difference between composition presets and runtime budget presets inside
  `experiment_presets`

### Likely Better In Advanced/Internal UI

- `policy_v2_default_engine`
- `policy_v2_default` genome schema
- `default_runtime_profile`

### Refactor Later

- split or tag `experiment_presets` so runtime budget presets and declarative
  composition presets are not visually mixed without explanation
- classify catalog entries explicitly in backend metadata rather than only in
  audit docs
- decide whether built-in code engines should keep `origin = "plugin"` or gain
  a more precise distinction later
- decide whether empty future-facing categories such as `signal_plugins` should
  remain always visible or move behind an advanced toggle

## Current Limits

This audit improves clarity, but some questions remain intentionally unresolved:

- no explicit backend field yet says `active`, `legacy`, `adapter`, or `example`
- UI explanations still rely partly on frontend-side wording
- some classifications remain architectural judgments rather than formal system
  metadata
- the catalog still prefers exposure continuity over a perfectly curated
  product-facing taxonomy
