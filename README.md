# Web GIS Refactor (Django REST + React Vite)

## New Project Structure

```text
backend/
  manage.py
  requirements.txt
  config/
  apps/
    accounts/
    activity/
    climate/
    gee/
    common/

frontend/
  package.json
  vite.config.js
  src/
    api/
    context/
    components/
    pages/
```

## Backend Setup

1. Go to backend:
   - `cd backend`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy env:
   - `copy .env.example .env` (Windows) or `cp .env.example .env`
4. Run API server:
   - `python manage.py runserver 0.0.0.0:8000`

## Frontend Setup

1. Go to frontend:
   - `cd frontend`
2. Install dependencies:
   - `npm install`
3. Copy env:
   - `copy .env.example .env` (Windows) or `cp .env.example .env`
4. Run Vite:
   - `npm run dev`

## External GEE Service

This refactor keeps the current ingestion service pattern:
- Run `backend/scripts/api_server.py` separately on `http://127.0.0.1:3001`
- Django `/api/gee/*` endpoints proxy requests to that service.

### Connect to Google Earth Engine (real)

1. Set GEE env values in `backend/.env`:
   - `GEE_PROJECT=<your-gee-cloud-project-id>`
   - Optional service account mode:
     - `GEE_SERVICE_ACCOUNT=<service-account-email>`
     - `GEE_PRIVATE_KEY_FILE=<absolute-path-to-json-key>`
2. If you do not use service account, authenticate once in your venv:
   - `python -c "import ee; ee.Authenticate()"`
3. Start Flask GEE service:
   - `python backend/scripts/api_server.py`
4. Check status:
   - `GET http://127.0.0.1:3001/status`
   - Expected: `"status":"online"` and `"gee_initialized":true`
5. Start Django + frontend, then run analysis buttons.

## Functional Coverage Preserved

- Auth: register, login, logout, current user
- Activity logs: log, history, stats
- Rainfall: range, monthly, yearly, compare periods, compare locations
- Temperature: range, monthly
- NDVI: range, monthly, yearly
- TVDI: range, monthly, drought summary, severe events
- Dashboard: overview, timeseries
- GEE fetch: status, fetch, fetch-rainfall, fetch-temperature, fetch-all

## Legacy Source

Original Node/Express + static HTML implementation is preserved in:
- `legacy/node-express/`
