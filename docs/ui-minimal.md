# Minimal UI

## What This UI Does

This UI is a small React + TypeScript + Vite frontend for:

- landing in a compact Lab Home operational surface
- exploring the experimental catalog exposed by the current HTTP API
- operating the first canonical Run Lab flow with lower friction

It is intentionally simple and focused on:

- checking that the API is reachable
- listing catalog categories
- browsing category items
- viewing basic item details and raw payload JSON
- making technical catalog entries easier for humans to scan
- forming a canonical run config from the current active workflow
- saving that config under `configs/runs/`
- launching the existing multiseed execution path from the UI

This UI is exploratory rather than productized. Many labels still reflect
internal naming from the current system, and the frontend adds small human
descriptions only to make exploration easier.

## Project Location

- `ui/web/`

## How To Run It Locally

From the repository root:

```powershell
python src/api/main.py
cd ui/web
npm install
npm run dev
```

If the API is already running elsewhere, you can keep the same UI commands and
set `VITE_API_BASE_URL` instead.

Equivalent split steps:

```powershell
python src/api/main.py
```

```powershell
cd ui/web
npm install
npm run dev
```

Optional production build:

```powershell
cd ui/web
npm run build
```

Expected local setup:

- the catalog API running on `http://localhost:8000`
- or `VITE_API_BASE_URL` configured to another base URL

## Endpoints Used

The UI consumes only these endpoints:

- `GET /health`
- `GET /catalog`
- `GET /catalog/{category}`
- `POST /run-lab/authoring/mutation-profiles`
- `POST /run-lab/authoring/signal-packs`
- `GET /run-lab`
- `POST /run-lab/configs`
- `POST /run-lab/executions`
- `GET /runs/campaigns`
- `GET /runs/monitor`
- `GET /runs/campaign/{id}`
- `DELETE /runs/campaign/{id}`
- `GET /runs/compare?ids=...`

By default, the Vite dev server proxies those paths to:

- `http://localhost:8000`

If needed, the frontend can also use:

- `VITE_API_BASE_URL`

to point to another API base URL.

## Pages

The UI includes four main views:

1. Home
   - default landing page for the research workbench
   - summarizes active or recent persisted executions
   - provides quick actions into Run Lab, Results, Catalog, and current authoring flows
   - shows a compact recent campaigns list
2. Overview
   - shows health status
   - lists catalog categories
   - now lives under the Catalog route rather than the app root
3. Category view
   - shows items for one category
   - can create a new mutation profile or signal pack from the natural catalog category using the same canonical authoring endpoints as Run Lab
4. Detail view
   - shows id, category, origin, description, file path, and payload JSON
   - explains what the selected item is and why it exists

It also includes a first operational tab:

5. Run Lab
   - selects a dataset catalog
   - selects signal pack, genome schema, mutation profile, and decision policy
   - can either reuse an existing canonical config or create a new one from a starting template
   - supports focused authoring modals for creating a new signal pack or mutation profile
   - chooses a runtime experiment preset
   - chooses a parallel execution count for the canonical multiseed launch path
   - saves a canonical config file
   - can save and launch the canonical multiseed script
6. Runs / Results
   - lists persisted multiseed campaigns
   - highlights the champion block first
   - shows train, validation, and external summaries without recalculating them
   - exposes multiseed execution rows to spot instability
   - compares selected campaigns side by side
   - allows conservative deletion of persisted campaigns that are no longer needed

The application shell also includes:

7. Global execution monitor
   - polls canonical persisted campaign status
   - shows active or recent multiseed executions across pages in a compact drawer
   - stays honest about execution state and does not imply a scheduler-backed queue
   - only shows progress signals that are safely known from persisted state

## Labels And Dark Mode

The UI applies a lightweight presentation layer to improve readability without
changing the underlying API payloads.

- primary labels are rendered in a humanized Title Case format
- technical IDs stay visible as secondary metadata
- category descriptions add quick context for people who do not know the
  internal vocabulary yet

Dark mode is intentionally simple and local to the frontend:

- it uses `prefers-color-scheme` as the default
- it provides a manual light/dark toggle in the header
- the manual preference is stored in `localStorage`
- colors are driven by CSS variables so text, backgrounds, cards, borders, and
  technical panels stay in sync

This is still a minimal theming layer, not a full design system.

## Limitations

Current limitations are intentional:

- no authentication
- no advanced filtering
- no pagination
- no write operations
- no state library
- no React Router
- no SSR
- no UI framework
- no product-level frontend architecture yet
- many names still originate from internal IDs and experimental metadata
- category explanations are currently frontend-side helpers, not backend-owned descriptions
- dark mode is still a local UI concern, not a backend-owned theming system
- Run Lab still depends on active template configs already present in `configs/runs/`
- Run Lab config reuse locks structural fields by default; duplicating into a brand-new config is still a deliberate operator action
- execution launch is intentionally simple and does not yet provide live run monitoring
- the global execution monitor uses polling, not websockets, and only shows compact seed-level progress
- results are read-only and limited to persisted campaign summaries, champion
  analyses, and external evaluation artifacts
- campaign deletion is conservative and blocks campaigns still marked as running

This is an exploration tool, not a polished product UI.

## What Should Improve Later

Future phases can improve:

- formal routing
- richer error handling
- category filters/search
- loading skeletons or more polished loading states if the UI grows
- response typing aligned with a more mature API
- stronger visual hierarchy
- better detail rendering for known asset/module types

The current goal is only to prove that the API is navigable and useful from a
minimal frontend.
