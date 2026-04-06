# Catalog API

## Objective

Expose a first minimal HTTP surface over the experimental catalog without
touching the methodological core.

This API is intentionally small. Its purpose is to prove the layering path from
core to application to HTTP, not to expose the whole system yet.

## What This First API Exposes

The current HTTP surface exposes:

- `GET /health`
- `GET /catalog`
- `GET /catalog/{category}`
- `GET /run-lab`
- `POST /run-lab/configs`
- `POST /run-lab/executions`
- `GET /runs/campaigns`
- `GET /runs/campaign/{id}`
- `GET /runs/compare?ids=...`

These endpoints return JSON only and cover:

- the experimental catalog prepared in earlier phases
- the first canonical Run Lab bootstrap/save/launch flow
- a read-only Runs / Results surface over persisted campaigns and evaluations

## Local Development Server

The API can now be started locally with the standard library server built into
the current transitional app.

From the repository root:

```powershell
python src/api/main.py
```

By default it listens on:

- `127.0.0.1:8000`

Optional overrides:

```powershell
python src/api/main.py --host 127.0.0.1 --port 8000
```

## Why It Consumes The `application` Layer

The HTTP layer should consume `application`, not `experimental_space`
directly.

That separation matters because:

- the protected core should stay focused on runtime and structural concerns
- the application layer can shape outputs for external consumers
- the HTTP layer should remain transport-focused and thin

This keeps future UI/API work from coupling directly to internal core service
types.

## What It Does Not Expose Yet

This API does not expose:

- run execution control beyond the existing Run Lab launch bridge
- mutation flows
- reporting writes or recomputation
- persistence operations outside the canonical runtime path
- champion selection
- evaluator/scoring behavior
- authentication or authorization

The current write surface is intentionally narrow and limited to Run Lab config
save plus canonical launch orchestration.

## Why This Helps A Future UI

The future UI can already rely on a real HTTP surface for:

- health checks
- listing experimental catalog categories
- loading one catalog category at a time
- loading the canonical Run Lab bootstrap
- saving canonical run configs
- launching the existing multiseed entrypoint through a thin HTTP bridge
- listing persisted campaigns
- reading one campaign detail
- comparing several campaigns side by side using persisted summaries only

That is enough to start frontend integration work without forcing premature
productization of the rest of the platform.

## Current Limits

- the implementation uses a minimal standard-library WSGI app
- there is no FastAPI layer yet
- there are no response schemas beyond stable JSON shapes
- deep validation and richer query features remain future work

This is deliberate. The API stays small and conservative until broader product
surfaces are ready.

## Transitional Status

This API is explicitly transitional.

Today it is useful because it gives the future UI a real HTTP seam over the
catalog, but it is not yet the final API architecture.

In particular, it is intentionally missing:

- a framework-level HTTP stack such as FastAPI
- formal response schemas
- richer query parameters and filtering
- standardized error envelopes beyond the minimal current shape
- CORS, auth, and broader transport concerns
