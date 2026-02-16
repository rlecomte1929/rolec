# Deploy Backend on Render

## Service Type

**Python** Web Service (not Node/Docker).

## Settings

| Field            | Value                                                       |
| ---------------- | ----------------------------------------------------------- |
| Root Directory   | *(leave blank — repo root)*                                 |
| Build Command    | `pip install -r backend/requirements.txt`                   |
| Start Command    | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`     |
| Python Version   | Controlled by `.python-version` (currently **3.11.7**)      |

## Environment Variables

| Variable       | Example                                                   |
| -------------- | --------------------------------------------------------- |
| `CORS_ORIGINS` | `https://your-cloudflare-pages-domain.pages.dev`          |

Add every frontend origin that should be allowed (comma-separated).

## Verify Deployment

After deploy, hit:

```
https://<your-render-service>.onrender.com/health
```

Expected response:

```json
{"status": "ok"}
```

## Connect Frontend (Cloudflare Pages)

In Cloudflare Pages → Settings → Environment Variables, set:

```
VITE_API_URL = https://<your-render-service>.onrender.com
```

Then redeploy Pages so Vite bakes the URL into the frontend build.
