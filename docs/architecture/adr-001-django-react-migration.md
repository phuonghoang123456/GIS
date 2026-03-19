# ADR-001: Migrate from Node/Express + Static HTML to Django REST + React Vite

## Status
Accepted

## Context
The existing Web GIS system mixes:
- Node/Express API for business endpoints.
- Standalone Python Flask API for Google Earth Engine extraction.
- Static HTML pages with duplicated logic.

The project needs:
- A clean split into `backend/` and `frontend/`.
- Better maintainability for long-term feature growth.
- No loss of current functional coverage (auth, activity, rainfall, temperature, NDVI, TVDI, dashboard, GEE fetch).

## Decision
Adopt a modular monolith architecture:
- `backend/`: Django REST Framework.
- `frontend/`: React + Vite + React Router + Chart.js.
- Keep Python GEE service as an external ingestion service, proxied through Django API.

## Rationale
1. Django REST gives fast endpoint development with strong conventions and stable ORM integration.
2. React Vite removes duplicated page logic and enables reusable components across all climate modules.
3. API proxy pattern preserves current GEE ingestion behavior while allowing backend governance.

## Trade-offs
- Added migration complexity and temporary dual-stack operation.
- Need Python runtime for both Django backend and GEE service.
- Existing DB tables are preserved (`managed = False`) to avoid accidental schema drift.

## Consequences
- Positive:
  - Clear project structure (`backend/`, `frontend/`).
  - Consistent response envelope and auth flow.
  - Easier to add future modules (soil moisture page, alert center, admin analytics).
- Negative:
  - Initial setup requires installing new dependencies and env configuration.
  - Frontend charts now depend on React build tooling.
- Mitigation:
  - Provide `.env.example` for both backend and frontend.
  - Keep endpoint names compatible with legacy API paths.

## Revisit Trigger
- Need for multi-tenant scaling or heavy background ingestion beyond current workload.
- Requirement to merge GEE ingestion into main backend process.
