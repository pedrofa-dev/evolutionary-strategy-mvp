# Plugin And Asset Loading

## Objective

Add a minimal, explicit loading boundary for future experimental-space plugins
and declarative assets without changing the current runtime behavior.

This phase is intentionally small:

- Python plugins are loaded explicitly by module name
- declarative assets are loaded explicitly from disk
- the current runtime does not consume them yet

## Plugin Vs Asset

### Plugins

Plugins are Python code modules. They are the right place for behavior that
cannot be expressed safely as plain data, such as:

- signal-pack construction logic
- decision-policy engines
- future gene-type builders or validators

A **signal plugin** is therefore executable code that can build or register a
signal implementation.

### Assets

Assets are declarative files stored on disk. They are the right place for
stable configuration-like definitions such as:

- named signal-pack descriptors
- gene catalog metadata
- genome schema descriptors
- mutation profile presets
- experiment presets

A **signal pack asset** is therefore data describing a named signal-pack
definition or metadata layer, not executable signal logic by itself.

## Asset Design Principles

Declarative assets should stay small, focused, and readable.

The intended design principles are:

- one asset should represent one clear responsibility or one concrete
  composition
- an asset should be understandable by reading the file itself, without having
  to reverse-engineer a large amount of runtime code
- assets should describe structure, parameters, and composition, not absorb
  complex runtime behavior
- if an asset starts to look like a mini language, rule engine, or deeply
  nested logic tree, that behavior probably belongs in code instead

In practice, this means assets should favor:

- explicit names
- simple fields
- stable shapes
- small payloads that map cleanly to built-in runtime components

This keeps future UI/API/SaaS layers easier to reason about. They can present
assets as inspectable building blocks instead of exposing a hidden execution
language through configuration files.

## Format Choice

This phase uses **JSON**, not YAML.

Reason:

- the repository already uses JSON heavily for configs and persisted snapshots
- JSON support is built into Python
- YAML would require a new dependency or a custom parser strategy before the
  format has stabilized

That keeps the change dependency-free and consistent with the repo today.

## What Was Added

- `src/evo_system/experimental_space/asset_loader.py`
  with two clearly separated responsibilities:
  - Python plugin module loading
  - declarative asset loading from disk
- asset directories under
  `src/evo_system/experimental_space/assets/`
  for:
  - `signal_packs`
  - `gene_catalogs`
  - `genome_schemas`
  - `decision_policies`
  - `mutation_profiles`
  - `experiment_presets`
- simple DTOs:
  - `LoadedPluginModule`
  - `DeclarativeAsset`

## What Has Not Changed Yet

- no plugin autodiscovery across the repository
- no runtime registration of loaded plugins
- no replacement of current built-in defaults
- no migration of existing JSON run configs to declarative assets
- no UI/API layer yet

## Why This Helps Future UI And SaaS Work

This separation makes future external layers easier to build:

- a UI can list declarative assets without importing runtime code
- a SaaS or API layer can validate asset names separately from code plugins
- the core can stay closed while allowing controlled extension points

## Current Limitations

- plugin loading is still explicit, not discovered automatically
- assets are only loaded and validated, not interpreted by the runtime yet
- reading assets does not create directories; directory creation stays in the
  explicit bootstrap helper
- there is no plugin manifest format yet
- no security or sandbox policy exists yet for external plugin code

## Recommended Next Steps

1. Define how built-in modules map to declarative asset descriptors.
2. Add optional registration helpers that connect loaded plugins/assets to the
   existing registries.
3. Decide plugin discovery scope before introducing autoimport or manifests.
4. Keep runtime adoption separate from loading infrastructure to preserve
   reproducibility controls.
