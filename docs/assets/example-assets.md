# Example Assets

## Asset Design Principles

Assets must be small and easy to read.

The intended rules are:

- each asset should represent one clear responsibility
- an asset should describe one concrete composition, not a general-purpose
  execution language
- assets should describe composition and parameters, not runtime logic
- an asset should be understandable by reading the file alone
- complex logic must remain in code plugins
- if an asset becomes complex, it should be split or moved to code

These principles matter more than flexibility in this phase. The goal is to
create inspectable building blocks that a future UI can present safely.

## Examples

This phase adds a first minimal set of example assets under
`src/evo_system/experimental_space/assets/`.

### Signal pack

File:

- `src/evo_system/experimental_space/assets/signal_packs/core_policy_v21_signals_v1.json`

Purpose:

- describe a small named bundle of signal identifiers
- show optional `params`
- show optional `alias`

Fields:

- `id`: stable asset identifier
- `signals`: ordered signal descriptors
- `signal_id`: stable signal/plugin-facing identifier
- `params`: small configuration object for that signal
- `alias`: optional UI-friendly local alias

### Genome schema

File:

- `src/evo_system/experimental_space/assets/genome_schemas/modular_policy_v2_schema_v1.json`

Purpose:

- describe the structural modules that make up a schema

Fields:

- `id`: stable schema asset identifier
- `modules`: ordered schema modules
- `name`: module/slot name
- `gene_type`: gene type expected in that slot
- `required`: whether the slot is mandatory

### Decision policy

File:

- `src/evo_system/experimental_space/assets/decision_policies/weighted_policy_v2_v1.json`

Purpose:

- describe a policy composition that still relies on a code engine

Fields:

- `id`: stable policy asset identifier
- `engine`: code engine name that would interpret the asset later
- `entry`: entry-side composition metadata
- `exit`: exit-side composition metadata
- `trigger_gene`: gene module providing entry threshold logic
- `signals`: simple signal-to-weight mappings
- `policy_gene`: gene module providing exit policy thresholds
- `trade_control_gene`: gene module providing holding/cooldown behavior

### Mutation profile

File:

- `src/evo_system/experimental_space/assets/mutation_profiles/balanced_runtime_profile_v1.json`

Purpose:

- describe a small preset aligned with the current runtime mutation profile

Fields:

- `id`: stable profile identifier
- `profile`: payload matching the current built-in runtime mutation fields

### Experiment preset

File:

- `src/evo_system/experimental_space/assets/experiment_presets/btc_1h_probe_v1.json`

Purpose:

- compose the other assets into one named experiment setup

Fields:

- `id`: stable preset identifier
- `signal_pack`
- `genome_schema`
- `decision_policy`
- `mutation_profile`
- `dataset`: small descriptive dataset stub for future UI use

## How A Future UI Would Use These

A future UI could:

- list available asset ids without importing runtime code
- show human-readable composition of a preset
- verify that a preset references existing assets
- let a user inspect schema modules, signal bundles, and mutation presets

The UI should treat these assets as inspectable metadata, not as executable
runtime definitions.

## Current Limits

- assets do not control the runtime yet
- assets coexist with the current built-in system
- assets do not replace existing run configs
- decision policy assets still rely on code engines
- schema and signal assets are descriptive examples, not active runtime
  authorities yet
