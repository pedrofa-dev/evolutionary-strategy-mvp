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

## Future SaaS Considerations

If this repository evolves toward a real SaaS or externally exposed product,
the following areas will need explicit design instead of the current
transitional defaults.

### HTTP Framework And API Formalization

- adopt a more complete HTTP framework such as FastAPI or equivalent
- formalize route composition and dependency injection
- define stable external response models
- introduce explicit API versioning

### Authentication, Authorization, And Exposure Boundaries

- user authentication
- role-based or scope-based authorization
- multi-tenant boundaries if needed
- separation between internal research APIs and externally exposed APIs

### Frontend / Backend Separation

- CORS policy
- separate deployment of frontend and backend
- environment-aware API base URLs
- stricter transport contracts between UI and backend

### Richer API Behavior

- consistent error envelopes
- richer status code strategy
- pagination
- query parameters and filters
- sorting and search behavior

### Deeper Asset And Composition Validation

- compatibility checks across assets
- user-facing diagnostics for invalid combinations
- validation paths shared across UI, API, and execution

### Observability And Logging

- structured request logging
- correlation/request ids
- metrics
- health/readiness strategy beyond the current minimal `/health`
- error monitoring

### Environment Configuration

- dev/staging/prod configuration strategy
- secret management
- runtime feature flags where justified
- explicit API/UI environment separation

### Deployment And CI/CD

- frontend build pipeline
- backend packaging and serving strategy
- automated checks for API/application compatibility
- deployment automation and rollback strategy

### Persistence And Traceability Productization

- product-facing traceability views
- stronger lineage between assets, runs, and published results
- more ergonomic querying over persisted metadata
- externally visible compatibility/versioning strategy

### Basic Security For An Exposed App

- request size limits
- input validation hardening
- dependency review and update process
- secure default headers
- handling of untrusted asset/plugin references if exposure grows

### Frontend Maturity

- formal routing
- more mature state handling only if proven necessary
- frontend testing strategy
- accessibility review
- stronger design system or shared component layer
- UX patterns for empty/loading/error states beyond the current minimal tool

## UI/UX And Productization

If the catalog browser evolves into a more serious UI, several product-facing
concerns will need explicit treatment instead of the current lightweight
frontend helpers.

### User-Oriented Naming Versus Internal Naming

- separate technical IDs from user-facing labels
- define naming rules for what can stay internal versus what should be shown to
  users
- reduce direct exposure of raw snake_case identifiers in primary UI surfaces

### Descriptions Owned By The Backend

- move category and item descriptions toward backend- or asset-owned metadata
- avoid hardcoding explanatory copy in the frontend long term
- define which descriptions are canonical and where they should live

### Asset Hygiene And Classification

- clean up experimental assets that are too raw for user-facing browsing
- add tagging or classification such as `test`, `prod`, `experimental`
- make presets easier to understand by intent, not only by technical id

### Guided Navigation And Onboarding

- add better onboarding copy, tooltips, and help surfaces
- provide guided browsing paths for users who do not know the system vocabulary
- reduce reliance on prior domain knowledge

### Dark Mode And Visual System

- evolve from basic `prefers-color-scheme` support to a fuller dark mode design
- define a more stable design system
- improve visual hierarchy for technical versus human-facing information

### Accessibility And Internationalization

- review keyboard navigation and screen-reader behavior
- improve semantic labeling and accessible states
- consider i18n if the UI grows beyond internal use

## Design System & Theming

The current catalog UI uses a deliberately small theming layer based on CSS
variables and a manual dark-mode override. That is enough for local exploration,
but it is not yet a full product-facing design system.

Future work should define:

- a stable set of design tokens for colors, spacing, typography, borders, and
  elevation
- a more complete dark mode strategy across all screens and states
- stronger visual consistency between overview, category, detail, and future
  run/reporting surfaces
- accessibility review for contrast ratios and interactive states
- clear rules for when technical metadata should be visually secondary
- backend-supported labels and descriptions instead of frontend-only display
  helpers
