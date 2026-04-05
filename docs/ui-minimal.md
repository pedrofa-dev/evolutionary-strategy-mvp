# Minimal UI

## What This UI Does

This UI is a small React + TypeScript + Vite frontend for exploring the
experimental catalog exposed by the current HTTP API.

It is intentionally simple and focused on:

- checking that the API is reachable
- listing catalog categories
- browsing category items
- viewing basic item details and raw payload JSON
- making technical catalog entries easier for humans to scan

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

By default, the Vite dev server proxies those paths to:

- `http://localhost:8000`

If needed, the frontend can also use:

- `VITE_API_BASE_URL`

to point to another API base URL.

## Pages

The UI includes three minimal views:

1. Overview
   - shows health status
   - lists catalog categories
2. Category view
   - shows items for one category
3. Detail view
   - shows id, category, origin, description, file path, and payload JSON
   - explains what the selected item is and why it exists

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
