# Cloudflare Pages Deployment

This repo hosts a Vite/React app in `frontend/`. The root `package.json` delegates the build so Cloudflare Pages can run from the repo root.

## Recommended (most efficient) Pages settings

- **Root directory**: `.`
- **Build command**: `npm run build`
- **Build output directory**: `frontend/dist`
- **Node version**: `20.18.1` (matches `.nvmrc`)
- **Deploy command**: *(leave empty)*

Pages already handles deployment; no Wrangler deploy command is required.

## Connect frontend to backend

The hosted frontend must point to a reachable backend and the backend must allow the frontend origin.

1) **Cloudflare Pages env vars** (frontend) — Production **and** Preview scopes:

   Required for the SPA to mount (`frontend/src/config/env.ts` throws before
   `ReactDOM.createRoot()` if either Supabase var is missing; the page then
   stays as inert prerendered HTML — GitHub #2285):

   - `VITE_API_URL=https://api.relopass.com`
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`

   These are public, client-side values (the anon key is already in the
   production bundle and is subject to Supabase RLS). They are also committed
   in `frontend/.env.production` so Pages builds work even when the dashboard
   vars are unset. Dashboard values still override the file when present.

2) **Backend env vars** (FastAPI):
   - `CORS_ORIGINS=https://<your-pages-domain>,http://localhost:5173`

Without these, auth will work locally but fail online due to CORS or API base URL mismatch.

## If you keep a deploy command

If your project settings still run `npx wrangler deploy`, this repo now includes `wrangler.jsonc` with an assets directory:

```
./frontend/dist
```

This allows Wrangler to deploy the static assets without a Worker entry point.
