# Run Lab Authoring V1 Plan

## Purpose

This document defines a conservative path for adding authoring flows to the UI
 without turning Run Lab into a giant universal editor.

The intent is to keep a clean separation between:

- operational UX: select, review, execute
- authoring UX: create reusable canonical components

Run Lab should remain the execution workspace. Authoring should appear as small,
 focused modal flows attached to the relevant selectors.

## Current Baseline

Today the repository already supports:

- runtime-backed registries for active execution components
- declarative asset loading for example experimental components
- a catalog surface that exposes runtime entries and declarative assets
- Run Lab for selecting existing components and launching canonical runs

This means the UI already has two important ingredients:

1. a read surface over component categories
2. a declarative file format for some component types

What it does not yet have is a canonical save path for authoring those
 declarative assets from the UI.

## Audit By Component Type

### Signal Packs

Current state:

- active runtime path is still registry-driven through `policy_v21_default`
- there is already a declarative asset example under
  `src/evo_system/experimental_space/assets/signal_packs/`
- the declarative shape is small and understandable:
  - `id`
  - `description`
  - `signals[]`
    - `signal_id`
    - optional `params`
    - optional `alias`

Assessment:

- good candidate for modal authoring now
- mostly declarative at the asset level
- still not the active runtime default, so new authored items should initially
  be treated as declarative assets for composition/reference, not as automatic
  replacements for the active runtime signal pack

Minimum editable fields that make sense:

- `id`
- `description`
- list of signals
- per-signal:
  - `signal_id`
  - optional alias
  - small JSON-ish key/value params block

Canonical persistence path:

- `src/evo_system/experimental_space/assets/signal_packs/<id>.json`

Main caution:

- available `signal_id` values are not yet served as a rich canonical signal
  catalog, so the first UI may need a plain text field or a conservative list
  derived from known examples/runtime names

### Genome Schemas

Current state:

- runtime remains centered on `policy_v2_default` and `modular_genome_v1`
- there is already a declarative asset example under
  `src/evo_system/experimental_space/assets/genome_schemas/`
- the declarative shape is structural and small:
  - `id`
  - `description`
  - `modules[]`
    - `name`
    - `gene_type`
    - `required`

Assessment:

- good candidate for modal authoring now
- declarative structure is clear
- still partly constrained by runtime compatibility, so authoring should be
  framed as creating declarative schemas for composition/reference first

Minimum editable fields that make sense:

- `id`
- `description`
- module list
- per module:
  - module name
  - gene type
  - required boolean

Canonical persistence path:

- `src/evo_system/experimental_space/assets/genome_schemas/<id>.json`

Main caution:

- gene type values should come from existing `gene_type_definitions`, not from
  free invention, if we want authored schemas to remain interpretable

### Mutation Profiles

Current state:

- active runtime path is still the compatibility-backed
  `default_runtime_profile`
- there is already a declarative asset example under
  `src/evo_system/experimental_space/assets/mutation_profiles/`
- the declarative shape is compact:
  - `id`
  - `description`
  - `profile`
    - `strong_mutation_probability`
    - `numeric_delta_scale`
    - `flag_flip_probability`
    - `weight_delta`
    - `window_step_mode`

Assessment:

- strongest candidate for modal authoring now
- most compact and constrained declarative shape of the group
- easiest to validate clearly

Minimum editable fields that make sense:

- `id`
- `description`
- the five profile fields already required by the asset validator

Canonical persistence path:

- `src/evo_system/experimental_space/assets/mutation_profiles/<id>.json`

Main caution:

- the current active runtime still uses the adapter-backed runtime profile, so
  new authored mutation assets should initially be selectable only where the
  system already treats asset-backed entries as safe and explicit

### Decision Policies

Current state:

- active runtime policy is `policy_v2_default`
- active runtime engine is `policy_v2_default_engine`
- there is a declarative example under
  `src/evo_system/experimental_space/assets/decision_policies/`
