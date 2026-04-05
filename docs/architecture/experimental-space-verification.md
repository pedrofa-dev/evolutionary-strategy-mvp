# Experimental Space Verification

## Objective

Provide a small verification layer over the recent experimental-space
infrastructure so the repository can confirm that:

- built-in registries still resolve expected modules
- example declarative assets still load correctly
- the policy engine seam remains compatible with the current runtime decision
  policy
- the internal catalog service exposes stable, serializable output

This phase does not add new runtime capabilities. It only verifies that the
new architectural base is coherent and safe to build on.

## What This Phase Verifies

The current verification pass checks:

- registry behavior remains stable
- declarative example assets load and validate correctly
- asset reference validation works for example presets
- the default policy engine still builds a decision policy compatible with the
  default runtime policy
- gene metadata and genome schema metadata remain serializable
- the catalog service lists expected runtime modules and declarative assets
- empty categories remain safe and serializable

It also adds a small smoke script:

- `scripts/verify_experimental_space.py`

That script loads the catalog, validates example assets, checks default policy
compatibility, and prints a short readable summary.

## Guarantees Of This Phase

This phase gives a lightweight confidence check that the current foundation is:

- internally coherent
- serializable enough for future API/UI work
- compatible with the current runtime path
- still conservative about empty or not-yet-implemented categories

## What This Phase Does Not Guarantee

This phase does not guarantee:

- deep compatibility resolution between all possible assets
- runtime execution from declarative assets
- plugin autodiscovery
- HTTP/API behavior
- product-level validation or user-facing error presentation

## What Would Still Be Needed Before A Real API/UI

Before a real API/UI layer, the repository would still need:

1. clear external DTOs or response models for the chosen UI/API use cases
2. deeper validation for asset compatibility and composition
3. controlled exposure rules for runtime-only versus UI-facing metadata
4. an application boundary that turns these internal catalog/verification
   helpers into API or CLI endpoints

## Design Note

This verification layer prioritizes clarity over completeness.

That is deliberate:

- the goal is to catch obvious breakage early
- not to create a second runtime
- and not to front-load productization before the internal architecture is
  ready
