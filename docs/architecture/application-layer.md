# Application Layer

## Why Introduce An Application Layer

The repository now has a richer internal experimental-space foundation:

- registries
- plugin seams
- declarative assets
- structural metadata
- a read-only internal catalog

That is enough to justify a very small application boundary.

The purpose of this layer is not to add new business behavior. It is to expose
the protected core through stable, external-facing shapes that a future CLI,
API, or UI can consume more safely.

## `experimental_space` Vs `application`

### `experimental_space`

`experimental_space` remains part of the protected core. It owns:

- runtime-adjacent module definitions
- internal registries
- asset loading
- structural metadata
- internal catalog aggregation

### `application`

`application` is a thinner boundary for external consumers. It should:

- depend on core services
- reshape outputs for external consumption
- avoid leaking internal implementation details unnecessarily
- remain read-oriented and conservative unless a future use case requires more

## Why UI/API Should Not Talk Directly To Core

UI/API code should not speak directly to the core because the core is optimized
for runtime correctness and research evolution, not for external contracts.

An application layer helps:

- stabilize output shapes
- isolate UI/API-facing naming from internal implementation details
- keep future transport choices separate from the methodological core
- reduce the chance that product concerns reshape protected runtime code

## What This First Step Adds

This phase adds a minimal application-facing catalog service:

- `src/application/catalog/service.py`

It wraps the internal experimental-space catalog and exposes:

- `ApplicationCatalogItem`
- `ApplicationCatalogSnapshot`
- `ExperimentalCatalogApplicationService`

The service keeps the scope intentionally small:

- read-only
- serializable
- catalog-focused only

## What Remains Pending Before A Real API/UI

Before a real API/UI layer, the repository would still need:

1. transport-specific adapters, such as HTTP or CLI controllers
2. explicit response models for chosen UI/API use cases
3. deeper asset compatibility and validation flows
4. authentication, authorization, and product-facing error handling if a real
   service is introduced
5. additional application services for runs, reporting, and persistence reads

This first step only proves the layering direction. It does not attempt to
productize the system yet.

## Transitional Status

The current application layer should be read as a transition layer, not a
final product architecture.

At this stage it is intentionally:

- small
- read-oriented
- catalog-focused
- conservative about output shaping

That is useful now because it prevents UI/API work from depending directly on
core internals, while still avoiding a premature redesign of runs, execution,
or reporting workflows.
