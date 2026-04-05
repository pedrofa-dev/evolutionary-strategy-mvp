# Future Refactors

## Purpose

This document records the most important refactors that are intentionally being
deferred while the repository transitions from protected research core to a
future UI/API-facing architecture.

The goal is to make transitional pieces explicit instead of quietly letting
them harden into accidental long-term design.

## API / HTTP Future Refactor

The current catalog HTTP surface is intentionally minimal and transitional.

Future work should decide:

- whether the long-term HTTP layer will use FastAPI or an equivalent framework
- how routing, dependency injection, and application bootstrapping should be
  organized
- whether health, catalog, runs, reporting, and execution should live under a
  shared API composition root

## Possible Migration To FastAPI Or Equivalent

The repository does not need that migration yet, but a future API will likely
benefit from:

- explicit request/response models
- automatic OpenAPI generation
- clearer testing ergonomics
- better dependency management for application services

That migration should happen when there is enough real API surface to justify
it, not earlier.

## Response Model Formalization

Current JSON payloads are stable enough for early integration work, but they
are still lightweight dictionaries.

Future work should formalize:

- response DTOs by use case
- versioning strategy for exposed payloads
- category-specific payload contracts instead of one generic shape everywhere

## Error Handling / Status Codes / CORS / Query Params

The current API uses minimal error payloads and basic HTTP statuses only.

Future work should define:

- consistent error envelope structure
- category-specific status code rules
- filtering/query parameters
- pagination where needed
- CORS behavior
- transport-level concerns such as auth and request tracing

## Naming Cleanup Pending

Some names remain intentionally conservative because they preserve continuity
with the existing core. Areas to revisit later include:

- runtime-oriented legacy identifiers such as `policy_v21_default`
- whether `ExperimentalCatalogApplicationService` should be split into more
  focused service names once the application layer grows
- whether generic names like `payload` should become more use-case-specific in
  external DTOs

These are not urgent enough to justify a large rename pass today.

## Deep Validation Between Assets

Current asset validation is intentionally shallow.

Future work should define:

- compatibility checks between signal packs, genome schemas, decision policies,
  and mutation profiles
- validation ownership boundaries between asset loading, application
  composition, and runtime selection
- better user-facing diagnostics for invalid compositions

## Plugin Autodiscovery

Plugin infrastructure exists, but discovery is still explicit and conservative.

Future work should decide:

- whether plugin manifests are needed
- whether autodiscovery is filesystem-based, entry-point-based, or fully
  explicit
- how plugin trust, sandboxing, and validation should be handled

## Growth Of The Application Layer

The application layer is currently catalog-focused.

Future work will likely need application services for:

- persisted runs
- reporting/read models
- execution orchestration entry points
- UI-oriented search, filtering, and composition flows

That growth should stay deliberate so the application layer does not become a
thin duplicate of the whole core.

## Traceability / Versioning / Lineage

The repository already has strong runtime traceability, but some future topics
remain open:

- external API-facing versioning of catalog payloads
- lineage between declarative assets and persisted runs
- richer module/config fingerprints for externally visible comparisons
- how to present compatibility across logic versions without weakening current
  manual reproducibility controls

## Future Test And Integration Strategy

Current tests are strong for the internal phases already implemented.

Future work should expand toward:

- application-layer contract tests
- HTTP integration tests with more realistic transport behavior
- compatibility tests across catalog/application/API layers
- eventual end-to-end tests once UI-facing flows exist

The key principle is to add those tests when the corresponding surface becomes
real, not before.
