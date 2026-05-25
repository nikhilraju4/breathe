# Breathe ESG — Data Ingestion & Review Platform

Django REST API and React dashboard for ingesting enterprise emissions-related data (SAP, utility electricity, corporate travel), normalizing it to activity records, and letting analysts review and lock rows before audit.

**Live demo:** https://breathe-esg-i3e9.onrender.com  
**Login:** `analyst` / `demo1234`

## Architecture

- **Backend:** Django 5 + Django REST Framework, PostgreSQL (production) / SQLite (local)
- **Frontend:** React (Vite), served from Django in production
- **Deploy:** Docker on Render (`render.yaml`)

## Local setup

```powershell
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Build the UI and open http://127.0.0.1:8000:

```powershell
cd frontend
npm install
npm run build
```

Or use hot reload: `npm run dev` → http://localhost:5173 (API proxied to :8000).

## Sample data

CSV fixtures in `sample_data/` mirror realistic export shapes:

- `sap_fuel_procurement_export.csv` — semicolon-delimited SAP-style fuel & procurement
- `utility_portal_electricity.csv` — utility portal electricity export
- `concur_travel_export.csv` — Concur-style travel expenses

Upload these from the dashboard **Ingest data** panel.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login/` | POST | Obtain auth token |
| `/api/dashboard/` | GET | Review queue summary |
| `/api/ingest/upload/` | POST | Upload CSV (`source_type`, `file`) |
| `/api/records/` | GET | List/filter activity records |
| `/api/records/{id}/approve/` | POST | Approve a row |
| `/api/records/{id}/reject/` | POST | Reject a row |
| `/api/audit/lock/` | POST | Lock all approved rows |

## Design documentation

- [MODEL.md](./MODEL.md) — data model (multi-tenancy, scopes, audit trail)
- [DECISIONS.md](./DECISIONS.md) — format and scope choices per source
- [TRADEOFFS.md](./TRADEOFFS.md) — deliberate omissions
- [SOURCES.md](./SOURCES.md) — research notes and sample data rationale

## Deployment

Connect the repo to [Render](https://render.com) via **Blueprint** (`render.yaml`). The Dockerfile builds the frontend and runs migrations + demo seed on startup.
