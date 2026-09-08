# otto-loader edge function

Receiving end of the Audos → ReloPass "Bridge B" data load. Audos/Otto uploads a manifest
JSON to Google Cloud Storage, then calls this function to fetch + stage the referenced files
into the ReloPass Supabase tables (all as `status='pending'`, never `verified`).

## Deployment contract — these are NOT the CLI defaults, do not lose them
- **`verify_jwt = false`.** This function does its OWN auth (shared secret). If it is deployed
  with `verify_jwt: true`, Supabase's platform gate rejects the Bridge caller *before* this
  code runs. Ensure `supabase/config.toml` contains:

      [functions.otto-loader]
      verify_jwt = false

- **Secret `OTTO_LOADER_TOKEN`** (Supabase Edge Function secret) MUST equal the
  `OTTO_LOADER_TOKEN` configured on the Audos side. Deleting it makes the function fail closed
  (`401` on every request). Regenerating one side without the other → `401 unauthorized`.

## Auth — how the caller presents the secret
Either header is accepted, constant-time compared to `OTTO_LOADER_TOKEN`:
- `x-otto-token: <secret>`            (canonical)
- `Authorization: Bearer <secret>`   (compat, added 2026-08-19 — the Audos proxy uses this)

A query-param token (`?token=`) is NOT accepted (it leaks into logs).

## Request — how the caller passes the manifest
- Query: `POST .../otto-loader?manifest=<gcs-url>&dry_run=true&tables=all`
- Body fallback (added 2026-08-19): a JSON POST body carrying the manifest URL under
  `manifest` / `manifest_url` / `url` / `gcs_url` — or any `storage.googleapis.com` URL
  anywhere in the body.
- The manifest URL host MUST be `storage.googleapis.com` (SSRF allowlist). Any other host →
  `400 "manifest url rejected"`.
- `dry_run` defaults to `true` (no writes). Set `dry_run=false` to actually insert.

## History
Deployed ad-hoc from a scratchpad and was missing from this repo; committed here 2026-08-19
so a repo deploy can't silently drop the `Authorization`/body-manifest compat or flip
`verify_jwt`. Live deployed version at time of commit: **v18**.
