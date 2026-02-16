# Deploy on Render

## Backend — Web Service (Python)

| Setting        | Value                                                   |
| -------------- | ------------------------------------------------------- |
| Runtime        | Python                                                  |
| Build Command  | `pip install -r backend/requirements.txt`               |
| Start Command  | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Python Version | Controlled by `.python-version` (3.11.7)                |

### Environment Variables

| Variable       | Required | Example                                              |
| -------------- | -------- | ---------------------------------------------------- |
| `DATABASE_URL` | Yes      | `postgresql://user:pass@host:5432/dbname`            |
| `CORS_ORIGINS` | Optional | `https://relopass.com,https://www.relopass.com`      |

- If `DATABASE_URL` is not set, the backend falls back to local SQLite (`relopass.db`).
- Supabase provides the connection string under Project Settings → Database → Connection string → URI.
- If the URI starts with `postgres://`, the backend auto-converts it to `postgresql://`.

### Database Initialization

No Alembic or pre-deploy command needed. On every startup, the backend:

1. Runs `CREATE TABLE IF NOT EXISTS` for all legacy tables (users, sessions, assignments, etc.)
2. Runs `Base.metadata.create_all()` for all SQLAlchemy tables (wizard cases, country profiles, etc.)

Both steps are idempotent and safe to run on every boot.

### Verify Deployment

```bash
curl https://api.relopass.com/health
```

Expected:
```json
{"status": "ok", "service": "ReloPass API", "version": "1.0.0", "timestamp": "..."}
```

Look for these log lines in Render:
```
INFO:backend.database:DB schema ensured (legacy tables)
INFO:backend.main:Initializing database schemas...
INFO:backend.app.db:DB schema ensured (SQLAlchemy tables)
INFO:backend.main:Startup complete.
```

---

## Frontend — Static Site

| Setting           | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Build Command     | `npm --prefix frontend ci && npm --prefix frontend run build`      |
| Publish Directory | `frontend/dist`                                                    |
| Node Version      | Controlled by `.nvmrc` (20.18.1)                                   |

### Environment Variables

| Variable       | Required | Value                          |
| -------------- | -------- | ------------------------------ |
| `VITE_API_URL` | Yes      | `https://api.relopass.com`     |

### SPA Routing

The file `frontend/public/_redirects` ensures all routes serve `index.html`:
```
/*    /index.html   200
```

---

## Connect Frontend ↔ Backend

1. Set `VITE_API_URL` in Render Static Site → Environment Variables
2. Set `CORS_ORIGINS` in Render Web Service → Environment Variables (include the frontend domain)
3. Set `DATABASE_URL` in Render Web Service → Environment Variables (Supabase connection string)
4. Redeploy both services