- the declarative shape already references engine-level concepts:
  - `engine`
  - `entry`
  - `exit`
  - signal-to-gene-field mappings

Assessment:

- not the best candidate for authoring v1
- still too runtime-shaped
- too easy to imply that the UI is authoring executable decision behavior when
  the current system still treats this area as more sensitive and engine-bound

Minimum editable fields that would be needed eventually:

- `id`
- `description`
- engine
- trigger gene
- signal mappings
- exit policy gene
- trade control gene

Canonical persistence path:

- `src/evo_system/experimental_space/assets/decision_policies/<id>.json`

Reason to defer:

- the UI should not make `policy_engine` a main operator concept
- policy authoring needs a better canonical story for engine compatibility and
  allowed field mappings before it becomes a safe modal builder

## Recommended Phase Order

### Phase A

Add focused modal authoring for:

- mutation profile
- signal pack
- genome schema

Recommended internal order:

1. mutation profile
2. signal pack
3. genome schema

Why this order:

- mutation profile has the smallest and safest form surface
- signal pack is still small, but depends on signal naming choices
- genome schema is structurally clear, but should ideally reuse known gene
  types rather than allowing arbitrary names

### Phase B

Add cautious authoring for:

- decision policy

Only after:

- engine compatibility rules are clearer
- the UI can guide allowed mappings without pretending to author runtime logic

### Deferred

Keep dataset authoring out of this pass.

Reason:

- dataset work is larger and lives closer to manifest/catalog construction than
  to Run Lab execution composition
- it deserves its own workflow rather than being squeezed into the same modal
  pattern

## Authoring UX Pattern

For each supported Run Lab selector:

- keep the existing selector for current items
- add a small `New` button beside it
- open a focused modal for that component type

On successful save:

1. persist the new asset canonically
2. refresh the Run Lab bootstrap/options
3. auto-select the newly created item
4. keep the user inside Run Lab

This preserves Run Lab as:

- select
- review
- execute

while still giving the operator a low-friction path to create missing pieces.

## Canonical Save Rules

Authoring must not be UI-only.

The canonical integrity rules should live in the application/backend save path:

- `id` is required
- asset payload must pass the existing validator for that asset type
- same `id` and identical canonical content may be treated as safe reuse
- same `id` with different content must be rejected clearly
- file name should be normalized to `<id>.json`

This should mirror the same integrity philosophy already used for run config
 collision handling.

## Suggested Application/API Shape

Keep the addition narrow.

Recommended application service:

- `application.authoring.service` or
- `application.run_lab_authoring.service`

Responsibilities:

- build canonical asset payloads
- validate against the existing declarative asset rules
- write canonical asset files
- expose refreshed option snapshots back to Run Lab

Recommended initial endpoints:

- `POST /run-lab/authoring/mutation-profiles`
- `POST /run-lab/authoring/signal-packs`
- `POST /run-lab/authoring/genome-schemas`

Return shape should stay small:

- saved asset id
- file path
- payload
- refreshed Run Lab option category if convenient

## Modal Scope Guidance

The first authoring modals should stay intentionally small.

### Mutation Profile Modal

Good first implementation because it can be a simple structured form with a few
 numeric fields and one mode string.

### Signal Pack Modal

Should support adding/removing signal rows, but avoid turning row params into a
 mini language.

### Genome Schema Modal

Should support adding/removing module rows and choosing from known gene types.
Avoid exposing deep compatibility logic in v1.

## Non-Goals For Authoring V1

This phase should not:

- turn Run Lab into a full-page builder studio
- make decision policy authoring look runtime-complete before it is
- introduce dataset authoring into the same flow
- bypass canonical asset validation
- create UI-only drafts that masquerade as persisted assets
- resolve every compatibility question in the UI

## Recommended First Implementation

If only one authoring flow is implemented first, it should be:

- mutation profile modal authoring

Why:

- small payload
- strong validator already exists
- low ambiguity
- high value as the first reusable authored component

Signal pack should be next, then genome schema.
